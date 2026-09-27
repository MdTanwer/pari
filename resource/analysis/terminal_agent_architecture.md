# Terminal Agent Architecture: Deep Dive
## Analyzing Claude Code & Building Something Better

> [!NOTE]
> This document is based on direct analysis of the Claude Code source repository at
> `c:\Users\tanw9\pari\resource\claude-code` — specifically its engine type contracts
> (`mods/types/claude-code.d.ts`, 13,045 lines) and internal mod implementations.

---

## Table of Contents

1. [What Is Claude Code At Its Core](#1-what-is-claude-code-at-its-core)
2. [The 5-Tier Onion Middleware Pipeline](#2-the-5-tier-onion-middleware-pipeline)
3. [The Microkernel Engine Context — `$`](#3-the-microkernel-engine-context--)
4. [Built-in Tools Inventory](#4-built-in-tools-inventory)
5. [Terminal UI & Multi-Surface Architecture](#5-terminal-ui--multi-surface-architecture)
6. [The Plugin / Mod System](#6-the-plugin--mod-system)
7. [Subagents & Workflow Orchestration](#7-subagents--workflow-orchestration)
8. [Context Management & Compaction](#8-context-management--compaction)
9. [Architectural Weaknesses](#9-architectural-weaknesses)
10. [Blueprint: Building a Better Terminal Agent](#10-blueprint-building-a-better-terminal-agent)
11. [Implementation Roadmap](#11-implementation-roadmap)

---

## 1. What Is Claude Code At Its Core

Claude Code is an **agentic coding tool** that runs inside your terminal. It is not a simple chatbot wrapper — it is a full **microkernel engine** with:

- An event-driven middleware pipeline that every operation passes through
- A sandboxed plugin runtime (hooks modules) with no access to the DOM, `require`, or raw Node globals
- A model-driven ReAct loop (Reason → Act → Observe → Repeat) built around an Anthropic-hosted model
- A multi-surface rendering system that works across terminal, desktop, VS Code, and mobile clients simultaneously

The binary ships with four built-in "mods" (engine-level plugins):

| Mod | What It Does |
| :--- | :--- |
| `sec-default` | Keeps organization policies, prompt content, managed settings, and tool permission rules out of reach of user-installed plugins |
| `diff` | Powers the `/diff` command — shows a live split-pane view of uncommitted file changes, refreshed as Claude edits |
| `telemetry` | Hooks the `$.telemetry` noun for first-party analytics; refuses calls from third-party plugins |
| `agents-md` | Controls how `AGENTS.md` / `CLAUDE.md` instruction files are loaded and merged into the system prompt |

---

## 2. The 5-Tier Onion Middleware Pipeline

This is the heart of the architecture. Every single operation in Claude Code — a file read, a tool call, a model turn, a UI render — is dispatched as a **named event** that travels through a fixed 5-tier chain.

### The Tiers (Outermost to Innermost)

```
[ prepend ] → [ user ] → [ append ] → [ builtin ] → [ core ]
```

Source: [`claude-code.d.ts` line 9601](mods/types/claude-code.d.ts)

```typescript
const TIERS: readonly ["prepend", "user", "append", "builtin", "core"];
```

### Tier Descriptions

| Tier | Authority Level | Who Populates It |
| :--- | :--- | :--- |
| `prepend` | Highest (Outermost) | Managed plugins prepended by an IT administrator. These cannot be bypassed by the user. Used for corporate security policies, content filtering, and audit logging. |
| `user` | Medium-High | Everything a developer installs manually via `claude install <plugin>` or from the marketplace. |
| `append` | Medium | Managed plugins appended by an administrator (post-filters, compliance checkers). |
| `builtin` | Medium-Low | The four mods (`diff`, `telemetry`, `sec-default`, `agents-md`) bundled into the binary itself. |
| `core` | Lowest (Innermost) | The engine's own primitive implementation — actual file I/O, actual model API calls, actual subprocess execution. |

### How a Hook Works

Every hook has this exact signature:

```typescript
on("tool.call", ($, e, next) => {
  // e   = the frozen event payload (immutable)
  // $   = the engine context (nouns like $.ui, $.fs, $.session)
  // next = call this to pass the event to the next tier

  // Example: block all writes to /etc
  if (e.tool === "Write" && e.file_path.startsWith("/etc")) {
    return { deny: "Writing to /etc is not allowed" }
  }

  // Pass through to the next tier
  return next(e)
})
```

### The Chain-of-Responsibility Mechanism

1. **Inspect & Mutate Input**: A hook can rewrite the event payload before passing it on.
   ```typescript
   // Force all Bash commands to run with a 10 second timeout
   on("tool.call", { tool: "Bash" }, ($, e, next) =>
     next({ ...e, timeout: 10_000 })
   )
   ```

2. **Veto / Deny**: A hook can return `{ deny: "reason" }` to stop execution entirely without calling `next`.

3. **Observe Output**: Because `next(e)` is an async call, outer hooks can inspect what inner tiers produced.
   ```typescript
   on("tool.call", { tool: "Bash" }, async ($, e, next) => {
     const result = await next(e)
     $.ui.log(`Command exited with code ${result.exitCode}`)
     return result
   })
   ```

4. **Event Patterns**: Hooks can be registered with a **pattern object** that narrows which events trigger them:
   ```typescript
   on("tool.call", { tool: "Read" },    handler)  // Only file reads
   on("tool.call", { tool: "Bash" },    handler)  // Only shell commands
   on("tool.call", { tool: /^mcp__/ },  handler)  // All MCP tool calls
   ```

---

## 3. The Microkernel Engine Context — `$`

Plugins never access Node's `fs`, `child_process`, or `process` directly. All capabilities are mediated through the `$` object (an instance of `CoreEngineInterface`). This is the kernel's API surface.

### `$.ui` — Display & Interaction

Controls everything the user sees and can interact with.

```typescript
$.ui.open({ id: "diff-pane", title: "Changes", rows: 40 })
$.ui.close({ id: "diff-pane" })
$.ui.ask("Deploy to prod?", ["Yes", "No"])        // Modal question dialog
$.ui.toast("Build succeeded in 3.2s")              // Ephemeral notification
$.ui.status("Indexing repository...")              // Persistent status line
$.ui.log("Cache miss for tool_use_id_123")         // Transcript line
$.ui.notice(e.tool_use_id, "Running security scan") // Dialog sub-notice
$.ui.invalidate("ui.render")                       // Trigger a re-render
```

**Surfaces**: The engine renders to these independently:
- `terminal` — ANSI terminal (the primary surface, Ink/React-like)
- `desktop` — Electron-based Claude desktop app
- `vscode` — VS Code extension panel
- `mobile` — iOS/Android Claude app

A hook gets `e.surface` to know which surface it's drawing for:
```typescript
on("ui.render", { component: "Pane" }, ($, e) => {
  const { Box, Text, Button } = $.ui.resolve(e)  // Gets typed element table for the surface
  return <Box><Text bold>{state.title}</Text></Box>
})
```

### `$.model` — LLM Access

```typescript
// Free-form completion (no tools, no history)
const reply = await $.model.complete({
  model: "haiku",
  prompt: "In one word, summarize this error: " + stderr,
  maxTokens: 20
})

// Fork from current session's transcript (shares prompt cache!)
// Zero cost on cached tokens — very efficient for analysis tasks
const analysis = await $.model.fork({ prompt: "What files did you just change?" })

// Zero-shot text classifier
const category = await $.model.classify(
  userInput,
  ["code-question", "file-operation", "git-task", "other"]
)
```

> [!IMPORTANT]
> `$.model.fork()` is architecturally important — it creates a **cache-sharing branch** off the main session's conversation, so it can query the model about the current session context at near-zero token cost. It can NOT call tools. This is how Claude Code builds lightweight "meta-analysis" without inflating the main context window.

### `$.fs` — File System

```typescript
const content = await $.fs.read("src/main.rs")
const { base64 } = await $.fs.read("model.bin", { as: "bytes" })

await $.fs.write("output.txt", "Hello World")

const entries = await $.fs.list("src/")
// entries: { name: string, kind: "file"|"dir"|"other", size: number, isLink: boolean }[]

const exists = await $.fs.exists(".env")

const stat = await $.fs.stat("symlink.ts", { resolve: true })
// stat: { kind, size, mtimeMs, isLink, realPath? }

// Walk up the directory tree to find AGENTS.md / CLAUDE.md files
const instructionFiles = await $.fs.ancestors({
  names: ["AGENTS.md", "CLAUDE.md"],
  of: e.file_path,
  below: await $.session.root()
})
```

> [!NOTE]
> `$.fs.ancestors()` is how the `agents-md` built-in mod implements the directory-hierarchy instruction merging feature — it walks from the project root down to the current file, collecting all `CLAUDE.md` / `AGENTS.md` files it finds along the way.

### `$.session` — Running Session State

```typescript
const msgs = await $.session.messages()
// Returns up to 4096 most recent SessionMessage entries
// { role: "user"|"assistant", text: string, toolUses: ToolUse[] }

const cwd = await $.session.cwd()           // Current working directory
const root = await $.session.root()         // Project root (set at session start)
const model = await $.session.model()       // e.g. "claude-sonnet-4-5-20251"
const turns = await $.session.turns()       // Number of user turns so far

const usage = await $.session.usage()
// { context: { percent: 73 }, rateLimits: {...}, cost: "$0.12" }

// Trigger context compaction (equivalent to /compact command)
if (usage.context.percent >= 85) {
  await $.session.compact({ instructions: "Focus on the refactoring task" })
}

// Get a credential handle for first-party API auth
const auth = await $.session.authorize()
await $.http.fetch(apiUrl, { auth: auth?.handle })
```

### `$.tool` — Tool Registry & Execution

```typescript
// See what tools the model currently has access to
const tools = await $.tool.list()
// [{ name: "Bash", description: "...", inputSchema: {...} }, ...]

// Call a tool as if the model called it (goes through all hooks)
const result = await $.tool.call({ tool: "Read", file_path: "README.md" })

// Check if a tool call would be permitted without actually running it
const { decision } = await $.tool.check({ tool: "Bash", command: "rm -rf /" })

// Register a new custom tool the model can call
await $.tool.register({
  name: "weather",
  description: "Get current weather for a city",
  inputSchema: {
    type: "object",
    properties: { city: { type: "string" } }
  }
})
// Now serve it:
on("tool.call", { tool: "mcp__my-plugin__weather" }, async ($, e) => {
  const data = await fetch(`/api/weather?city=${e.city}`)
  return { result: await data.json() }
})
```

### `$.agent` — Subagent Control

```typescript
// Spawn a background subagent
const { agentId } = await $.agent.spawn({
  prompt: "Read all .ts files in src/ and produce a dependency graph",
  run_in_background: true
})

// Register a custom agent type (with its own system prompt)
await $.agent.register({
  name: "security-auditor",
  description: "Audits code for security vulnerabilities",
  prompt: SECURITY_AUDIT_SYSTEM_PROMPT,
  tools: ["Read", "Bash"],
  omitClaudeMd: true   // Don't load CLAUDE.md for this agent
})

// List all running/completed subagents
const agents = await $.agent.list()
```

### `$.process` — Host Command Execution

```typescript
// Run a command directly (not through Bash tool)
const { exitCode, stdout, stderr } = await $.process.run(
  ["git", "log", "--oneline", "-10"],
  { cwd: "/path/to/repo", timeoutMs: 5000 }
)
```

### `$.store` — Persistent Key-Value Store

```typescript
// Per-plugin, survives sessions and hot reloads
const lastSeen = await $.store.get("lastSeenCommit")
await $.store.set("lastSeenCommit", "abc123def")
await $.store.delete("lastSeenCommit")
const allKeys = await $.store.keys()
```

### `$.clock` — Virtualized Timers

```typescript
// One-shot timer
const timer = $.clock.after(5000, () => $.ui.toast("5 seconds elapsed"))
timer.cancel()  // Cancel before it fires

// Recurring interval
const poll = $.clock.every(30_000, async () => {
  const { stdout } = await $.process.run(["git", "fetch"])
  if (stdout.includes("origin")) $.ui.toast("New commits available")
})

// Direct sleep (respects AbortSignal from the hook's dispatch)
await $.clock.sleep(1000, { signal: next.signal })
```

### `$.mcp` — External MCP Server Calls

```typescript
const { content, isError } = await $.mcp.call(
  "claude.ai Gmail",         // Server name
  "create_draft",            // Tool on that server
  { to: "team@company.com", subject: "Release Notes", body: "..." }
)
```

---

## 4. Built-in Tools Inventory

These are the tools the engine makes available to the LLM. Each maps directly to a TypeScript interface in `BuiltinToolInputs`.

### File Tools

| Tool | Key Inputs | Description |
| :--- | :--- | :--- |
| `Read` | `file_path`, `offset?`, `limit?`, `pages?` | Reads a file. Supports PDF page ranges. |
| `Write` | `file_path`, `content` | Writes a complete file (creates if missing). Must be an absolute path. |
| `Edit` | `file_path`, `old_string`, `new_string`, `replace_all?` | Replaces the first (or all) occurrence of `old_string` with `new_string`. The old string must be **unique** in the file. |
| `NotebookEdit` | `notebook_path`, `cell_id?`, `new_source`, `cell_type?`, `edit_mode?` | Modifies Jupyter notebook cells (replace, insert, or delete). |

### Execution Tools

| Tool | Key Inputs | Description |
| :--- | :--- | :--- |
| `Bash` | `command`, `timeout?`, `run_in_background?`, `dangerouslyDisableSandbox?` | Runs a shell command. Max timeout: 600 seconds. |
| `PowerShell` | `command`, `timeout?`, `run_in_background?` | Windows PowerShell equivalent of Bash. |

### Git & Isolation Tools

| Tool | Key Inputs | Description |
| :--- | :--- | :--- |
| `EnterWorktree` | `name?`, `path?` | Creates or enters a Git worktree — an isolated working copy of the repository on a separate branch. Safe for risky refactoring. |
| `ExitWorktree` | `action: "keep" or "remove"`, `discard_changes?` | Exits the worktree, optionally deleting all changes. |

### Scheduling & Loop Tools

| Tool | Key Inputs | Description |
| :--- | :--- | :--- |
| `CronCreate` | `cron`, `prompt`, `recurring?`, `durable?` | Creates a cron job that fires a prompt on a schedule. `durable: true` survives session restarts. |
| `CronDelete` | `id` | Deletes a cron job by its ID. |
| `CronList` | (none) | Lists all active cron jobs. |
| `ScheduleWakeup` | `delaySeconds`, `reason`, `prompt`, `stop?`, `noop?` | Schedules the agent to wake up and re-enter a loop. `noop: true` collapses consecutive idle ticks in the UI. |

### Workflow & Coordination Tools

| Tool | Key Inputs | Description |
| :--- | :--- | :--- |
| `Workflow` | `script?`, `name?`, `args?`, `scriptPath?`, `resumeFromRunId?` | Runs a JavaScript/TypeScript workflow script using a DSL (`agent()`, `parallel()`, `pipeline()`, `phase()`). Supports **checkpointing and resume** — completed steps are cached and skipped on re-run. |
| `Agent` | `description`, `prompt`, `subagent_type?`, `model?`, `run_in_background?`, `isolation?` | Spawns a subagent. `isolation: "worktree"` runs it on a temporary Git worktree. `isolation: "remote"` runs it in a cloud environment. |
| `SendMessage` | `to`, `message`, `notify_when_idle?` | Sends a message between sessions or agents. `notify_when_idle` subscribes to idle notifications. |
| `ListAgents` | (none) | Lists running agents on this machine. |

### Discovery & Search Tools

| Tool | Key Inputs | Description |
| :--- | :--- | :--- |
| `WebSearch` | `query`, `allowed_domains?`, `blocked_domains?` | Web search. |
| `WebFetch` | `url`, `prompt` | Fetches a URL and runs the prompt against its content. |
| `ToolSearch` | `query`, `max_results` | **Lazily discovers deferred tools** — tools not shown in the default list to save context. Use `select:<tool_name>` for direct selection. |

### Analysis Tools

| Tool | Key Inputs | Description |
| :--- | :--- | :--- |
| `Skill` | `skill`, `args?` | Invokes a named skill from `.claude/skills/`. |
| `ReportFindings` | `level?`, `findings[]` | Reports code review findings (used by security/code-review agent types). |
| `TaskOutput` | `task_id`, `block`, `timeout` | Gets stdout/stderr from a background task. |
| `TaskStop` | `task_id?` | Stops a background task or subagent. |

---

## 5. Terminal UI & Multi-Surface Architecture

### JSX-Like Declarative Rendering

Claude Code uses a JSX-like rendering model in its hook modules. Elements are not HTML — they're terminal-native primitives:

```typescript
on("ui.render", { component: "Pane" }, ($, e) => {
  const { Box, Text, Button, Input } = $.ui.resolve(e)

  return (
    <Box flexDirection="column" padding={1}>
      <Text bold color="cyan">Git Diff Viewer</Text>
      <Text dimColor>{hunks.length} changed files</Text>
      <Button key="refresh" onPress={() => void refresh()}>
        Refresh
      </Button>
    </Box>
  )
})
```

The element set varies by surface — `terminal` has `Box`, `Text`, `Button`, `Input`, `Raster`; `desktop` and `mobile` may have additional elements suited to those environments.

### Pane Split Layout

The `/diff` mod ([`mods/diff/hooks/register.ts`](mods/diff/hooks/register.ts)) implements this behavior:

- If the terminal has **≥ 144 columns**: the diff pane opens automatically beside the transcript (side-by-side layout).
- If the terminal has **≥ 110 columns** (after the user explicitly opens it): the pane is shown.
- Below that: no pane is attempted (too narrow).

```typescript
// From register.ts, simplified:
on("session.start", async ($, e, next) => {
  const result = await next(e)
  columns = e.columns

  if (columns >= 144 && !hasAutoOpened) {
    await $.ui.open({ id: "diff", title: "Changes", rows: AUTO_ROWS })
    hasAutoOpened = true
  }

  return result
})
```

### Live Blit (Raster Repaint)

For high-frequency UI updates (e.g. a terminal raster animation or a streaming progress bar) that don't need a full layout recompute:

```typescript
// Register a raster element
on("ui.render", { component: "Pane" }, ($, e) => {
  const { Raster } = $.ui.resolve(e)
  return <Raster key="terminal-output" columns={80} rows={24} />
})

// Later, repaint it at up to 120fps without triggering a React-like re-render
$.clock.every(33, () =>
  $.ui.blit({ requestId: paneId, key: "terminal-output", cells: renderFrame() })
)
```

---

## 6. The Plugin / Mod System

A plugin (also called a "mod" when shipped inside the binary) is a directory with:

```
my-plugin/
├── .claude-plugin/
│   └── plugin.json        ← manifest: name, tier, hooks entry, userConfig, types
├── hooks/
│   ├── hooks.json         ← declares the hooks module entry point
│   └── register.ts        ← the main hooks module (exported `register` function)
└── tests/
    └── register.test.ts   ← test file
```

### `plugin.json` Fields

| Field | Description |
| :--- | :--- |
| `name` | Unique plugin name (used as plugin ID in `$.plugin.name`) |
| `tier` | One of the 5 tiers (determines where in the onion it sits) |
| `hooks` | Relative path to the hooks module entry |
| `userConfig` | Schema for user-configurable settings that appear in `/config` |
| `types` | Path to a `.d.ts` file if this plugin extends `EngineInterface` with a new noun |

### The `register` Entrypoint

```typescript
// hooks/register.ts
import type { Register } from 'claude-code'

export const register: Register = (on, options) => {
  // options.config has the user's config values

  // Register event hooks here
  on("session.start", ($, e, next) => { /* ... */ return next(e) })
  on("tool.call", { tool: "Bash" }, ($, e, next) => { /* ... */ return next(e) })
  on("ui.render", { component: "Pane" }, ($, e) => { /* ... */ })
}
```

### Extending `$` with a New Noun

If your plugin wants to add `$.weather` to the engine interface:

```typescript
// types/index.d.ts
export type Weather = {
  current: (city: string) => Promise<{ tempC: number; condition: string }>
}

declare module 'claude-code' {
  interface EngineInterface { weather: Weather }
}
```

```typescript
// hooks/register.ts
on("engine.create", ($, e, next) => {
  const engine = await next(e)
  return {
    ...engine,
    weather: {
      current: async (city) => { /* fetch weather */ }
    }
  }
})
```

Other plugins can now call `$.weather.current("London")`.

---

## 7. Subagents & Workflow Orchestration

### Background Subagents

Subagents are isolated instances of the agent loop with their own:
- System prompt
- Tool policy (a subset of the parent's tools)
- Optional Git worktree isolation
- Optional remote cloud environment isolation

```typescript
// Agent definition (can be registered dynamically)
await $.agent.register({
  name: "typescript-reviewer",
  description: "Reviews TypeScript code for correctness and style",
  prompt: `You are an expert TypeScript code reviewer.
Review the provided file for:
1. Type safety issues
2. Unused imports
3. Dead code
4. Performance anti-patterns
Report each finding with file, line, summary, and a failure_scenario.`,
  tools: ["Read", "Bash"],    // Only these tools
  omitClaudeMd: true
})

// Spawn it
const { agentId } = await $.agent.spawn({
  subagentType: "typescript-reviewer",
  prompt: "Review src/api/handler.ts",
  description: "TS code review"
})
```

### Workflow DSL

The `Workflow` tool accepts a JavaScript/TypeScript script body using a special DSL:

```javascript
export const meta = {
  name: "full-stack-feature",
  description: "Plan, implement, test, and review a new feature",
  phases: ["plan", "implement", "test", "review"]
}

// Sequential phases
const plan = await agent({
  prompt: `Plan the feature: ${args.featureDescription}`,
  subagent_type: "architect"
})

// Parallel execution
const [backendResult, frontendResult] = await parallel([
  agent({ prompt: `Implement backend: ${plan.output}`, tools: ["Bash", "Write", "Edit"] }),
  agent({ prompt: `Implement frontend: ${plan.output}`, tools: ["Write", "Edit"] }),
])

// Pipeline (output of one feeds into next)
const reviewed = await pipeline([
  { prompt: "Run all tests and fix failures" },
  { prompt: "Security audit the new code" },
  { prompt: "Summarize all changes for the PR description" }
])
```

> [!TIP]
> Workflows support **resumable checkpointing** via `resumeFromRunId`. When you re-invoke the same workflow script after editing one `agent()` call, only the changed steps re-run — completed steps return their cached results instantly. This makes iterative refinement of long workflows very efficient.

### Worktree Isolation

```typescript
// Risky refactoring in an isolated worktree
const { agentId } = await $.agent.spawn({
  prompt: "Refactor all API handlers to use the new middleware pattern",
  isolation: "worktree",    // Creates a temporary git worktree
  description: "API refactor"
})

// The agent works on `tmp/worktree-<random>/` — a separate branch
// The main working tree is completely unaffected
// User can review with: git diff main..refactor/api-handlers
```

---

## 8. Context Management & Compaction

### Monitoring Token Budget

```typescript
on("prompt.submit", async ($, e, next) => {
  const { context } = await $.session.usage()

  if ((context.percent ?? 0) >= 85) {
    $.ui.toast("Context window is 85%+ full — compacting before this turn")
    await $.session.compact({
      instructions: "Preserve the current task goal and recent file changes"
    })
  }

  return next(e)
})
```

### What Compaction Does

The `session.compact` call triggers the same operation as the `/compact` slash command:
1. The model generates a **summary of the conversation so far**
2. The summary replaces the full conversation history in the context window
3. Recent critical messages can be preserved based on `instructions`
4. The transcript file on disk retains the full history; only the in-memory context is compacted

---

## 9. Architectural Weaknesses

Claude Code is brilliantly engineered, but it has real limitations worth understanding before deciding to build something better:

### Weakness 1: Node.js Runtime Overhead

- **Problem**: The binary bundles a Node.js runtime. Startup time is 800ms–2s cold, memory footprint is 150–300MB.
- **Impact**: Makes it feel "heavy" for quick one-off tasks. Subprocess PTY emulation on Windows requires extra shims and edge-case handling.

### Weakness 2: Anthropic Model Lock-In

- **Problem**: The session model, cache prefix sharing (`$.model.fork`), and credential system are architected around Anthropic's API contracts.
- **Impact**: Cannot transparently route to OpenAI `o3`, Gemini 2.5 Pro, or a local Llama model without significant re-engineering.

### Weakness 3: Lexical/Linear Context Retrieval

- **Problem**: The agent explores code using `Read`, `Bash`/`grep`, and natural-language pattern matching.
- **Impact**: No semantic understanding of call graphs, type definitions, or import trees. Finding where a function is called from requires either a `grep` command or asking the LLM to guess.

### Weakness 4: Post-Edit Error Discovery

- **Problem**: The `Edit` and `Write` tools apply changes directly to disk.
- **Impact**: Syntax errors, type errors, or test failures are discovered only after the file is written and a subsequent `Bash` command runs the compiler or tests. There is no pre-check sandbox.

### Weakness 5: Multi-Agent Coordination via Natural Language

- **Problem**: Subagent coordination is purely through natural language prompts and untyped outputs.
- **Impact**: Complex multi-agent workflows are fragile — agents may duplicate work, produce incompatible outputs, or fail silently without a typed state machine governing handoffs.

### Weakness 6: No Native Diff Review Interface

- **Problem**: The `/diff` pane shows a read-only view of changes. There is no interactive hunk staging (like `git add -p`) within the terminal UI itself.
- **Impact**: The developer must leave the Claude Code session to use `lazygit`, `git add -p`, or a GUI to cherry-pick specific changes.

---

## 10. Blueprint: Building a Better Terminal Agent

### Core Philosophy

The better terminal agent should:
1. **Start instantly** — no runtime cold-start, sub-20ms to first interactive prompt
2. **Understand code structurally** — not just as text, but as AST nodes, types, and call graphs
3. **Never corrupt the working tree** — use shadow execution for all edits before committing
4. **Route to any model** — be model-agnostic with consistent routing heuristics
5. **Coordinate agents with typed contracts** — not just free-text prompts

---

### Layer 1: Native Core Engine (Rust)

**Why Rust**: The same reason `codex-rs` exists. Rust gives you:
- Sub-millisecond startup (no VM, no GC warmup)
- < 15MB binary (single self-contained executable via `musl` static linking)
- First-class async I/O (`tokio`)
- Native PTY control (`portable-pty`) that works correctly on Windows, macOS, and Linux

#### Component: Terminal UI Layer

Use `ratatui` (previously `tui-rs`) + `crossterm` for cross-platform ANSI rendering:

```
┌─────────────────────────────────────┬──────────────────────────┐
│  Transcript Pane                    │  Live Diff Viewer        │
│                                     │                          │
│  User: Add pagination to the API    │  src/api/handler.rs      │
│                                     │  @@ -45,7 +45,12 @@     │
│  Agent: I'll add a `page` and       │  - pub async fn list()   │
│  `per_page` query parameter...      │  + pub async fn list(    │
│                                     │  +   page: u32,          │
│  [Tool: Edit src/api/handler.rs]    │  +   per_page: u32,      │
│  [Tool: Edit tests/api_test.rs]     │  +  ) -> Result<...> {   │
│  [Tool: Bash: cargo test]           │  [h] [j] [k] [a] [d]    │
├─────────────────────────────────────┴──────────────────────────┤
│  > _                                   [Ctrl+D Diff] [Ctrl+A Approve All]│
└────────────────────────────────────────────────────────────────┘
```

**Dual-Mode**:
- **Inline mode**: Pure streaming terminal output, works in any `$TERM`. No alternate screen.
- **TUI mode**: Full alternate-screen layout with interactive panes, triggered with a keypress.

---

### Layer 2: Model-Agnostic Routing Engine

The model router receives a `CompletionRequest` and dispatches to the appropriate provider:

```
CompletionRequest {
  tier: "fast" | "balanced" | "reasoning",
  messages: [...],
  tools: [...],
  max_tokens: usize
}
```

**Routing Table**:

| Tier | Default Model | Override |
| :--- | :--- | :--- |
| `fast` | Gemini 2.5 Flash / Claude Haiku | Ollama Phi-4 (offline) |
| `balanced` | Claude Sonnet 4.5 / GPT-4o | Any OpenAI-compatible API |
| `reasoning` | Claude Sonnet 4.5 Thinking / o3-mini | DeepSeek R1 via Ollama |

**Dynamic Selection Heuristic**:

```
Input: Task classification from fast model
  ┌─────────────────────────────────────────────────────────────┐
  │  is_simple_query (explain, list, describe)   → fast tier    │
  │  is_file_edit (targeted single-file change)  → balanced     │
  │  is_architecture (cross-cutting refactor)    → reasoning    │
  │  is_security_audit (vulnerability analysis)  → reasoning    │
  └─────────────────────────────────────────────────────────────┘
```

---

### Layer 3: Semantic Code Understanding (Tree-sitter + LSP)

This is the biggest architectural leap over Claude Code.

#### Tree-sitter Integration

Embed the `tree-sitter` library (available as a Rust crate) with grammars for:
- Rust, TypeScript/JavaScript, Python, Go, Java, C/C++, Ruby, Kotlin

This gives the agent structural awareness at **zero LLM token cost**:

```rust
// Example: Find all function definitions that call a specific function
let query = "(call_expression function: (identifier) @fn_name (#eq? @fn_name \"authenticate\"))";
let matches = tree_sitter_query(source_code, query);
// Returns: [{ file: "src/auth.rs", line: 47 }, { file: "src/api.rs", line: 123 }]
```

Use cases:
- **Symbol lookup**: "Where is `UserService` defined?" — answered in < 1ms
- **Call site finding**: "What calls `handleError`?" — answered by AST query, not grep
- **Structural diff**: Compare two ASTs to understand *what changed semantically*, not just textually

#### LSP Client Integration

Run language server daemons in the background (spawned lazily per language detected):

| Language Server | Language |
| :--- | :--- |
| `rust-analyzer` | Rust |
| `typescript-language-server` | TypeScript / JavaScript |
| `pyright` | Python |
| `gopls` | Go |
| `clangd` | C / C++ |

**After every edit, immediately query the LSP**:

```
Agent writes Edit(file="src/api.rs", ...)
→ LSP detects file change
→ LSP reports diagnostics within 200ms:
    ERROR src/api.rs:52 — expected type `String`, found `&str`
→ Diagnostic fed back into agent context
→ Agent self-corrects BEFORE the test suite runs
```

This cuts the feedback loop from "run tests, wait 30s, read failure" to "edit, wait 200ms, see type error, fix."

---

### Layer 4: Shadow Workspace (Copy-on-Write Execution)

Every agent edit passes through the shadow workspace before touching the real working tree.

#### Implementation Approach

**Option A — Git Index Overlay** (Simpler, Git-Repos Only):
```
1. Agent requests Edit("src/api.rs", old_str, new_str)
2. Engine applies edit to an in-memory copy
3. Engine writes to a hidden git ref: refs/shadow/current
4. LSP checks this hidden ref for diagnostics
5. Tests run against the shadow state
6. On success: git apply shadow → working tree
7. On failure: shadow is discarded, agent gets the error
```

**Option B — tmpfs CoW Overlay** (Any Directory):
```
1. Mount an overlayfs (Linux) or APFS CoW clone (macOS) over the project dir
2. All writes go to the upper layer (tmpfs)
3. Reads come from the lower layer (real files) unless shadowed
4. On success: rsync upper → lower (atomic rename where possible)
5. On failure: unmount upper layer, lower is pristine
```

**User Experience**:

```
Agent: I'll update the authentication handler.

[Shadow] Editing src/auth.ts... (LSP: 0 errors)
[Shadow] Editing tests/auth.test.ts... (LSP: 0 errors)
[Shadow] Running: npm test auth...
   ✓ login with valid credentials (45ms)
   ✓ reject expired token (12ms)
   ✓ rate limiting (103ms)

All 3 tests passed. Apply changes to disk? [Y/n]: _
```

---

### Layer 5: Typed Actor State Machine for Multi-Agent Coordination

Replace free-form subagent coordination with a **deterministic actor graph**:

```
                      ┌─────────────────┐
                      │   Orchestrator  │
                      │  (coordinates   │
                      │   the actors)   │
                      └────────┬────────┘
                               │
              ┌────────────────┼────────────────┐
              │                │                │
     ┌────────▼───────┐ ┌──────▼──────┐ ┌──────▼──────┐
     │   Planner       │ │   Executor  │ │  Verifier   │
     │                 │ │             │ │             │
     │ Input:          │ │ Input:      │ │ Input:      │
     │   user request  │ │   task_spec │ │   edit_set  │
     │ Output:         │ │ Output:     │ │ Output:     │
     │   task_spec     │ │   edit_set  │ │   verdict   │
     └────────────────┘ └─────────────┘ └─────────────┘
```

**Typed Contract Between Actors**:

```typescript
interface TaskSpec {
  goal: string
  affected_files: string[]
  phases: Phase[]
  constraints: string[]
  acceptance_criteria: string[]
}

interface EditSet {
  edits: { file: string; hunks: Hunk[] }[]
  commands_run: string[]
  test_results: TestResult[]
}

interface Verdict {
  passed: boolean
  failures: Failure[]
  coverage_delta: number
}
```

Each actor receives a **strongly-typed input** and returns a **strongly-typed output**. The orchestrator validates these contracts at each handoff — if the Planner returns a `TaskSpec` with `affected_files: []`, the orchestrator can immediately reject it and ask the Planner to retry with specific files.

---

### Layer 6: Interactive Diff Review & Hunk Staging

The final loop after agent work:

```
┌──────────────────────────────────────────────────────────────────┐
│  Changes ready for review (3 files, +127 / -43 lines)           │
│                                                                  │
│  [1/3] src/api/handler.rs (+89 / -31)                           │
│  ────────────────────────────────────────────────────────────── │
│  @@ -45,7 +45,18 @@ impl ApiHandler {                           │
│ -    pub async fn list_users(                                    │
│ +    pub async fn list_users(                                    │
│ +        page: Option<u32>,                                      │
│ +        per_page: Option<u32>,                                  │
│      db: &Database                                               │
│      ) -> Result<Vec<User>, ApiError> {                         │
│  ────────────────────────────────────────────────────────────── │
│  [a] Accept hunk  [d] Discard hunk  [n] Next  [p] Prev         │
│  [A] Accept all   [D] Discard all   [e] Edit hunk manually      │
│                                                                  │
│  Progress: ████████░░░░░░░░ 1/3 files  (47% applied)            │
└──────────────────────────────────────────────────────────────────┘
```

**Keybindings**:
- `a` / `d` — accept or discard the current hunk
- `n` / `p` — next / previous hunk
- `A` / `D` — accept or discard the entire current file
- `e` — open the hunk in `$EDITOR` for manual editing
- `Enter` — commit accepted hunks to disk and exit review

---

## 11. Implementation Roadmap

### Phase 1 — Native REPL & Tool Loop (Weeks 1–3)

**Goal**: A working terminal agent that can answer questions, read/edit files, and run commands.

Deliverables:
- Rust project with `tokio` async runtime
- Basic TUI with `ratatui` + `crossterm` (transcript pane + input box)
- LLM client for one model (Claude Sonnet via Anthropic SDK)
- Core tool implementations: `Read`, `Write`, `Edit`, `Bash` (with PTY via `portable-pty`)
- Streaming token output to the transcript

### Phase 2 — Middleware Pipeline (Weeks 4–5)

**Goal**: A configurable onion middleware system for hooks.

Deliverables:
- Event type system (enums for all tool calls, session events, UI events)
- Hook registry with 5-tier ordering
- `next()` chain-of-responsibility executor
- Built-in guardrails: read-only directories, command confirmation policy, path traversal prevention

### Phase 3 — Semantic Code Understanding (Weeks 6–8)

**Goal**: The agent understands code structure without burning tokens on naive grep.

Deliverables:
- Tree-sitter integration with grammars for Rust, TypeScript, Python
- Symbol index: definitions, references, call sites
- LSP client runner (manages lifecycle of `rust-analyzer`, `tsserver`, `pyright`)
- Post-edit diagnostic feedback loop (LSP error → agent context → self-correction)

### Phase 4 — Shadow Workspace (Weeks 9–10)

**Goal**: All agent edits are sandboxed before touching the real working tree.

Deliverables:
- Git index overlay for shadow execution
- Pre-commit validation pipeline (LSP diagnostics → build → targeted test run)
- Interactive diff review TUI (hunk-level accept/discard)
- Atomic commit to disk on user approval

### Phase 5 — Multi-Model Routing (Weeks 11–12)

**Goal**: Route intelligently across Anthropic, OpenAI, Google, and local Ollama models.

Deliverables:
- Unified `CompletionRequest` / `CompletionResponse` trait
- Provider adapters: Anthropic, OpenAI, Gemini, Ollama (OpenAI-compatible)
- Fast model call for intent classification
- Routing heuristic based on task complexity tier

### Phase 6 — Subagents & Typed Actors (Weeks 13–16)

**Goal**: Parallel multi-agent execution with typed handoffs.

Deliverables:
- Actor system with Planner / Executor / Verifier roles
- Typed `TaskSpec` → `EditSet` → `Verdict` contract chain
- Orchestrator that validates contracts and handles retry on failure
- Workflow DSL (similar to Claude Code's but with typed phase outputs)
- Agent inter-communication via typed message passing (not just free text)

### Phase 7 — MCP & Plugin System (Weeks 17–20)

**Goal**: Community extensibility via the standard Model Context Protocol.

Deliverables:
- MCP server client (connect to external tools via JSON-RPC)
- Plugin manifest format and loader
- Sandboxed plugin execution environment
- Built-in plugins: `git-status`, `project-navigator`, `test-runner`

---

## Summary: Claude Code vs. The Better Agent

| Dimension | Claude Code | Better Terminal Agent |
| :--- | :--- | :--- |
| **Runtime** | Node.js (150–300MB, 800ms startup) | Rust native (< 15MB, < 20ms startup) |
| **Code Understanding** | Text search (grep, Read) | Tree-sitter AST + LSP diagnostics |
| **Edit Safety** | Direct writes to disk | Shadow CoW workspace + LSP pre-check |
| **Model Support** | Anthropic-centric | Any model via unified router |
| **Plugin Security** | 5-tier onion middleware | Same (adopt this model) |
| **Multi-Agent** | NL-coordinated subagents | Typed actor FSM with contracts |
| **Diff Review** | Read-only pane | Interactive hunk staging (accept/discard) |
| **Scheduling** | CronCreate + ScheduleWakeup | Same (adopt this model) |
| **Context Management** | Token % monitor + /compact | Same + LSP-aware context pruning |

> [!TIP]
> You don't need to replace Claude Code — you can **extend** it using its plugin system. The hook API is powerful enough to add LSP-backed pre-edit validation, custom multi-agent workflows, and alternative model routing today, without rebuilding the engine from scratch. Save the native Rust rewrite for when you've validated the product concept.
