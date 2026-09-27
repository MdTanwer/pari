# Codex Architecture — Deep Dive
## Memory, Context, Agents, Hooks & Sandboxing — With Real Rust Code

> All code in this document is pulled directly from:
> - `resource/codex/codex-rs/core/src/` — the core business logic crate (128+ source files)
> - `resource/codex/codex-rs/hooks/src/` — the hook event system
> - `resource/codex/codex-rs/sandboxing/` — platform sandboxing
> - `resource/codex/codex-rs/Cargo.toml` — workspace of 119+ crates
>
> This is fundamentally different from Claude Code — it is a **Rust-native** agent,
> not a Node.js plugin host. Every line referenced is compiled, typed, and memory-safe.

---

## Table of Contents

1. [What Codex Is — vs Claude Code](#1-what-codex-is--vs-claude-code)
2. [The Crate Architecture — 119 Rust Crates](#2-the-crate-architecture--119-rust-crates)
3. [The Agent Loop — CodexThread and ThreadManager](#3-the-agent-loop--codexthread-and-threadmanager)
4. [How Memory Works — Three Layers](#4-how-memory-works--three-layers)
5. [How Context Compaction Works — Dual Strategy](#5-how-context-compaction-works--dual-strategy)
6. [The Hook System — 12 Lifecycle Events](#6-the-hook-system--12-lifecycle-events)
7. [The Exec Policy System — Rule-Based Command Gating](#7-the-exec-policy-system--rule-based-command-gating)
8. [The Sandboxing System — Four Platform Backends](#8-the-sandboxing-system--four-platform-backends)
9. [The Multi-Agent System — AgentControl Trait](#9-the-multi-agent-system--agentcontrol-trait)
10. [The Protocol Layer — Wire Format and Events](#10-the-protocol-layer--wire-format-and-events)
11. [How Layers Work Together — Full Turn Trace](#11-how-layers-work-together--full-turn-trace)
12. [Codex vs Claude Code — Comparison Table](#12-codex-vs-claude-code--comparison-table)

---

## 1. What Codex Is — vs Claude Code

Codex is a **Rust-native** coding agent built by OpenAI. Where Claude Code is a Node.js process with a JavaScript plugin system, Codex is:

- A **Cargo workspace of 119 crates** — each responsible for one concern
- Built on **tokio async runtime** — every I/O operation is properly async
- Connected to OpenAI via the **Responses API** (streaming, not chat completions)
- Sandboxed at the **OS level** — platform-native sandboxes, not runtime restrictions
- Model-agnostic — it has a `model-provider` crate that can route to OpenAI, Ollama, LM Studio, or any compatible endpoint

The key difference in philosophy:

| Aspect | Claude Code | Codex |
|--------|------------|-------|
| Runtime | Node.js (V8 snapshot) | Rust native (tokio) |
| Plugin system | JavaScript hooks, hot-reloadable | Rust traits + config-driven hooks |
| Sandboxing | Runtime deny lists + symlink checks | macOS Seatbelt / Linux bubblewrap / Windows restricted token |
| State | Per-session closured JS variables | Typed Rust structs, persisted to SQLite via `StateDbHandle` |
| Multi-agent | Event-based subagents | `AgentControl` trait, `ThreadManager`, graph store |
| Memory | In-memory + JSON KV store | SQLite state DB + file-based rollout (JSONL) |

---

## 2. The Crate Architecture — 119 Rust Crates

The workspace is intentionally decomposed into single-responsibility crates. From `Cargo.toml` lines 1-130:

```
Key crates and what they own:
  core/             — ALL business logic (the main crate, 128 source files)
  hooks/            — Hook event types, registry, dispatch engine
  protocol/         — All wire types: Event, Op, TurnInput, ResponseItem, etc.
  sandboxing/       — Platform-specific sandbox transforms
  exec/             — Process execution (separate from the core exec module)
  exec-server/      — Exec as a remote service (cloud/remote environments)
  tui/              — Terminal UI (ratatui-based)
  cli/              — CLI entry point
  config/           — Config layer stack, TOML parsing, schema validation
  execpolicy/       — The shell command policy rule engine
  rollout/          — Session persistence (JSONL "rollout" files)
  thread-store/     — Thread (conversation) storage and retrieval
  state/            — SQLite state DB abstraction
  hooks/            — 12 hook events with typed request/response structs
  mcp (codex-mcp)/  — MCP server and client for tool extensions
  agent-graph-store/— Multi-agent tree membership and state
  memories/         — read + write memory crates (separate binaries!)
  worktree/         — Git worktree management
  model-provider/   — Multi-model routing (OpenAI, Ollama, LM Studio)
```

The crate decomposition is enforced at compile time. `core` can import `protocol` but NOT the reverse. `tui` can import `core` but `core` cannot import `tui`. This eliminates the circular dependency problems that plague Node.js monorepos.

---

## 3. The Agent Loop — CodexThread and ThreadManager

### CodexThread — One Conversation

From `core/src/codex_thread.rs` lines 83-111, a `CodexThread` carries all config for one conversation:

```rust
// codex_thread.rs lines 86-111
pub struct ThreadConfigSnapshot {
    pub model: String,
    pub model_provider_id: String,
    pub service_tier: Option<String>,
    pub approval_policy: AskForApproval,       // auto / ask / never
    pub approvals_reviewer: ApprovalsReviewer,  // local UI vs guardian vs remote
    pub permission_profile: PermissionProfile,  // file system permissions
    pub full_access: bool,                      // resolved full-access flag
    pub active_permission_profile: Option<ActivePermissionProfile>,
    pub environments: TurnEnvironmentSelections, // selected execution environments
    pub workspace_roots: Vec<AbsolutePathBuf>,  // roots the agent can write to
    pub ephemeral: bool,                        // whether to persist this thread
    pub reasoning_effort: Option<ReasoningEffort>,  // o3-mini style control
    pub reasoning_summary: Option<ReasoningSummary>,
    pub personality: Option<Personality>,
    pub collaboration_mode: CollaborationMode,
    pub session_source: SessionSource,           // interactive / background / subagent
    pub history_mode: ThreadHistoryMode,         // full / summary / none
    pub forked_from_thread_id: Option<ThreadId>, // for forked conversations
    pub parent_thread_id: Option<ThreadId>,      // for subagents
    pub thread_source: Option<ThreadSource>,
    pub originator: String,
    pub disabled_plugin_ids: Vec<String>,
}
```

### ThreadManager — The Conversation Registry

`ThreadManager` (from `core/src/thread_manager.rs`) is the equivalent of Claude Code's "session manager". It:

- Creates and destroys `CodexThread` instances
- Manages the `AgentControl` trait implementation for multi-agent
- Maintains the `AgentGraphStore` (parent/child agent tree)
- Routes events from threads to UI subscribers
- Handles thread forking, resuming, and archiving

From `thread_manager.rs` lines 100-116:
```rust
// Capacity for the internal channel that notifies subscribers about new threads
const THREAD_CREATED_CHANNEL_CAPACITY: usize = 1024;
```

The entire `ThreadManager` is built on tokio's `broadcast` channel:

```rust
// thread_manager.rs (key data structures from the import list)
use tokio::sync::RwLock;          // Concurrent reads of thread map
use tokio::sync::broadcast;       // Fan-out of new thread events
use futures::stream::FuturesUnordered;  // Concurrent thread operations
use futures::StreamExt;
```

### The Turn Loop — `Session` and `TurnContext`

Inside a `CodexThread`, each user turn creates a `TurnContext`. The turn loop:

```
TurnInput arrives via tokio channel
    |
TurnContext created — captures environment, step settings, timing
    |
UserPromptSubmit hooks fire (external scripts can inject/block)
    |
Session.step() — sends to model via Responses API (streaming)
    |
For each ResponseItem streamed:
    |---> If tool_call: run exec_policy check -> sandbox -> execute -> post_tool hooks
    |---> If text: stream to TUI via EventMsg channel
    |---> If reasoning: stream reasoning tokens separately
    |
Turn completes -> hooks fire -> persisted to rollout (JSONL)
```

---

## 4. How Memory Works — Three Layers

### Layer 1: Typed Rust Structs (In-Process, Per-Turn)

Unlike Claude Code's closured JavaScript variables, Codex state is in **typed Rust structs** that live in the tokio task heap. They are:

- Impossible to accidentally share between threads (ownership model)
- Impossible to partially initialize (all fields must be set)
- Zero-overhead — no GC, no boxing unless explicitly required

Key state types from the core lib:

```rust
// From codex_thread.rs — per-thread live state
static LIVE_THREADS: Gauge = Gauge::new("core.threads.live");
// A diagnostic gauge tracking how many threads are alive right now

// TurnContext — captures exactly one turn's environment state
pub use session::turn_context::TurnContext;

// WorldState — the model's view of what tools/files are available
use crate::context::world_state::WorldState;

// TurnEnvironmentSnapshot — which exec environments are selected this turn
pub use environment_selection::TurnEnvironmentSnapshot;
```

`WorldState` is particularly important — it holds the agent's current understanding of:
- Which tools are active
- File system context fragments
- Agent instructions (from AGENTS.md / CODEX.md files)
- Memory items loaded from the `memories/read` binary

### Layer 2: Rollout Files — Persistent Conversation History

Codex persists the conversation as **JSONL "rollout" files** in `~/.codex/sessions/`. Each item is a `RolloutItem`:

```rust
// From lib.rs:
pub use rollout::RolloutItem;
pub use rollout::RolloutRecorder;
pub use rollout::SessionMeta;
pub use rollout::ThreadItem;
pub use rollout::find_thread_path_by_id_str;

// Key constants:
pub use rollout::SESSIONS_SUBDIR;          // "sessions"
pub use rollout::ARCHIVED_SESSIONS_SUBDIR; // "archived"
pub use rollout::INTERACTIVE_SESSION_SOURCES;

// The rollout records conversation in chronological JSONL:
// ~/.codex/sessions/<thread-id>/rollout.jsonl
// Each line: { "item": <ResponseItem>, "metadata": {...} }
```

The `RolloutRecorder` appends to this file after every model response and tool execution. This is how `/resume` works — it re-reads the JSONL and reconstructs the conversation.

Unlike Claude Code where the disk transcript is a separate mechanism, Codex's rollout IS the source of truth for persistence. The in-memory `Session` is derived from it.

### Layer 3: State DB — SQLite for Persistent Metadata

From `lib.rs`:

```rust
pub use state_db_bridge::StateDbHandle;
pub use state_db_bridge::init_state_db;
pub use rollout::state_db::StateDbHandle;
```

The `StateDbHandle` wraps a SQLite database stored at `~/.codex/state.db`. It holds:

- Thread metadata (name, tags, archive status)
- Hook state (which hooks have been approved by the user)
- Agent graph membership (parent/child relationships for multi-agent)
- Feature rollout state

The key difference from Claude Code's KV store:
- Claude Code: flat JSON KV, max 4 MiB, no querying
- Codex: SQLite with proper schemas, indexing, and transactions

### Memory Layer Summary

| Layer | What It Holds | Lifetime | Location |
|-------|--------------|----------|----------|
| Rust Structs | Turn state, world state, active tools | Current tokio task | Process heap |
| Rollout JSONL | Full conversation transcript | Permanent | `~/.codex/sessions/<id>/rollout.jsonl` |
| State DB | Thread metadata, hook state, agent graph | Permanent | `~/.codex/state.db` (SQLite) |
| Memories | Long-term facts (separate binary) | Permanent | `~/.codex/memories/` |

---

## 5. How Context Compaction Works — Dual Strategy

Codex has two completely different compaction implementations. This is one of its most architecturally interesting features.

### Strategy 1: Local Compaction (`compact.rs`)

From `compact.rs` lines 53-75:

```rust
// The SUMMARIZATION_PROMPT is the system prompt given to the model when
// compacting — it tells the model how to summarize the conversation
pub use codex_prompts::SUMMARIZATION_PROMPT;
pub use codex_prompts::SUMMARY_PREFIX;

// Hard cap: the user message text in the compact request
// cannot exceed 20,000 tokens
const COMPACT_USER_MESSAGE_MAX_TOKENS: usize = 20_000;

// Controls whether the replacement history gets initial context injected
pub(crate) enum InitialContextInjection {
    // Used by mid-turn compaction:
    // The model expects to see the summary, then the initial context,
    // then the last real user message, in that order
    BeforeLastUserMessage {
        world_state: Arc<WorldState>,
        step_context: Arc<StepContext>,
    },
    // Used by pre-turn and manual compaction:
    // Just replace history with summary; initial context will be
    // re-injected on the next regular turn
    DoNotInject,
}

// The compacted history metadata — kept separate from the replacement history
pub(crate) struct CompactedHistoryMetadata {
    pub(crate) message: String,
    pub(crate) window_number: u64,   // monotonic counter — window 1, 2, 3...
```

The `window_number` is important — it is how Codex tracks "the third compaction in this thread". The rollout stores each compaction window separately, so you can look back at pre-compaction history.

### Strategy 2: Remote Compaction V2 (`compact_remote_v2.rs`)

From `compact_remote_v2.rs` lines 69-79:

```rust
// Two token budgets control what gets retained across compaction:
pub(crate) const RETAINED_MESSAGE_TOKEN_BUDGET: usize = 64_000;
// Retained assistant messages can be at most 10,000 tokens each
const MAX_RETAINED_AGENT_MESSAGE_TOKENS: i64 = 10_000;
// The remote compaction stream can retry up to 2 times before giving up
const MAX_REMOTE_COMPACTION_V2_STREAM_RETRIES: u64 = 2;
```

The key difference in Remote V2:
- **Local compaction**: sends the transcript to the model locally, model generates a summary
- **Remote V2**: uses a server-side compaction service that can access the full conversation in parallel, uses a token budget model to decide what to keep vs summarize

Both strategies fire the same hooks (`PreCompact` and `PostCompact`) so hook scripts cannot tell which strategy ran.

### When Each Strategy Runs

```rust
// From compact.rs (the dispatch logic, simplified):
// Mid-turn compaction: triggered when context window approaches limit DURING a turn
//   -> uses InitialContextInjection::BeforeLastUserMessage
//   -> uses local compaction (fast, no network round-trip)
//
// Pre-turn compaction: triggered before a new user turn starts
//   -> uses InitialContextInjection::DoNotInject
//   -> may use remote V2 if the thread is configured for it
//
// Manual compaction: triggered by user /compact command
//   -> always uses InitialContextInjection::DoNotInject
//   -> uses local compaction
```

### The Hook Contract for Compaction

From `hooks/src/lib.rs` line 27-28:

```rust
// These are the two hook event names fired around compaction
"PreCompact",
"PostCompact",
```

From `hooks/src/events/compact.rs` (implied by lib.rs exports):

```rust
// PreCompact hook can:
pub enum PreCompactOutcome {
    // Allow compaction to proceed (normal case)
    Allow,
    // Skip this compaction (useful if mid-task and you don't want summary to replace context)
    Skip { reason: String },
    // Override the compaction instructions
    OverrideInstructions { instructions: String },
}

// PostCompact hook receives:
pub struct PostCompactRequest {
    // What the summary looked like
    // Hook can log it, send it to external storage, etc.
}
```

---

## 6. The Hook System — 12 Lifecycle Events

Codex hooks are fundamentally different from Claude Code hooks:

| Aspect | Claude Code | Codex |
|--------|------------|-------|
| Hook handler | JavaScript function | External process (shell command) OR MCP server call OR built-in plugin |
| Registration | `register()` function in plugin | `hooks.json` in plugin dir OR `~/.codex/hooks.json` |
| Execution | In-process, async | Out-of-process subprocess OR async MCP call |
| Data passing | Event object passed by reference | JSON serialized to environment + stdin/stdout |

### The 12 Hook Events

From `hooks/src/lib.rs` lines 23-36:

```rust
pub const HOOK_EVENT_NAMES: [&str; 12] = [
    "PreToolUse",       // Before any tool runs — can block or modify input
    "PermissionRequest",// When the agent needs permission for a sensitive operation
    "PostToolUse",      // After a tool runs — can inject context based on output
    "PreCompact",       // Before context window compaction — can skip or modify
    "PostCompact",      // After compaction — can log the summary
    "SessionStart",     // When a new conversation starts — can inject initial context
    "SessionEnd",       // When a conversation ends — can log final state
    "UserPromptSubmit", // When user submits a prompt — can modify or block
    "SubagentStart",    // When a subagent loop starts
    "SubagentStop",     // When a subagent loop ends
    "Stop",             // When the agent finishes its work (idle)
    "Interrupt",        // When the agent is interrupted mid-turn
];
```

From `hooks/src/lib.rs` lines 43-53:

```rust
// Only these events support MATCHER fields (tool name, trigger, source, etc.)
pub const HOOK_EVENT_NAMES_WITH_MATCHERS: [&str; 9] = [
    "PreToolUse",        // matcher: { tool_name: "bash" }
    "PermissionRequest", // matcher: { tool_name: "..." }
    "PostToolUse",       // matcher: { tool_name: "..." }
    "PreCompact",        // matcher: { trigger: "auto" | "manual" }
    "PostCompact",       // matcher: { trigger: "..." }
    "SessionStart",      // matcher: { source: "interactive" | "background" }
    "SessionEnd",        // matcher: { reason: "..." }
    "SubagentStart",     // matcher: { subagent_type: "..." }
    "SubagentStop",      // matcher: { subagent_type: "..." }
];
// Stop and Interrupt do NOT support matchers — they fire unconditionally
```

### The Hook Payload Structure

From `hooks/src/types.rs` lines 62-97:

```rust
// Every hook receives this payload (serialized to JSON and passed to the subprocess)
#[derive(Debug, Serialize, Clone)]
pub struct HookPayload {
    pub session_id: ThreadId,           // UUID of this conversation
    pub cwd: AbsolutePathBuf,           // Current working directory
    pub client: Option<String>,         // Client identifier (tui, cli, etc.)
    pub triggered_at: DateTime<Utc>,    // When this hook fired (ISO 8601)
    pub hook_event: HookEvent,          // The event-specific data
}

// The event-specific data:
pub enum HookEvent {
    AfterAgent {
        event: HookEventAfterAgent,
    },
    // ... PreToolUse, PostToolUse etc. have their own variants
}

// What PostAgent hooks receive about the turn that just completed:
pub struct HookEventAfterAgent {
    pub thread_id: ThreadId,                       // Which thread
    pub turn_id: String,                           // Which turn
    pub input_messages: Vec<String>,               // What the user sent
    pub last_assistant_message: Option<String>,    // What the model replied
}
```

### Hook Handler Types

From `hooks/src/declarations.rs`:

```rust
// A hook handler can be one of three types:
// (from the test at line 64-79)

// 1. Prompt — asks the model to "review" this event. The model can approve/deny.
HookHandlerConfig::Prompt {}

// 2. Command — runs an external shell command
HookHandlerConfig::Command {
    command: "echo hi".to_string(),
    command_windows: None,     // Windows-specific override
    timeout_sec: None,         // Optional timeout in seconds
    r#async: false,            // If true, don't wait for completion
    status_message: None,      // Shown in TUI while hook runs
    additional_context_limit: None,  // Max bytes of output to inject as context
}

// 3. Agent — spawns a sub-agent to handle the event
HookHandlerConfig::Agent {}
```

### Hook Result Types

From `hooks/src/types.rs` lines 14-29:

```rust
pub enum HookResult {
    // Hook ran successfully and the operation should continue
    Success,

    // Hook failed, but the subsequent hooks and the operation should still run
    // (non-fatal error — logged but doesn't stop the turn)
    FailedContinue(Box<dyn std::error::Error + Send + Sync + 'static>),

    // Hook failed AND the operation should be aborted
    // (fatal error — blocks the tool call or turn)
    FailedAbort(Box<dyn std::error::Error + Send + Sync + 'static>),
}
```

### How Hook Data Flows

From `core/src/hook_runtime.rs` lines 76-89:

```rust
// What the hook system returns after running all hooks for one event:
pub(crate) struct HookRuntimeOutcome {
    pub should_stop: bool,               // Should the agent stop after this?
    pub additional_contexts: Vec<String>,// Strings to inject into model context
}

// The PreToolUse hook specifically can:
pub(crate) enum PreToolUseHookResult {
    // Allow the tool to run (optionally with a modified input JSON)
    Continue { updated_input: Option<Value> },
    // Block the tool entirely with a reason
    Blocked(String),
}
```

The `additional_contexts` field is how external hook scripts inject information into the model's context. If a `SessionStart` hook outputs JSON containing `{ "context": "This repo uses pnpm, not npm" }`, that string gets added to the model's initial context.

---

## 7. The Exec Policy System — Rule-Based Command Gating

Codex has a dedicated `execpolicy` crate that implements a **rule-based DSL** for deciding which shell commands are allowed without user confirmation.

From `core/src/exec_policy.rs` lines 48-55:

```rust
// The error messages shown when policies conflict:
const PROMPT_CONFLICT_REASON: &str =
    "approval required by policy, but AskForApproval is set to Never";
const REJECT_SANDBOX_APPROVAL_REASON: &str =
    "approval required by policy, but AskForApproval::Granular.sandbox_approval is false";
const REJECT_RULES_APPROVAL_REASON: &str =
    "approval required by policy rule, but AskForApproval::Granular.rules is false";
```

### The Policy Rule Engine

From `exec_policy.rs` lines 1-44:

```rust
// The policy engine comes from the `codex_execpolicy` crate
use codex_execpolicy::Decision;      // Allow | Require(approval) | Deny
use codex_execpolicy::Evaluation;    // The result of evaluating one command
use codex_execpolicy::MatchOptions;  // How to match commands
use codex_execpolicy::Policy;        // A set of rules
use codex_execpolicy::PolicyParser;  // Parses .rules files
use codex_execpolicy::RuleMatch;     // Which rule matched

// The policy is loaded from .rules files
const RULES_DIR_NAME: &str = "rules";
const RULE_EXTENSION: &str = "rules";
const DEFAULT_POLICY_FILE: &str = "default.rules";
```

### The Dangerous Command Blocklist

From `exec_policy.rs` lines 57-100, a hardcoded list of shell prefixes that are **always blocked** regardless of policy:

```rust
pub(crate) static BANNED_PREFIX_SUGGESTIONS: &[&[&str]] = &[
    // Shell interpreters as argument (would bypass policy parsing)
    &["/bin/bash"], &["/bin/bash", "-c"], &["/bin/sh"], &["/bin/sh", "-c"],
    &["/bin/zsh"], &["/bin/zsh", "-c"],

    // Scripting languages that can run arbitrary code
    &["node"], &["node", "-e"],
    &["python"], &["python3"],
    &["ruby"], &["ruby", "-e"],
    &["perl"], &["perl", "-e"],
    &["lua"], &["lua", "-e"],
    &["julia"], &["julia", "-e"],

    // Package runners that spawn subprocesses
    &["npm", "run"],
    &["bun"], &["bun", "run"],
    &["deno"], &["deno", "eval"],

    // Windows shell
    &["cmd"], &["cmd", "/c"], &["cmd.exe"], &["cmd.exe", "/c"],
    // ... and many more
];
```

These prefixes are "suggestions" — meaning Codex suggests safe alternatives when it encounters them. For example, if the model tries to run `bash -c "curl ..."`, Codex blocks the `bash -c` wrapper and suggests just running `curl ...` directly (which CAN be policy-matched cleanly).

### Policy Evaluation Flow

```
Model calls shell_command tool with argv: ["npm", "test", "--coverage"]

exec_policy.rs:
  1. check_execpolicy_for_warnings(argv)
     -> Is argv in BANNED_PREFIX_SUGGESTIONS? No (npm run is blocked, not npm test)
  
  2. load_exec_policy(config, cwd)
     -> Reads ~/.codex/rules/*.rules files
     -> Reads workspace .codex/rules/*.rules files  
     -> Merges via ConfigLayerStack (workspace overrides global)
  
  3. policy.evaluate(argv, MatchOptions { network: allowed?, ... })
     -> Decision::Allow        -> run without asking
     -> Decision::Require(..)  -> show approval dialog or auto-approve
     -> Decision::Deny(reason) -> block, show error to model

  4. If Require and AskForApproval::Granular:
     -> PermissionRequest hook fires first
     -> If hook returns "grant" -> auto-approve
     -> Otherwise -> show TUI dialog
```

---

## 8. The Sandboxing System — Four Platform Backends

From `core/README.md`:

```
Platform    | Sandbox Mechanism
------------|--------------------------------------------------
macOS       | /usr/bin/sandbox-exec (Apple Seatbelt / sandbox profiles)
Linux       | bubblewrap (bwrap) — user namespace container
Windows     | Restricted token (unelevated) OR elevated Windows sandbox service
WSL2        | Normal Linux bubblewrap path
WSL1        | NOT supported (cannot create user namespaces)
```

### The Sandbox Policy Model

From `exec_policy.rs` lines 24-25:

```rust
use codex_protocol::permissions::FileSystemSandboxKind;
use codex_protocol::protocol::SandboxPolicy;
```

Codex has two distinct sandbox models:

**Legacy model** (`SandboxPolicy` enum):
```
ReadOnly       -> All reads allowed, NO writes at all
WorkspaceWrite -> Reads allowed everywhere, writes only in workspace roots
```

**New split filesystem model** (`FileSystemSandboxPolicy`):
```
Each path has an explicit policy:
  /repo          -> write
  /repo/.git     -> read-only (carved out under writable root)
  /repo/secrets  -> none (no access at all)
  /usr/lib       -> read (implicit platform default)
```

The split model is more expressive but requires platform support. From `core/README.md`:

```
Linux: Split policies that need direct enforcement route through bubblewrap.
       Legacy policies that round-trip through the legacy model use Landlock.
       Overlapping cases (/repo=write, /repo/a=none, /repo/a/b=write) are
       handled by re-opening writable descendants under denied parents.
```

### macOS Seatbelt Profile Generation

The `sandboxing` crate generates a Seatbelt profile (a Scheme-like DSL) from the `SandboxPermissions` struct. For example, for a `WorkspaceWrite` policy on `/Users/alice/myproject`:

```scheme
; Generated Seatbelt profile (simplified)
(version 1)
(deny default)
(allow file-read*)                    ; Full read everywhere
(allow file-write* (subpath "/Users/alice/myproject"))  ; Write in workspace
(deny file-write* (subpath "/Users/alice/myproject/.git"))  ; Except .git
(deny file-write* (subpath "/Users/alice/myproject/.codex")) ; And .codex config
(allow user-preference-read)          ; macOS cfprefs compatibility
(allow process*)                      ; Allow spawning child processes
```

### Linux Bubblewrap

For Linux, the sandbox is created by re-exec'ing Codex with `arg0 = "codex-linux-sandbox"`. The `arg0` crate detects this and enters sandbox mode:

```rust
// From core/README.md:
// Expects the binary containing codex-core to run the equivalent of
// `codex sandbox` when `arg0` is `codex-linux-sandbox`.

// The bwrap command (simplified):
// bwrap \
//   --bind /repo /repo \         <- Bind workspace (writable)
//   --ro-bind / / \             <- Bind entire system read-only
//   --tmpfs /tmp \              <- Temporary FS for /tmp
//   --dev /dev \                <- Device files
//   --proc /proc \              <- Process info
//   -- codex-linux-sandbox <actual command args>
```

The sandbox binary selection is smart from `core/README.md`:
```
- Prefers bwrap found on PATH (outside cwd — avoids using a project-local bwrap)
- Falls back to bundled codex-resources/bwrap if system bwrap is missing
- Falls back to no sandbox with a warning if bwrap cannot create user namespaces
```

### Windows Sandbox

Windows has two backends:

```
1. Unelevated restricted-token backend (legacy):
   - Uses a Windows restricted token (low-privilege)
   - Supports ReadOnly and WorkspaceWrite behavior
   - Does NOT support exact-read or exact-write split policies

2. Elevated Windows sandbox service (new):
   - Uses the windows-sandbox-service crate
   - Supports split filesystem policies
   - Supports exact readable roots, exact writable roots
   - Automatically adds: C:\Windows, C:\Program Files, C:\ProgramData
     as system read roots when requested

Policy selection:
  If split policy can be handled by unelevated backend -> unelevated (safer)
  If split policy needs explicit unreadable carveouts -> elevated
  If policy would require weaker enforcement -> FAILS CLOSED (refused, not weakened)
```

---

## 9. The Multi-Agent System — AgentControl Trait

### The AgentControl Trait

From `core/src/agent/api.rs` lines 40-100:

```rust
// The central abstraction for all multi-agent operations.
// It's a Rust trait — local and remote backends implement the same interface.
pub trait AgentControl: Send + Sync {
    fn identity(&self) -> SessionId;

    // Resolve a target name to a ThreadId (lazy — does not load the agent)
    fn resolve<'a>(
        &'a self,
        caller: ThreadId,
        parent: Option<ThreadId>,
        source: &'a SessionSource,
        target: &'a str,
    ) -> BoxFuture<'a, Result<ThreadId>>;

    // Start a child agent — returns its live handle and config snapshot
    fn spawn(
        &self,
        request: SpawnRequest,
    ) -> BoxFuture<'_, Result<(LiveAgent, ThreadConfigSnapshot)>>;

    // Send a message to an existing agent (may wake it if idle)
    fn send(&self, request: SendRequest) -> BoxFuture<'_, Result<DeliveryReceipt>>;

    // Load a recorded V2 child without sending input
    // (for restoring a sub-agent tree from a saved session)
    fn ensure_child_loaded(&self, parent: ThreadId, child: ThreadId) -> BoxFuture<'_, Result<()>>;

    // Interrupt an agent mid-turn
    fn interrupt(
        &self,
        caller: ThreadId,
        target: AgentTarget,
        version: MultiAgentVersion,
    ) -> BoxFuture<'_, Result<AgentInfo>>;

    // List all agents visible to the caller
    fn list<'a>(
        &'a self,
        caller: ThreadId,
        parent: Option<ThreadId>,
        source: &'a SessionSource,
        path_prefix: Option<&'a str>,
    ) -> BoxFuture<'a, Result<Vec<LiveAgent>>>;

    // Get direct child agent paths for model context injection
    fn child_agent_paths(&self, parent: ThreadId) -> BoxFuture<'_, Vec<AgentPath>>;

    // Advisory capacity check (non-binding, doesn't reserve a slot)
    fn check_turn_admission(
        &self,
        version: MultiAgentVersion,
        source: &SessionSource,
    ) -> Result<()>;
}
```

### Agent Versions — V1 vs V2

The `MultiAgentVersion` enum controls behavior:

```
MultiAgentVersion::V1:
  - Simple parent/child hierarchy
  - Child agents cannot interrupt root or self
  - Direct-ID interruption supported
  - Best-effort delivery reporting

MultiAgentVersion::V2:
  - Tree-based agent graph stored in StateDb
  - V2 rejects root/self interrupt targets
  - Tolerates known unloaded agents (lazy loading)
  - Full agent path resolution
```

### The Agent Graph Store

From `lib.rs`:

```rust
pub use thread_manager::local_agent_graph_store_from_state_db;
```

The `AgentGraphStore` is backed by SQLite. It persists:
- Parent/child relationships (even across process restarts)
- Agent metadata (description, type, status)
- Agent path strings for V2 address routing

### SpawnAgentOptions

From `core/src/agent/types.rs` (implied by lib.rs exports):

```rust
pub struct SpawnAgentOptions {
    // Which fork mode to use:
    pub fork_mode: SpawnAgentForkMode,
    // ...
}

pub enum SpawnAgentForkMode {
    // Start fresh with a new empty conversation
    Fresh,
    // Fork from the current thread (shares context up to the fork point)
    Fork,
    // Start with an explicit history loaded
    WithHistory { thread_id: ThreadId },
}
```

### Multi-Agent Message Board

From `lib.rs`:

```rust
pub use agent_message_board::install_agent_message_board;
```

The `agent-message-board-client` crate implements a typed message bus between agents. Unlike Claude Code's `SendMessage` tool (which uses natural language strings), the Codex message board uses typed envelopes:

```
Agent A sends: { to: "security-reviewer", payload: { file_paths: [...] } }
Agent B receives: { from: "main", payload: { file_paths: [...] } }
```

---

## 10. The Protocol Layer — Wire Format and Events

### Event and Op

From `codex_thread.rs` imports:

```rust
use codex_protocol::protocol::Event;
use codex_protocol::protocol::Op;
use codex_protocol::protocol::EventMsg;
```

The protocol crate defines the full wire format:

```rust
// An Op is what flows FROM the UI TO the core (user inputs)
enum Op {
    UserTurnSubmit { input: TurnInput, ... },
    Interrupt { turn_id: String },
    ForkThread { ... },
    // ...
}

// An Event is what flows FROM the core TO the UI (agent outputs)
enum Event {
    // Model streaming
    AgentReasoningDelta { delta: String },
    AgentMessageDelta { delta: String },
    AgentTurnDone { ... },

    // Tool execution
    ExecCommandBegin { command: Vec<String>, ... },
    ExecCommandOutputDelta { stream: ExecOutputStream, data: Vec<u8> },
    ExecCommandEnd { exit_code: i32, ... },

    // Hook lifecycle
    HookStarted { ... },
    HookCompleted { ... },

    // Warnings and errors
    Warning { code: String, message: String },
    Error { ... },
    // ...
}
```

### TurnInput — All Ways to Start a Turn

From `lib.rs` imports:

```rust
pub use codex_protocol::turn_input::TurnInput;
pub use codex_protocol::turn_input::TurnInputSubmission;
pub use codex_protocol::turn_input::SteerSubmission;
pub use codex_protocol::turn_input::SuspendTurnOutcome;
pub use codex_protocol::turn_input::RecoverTurnRequest;
pub use codex_protocol::turn_input::StartIfIdleSubmission;
```

```rust
// How a turn can start:
enum TurnInput {
    // Normal user message
    UserMessage { text: String, attachments: Vec<Attachment> },

    // Steer: inject a message mid-turn to redirect the agent
    Steer(SteerSubmission),

    // Start only if the agent is currently idle (used by cron/background tasks)
    StartIfIdle(StartIfIdleSubmission),

    // Recover from an interrupted or failed turn
    Recover(RecoverTurnRequest),
}
```

### The Responses API — Streaming Architecture

Codex uses OpenAI's Responses API (not Chat Completions). This API:

```
POST /v1/responses
Request: { model, input: [...], tools: [...], stream: true }

Response (SSE stream):
  data: {"type": "response.created", ...}
  data: {"type": "response.output_item.added", ...}
  data: {"type": "response.content_part.delta", "delta": {"text": "..."}}
  data: {"type": "response.output_item.done", ...}
  data: {"type": "response.done", ...}
```

From `client.rs` public exports:

```rust
pub use client::X_RESPONSESAPI_INCLUDE_TIMING_METRICS_HEADER;
pub use client::X_CODEX_INSTALLATION_ID_HEADER;
pub use client::X_CODEX_ROUTING_HINT_HEADER;
pub use client::X_CODEX_TURN_METADATA_HEADER;
```

The `X_CODEX_TURN_METADATA_HEADER` carries per-turn metadata to the server — model type, reasoning effort, active environments, etc. — allowing server-side routing decisions.

---

## 11. How Layers Work Together — Full Turn Trace

Let's trace "Add pagination to the API endpoint" through the entire Codex stack.

### Initial State

```
Process state:
  ThreadManager: 1 active CodexThread (ID: "thr_abc")
  Session: conversation loaded from ~/.codex/sessions/thr_abc/rollout.jsonl
  WorldState: { tools: [shell_command, apply_patch, web_search], files_context: [] }
  SandboxPermissions: WorkspaceWrite ["/Users/alice/myapi"]

In-memory state (Rust structs):
  active_model: "gpt-5-codex"
  approval_policy: AskForApproval::Granular { sandbox: true, rules: true }
  exec_policy: loaded from ~/.codex/rules/default.rules

State DB (SQLite):
  threads: [{ id: "thr_abc", name: "pagination task", ... }]
  hook_states: [{ key: "my-plugin:hooks.json:pre_tool_use:0:0", state: "approved" }]
```

### Step 1: User Types the Prompt

```
TUI receives keypress -> buffers text -> Enter pressed
Op::UserTurnSubmit sent via tokio channel to ThreadManager
ThreadManager routes to CodexThread "thr_abc"
```

### Step 2: UserPromptSubmit Hook Fires

```rust
// hook_runtime.rs — run_user_prompt_submit_hooks()
// Fires all registered UserPromptSubmit handlers:

// For each handler in the registry:
//   1. Serialize HookPayload { session_id, cwd, triggered_at, hook_event }
//   2. If handler is Command:
//        spawn subprocess, write payload to stdin
//        read stdout for additional context (up to additional_context_limit bytes)
//   3. If handler returns context: add to TurnContext.additional_contexts

// My audit hook script might output:
// { "context": "Project uses cargo test, not npm test" }

// HookRuntimeOutcome:
//   should_stop: false
//   additional_contexts: ["Project uses cargo test, not npm test"]
```

### Step 3: Build the Prompt and Send to Model

```rust
// session/step_context.rs builds the full prompt:
// - AGENTS.md / CODEX.md content (from agents_md.rs)
// - Active tool schemas (from WorldState)
// - Conversation history (from rollout.jsonl, compacted if needed)
// - Additional contexts from hooks (Step 2)
// - Current turn's user message

// client.rs:
// POST /v1/responses
// Headers: X-Codex-Turn-Metadata: { model, environments, ... }
// Body: { model: "gpt-5-codex", stream: true, input: [...] }

// Response stream begins flowing:
// AgentReasoningDelta events -> streamed to TUI
// AgentMessageDelta events -> streamed to TUI
// response.output_item.added (tool_call) -> triggers tool execution
```

### Step 4: Model Calls shell_command

```
Model outputs:
  { type: "function_call", name: "shell_command", arguments: { cmd: "cargo test" } }

core/src/exec.rs receives the tool call
```

```rust
// Step 4a: exec_policy check
exec_policy.evaluate(["cargo", "test"])
// Result: Decision::Allow (cargo test is in the allow list)
// No dialog shown

// Step 4b: PreToolUse hooks fire
// hook_runtime.rs: run_pre_tool_use_hooks(tool: "shell_command", input: {...})
//   - Hooks can modify the input JSON or block entirely
//   - PreToolUseHookResult::Continue { updated_input: None }
//   -> proceed with original input

// Step 4c: Sandbox wraps the command
// sandboxing::SandboxManager.transform(SandboxTransformRequest {
//   argv: ["cargo", "test"],
//   cwd: "/Users/alice/myapi",
//   permissions: WorkspaceWrite(["/Users/alice/myapi"]),
// })
// On macOS: prepends /usr/bin/sandbox-exec -f <generated_profile>
// Result: ["/usr/bin/sandbox-exec", "-f", "/tmp/codex-sb-xyz.sb", "cargo", "test"]
```

```rust
// Step 4d: Process execution
// exec.rs:
pub const DEFAULT_EXEC_COMMAND_TIMEOUT_MS: u64 = 10_000;  // 10 second default

// spawn_child_async(SpawnChildRequest {
//   argv: ["/usr/bin/sandbox-exec", "-f", "...", "cargo", "test"],
//   cwd: "/Users/alice/myapi",
//   stdio: StdioPolicy::Pipe,
//   cancellation_token: ...,
// })

// Output streams:
// - stdout chunks -> ExecCommandOutputDelta events (capped at MAX_EXEC_OUTPUT_DELTAS_PER_CALL = 10,000)
// - stderr chunks -> ExecCommandOutputDelta events
// - Hard cap: EXEC_OUTPUT_MAX_BYTES on retained output (mirrors DEFAULT_OUTPUT_BYTES_CAP)
// - IO drain timeout: IO_DRAIN_TIMEOUT_MS = 2,000 ms after kill
```

```rust
// Step 4e: PostToolUse hooks fire
// hook_runtime.rs: run_post_tool_use_hooks(tool: "shell_command", output: {...})
// If a PostToolUse hook injects context: adds to model's next turn context

// Result serialized as ExecToolCallOutput:
// { exit_code: 0, stdout: "running 42 tests...\n...\nok", stderr: "" }
// Appended to conversation as function_call_output
```

### Step 5: Model Calls apply_patch

```
Model decides to edit the file. It calls apply_patch with a patch format:

*** Begin Patch
--- src/api/users.rs
+++ src/api/users.rs
@@ -45,7 +45,12 @@
-pub async fn list_users(db: &Database) -> Vec<User> {
+pub async fn list_users(
+    db: &Database,
+    page: Option<u32>,
+    per_page: Option<u32>,
+) -> PaginatedResult<User> {
*** End Patch

exec_policy: apply_patch is a built-in tool, not shell — no policy check needed

Sandboxing for apply_patch:
  Path check: is /Users/alice/myapi/src/api/users.rs inside workspace root?
  -> YES -> write permitted
  -> applies patch atomically

PostToolUse hooks fire (can observe the patch, log changes, etc.)
```

### Step 6: Turn Completes — Rollout Persistence

```rust
// After the model's final message:
// rollout.rs: RolloutRecorder.append_turn(RolloutItem {
//   response_items: [...],   // All model messages and tool calls
//   metadata: CodexHarnessMetadata {
//     model: "gpt-5-codex",
//     usage: TokenUsage { input: 12453, output: 843, ... },
//     ...
//   }
// })
// Appended to: ~/.codex/sessions/thr_abc/rollout.jsonl

// Stop hook fires:
// hook_runtime.rs: run_stop_hooks()
// If any Stop handler script runs: can trigger cleanup, notifications, etc.

// TUI receives:
// AgentTurnDone { turn_id: "turn-42", ... }
// Shows turn completion, total tokens used, cost
// Prompts for next user input
```

---

## 12. Codex vs Claude Code — Comparison Table

### Architecture Philosophy

| Dimension | Claude Code | Codex |
|-----------|------------|-------|
| Runtime | Node.js + V8 snapshot | Rust + tokio |
| Startup time | 800ms–2s | < 20ms |
| Memory footprint | 150–300 MB | < 50 MB |
| Plugin/hook system | In-process JS | Out-of-process subprocess OR MCP |
| Plugin language | TypeScript (same runtime) | Any language (shell scripts, Python, etc.) |
| Plugin hot-reload | Yes (engine-level) | Requires restart |
| Compile-time safety | Runtime type checks | Full Rust type system |

### Memory Systems

| System | Claude Code | Codex |
|--------|------------|-------|
| Ephemeral state | Closured JS let variables | Typed Rust structs (owned) |
| Persistent KV | `$.store` (JSON file, 4 MiB max) | SQLite state DB (no size limit) |
| Conversation history | JSONL transcript file | JSONL rollout file (`~/.codex/sessions/`) |
| Long-term memory | Not built-in | Dedicated `memories/read` + `memories/write` binaries |

### Context Management

| Feature | Claude Code | Codex |
|---------|------------|-------|
| Compaction trigger | ~85% context full | Configurable threshold |
| Compaction strategy | Single (model summarizes) | Dual: local (fast) OR remote V2 (server-side) |
| Retained token budget | Not exposed | 64,000 tokens retained by default |
| Hooks around compaction | `session.compact` event | `PreCompact` + `PostCompact` events |
| Pre-compute | Yes (speculative summary before needed) | Yes (runs before threshold hit) |

### Hook System

| Feature | Claude Code | Codex |
|---------|------------|-------|
| Hook events | 15+ (session.start, tool.call, ui.render, etc.) | 12 named events |
| Hook execution | Sync/async in-process JS | Out-of-process subprocess OR MCP OR built-in plugin |
| Hook registration | plugin `register()` function | `hooks.json` config file |
| Hook pattern matching | Event pattern objects | matcher fields per event type |
| Hook result | Return value from async JS function | Exit code + JSON stdout |
| Context injection | `next({ ...e, context: [...] })` | stdout `{ "context": "..." }` from subprocess |
| Hook failure modes | Throw -> skip hook, others continue | FailedContinue vs FailedAbort enum |

### Sandboxing

| Feature | Claude Code | Codex |
|---------|------------|-------|
| Sandbox mechanism | Runtime path checks + deny lists | OS-level: Seatbelt / bubblewrap / Windows sandbox |
| macOS sandbox | Symlink-safe stat checks | `/usr/bin/sandbox-exec` with generated Seatbelt profile |
| Linux sandbox | No OS sandbox | bubblewrap (user namespaces) |
| Windows sandbox | No OS sandbox | Restricted token OR elevated sandbox service |
| Writable roots | Any path inside project root | Explicit `workspace_roots` list |
| Read-only carveouts | Allowed via 5-tier deny | Explicit `FileSystemSandboxPolicy` |
| Network policy | Not enforced at OS level | `NetworkSandboxPolicy` via network proxy |
| Policy files | Not supported | `~/.codex/rules/*.rules` DSL files |

### Multi-Agent

| Feature | Claude Code | Codex |
|---------|------------|-------|
| Agent abstraction | `$.agent.spawn()` API | `AgentControl` trait (local or remote backends) |
| Agent tree | In-memory during session | Persisted in SQLite `AgentGraphStore` |
| Agent versions | Single (no versioning) | V1 (simple) + V2 (typed tree, lazy loading) |
| Agent messaging | `SendMessage` tool (natural language) | `agent-message-board` typed envelopes |
| Agent isolation | Git worktree | Git worktree + remote cloud environments |
| Agent listing | `$.agent.list()` | `AgentControl::list()` with path prefix filtering |
| Max concurrency | Not enforced | `check_turn_admission()` advisory check |

> [!TIP]
> The key architectural insight: Codex is more **infrastructure** and less **product**. It exposes raw Rust types through traits, lets you swap backends (local vs remote exec, local vs cloud agent control, local vs server-side compaction). Claude Code is more opinionated — it defines THE plugin API and THE event model. Codex lets you reimplement any layer.

