# How the Layers Work Together
## Memory, Context, Agent Architecture & Sandboxing — With Real Code

> All code in this document is pulled directly from the live source:
> - `resource/claude-code/mods/diff/hooks/register.ts` (the diff pane mod, 1013 lines)
> - `resource/claude-code/mods/types/claude-code.d.ts` (the engine type contract, 13,045 lines)
>
> Line numbers are exact and point to real declarations.

---

## Table of Contents

1. [The Lifecycle of a Single Session](#1-the-lifecycle-of-a-single-session)
2. [How Memory Works — Three Distinct Memory Systems](#2-how-memory-works--three-distinct-memory-systems)
3. [How the Context Window Works — Real Token Accounting](#3-how-the-context-window-works--real-token-accounting)
4. [How Compaction Works — The Real Code Path](#4-how-compaction-works--the-real-code-path)
5. [How the Onion Pipeline Executes — Step by Step](#5-how-the-onion-pipeline-executes--step-by-step)
6. [How Agent Architecture Works — Loops Within Loops](#6-how-agent-architecture-works--loops-within-loops)
7. [How Sandboxing Works — The Trust Boundary Model](#7-how-sandboxing-works--the-trust-boundary-model)
8. [How the diff Mod Wires All Layers Together](#8-how-the-diff-mod-wires-all-layers-together)
9. [Worked Example — "Add pagination to my API"](#9-worked-example--add-pagination-to-my-api)
10. [Key Architectural Insights](#10-key-architectural-insights)

---

## 1. The Lifecycle of a Single Session

Before looking at individual systems, understand what happens in order when you run `claude` in a terminal:

```
Phase 1 — Binary starts (Node.js runtime + bundled V8 snapshot)
    |
Phase 2 — engine.create FOLD runs (builds the $ object, once per load)
    All plugins run their engine.create hook, outermost-to-innermost.
    Each plugin receives what inner plugins built (post-order).
    |
Phase 3 — session.start EVENT fires
    Hooks register slash commands, load user preferences, probe git repos,
    check for CLAUDE.md / AGENTS.md files, set up timers.
    |
Phase 4 — Interactive REPL loop
    User types prompt -> prompt.submit event -> turn.start event
    -> model streams tokens -> model calls tools -> tool.call events
    -> results appended to transcript -> turn.complete event
    -> back to waiting for user input
    |
Phase 5 — session ends (/exit, Ctrl+C)
```

The key insight is that **Phases 2 and 3 are different**:

- **`engine.create`** = builds the kernel itself. `$` does not exist yet as a full object during this phase. Hooks here are constructors, not event handlers.
- **`session.start`** = the kernel exists. Hooks here initialize per-session state, register commands, and start timers.

From [`claude-code.d.ts` line 3193-3221]:

```typescript
// engine.create input — very simple, just the plugin list
export type EngineCreateInput = {
  plugins: readonly string[]  // all plugins in load order
}

// engine.create result — a partial EngineInterface to merge
export type EngineCreateResult = Partial<EngineInterface> & {
  readonly [noun: string]: unknown
}
```

A plugin that adds a new noun to `$` must do it in `engine.create`, NOT in `session.start`:

```typescript
// CORRECT: Adding $.weather in engine.create
on("engine.create", async (_, e, next) => {
  const built = await next(e)       // Let inner plugins build first
  return {
    ...built,                        // Preserve all inner plugins' nouns
    weather: {                       // Add our noun
      current: async (city: string) => {
        const res = await fetch(`/weather/${city}`).then(r => r.json())
        return res.text
      }
    }
  }
})

// WRONG: Trying to add $.weather in session.start
// At session.start, $ is sealed — you cannot add new nouns
on("session.start", ($, e, next) => {
  // $.weather is undefined here if not added in engine.create
  return next(e)
})
```

---

## 2. How Memory Works — Three Distinct Memory Systems

Claude Code has **three completely separate memory systems** that serve different purposes and have different lifetimes.

### Memory System 1: Plugin In-Process State (Ephemeral, Per-Session)

This is plain JavaScript/TypeScript module-level variables inside a plugin's `register()` function. They live only for the duration of the running process.

From [`register.ts` lines 45-73], the diff mod's in-process state:

```typescript
export function register(on: On) {
  // ---------- IN-PROCESS STATE -----------------------------------------------
  // These variables exist ONLY in this process's memory.
  // They are LOST when the session ends or the plugin hot-reloads.

  let host: Host | null = null           // The engine's API bridge
  let backend: Backend.Backend | null = null  // Git repository backend
  let probing: Promise<boolean> | null = null // In-flight git probe
  let sessionStartMs = 0                 // Session start timestamp (ms)
  let isPaneOpen = false                 // Is the diff pane visible?
  let dialogRows: number | null = null   // Rows allocated to the pane
  let hasAutoOpened = false              // Did we auto-open on first edit?
  let hasRestoredEdits = false           // Did this session have prior edits?
  let columns: number | null = null      // Terminal width
  let shownSessionId: string | null = null  // For telemetry deduplication
  let armed: Ask.ArmedAsk | null = null  // "Ask Claude about this diff" state
  let carrying: Ask.ArmedAsk | null = null  // Diff context being sent to model
  let isRefreshing = false               // Mutex: prevents concurrent refreshes
  let isRefreshQueued = false            // Refresh queued while one runs
  let generation = 0                    // Monotonic counter for cache invalidation
  let landed = 0                        // Total file edit count this session

  // A Map of in-flight body load promises (keyed by file path)
  const bodyLoads = new Map<string, Promise<Git.FileHunks | null>>()

  // Polled state (git HEAD key for detecting commits mid-session)
  const polled = { toplevel: '', headKey: '' }
  // "Pin" state — the locked working directory for this backend
  const pin = { cwd: '', isEmpty: false, epoch: 0 }

  // The pane's model state — all rendering is derived from this single object
  let model: PaneState.PaneModel = PaneState.INITIAL_MODEL

  // Cancellable timers (debounce, polling)
  const timers = new Map<'refresh' | 'redraw' | 'poll', Timer>()
  // ---------- END IN-PROCESS STATE -------------------------------------------
```

**Critical rules for in-process state:**
1. A hot-reload (engine reloads your plugin while the session runs) **wipes all closured state** and re-runs `register()` from scratch.
2. All async timers (`$.clock.after`, `$.clock.every`) that reference these variables are cancelled on reload.
3. State is **per plugin instance** — two plugins cannot see each other's closured variables.

### Memory System 2: The Plugin Key-Value Store (Persistent, Cross-Session)

The `$.store` API persists state across sessions, reloads, and binary updates. It is backed by a JSON file on disk under the user's Claude Code config directory.

From [`register.ts` lines 472-476], reading a user preference from the store:

```typescript
async function openOnFirstEdit(engine: Host): Promise<void> {
  // Read a boolean preference: should the diff pane auto-open?
  // This survived the last session — it is from the previous run.
  const preference = await engine.storeGet(Names.STORE_OPEN_KEY)
  const isKeptOpen = preference === true

  const floor = isKeptOpen
    ? Limits.OPEN_MIN_COLUMNS       // 110 — if user explicitly opened it before
    : Limits.AUTO_OPEN_MIN_COLUMNS  // 144 — for the first auto-open
```

From [`register.ts` lines 787-788], writing a preference to the store:

```typescript
// User toggled the diff panel. Persist their preference so
// the next session knows whether to auto-open.
await host.storeSet(Names.STORE_OPEN_KEY, isOpening).catch(() => undefined)
```

From [`register.ts` lines 153-166], reading and applying a stored git diff base mode:

```typescript
// Each git repository has its own "base mode" preference stored separately.
// The key is derived from the repository's root path.
const stored = PaneState.baseModeOf(
  await engine
    .storeGet(Names.baseStoreKeyOf(probed.repository.toplevel))
    .catch(() => undefined),
)

const mode = stored && probed.baseModes.includes(stored) ? stored : null

model = {
  ...model,
  words: probed.words,
  baseModes: probed.baseModes,
  ...(mode && { requestedMode: mode }),  // Only apply if stored mode is still valid
}
```

**Store constraints** (from `claude-code.d.ts`):
- Values must be JSON-serializable (no functions, no cycles, no `Date` objects — `Date` is serialized as ISO string)
- Maximum store size: **4 MiB** total JSON text across all keys
- `set` is async — writes go through the engine host, not directly to disk

### Memory System 3: The Conversation Transcript (The Model's Memory)

This is the LLM's actual "memory" — the sequence of user/assistant message pairs that forms the prompt context.

From [`claude-code.d.ts` lines 8820-8848]:

```typescript
// One message in the conversation transcript
export type SessionMessage = {
  role: 'user' | 'assistant'

  // All text blocks from this message, joined into one string
  text: string

  // Tool calls the assistant made in this message
  toolUses: ToolUseSummary[]

  // Tool results the user message carries (responses to assistant tool calls)
  toolResults?: ToolResultSummary[]

  // Opaque token used during compaction — only present in session.compact hooks
  handle?: string
}
```

The diff mod reads the transcript in [`register.ts` lines 508-515] to detect if a resumed session already has edits:

```typescript
async function openOnRestore(engine: Host): Promise<void> {
  // Read the FULL session transcript from the engine
  const messages = await engine.messages().catch((): SessionMessage[] => [])

  // Parse tool call results to find any Edit/Write tool calls in prior turns
  // If the resumed session already has file edits, show the diff pane
  hasRestoredEdits = Turns.turnDiffsOf(messages).length > 0

  if (hasRestoredEdits) {
    await openOnFirstEdit(engine)
  }
}
```

Also in [`register.ts` lines 336-341], the refresh function reads the transcript alongside git diff data:

```typescript
// Always read transcript and git diff together — atomically with Promise.all
const [outcome, messages] = await Promise.all([
  fetched(),                                           // git diff data
  engine.messages().catch((): SessionMessage[] => [])  // conversation history
])

// The pane model needs BOTH pieces: git diff data AND session transcript,
// because the pane can show diffs per-turn (which edit happened in which turn)
model = PaneState.afterFetch(model, { outcome, messages })
```

### Memory System Summary

| System | Lifetime | Where Stored | Max Size | Access API |
|--------|----------|--------------|----------|------------|
| In-Process State | Current process only | RAM | Unlimited (GC) | Closured `let` variables |
| KV Store | Persistent across sessions | JSON file on disk | 4 MiB total | `$.store.get/set()` |
| Conversation Transcript | One session (disk backup exists) | RAM + jsonl on disk | 4096 messages | `$.session.messages()` |

---

## 3. How the Context Window Works — Real Token Accounting

The context window is the fundamental resource the LLM operates within. Claude Code tracks it in real time.

From [`claude-code.d.ts` lines 1790-1818], the API usage structure:

```typescript
// Reported by the Anthropic API on every response
export type ContextApiUsage = {
  input_tokens: number                // Uncached tokens sent this request
  output_tokens: number               // Tokens generated by the model
  cache_creation_input_tokens: number // Tokens WRITTEN to the prompt cache
  cache_read_input_tokens: number     // Tokens READ from the prompt cache (free)
}
```

The context breakdown is split into **categories** from [`claude-code.d.ts` line 1824]:

```typescript
export type ContextCategory = {
  name: string        // "System prompt", "Messages", "Free space", etc.
  tokens: number      // Estimated token count for this category
  color: string       // Color key for /context visualization
  isDeferred: boolean // Is this a lazily-loaded tool schema?
  kind: ContextCategoryKind
}
```

You can get both a fast estimate and a precise count:

```typescript
// FAST: Uses last API response's usage numbers + local estimation
// No API call needed, essentially free
const fastUsage = await $.session.usage()
// Returns: { context: { percent: 47 }, rateLimits: [...], cost: {...} }

// PRECISE: Sends one token-count API request per category
// Takes ~500ms, costs a small amount
const detailedUsage = await $.session.usage({ breakdown: "full" })
// Returns: { context: { percent: 47, breakdown: [{ name: "System prompt", tokens: 2847 }, ...] } }

// ESTIMATE: Local estimation without API calls, slightly less accurate
const estimatedUsage = await $.session.usage({ breakdown: "summary" })
```

**The "deferred" tools optimization**: Tool schemas consume context tokens. Claude Code implements a `ToolSearch` tool that keeps rarely-used tools hidden from the context window:

```typescript
// ContextCategory.isDeferred = true means this tool's schema is NOT
// currently loaded in the context window. It stays hidden until the
// model calls ToolSearch to find it.
//
// This is how the context window can support 200+ tools without token bloat.
// Only the tools actively being used burn context tokens.
```

From [`claude-code.d.ts` line 1818]:

```typescript
// Two modes for counting context:
export type ContextBreakdownDetail = 'summary' | 'full'
//   'summary' = estimate locally, no API call
//   'full'    = send token-count API request per category (what /context does)
```

---

## 4. How Compaction Works — The Real Code Path

Compaction "resets" the context window without ending the session.

From [`claude-code.d.ts` lines 8489-8543]:

```typescript
// What fires when /compact runs (or auto-compact triggers)
export type SessionCompactInput = {
  // Who triggered this:
  //   'manual'     = user typed /compact
  //   'auto'       = engine hit its threshold (~85% full)
  //   'plugin'     = plugin called $.session.compact()
  //   'precompute' = engine pre-computed a summary speculatively
  trigger: SessionCompactTrigger

  // For subagent compaction — the subagent's loop id
  agentId?: string

  // Custom instructions for the summarizer
  instructions?: string

  // The FULL transcript being compacted
  // Each message carries an opaque 'handle' so the engine can correlate
  // a hook's modified message back to the original
  messages: readonly SessionMessage[]
}

// What compaction produces
export type SessionCompactResult = SessionCompacted | SessionCompactSkipped

export type SessionCompacted = {
  // The NEW conversation after compaction.
  // Typically 2-5 messages:
  //   [0] user turn: "The following is a summary of the conversation..."
  //   [1] assistant: "<the actual summary>"
  //   [2..n] the last few full messages preserved verbatim
  messages: readonly SessionMessage[]

  tokensBefore?: number  // Tokens before compaction (telemetry)
  tokensAfter?: number   // Tokens after compaction
}

// A hook can VETO compaction:
export type SessionCompactSkipped = {
  skip: string  // Reason shown to user in the transcript
}
```

**The precompute optimization**: The engine often runs `session.compact` speculatively (`trigger: 'precompute'`) before the context is actually full. This means the summary is already computed when compaction is needed — zero latency spike at the critical moment.

A plugin can intercept and customize the compaction:

```typescript
// Intercept compaction to preserve specific context
on("session.compact", async ($, e, next) => {

  // Veto the auto-compact if we are mid-task
  if (e.trigger === 'auto' && isTaskCritical) {
    return { skip: "mid-task: will compact after current subtask completes" }
  }

  // Inject custom instructions into the summarizer
  const result = await next({
    ...e,
    instructions: e.instructions
      ? `${e.instructions}. Also preserve the list of files already edited.`
      : "Preserve the list of files already edited."
  })

  return result
})

// Block precompute entirely (e.g. for a session that should never compact)
on("session.compact", { trigger: "precompute" }, () => ({ skip: "off" }))
```

**What happens to the disk transcript**: Compaction only replaces the **in-memory context window**. The full transcript file on disk (under `~/.claude/projects/`) retains every message ever sent. The `/resume` command can re-hydrate from the disk file.

---

## 5. How the Onion Pipeline Executes — Step by Step

Let's trace a single `tool.call` event through the entire 5-tier pipeline.

### The Call That Triggers It

The LLM decides to call `Bash` with `command: "npm test"`. This creates a `tool.call` event.

### Step-by-Step Execution

```
TIER: prepend (outermost — org security)
  Hook: "block dangerous commands"
  Input: { tool: "Bash", command: "npm test" }
  Action: checks against deny-list -> not blocked
  Calls: next(e)

TIER: user (developer-installed plugins)
  Hook A: "log all tool calls to my audit system"
  Action: logs to external API -> calls next(e)

  Hook B: "auto-inject --coverage flag to test commands"
  Input: { tool: "Bash", command: "npm test" }
  Action: modifies input -> calls next({ ...e, command: "npm test --coverage" })

TIER: append (org post-filters)
  (no hooks registered for tool.call in this example — passes through)

TIER: builtin (the diff mod)
  Hook: register.ts lines 947-963 — the diff mod's tool.call hook
  Action: calls next(e) first, then processes the RESULT afterward

TIER: core (the engine's own implementation)
  Action: runs tool.check event (permission system)
  Action: shows confirmation dialog if needed (in "ask" mode)
  Action: forks a child process, runs "npm test --coverage"
  Action: waits for exit, reads stdout/stderr
  Returns: { result: { exitCode: 0, stdout: "...", stderr: "" } }

Back in TIER: builtin (diff mod, AFTER next resolves)
  afterTool runs (register.ts lines 917-944)
  Returns: the result unchanged (passthrough)

Back in TIER: user (Hook B)
  No post-processing needed
  Returns: result unchanged

Back in TIER: user (Hook A, logging)
  Logs the result to the audit system
  Returns: result unchanged

Back in TIER: prepend
  No post-processing
  Returns: result to core's tool dispatch system
```

### The Real Hook from register.ts

```typescript
// register.ts lines 947-963 — the diff mod's tool.call hook
on(
  'tool.call',
  // Pattern: only intercept file-editing and shell tools
  { tool: [...Tools.EDITING_TOOLS, ...Tools.SHELL_TOOLS] },
  async ($, e, next) => {
    let result: ResultOf['tool.call'] | undefined

    try {
      result = await next(e)  // Execute the tool (everything beneath us)
      return result
    } finally {
      // ALWAYS run afterTool, even if next throws
      // The `finally` block is what makes this reliable
      if (host) {
        afterTool(host, e, result)
      }
    }
  },
)
```

The `finally` block is architecturally important — it runs even if the tool fails, times out, or is aborted. This is how the diff pane always knows about edits even when tools error out.

### The Debounce + Mutex Refresh Chain

When `afterTool` calls `scheduleRefresh`, it does not refresh immediately. From [`register.ts` lines 391-401]:

```typescript
function scheduleRefresh(engine: Host): void {
  // Cancel any pending refresh timer (debounce)
  timers.get('refresh')?.cancel()

  // Schedule a new refresh 150ms from now
  // If more edits land in that window, the timer resets again
  timers.set(
    'refresh',
    engine.after(Limits.REFRESH_DEBOUNCE_MS, () => {
      timers.delete('refresh')
      void refresh(engine)  // Actually run the refresh
    }),
  )
}
```

And refresh is guarded by a mutex from [`register.ts` lines 316-388]:

```typescript
async function refresh(engine: Host): Promise<void> {
  if (isRefreshing) {
    // Don't run two refreshes simultaneously — queue one instead
    isRefreshQueued = true
    return
  }

  isRefreshing = true  // Acquire mutex

  try {
    model = { ...model, isLoading: model.data === null }

    // ATOMIC: Fetch git diff AND session transcript simultaneously
    const [outcome, messages] = await Promise.all([
      fetched(),                                           // git diff
      engine.messages().catch((): SessionMessage[] => [])  // transcript
    ])

    model = PaneState.afterFetch(model, { outcome, messages })

    const hasHunksFailed = await loadBodies(engine)

  } finally {
    isRefreshing = false  // Release mutex
    redraw(engine)        // Trigger a UI re-render

    if (isRefreshQueued) {
      isRefreshQueued = false
      scheduleRefresh(engine)  // Run the queued refresh
    }
  }
}
```

---

## 6. How Agent Architecture Works — Loops Within Loops

### The Agent Loop Concept

Every LLM "agent" in Claude Code is a **loop** — a process that repeatedly:
1. Receives a prompt (user input or programmatic)
2. Sends it to the model
3. Executes any tool calls the model makes
4. Loops back to the model with the tool results

The **main loop** is what runs when you type prompts interactively. **Subagents** are additional loops running in parallel or sequence.

From [`claude-code.d.ts` lines 114-153]:

```typescript
// Every agent loop — main or sub — has this identity
export type AgentInfo = {
  id: string         // Unique loop ID (used in tool.call's `agentId` field)
  description: string  // What this agent is doing ("Reviewing auth.ts")
  type: string       // "general-purpose", "Explore", "typescript-reviewer", etc.
  status: string     // "running", "completed", "failed", "killed"
  parentId?: string  // ID of the loop that spawned this one
  spawnedBy?: string // Which plugin started it (for origin tracking)
  name?: string      // Optional name for SendMessage addressing
}
```

From [`claude-code.d.ts` lines 156-170], how events know which loop they are in:

```typescript
// EVERY event carries which loop dispatched it
export type AgentLoop = {
  // The ID of the loop this event happened in.
  // ABSENT (undefined) on the main loop.
  // PRESENT on any subagent loop.
  agentId?: string
}
```

This is how the diff mod distinguishes main-loop edits from subagent edits:

```typescript
// register.ts lines 940-944
const isMainLoopEdit = hasEdited && e.agentId === undefined

if (isMainLoopEdit) {
  // Auto-open the diff pane only when the MAIN LOOP edits a file.
  // Don't auto-open for background subagent edits — that would be disruptive.
  void openOnFirstEdit(engine).catch(() => undefined)
}
```

### Spawning a Subagent — The Full Event Chain

When your code calls `$.agent.spawn({ prompt: "Review auth.ts" })`, this is what fires:

```
1. agent.spawn event fires through ALL tiers (outermost to innermost)

   A prepend hook might: deny spawning if already at max concurrency
   A user hook might: attach additional system prompt instructions
   Core: creates the agent loop record, assigns an agentId, starts the loop

2. Agent loop starts in the BACKGROUND
   The parent loop continues immediately (if run_in_background: true)

3. Inside the subagent's loop:
   - Has its OWN event dispatch pipeline — same 5 tiers
   - tool.call events in the subagent carry { agentId: "agent-abc123" }
   - All 5 tiers still run in the subagent — security, user plugins, etc.
   - The subagent CAN spawn its own subagents (nested trees supported)

4. turn.complete fires when the subagent finishes
   The parent can match by agentId to collect results
```

### Worktree Isolation — Real File System Separation

When `isolation: "worktree"` is used, the engine runs:

```bash
# Internally (simplified):
git worktree add /tmp/claude-wt-abc123 -b claude/auth-refactor
# Creates a complete copy of the repo on a NEW BRANCH
# The main working tree is completely untouched
```

The subagent's `$.process.run()` and `$.fs.*` calls all operate with:
```
cwd = /tmp/claude-wt-abc123/
```

It can never touch your real working tree. When the agent finishes:
```bash
git diff main..claude/auth-refactor    # Review all changes
git merge claude/auth-refactor         # Merge if satisfied
git worktree remove /tmp/claude-wt-abc123  # Cleanup
```

### Workflow Orchestration — How Parallel Agents Coordinate

The `Workflow` tool accepts a JS script using a coordination DSL:

```typescript
export const meta = {
  name: "feature-impl",
  description: "Implement a complete feature with tests and review",
  phases: ["design", "implement", "test", "review"]
}

// Phase 1: Design — sequential, must finish before coding starts
const design = await agent({
  prompt: `Design the API surface for: ${args.feature}`,
  subagent_type: "architect"
})

// Phase 2: Implementation — parallel backend and frontend
// Both agents run simultaneously, in separate loops and worktrees
const [backend, frontend] = await parallel([
  agent({
    prompt: `Implement backend endpoints: ${design.output}`,
    tools: ["Write", "Edit", "Bash"],
    isolation: "worktree"    // Each gets its own isolated worktree
  }),
  agent({
    prompt: `Implement frontend components: ${design.output}`,
    tools: ["Write", "Edit"],
    isolation: "worktree"
  })
])

// Phase 3: Test — uses the results from both parallel agents
const tests = await agent({
  prompt: `Write integration tests.
Backend output: ${backend.output}
Frontend output: ${frontend.output}`
})
```

**Checkpoint and Resume**: If the workflow is interrupted, `resumeFromRunId` replays it:

```typescript
// First run
const { runId } = await $.tool.call({ tool: "Workflow", script: WORKFLOW_SCRIPT })

// After interruption — edit the script, then resume
// Completed phases return their cached results instantly
// Only changed or failed phases re-execute
await $.tool.call({
  tool: "Workflow",
  scriptPath: ".claude/workflows/feature-impl.js",
  resumeFromRunId: runId
})
```

---

## 7. How Sandboxing Works — The Trust Boundary Model

Sandboxing in Claude Code is **layered**, not a single on/off switch. There are four distinct trust boundaries.

### Layer A: The Plugin Runtime Sandbox

Plugins run in a **separate JavaScript module environment** from the engine core:

- Cannot `require()` or `import` Node built-ins directly
- Cannot access the DOM (there is none in this environment)
- Cannot access `process.env` directly — must go through `$.env.get()`
- Cannot read or write files directly — must use `$.fs.*`
- Cannot spawn processes directly — must use `$.process.run()`

From the engine type header ([`claude-code.d.ts` lines 14-21]):

```
The module, and every file it imports from the plugin, is named
.ts, .tsx, .jsx, .js, .mjs, .cjs, .mts or .cts (a file named otherwise
is not loaded) and is an ES module whatever its suffix: there is no
`require`.
```

All capability access is **mediated through the `$` API**, which means the engine controls what every plugin can and cannot do.

### Layer B: The Tool Permission System

Every `tool.call` event passes through a `tool.check` permission decision before the tool runs:

```typescript
// A tool.check hook can return:
// { decision: "allow" }  — permit immediately, no dialog
// { decision: "deny" }   — refuse, show error
// { decision: "ask" }    — show the approval dialog to the user
```

From [`register.ts` line 492], the diff mod reads settings before auto-opening:

```typescript
// Check if file checkpointing is enabled before auto-opening
// This reads the ACTUAL settings files, not just in-memory state
const isCheckpointed = await engine.isCheckpointing().catch(() => true)

// isCheckpointing reads from two sources simultaneously:
// 1. The merged settings.json (all settings sources combined)
// 2. The environment variable CLAUDE_CODE_DISABLE_FILE_CHECKPOINTING
```

### Layer C: The 5-Tier Deny System

Any tier can refuse a tool call. Here is how layered policies compose:

```typescript
// Tier 1 (prepend) — Organization policy: no writes outside project root
on("tool.call", { tool: "Write" }, async ($, e, next) => {
  const stat = await $.fs.stat(e.file_path, { resolve: true }).catch(() => undefined)
  const real = stat?.realPath
  const projectRoot = await $.session.root()

  if (real === undefined || !real.startsWith(projectRoot + "/")) {
    return { deny: "Policy: writes must stay inside the project root" }
  }
  return next(e)
})

// Tier 2 (user) — User plugin: no writes to secret files
on("tool.call", { tool: "Write" }, async ($, e, next) => {
  if (e.file_path.endsWith(".env") || e.file_path.endsWith("secrets.json")) {
    return { deny: "Refusing writes to secrets files" }
  }
  return next(e)
})

// Even if BOTH policies pass, the engine's own permission mode
// (auto/ask/manual) is applied at the core tier.
// In "ask" mode, the user still sees the dialog regardless.
```

### Layer D: The fs.stat Symlink-Safe Path Resolution

The most subtle sandboxing is path resolution. From [`claude-code.d.ts` lines 2782-2816], the full safe-write guard pattern:

```typescript
// For reading existing files — resolve the real path, follow symlinks
on("tool.call", { tool: "Read" }, async ($, e, next) => {
  const stat = await $.fs.stat(e.file_path, { resolve: true })
    .catch(() => undefined)

  const real = stat?.realPath  // The ACTUAL path after symlink resolution

  // The guard: real path must be inside the project root
  const isInside = real !== undefined && real.startsWith(ROOT + SEP)

  return isInside ? next(e) : { deny: "outside the project" }
})
```

For write operations to files that do not exist yet, the parent directory is checked instead:

```typescript
// For new files — stat the parent directory since the file does not exist yet
const placed = async (path) => {
  const cut = Math.max(path.lastIndexOf("/"), path.lastIndexOf("\\"))
  const name = path.slice(cut + 1)

  // First: is this even a placeable path spelling?
  const isPlaceable =
    !/^[A-Za-z]:(?![\\\/])/.test(path) &&  // Not drive-relative (D:x)
    !/^[\\\/][\\\/]/.test(path) &&          // Not UNC path (\\server)
    !/^[A-Za-z]:/.test(name) &&            // Name not a drive letter
    name !== "" && name !== "." && name !== ".."

  if (!isPlaceable) return undefined

  // Try to stat the file itself first
  const own = await $.fs.stat(path, { resolve: true }).catch(() => undefined)
  if (own) return own.realPath

  // File doesn't exist — stat the parent directory instead
  const folder = cut < 0 ? "." : path.slice(0, cut + 1)
  const dir = await $.fs.stat(folder, { resolve: true }).catch(() => undefined)

  return dir?.realPath === undefined
    ? undefined
    : `${dir.realPath.replace(/[\\\/]$/, "")}${SEP}${name}`
}

const real = await placed(e.file_path)
const isInside = real !== undefined && real.startsWith(ROOT + SEP)
return isInside ? next(e) : { deny: "cannot place it, or outside project" }
```

This guard prevents:
- **Symlink escapes**: `ln -s /etc project/etc` then `Write project/etc/passwd`
- **Path traversal**: `Write project/../../etc/passwd`
- **UNC path abuse** (Windows): `Write \\server\share\malicious.exe`
- **Drive-relative paths** (Windows): `Write C:malicious.bat`

---

## 8. How the diff Mod Wires All Layers Together

The diff mod is the best example of how all systems integrate in a real, shipping plugin. Let's trace what happens when Claude edits your first file in a session.

### The session.start Hook — Wiring the Host

From [`register.ts` lines 644-686], the diff mod builds its `Host` abstraction from the `$` kernel:

```typescript
on('session.start', async ($, e, next) => {
  await bind(
    {
      // EVERY capability is explicitly threaded from $.
      // This is the trust boundary: bind() only gets what $ provides.
      now:               () => $.clock.now(),
      after:             (ms, fn) => $.clock.after(ms, fn),
      every:             (ms, fn) => $.clock.every(ms, fn),
      run:               (argv, init) => $.process.run(argv, init),
      stat:              path => $.fs.stat(path),
      listDir:           path => $.fs.list(path),
      readFile:          path => $.fs.read(path),
      storeGet:          key => $.store.get(key),
      storeSet:          (key, value) => $.store.set(key, value),
      messages:          () => $.session.messages(),
      invalidate:        () => $.ui.invalidate('ui.render'),
      status:            text => $.ui.status(text),
      uiLog:             text => $.ui.log(text),
      openPane:          pane => $.ui.open(pane),
      closePane:         pane => $.ui.close(pane),
      registerCommand:   spec => $.command.register(spec),
      sessionId:         () => $.session.id(),
      isCheckpointing:   async () => isCheckpointing(
                           await $.settings.read(),
                           await $.env.get('CLAUDE_CODE_DISABLE_FILE_CHECKPOINTING'),
                         ),
      mark:              entry => $.telemetry.mark(entry),
      log:               entry => $.telemetry.log(entry),
    },
    e.cwd,
  )

  if (host) {
    void openOnRestore(host).catch(() => undefined)
  }

  return next(e)
})
```

The `bind()` function stores all these function references in the `host` in-process variable. From this point on, every other function in the mod calls `host.xxx()` instead of `$.xxx()`. This is both a design pattern (separating the kernel binding from the business logic) and a testability technique (in tests, you inject a mock `host`).

### The tool.call Hook — Detecting Edits

From [`register.ts` lines 917-963], how the mod detects that files changed:

```typescript
function afterTool(
  engine: Host,
  e: Args<'tool.call'>,
  result: ResultOf['tool.call'] | undefined,
) {
  // Is this one of: Edit, Write, NotebookEdit, MultiEdit?
  const isEdit = Tools.EDITING_TOOLS.some(name => name === e.tool)

  const hasEdited =
    isEdit &&
    result !== undefined &&
    result.deny === undefined &&   // Not denied by a hook
    result.isError !== true        // Tool did not return an error

  // For shell tools (Bash/PowerShell): heuristic — did this PROBABLY write?
  const hasLanded = isEdit ? hasEdited : Tools.mayHaveWritten(result)

  if (hasLanded) {
    landed += 1  // Track total edits this session (in-process memory)
  }

  if (hasLanded && isPaneOpen) {
    scheduleRefresh(engine)  // Update pane if it is already open
  }

  // Only main loop edits trigger auto-open
  // agentId is undefined on the main loop, present on subagents
  const isMainLoopEdit = hasEdited && e.agentId === undefined

  if (isMainLoopEdit) {
    void openOnFirstEdit(engine).catch(() => undefined)
  }
}

// The hook itself
on(
  'tool.call',
  { tool: [...Tools.EDITING_TOOLS, ...Tools.SHELL_TOOLS] },
  async ($, e, next) => {
    let result: ResultOf['tool.call'] | undefined

    try {
      result = await next(e)
      return result
    } finally {
      if (host) afterTool(host, e, result)
    }
  },
)
```

### The prompt.submit Hook — Injecting Diff Context

From [`register.ts` lines 965-1011], how diff context rides the next user prompt:

```typescript
on('prompt.submit', async ($, e, next) => {
  const asked = armed  // A specific file's diff that the user "armed"

  if (!host || !asked || carrying === asked) {
    return next(e)
  }

  const context = e.context ?? []

  // Build the diff text, respecting a character budget
  const text = Ask.fittedAskTextOf(
    asked.text,
    Limits.PROMPT_CONTEXT_MAX_CHARS -
      context.reduce((sum, entry) => sum + entry.length, 0),
  )

  if (text === undefined) {
    disarm(host)
    host.status(`${asked.path}'s diff did not fit in the prompt and was dropped`)
    return next(e)
  }

  carrying = asked

  try {
    // INJECT: pass the modified event to next with the diff appended
    const result = await next({
      ...e,
      context: [...context, text]  // <-- the diff text goes in here
    })

    if (result.drop === undefined) {
      Record.recorderOf(host).asked()

      if (armed === asked) {
        disarm(host)
        redraw(host)
      }
    }

    return result
  } finally {
    carrying = null
  }
})
```

---

## 9. Worked Example — "Add pagination to my API"

Let's put it all together with a complete realistic example showing every system at every step.

### Session State Before the Prompt

```
In-Process Memory (ephemeral):
  host          = <Host object>
  backend       = <GitBackend @ /projects/myapp>
  isPaneOpen    = false
  columns       = 200   (wide terminal)
  landed        = 0
  model.data    = null  (no diff loaded yet)

Store Memory (persistent from last session):
  "diff:open"          = true    (user kept pane open last time)
  "diff:base:myapp"    = "main"  (user prefers diff against main branch)

Transcript / Model Memory:
  []   (fresh session — empty)

Context Window: 12% full
  - System prompt (from CLAUDE.md)
  - Tool schemas for 8 active tools
```

### Step 1 — User Prompt

```
User types: "Add pagination to the users endpoint in src/api/users.rs"

prompt.submit event fires:
  armed diff? No -> next(e) called unchanged

Session turn starts.
Transcript now:
  [{ role: "user", text: "Add pagination..." }]

Context Window: 15% full (prompt tokens added)
```

### Step 2 — Model Reads Files

```
Model responds: "I'll add pagination parameters to the users endpoint."

Model calls tools:
  1. Read { file_path: "src/api/users.rs" }
  2. Read { file_path: "src/models/pagination.rs" }

For each tool.call:
  Prepend tier:  path check -> inside project -> allow
  Diff mod tier: Read is NOT in EDITING_TOOLS -> skips afterTool
  Core:          reads file, returns content

Context Window: 38% full (two large files now in context)
```

### Step 3 — Model Makes the Edit

```
Model calls:
  Edit {
    file_path: "src/api/users.rs",
    old_string: "pub async fn list_users(db: &Database) -> Vec<User>",
    new_string: "pub async fn list_users(
      db: &Database,
      page: Option<u32>,
      per_page: Option<u32>,
    ) -> PaginatedResult<User>"
  }

tool.call fires:

DIFF MOD (lines 947-963):
  result = await next(e)      <- Edit tool runs at this point

  CORE EXECUTES:
    tool.check: Edit allowed (auto permission mode)
    Writes file to disk
    Returns { result: { filePath: "src/api/users.rs" } }

  afterTool runs (always, via finally):
    isEdit    = true
    hasEdited = true  (no deny, no isError)
    landed    = 1     (in-process counter incremented)

    isPaneOpen = false -> no scheduleRefresh yet
    isMainLoopEdit = true  (agentId = undefined)
    -> openOnFirstEdit(engine) called
```

### Step 4 — Diff Pane Auto-Opens

```
openOnFirstEdit runs:
  isTaken() = false  (isPaneOpen=false, hasAutoOpened=false)

  STORE READ: "diff:open" = true -> isKeptOpen = true
  floor = 110 columns  (lower threshold: user previously opened it)
  columns = 200 -> hasRoom = true

  SETTINGS READ: isCheckpointed = true

  PROBE GIT BACKEND:
    $.process.run(["git", "rev-parse", "--show-toplevel"])
      -> "/projects/myapp"
    $.process.run(["git", "status", "--short"]) -> ...
    backend = GitBackend { repository: { toplevel: "/projects/myapp" } }

  STORE READ: "diff:base:myapp" = "main" -> requestedMode = "main"

  openPane(engine, 'auto_open'):
    $.ui.open({ id: "diff", title: "Changes", holdToasts: true })
    -> UI system creates the split pane in the terminal
    -> isPaneOpen = true

    refresh(engine) runs:
      Promise.all([
        git diff main...HEAD --unified=3  -> { hunks for users.rs },
        $.session.messages()              -> [user_msg, assistant_with_edit]
      ])

      model = PaneState.afterFetch(model, { outcome, messages })

      loadBodies():
        Fetches actual hunk text for users.rs
        model.bodies = Map { "src/api/users.rs" -> { hunks: [...] } }

      redraw(engine):
        $.ui.invalidate('ui.render') fires
        ui.render hook runs:
          const { Box, Text } = $.ui.resolve(e)
          return Views.paneView(...)  <- renders diff pane

Terminal now shows:
  Left half:  conversation transcript
  Right half: diff pane with users.rs changes (+4/-1 lines)
```

### Step 5 — Model Writes Tests and Runs Them

```
Model calls Write { file_path: "tests/api/users_test.rs", content: "..." }

afterTool:
  hasLanded = true
  landed = 2
  isPaneOpen = true -> scheduleRefresh(engine)

  Debounce timer: 150ms starts
  (150ms later) refresh() runs:
    git diff now shows TWO files
    Pane re-renders: users.rs + users_test.rs shown

Model calls Bash { command: "cargo test api::users" }

afterTool:
  Tools.mayHaveWritten(result)? No (clean test run, no write indicators)
  No refresh triggered (tests passed, nothing new written)
```

### Step 6 — User Arms a Hunk and Asks About It

```
User presses [a] key on src/api/users.rs in the diff pane

arm(engine, "src/api/users.rs") runs:
  armed = { path: "src/api/users.rs", text: "@@ -45,7 +45,12 @@..." }
  model.armedPath = "src/api/users.rs"
  $.ui.status("src/api/users.rs rides your next prompt (press asked v to drop it)")
  redraw() -> pane shows armed indicator on the file

User types: "Is this signature backward compatible?"

prompt.submit fires:
  armed is set
  
  Build diff text within character budget:
    text = "```diff\n@@ -45,7 +45,12 @@\n-pub async fn list_users(db: &Database)..."

  next({
    ...e,
    context: [...context, text]  <- diff injected into prompt
  })

  Model receives the prompt WITH the diff context.
  Model answers: "Yes — fully backward compatible. The new parameters
                  are Option<u32>, so callers that omit them get
                  page=None (treated as first page, default size)."

  armed cleared
  $.ui.status(undefined)  <- status line cleared
  redraw()
```

### Final State After the Turn

```
In-Process Memory (ephemeral):
  isPaneOpen  = true
  landed      = 2
  model.data  = { files: ["users.rs", "users_test.rs"], baseRef: "main" }
  armed       = null

Store Memory (unchanged — no storeSet called this turn):
  "diff:open"        = true
  "diff:base:myapp"  = "main"

Transcript / Model Memory: 8 messages
  [0] user:      "Add pagination..."
  [1] assistant: "I'll add pagination..." + [Read, Read, Edit, Write, Bash]
  [2] user:      [tool results]
  [3] assistant: summary of changes
  [4] user:      "Is this signature backward compatible?"
  [5] assistant: "Yes — fully backward compatible..."

Context Window: 62% full
  System prompt + 6 messages + tool schemas + file content in responses
```

---

## 10. Key Architectural Insights

### Insight 1: All State Is Explicit — No Hidden Globals

Every piece of state in the system is explicitly scoped:
- In-process closured variables — explicit `let` declarations in `register()`'s body
- Persistent data — explicit `$.store.get/set()` calls
- Conversation history — explicit `$.session.messages()` call
- Settings — explicit `$.settings.read()` call

There is no ambient global state a plugin can reach. This makes the system entirely auditable.

### Insight 2: The `finally` Block Is the Reliability Mechanism

The diff mod's tool.call hook uses `finally` (not `then`) to ensure `afterTool` always runs:

```typescript
try {
  result = await next(e)
  return result
} finally {
  // Runs even if next() throws, times out, or is aborted
  if (host) afterTool(host, e, result)
}
```

This pattern is how the pane stays consistent even when tools fail or abort.

### Insight 3: Immutable Model Updates

The pane model is never mutated in place:

```typescript
// WRONG (mutable mutation):
model.isLoading = true

// CORRECT (immutable spread creates a new object):
model = { ...model, isLoading: true }
```

This makes every state transition a pure function: `newState = f(oldState, event)`. It makes bugs reproducible and the system easy to reason about.

### Insight 4: Sandboxing Is Layered, Not Binary

There is no single "sandbox on/off" switch. Security is applied at:
- The **runtime** (no Node built-ins accessible to plugins)
- The **API boundary** (all capabilities through the `$` kernel)
- The **permission system** (tool.check events before every tool run)
- The **path resolution** (symlink-safe stat checks on every file path)
- The **5-tier deny system** (any tier can refuse any operation)

Each layer catches a different class of attack or mistake. Together they make it very hard for any single point of failure to compromise the system.

### Insight 5: The Host Object as a Test Seam

The diff mod wraps all `$` capabilities into a `Host` interface:

```typescript
// In production: bind() builds Host from $ capabilities
host = { run: (argv, init) => $.process.run(argv, init), ... }

// In tests: inject a mock Host
const mockHost = {
  run: async (argv) => ({ exitCode: 0, stdout: "main", stderr: "" }),
  storeGet: async (key) => key === "diff:open" ? true : undefined,
  messages: async () => [],
  ...
}
```

This is why the mod's test files can unit-test the full pane state machine without a real `$` engine — the Host abstraction is the seam.
