# OpenCode Architecture — Deep Dive
## Memory, Context Epochs, Agent Loop, Compaction, Sandboxing & Subagents — With Real TypeScript/Effect Code

> **Source Code References**: All code snippets, types, and architectural structures in this document are directly extracted from:
> - `resource/opencode/packages/core/src/` — The Core V2 business logic runtime
> - `resource/opencode/packages/core/src/session/` — Session runner, history, input, context epoch, compaction, and SQL tables
> - `resource/opencode/packages/core/src/system-context/` — Composable typed context sources and reconciliation
> - `resource/opencode/packages/core/src/tool/` — Tool definitions, registry, bash execution, and managed output store
> - `resource/opencode/packages/opencode/src/agent/` — Agent configurations, permission presets, and subagent hierarchy
> - `resource/opencode/packages/opencode/src/tool/task.ts` — Subagent orchestration and background execution
> - `resource/opencode/CONTEXT.md` & `AGENTS.md` — Authoritative runtime specifications and design contracts

---

## Table of Contents

1. [Architectural Overview & Monorepo Topology](#1-architectural-overview--monorepo-topology)
2. [The Effect-TS Functional Runtime Foundation](#2-the-effect-ts-functional-runtime-foundation)
3. [The Agent Execution Loop & State Machine](#3-the-agent-execution-loop--state-machine)
4. [How Memory Works — SQLite, Event Sourcing & Durable State](#4-how-memory-works--sqlite-event-sourcing--durable-state)
5. [The Context Architecture — Epochs, Baselines & Mid-Conversation Messages](#5-the-context-architecture--epochs-baselines--mid-conversation-messages)
6. [Context Compaction Engine — Proactive Budgeting & Overflow Recovery](#6-context-compaction-engine--proactive-budgeting--overflow-recovery)
7. [Tool System & Managed Output Storage](#7-tool-system--managed-output-storage)
8. [Sandboxing, Permissions & Process Execution](#8-sandboxing-permissions--process-execution)
9. [Multi-Agent Coordination & Subagent Hierarchy](#9-multi-agent-coordination--subagent-hierarchy)
10. [Content-Addressed Workspace Snapshots & Rewind](#10-content-addressed-workspace-snapshots--rewind)
11. [End-to-End Execution Trace](#11-end-to-end-execution-trace)
12. [Architectural Comparison: Claude Code vs. Codex vs. OpenCode](#12-architectural-comparison-claude-code-vs-codex-vs-opencode)

---

## 1. Architectural Overview & Monorepo Topology

OpenCode is designed as a modular, local-first coding assistant runtime built on **TypeScript**, **Bun**, and **Effect-TS**. Unlike traditional single-binary CLI tools or monolithic Node.js scripts, OpenCode is structured as a layered monorepo with strict dependency boundaries:

```
+-----------------------------------------------------------------------+
|                             USER CLIENTS                              |
|   packages/cli       packages/tui         packages/desktop    Web UI  |
+-----------------------------------------------------------------------+
                                   |
                                   v  (HttpApi / IPC)
+-----------------------------------------------------------------------+
|                         PACKAGES/SERVER & CLIENT                      |
|   packages/protocol (Typed HttpApi contracts & endpoints)            |
|   packages/client   (Generated SDK, Promise & Effect runtimes)        |
|   packages/server   (Hono/HttpApi server, routing, PTY host)         |
+-----------------------------------------------------------------------+
                                   |
                                   v
+-----------------------------------------------------------------------+
|                           PACKAGES/CORE                               |
|   session/runner/llm.ts  <--->  system-context/  <--->  tool/registry |
|   session/compaction.ts  <--->  session/epoch    <--->  permission.ts |
|   database/ (SQLite WAL) <--->  snapshot.ts (Git)<--->  process.ts    |
+-----------------------------------------------------------------------+
                                   |
                                   v
+-----------------------------------------------------------------------+
|                      PACKAGES/LLM & VENDORS                           |
|   @opencode-ai/llm (Streaming client, token estimators, adapters)    |
|   @ai-sdk/anthropic | @ai-sdk/openai | @ai-sdk/bedrock | models.dev   |
|   @agentclientprotocol/sdk (ACP protocol for IDE/agent interchange)   |
+-----------------------------------------------------------------------+
```

### Monorepo Packages Breakdown

| Package | Purpose | Key Responsibilities |
|---------|---------|----------------------|
| `packages/core` | Core Engine | Session loop, context epochs, tool registry, SQLite storage, permission evaluation, git snapshotting. |
| `packages/opencode` | Unified App / CLI | Default agent definitions (`build`, `plan`, `explore`), tool implementations (`task.ts`, `edit.ts`), MCP integration. |
| `packages/llm` | Model Transport | Provider adapters (OpenAI, Anthropic, Bedrock, Ollama), message conversion, token counting, stream normalization. |
| `packages/protocol` | API Schema Contracts | Strict `HttpApi` endpoint definitions, request/response models, transport-independent types. |
| `packages/server` | Execution Server | REST/SSE endpoints, PTY hosting, embedded client provider, background task worker. |
| `packages/client` | SDK Runtime | Type-safe generated client for remote or in-process (embedded) server communication. |
| `packages/tui` | Terminal Interface | Ink/React or Blessed-based interactive terminal UI with markdown rendering and diff view. |

---

## 2. The Effect-TS Functional Runtime Foundation

The architectural cornerstone of OpenCode is **Effect-TS** (`effect`). Unlike Claude Code (vanilla async/await with EventEmitter) or Codex (Rust Tokio with mpsc channels), OpenCode utilizes typed functional effect systems to manage:
- **Dependency Injection**: Via `Context.Service` and `Layer` compositions.
- **Resource Lifecycles**: Handled automatically through `Scope.Scope` and `Effect.addFinalizer`.
- **Fiber Concurrency & Interruption**: Controlled cancellation using `FiberSet`, `Semaphore`, and `Effect.uninterruptibleMask`.
- **Error Modeling**: Strongly typed tagged errors inheriting from `Schema.TaggedErrorClass`.

### How Dependency Injection Works in OpenCode

In `packages/core/src/session/runner/index.ts`:

```typescript
// packages/core/src/session/runner/index.ts:20-28
export interface Interface {
  readonly run: (input: {
    readonly sessionID: SessionSchema.ID
    readonly force: boolean
  }) => Effect.Effect<void, RunError>
}

export class Service extends Context.Service<Service, Interface>()("@opencode/v2/SessionRunner") {}
```

Services are composed into dependency graphs using `makeLocationNode` or `makeGlobalNode`:

```typescript
// packages/core/src/session/runner/llm.ts:421-439
export const node = makeLocationNode({
  service: Service,
  layer,
  deps: [
    EventV2.node,
    llmClient,
    AgentV2.node,
    ToolRegistry.node,
    SessionRunnerModel.node,
    SessionStore.node,
    Location.node,
    SystemContextRegistry.node,
    SkillGuidance.node,
    ReferenceGuidance.node,
    Config.node,
    Snapshot.node,
    Database.node,
  ],
})
```

---

## 3. The Agent Execution Loop & State Machine

The heart of OpenCode's agent execution is `SessionRunner.run` and `runTurnAttempt` in `packages/core/src/session/runner/llm.ts`.

### State Machine Lifecycle

```
[ User Input Admitted ]
           |
           v
+-------------------------------------------------------------------+
|                         SessionRunner.run                         |
|                                                                   |
|   1. failInterruptedTools() (Recovers any orphan pending tools)   |
|   2. Check hasPending(steer) vs hasPending(queue)                 |
|                                                                   |
|   WHILE (shouldRun):                                              |
|     WHILE (needsContinuation):                                    |
|       a. promoteSteers() (promote pending user steers)            |
|       b. initialize / prepare ContextEpoch                        |
|       c. check compaction.compactIfNeeded()                       |
|       d. capture startSnapshot = snapshots.capture()              |
|       e. stream LLM provider turn                                 |
|       f. fork tool calls concurrently into FiberSet               |
|       g. awaitToolFibers() & record settlements                   |
|       h. capture endSnapshot & emit Step.Ended                    |
|       i. re-evaluate needsContinuation                            |
|                                                                   |
|     promoteNextQueued() (promote one queued prompt when idle)     |
+-------------------------------------------------------------------+
```

### The Double-While Loop (`SessionRunner.run`)

Here is the exact outer orchestration code from `packages/core/src/session/runner/llm.ts`:

```typescript
// packages/core/src/session/runner/llm.ts:390-413
const run = Effect.fn("SessionRunner.run")(function* (input: {
  readonly sessionID: SessionSchema.ID
  readonly force: boolean
}) {
  const hasSteer = yield* SessionInput.hasPending(db, input.sessionID, "steer")
  const hasQueue = hasSteer ? false : yield* SessionInput.hasPending(db, input.sessionID, "queue")
  if (!input.force && !hasSteer && !hasQueue) return
  yield* failInterruptedTools(input.sessionID)
  let promotion: SessionInput.Delivery | undefined = hasSteer ? "steer" : hasQueue ? "queue" : undefined
  let shouldRun = input.force || hasSteer || hasQueue

  while (shouldRun) {
    let needsContinuation = true
    let step = 1
    while (needsContinuation) {
      const result = yield* runTurn(input.sessionID, promotion, step)
      needsContinuation = result.needsContinuation
      step = result.step + 1
      promotion = "steer"
      if (!needsContinuation) needsContinuation = yield* SessionInput.hasPending(db, input.sessionID, "steer")
    }
    shouldRun = yield* SessionInput.hasPending(db, input.sessionID, "queue")
    promotion = shouldRun ? "queue" : undefined
  }
})
```

#### Key Mechanics of the Loop:
1. **Prompt Steering vs. Queueing**:
   - `steer` prompts interrupt and inject directly into the running turn loop at the next turn boundary (`promotion = "steer"`).
   - `queue` prompts remain in the inbox and are **only** promoted when the agent would otherwise become completely idle (`!needsContinuation`).
2. **Step Limits**:
   - Agent definitions have an optional `steps` ceiling (`agent.info?.steps`).
   - When `currentStep >= agent.info.steps`, `isLastStep` becomes `true`.
   - The tool materialization is set to `undefined`, `toolChoice` is forced to `"none"`, and `MAX_STEPS_PROMPT` is appended to force the model to synthesize a final conclusion without issuing further tool calls.

---

## 4. How Memory Works — SQLite, Event Sourcing & Durable State

OpenCode does **not** rely on in-memory chat histories or loose JSON files. It implements an event-sourced durable relational store using **SQLite** managed via **Drizzle ORM** (`packages/core/src/session/sql.ts`).

### Database Configuration & PRAGMA Tuning

From `packages/core/src/database/database.ts`:

```typescript
// packages/core/src/database/database.ts:27-33
yield* db.run("PRAGMA journal_mode = WAL")
yield* db.run("PRAGMA synchronous = NORMAL")
yield* db.run("PRAGMA busy_timeout = 5000")
yield* db.run("PRAGMA cache_size = -64000") // 64MB high-performance memory cache
yield* db.run("PRAGMA foreign_keys = ON")
yield* db.run("PRAGMA wal_checkpoint(PASSIVE)")
```

### Database Schema Architecture

```
+--------------------+       +--------------------------+
|    session         | 1   * |     session_message      |
|--------------------|-------|--------------------------|
| id (PK)            |       | id (PK)                  |
| project_id (FK)    |       | session_id (FK)          |
| parent_id (FK)     |       | type (user/asst/sys/...) |
| tokens_input       |       | seq (monotonic int)      |
| tokens_output      |       | data (json)              |
| cost               |       +--------------------------+
| revert (json)      |
| model (json)       |       +--------------------------+
+--------------------+       |      session_input       |
          |                  |--------------------------|
          | 1                | id (PK)                  |
          v                  | session_id (FK)          |
+--------------------+       | delivery ('steer'|'queue'|
|session_context_epoch       | admitted_seq (int)       |
|--------------------|       | promoted_seq (int)       |
| session_id (PK, FK)|       +--------------------------+
| baseline (text)    |
| snapshot (json)    |
| baseline_seq (int) |
+--------------------+
```

### Table Definitions in Code

```typescript
// packages/core/src/session/sql.ts:22-60
export const SessionTable = sqliteTable("session", {
  id: text().$type<SessionSchema.ID>().primaryKey(),
  project_id: text().$type<ProjectV2.ID>().notNull().references(() => ProjectTable.id, { onDelete: "cascade" }),
  workspace_id: text().$type<WorkspaceV2.ID>(),
  parent_id: text().$type<SessionSchema.ID>(), // Identifies parent session for Subagents!
  slug: text().notNull(),
  directory: DatabasePath.directoryColumn().notNull(),
  title: text().notNull(),
  cost: real().notNull().default(0),
  tokens_input: integer().notNull().default(0),
  tokens_output: integer().notNull().default(0),
  tokens_reasoning: integer().notNull().default(0),
  tokens_cache_read: integer().notNull().default(0),
  tokens_cache_write: integer().notNull().default(0),
  revert: text({ mode: "json" }).$type<Revert.State>(),
  permission: text({ mode: "json" }).$type<PermissionV1.Ruleset>(),
  agent: text(),
  model: text({ mode: "json" }).$type<{ id: string; providerID: string; variant?: string }>(),
  ...Timestamps,
  time_compacting: integer(),
  time_archived: integer(),
})

// packages/core/src/session/sql.ts:119-138
export const SessionMessageTable = sqliteTable("session_message", {
  id: text().$type<SessionMessage.ID>().primaryKey(),
  session_id: text().$type<SessionSchema.ID>().notNull().references(() => SessionTable.id, { onDelete: "cascade" }),
  type: text().$type<SessionMessage.Type>().notNull(),
  seq: integer().notNull(), // Strictly monotonically increasing
  ...Timestamps,
  data: text({ mode: "json" }).notNull().$type<SessionMessageData>(),
}, (table) => [
  uniqueIndex("session_message_session_seq_idx").on(table.session_id, table.seq),
  index("session_message_session_type_seq_idx").on(table.session_id, table.type, table.seq),
])

// packages/core/src/session/sql.ts:140-166
export const SessionInputTable = sqliteTable("session_input", {
  id: text().$type<SessionMessage.ID>().primaryKey(),
  session_id: text().$type<SessionSchema.ID>().notNull().references(() => SessionTable.id, { onDelete: "cascade" }),
  prompt: text({ mode: "json" }).notNull().$type<Prompt>(),
  delivery: text().$type<SessionInput.Delivery>().notNull(), // 'steer' | 'queue'
  admitted_seq: integer().notNull(),
  promoted_seq: integer(), // NULL while pending, populated when admitted to conversation
  time_created: integer().notNull().$default(() => Date.now()),
})
```

---

## 5. The Context Architecture — Epochs, Baselines & Mid-Conversation Messages

One of OpenCode's most sophisticated architectural innovations is its distinction between **System Context**, **Baseline System Context**, **Context Epochs**, and **Mid-Conversation System Messages** (`CONTEXT.md`).

### Why This Design Matters
- Standard LLM agents recompute and re-send the entire system prompt on every turn, frequently invalidating provider KV prefix caches (Prompt Caching).
- OpenCode establishes an immutable **Baseline System Context** at the start of each **Context Epoch**.
- If context changes dynamically (e.g., instructions change, skills updated, timezone shifts), OpenCode **does not** modify the baseline. Instead, it emits a chronological **Mid-Conversation System Message** into the chat stream, preserving the provider cache prefix!

```
[Context Epoch Starts]
         |
         v
+-----------------------------------------------------------+
| BASELINE SYSTEM CONTEXT (Immutable Provider Cache Prefix) |
| - OS environment, Working directory, Git root             |
| - Ambient AGENTS.md instructions                          |
| - Initial Available Skills                                |
+-----------------------------------------------------------+
         |
         |  Provider Turn 1 (Cached)
         v
[User Message 1] -> [Assistant Response + Tool Call]
         |
         |  User edits AGENTS.md mid-conversation
         v
[Mid-Conversation System Message: SessionEvent.ContextUpdated]
"These instructions replace all previously loaded ambient instructions: ..."
         |
         |  Provider Turn 2 (Reuses Baseline Cache Prefix!)
         v
[User Message 2] -> [Assistant Response]
```

### The `SystemContext.Source<A>` Contract

In `packages/core/src/system-context/index.ts`:

```typescript
// packages/core/src/system-context/index.ts:32-39
export interface Source<A> {
  readonly key: Key
  readonly codec: Schema.Codec<A, Schema.Json, never, never>
  readonly load: Effect.Effect<A | Unavailable>
  readonly baseline: (current: A) => string
  readonly update: (previous: A, current: A) => string
  readonly removed?: (previous: A) => string
}
```

### Context Reconciliation (`SessionContextEpoch.prepare`)

```typescript
// packages/core/src/session/context-epoch.ts:40-78
const prepareOnce = Effect.fnUntraced(function* (
  db: DatabaseService,
  events: EventV2.Interface,
  context: Effect.Effect<SystemContext.SystemContext>,
  sessionID: SessionSchema.ID,
) {
  const [value, stored, compaction] = yield* Effect.all(
    [context, find(db, sessionID), SessionHistory.latestCompaction(db, sessionID)],
    { concurrency: "unbounded" },
  )
  if (!stored) {
    const generation = yield* SystemContext.initialize(value)
    const baselineSeq = yield* insert(db, sessionID, generation)
    return { baseline: generation.baseline, baselineSeq }
  }

  const snapshot = yield* Schema.decodeUnknownEffect(SystemContext.Snapshot)(stored.snapshot)
  const replacementSeq = compaction !== undefined && compaction.seq > stored.baseline_seq ? compaction.seq : undefined
  
  // If compaction occurred, replace baseline; otherwise reconcile updates
  const result = replacementSeq
    ? yield* SystemContext.replace(value, snapshot)
    : yield* SystemContext.reconcile(value, snapshot)

  if (result._tag === "Unchanged" || result._tag === "ReplacementBlocked") {
    return { baseline: stored.baseline, baselineSeq: stored.baseline_seq }
  }
  if (result._tag === "ReplacementReady") {
    const baselineSeq = replacementSeq ?? (yield* EventV2.latestSequence(db, sessionID))
    yield* replace(db, sessionID, baselineSeq, result.generation)
    return { baseline: result.generation.baseline, baselineSeq }
  }

  // Emits the Mid-Conversation System Message without altering the baseline!
  yield* events.publish(
    SessionEvent.ContextUpdated,
    { sessionID, messageID: SessionMessage.ID.create(), timestamp: yield* DateTime.now, text: result.text },
    { commit: () => advance(db, sessionID, result.snapshot).pipe(Effect.orDie) },
  )
  return { baseline: stored.baseline, baselineSeq: stored.baseline_seq }
})
```

---

## 6. Context Compaction Engine — Proactive Budgeting & Overflow Recovery

OpenCode implements a **dual-strategy context compaction system** (`packages/core/src/session/compaction.ts`):
1. **Proactive Budget Compaction (`compactIfNeeded`)**: Evaluates token consumption before issuing the LLM request.
2. **Reactive Overflow Recovery (`compactAfterOverflow`)**: Intercepts provider 400 Context Overflow errors when models reject the prompt, immediately summarizing and retrying.

### Compaction Constants & Budget Formulas

```typescript
// packages/core/src/session/compaction.ts:12-15
const DEFAULT_BUFFER = 20_000         // Reserve 20k tokens for output generation + buffer
const DEFAULT_KEEP_TOKENS = 8_000     // Keep the most recent 8,000 tokens of conversation verbatim
const TOOL_OUTPUT_MAX_CHARS = 2_000   // Tool outputs serialized during compaction truncated to 2,000 chars
const SUMMARY_OUTPUT_TOKENS = 4_096   // Hard ceiling for generated summary
```

### Proactive Trigger Condition

```typescript
// packages/core/src/session/compaction.ts:232-243
const compactIfNeeded = Effect.fn("SessionCompaction.compactIfNeeded")(function* (input: Input) {
  if (!config.auto) return false
  const context = input.model.route.defaults.limits?.context
  if (context === undefined || context <= 0) return false
  const output = input.request.generation?.maxTokens ?? input.model.route.defaults.limits?.output ?? 0
  
  // Triggers if total estimated tokens exceed context window minus buffer
  if (
    estimate({ system: input.request.system, messages: input.request.messages, tools: input.request.tools }) <=
    context - Math.max(output, config.buffer)
  )
    return false
  return yield* compactAfterOverflow(input)
})
```

### The Structured Summary Template

OpenCode uses a strict structured Markdown schema to ensure that the compacted state preserves all actionable context:

```markdown
## Objective
- [one or two brief sentences describing what the user is trying to accomplish]

## Important Details
- [constraints/preferences, decisions and why, important facts/assumptions, exact context needed to continue, or "(none)"]

## Work State
### Completed
- [finished work, verified facts, or changes made; otherwise "(none)"]

### Active
- [current work, partial changes, or investigation state; otherwise "(none)"]

### Blocked
- [blockers, failing commands, or unknowns; otherwise "(none)"]

## Next Move
1. [immediate concrete action, or "(none)"]
2. [next action if known, or "(none)"]

## Relevant Files
- [file or directory path: why it matters, or "(none)"]
```

### Combining Prior Summaries (`SUMMARY_UPDATE_INSTRUCTIONS`)

When a session compactor runs multiple times, OpenCode does **not** discard old summaries. It provides `<prior-summary>` alongside the new `<conversation>` and applies explicit conflict-resolution rules:
- **Conversation wins**: If `<conversation>` contradicts `<prior-summary>`, state the corrected fact.
- **Carry forward**: Carry forward unmentioned user directives, constraints, and parallel workstreams.
- **State migration**: Automatically move completed items from `Active` to `Completed`.

---

## 7. Tool System & Managed Output Storage

Tools in OpenCode are defined through a typed, functional builder pattern (`packages/core/src/tool/tool.ts`) that verifies schemas, extracts JSON Schemas for providers, and partitions **structured outputs** from **model-visible text projections**.

### Tool Definition Architecture

```typescript
// packages/core/src/tool/tool.ts:40-61
type Config<Input, Output, Structured = Output> = {
  readonly description: string
  readonly input: Input
  readonly output: Output
  readonly structured?: Structured
  readonly toStructuredOutput?: (input: { input: InputType; output: OutputType }) => StructuredType
  readonly execute: (input: InputType, context: Context) => Effect.Effect<OutputType, ToolFailure>
  readonly toModelOutput?: (input: { input: InputType; output: OutputType }) => ReadonlyArray<Content>
}
```

### Managed Tool Output Storage (`ToolOutputStore`)

A major risk in terminal coding agents is tools dumping megabytes of text (e.g., `cat bundle.js` or huge build logs), blowing out the context window. OpenCode solves this via **Managed Tool Output Files** (`packages/core/src/tool-output-store.ts`):

```typescript
// packages/core/src/tool-output-store.ts:13-17
export const MAX_LINES = 2_000
export const MAX_BYTES = 50 * 1024 // 50 KB hard limit
export const RETENTION = Duration.days(7)
export const MANAGED_DIRECTORY = "tool-output"
```

If a tool's output exceeds **2,000 lines** or **50 KB**:
1. The full verbatim content is written to disk: `~/.local/share/opencode/tool-output/tool_<timestamp_id>`.
2. A balanced **head & tail preview** is constructed: half lines/bytes from the top, half from the bottom.
3. The model receives the bounded preview with an unambiguous pointer:
   ```
   [First 1,000 lines...]

   ... output truncated; full content saved to /path/to/tool-output/tool_abc123 ...

   [Last 1,000 lines...]
   ```

---

## 8. Sandboxing, Permissions & Process Execution

### Permission System (`PermissionV2`)

OpenCode employs a fine-grained, tri-state permission model (`allow`, `deny`, `ask`) evaluated with wildcard pattern matching (`packages/core/src/permission.ts`):

```typescript
// packages/core/src/permission.ts:76-86
export function evaluate(action: string, resource: string, ...rulesets: Permission.Ruleset[]): Permission.Rule {
  return (
    rulesets
      .flat()
      .findLast((rule) => Wildcard.match(action, rule.action) && Wildcard.match(resource, rule.resource)) ?? {
      action,
      resource: "*",
      effect: "ask",
    }
  )
}
```

#### User Decline Semantics:
In `packages/core/src/session/runner/llm.ts:145-150`, declining a permission prompt throws a `PermissionV2.DeclinedError`. OpenCode treats this as an **immediate execution interruption**, terminating the agent loop cleanly rather than converting the rejection into a model-visible error string that the agent might attempt to bypass!

### External Directory Confinement

When executing shell commands (`packages/core/src/tool/bash.ts`), OpenCode inspects target paths and command arguments:
1. `workdir` is resolved via `LocationMutation.resolve`.
2. If `workdir` points outside the active workspace (`target.externalDirectory`), OpenCode explicitly triggers an `external_directory` permission prompt.
3. `externalCommandDirectories()` tokenizes the command string, scans for absolute path arguments, and verifies if any reference external directories outside the workspace root, attaching warning advisories to the tool output.

### PTY & Terminal Emulation

For interactive shell tasks, OpenCode supports native pseudoterminal creation via `@lydell/node-pty` (`packages/core/src/pty/pty.node.ts`):
- Windows: Uses native ConPTY (`useConptyDll: true`).
- POSIX: Uses forkpty for true terminal emulation.
- Merges host environment overlays (`PTY Environment`) while enforcing core invariants like `TERM=xterm-256color` and `OPENCODE_TERMINAL=1`.

---

## 9. Multi-Agent Coordination & Subagent Hierarchy

OpenCode natively supports subagents and hierarchical delegation through the `task` tool (`packages/opencode/src/tool/task.ts`).

### Built-in Agent Specializations

Configured in `packages/opencode/src/agent/agent.ts`:

```
+--------------------------------------------------------------------------+
|                               AGENT ROSTER                               |
+-----------+-----------+-------------------+------------------------------+
| Agent     | Mode      | Permissions       | Description                  |
+-----------+-----------+-------------------+------------------------------+
| build     | primary   | Default (full)    | Primary autonomous agent.    |
| plan      | primary   | edit: * -> deny   | Read-only architectural plan.|
|           |           | plans/*.md -> OK  | Explores and drafts plans.   |
| general   | subagent  | todowrite -> deny | General parallel worker.     |
| explore   | subagent  | read-only tools   | Ultra-fast codebase search.  |
| compaction| primary   | * -> deny         | Hidden single-turn compactor.|
+-----------+-----------+-------------------+------------------------------+
```

### Subagent Session Creation & Permission Inheritance

When the primary agent invokes the `task` tool:

```typescript
// packages/opencode/src/tool/task.ts:92-120
const run = Effect.fn("TaskTool.execute")(function* (params, ctx) {
  // 1. Spawns child session linked by parentID in SQLite
  const child = yield* sessions.create({
    parentID: ctx.sessionID,
    directory: ctx.directory,
    agent: params.subagent_type,
    title: params.description,
  })

  // 2. Inherits parent permissions with restrictive overlay
  const derivedPermission = deriveSubagentSessionPermission({
    parent: ctx.permissions,
    child: agentInfo.permission,
  })

  // 3. Spawns foreground execution or registers with BackgroundJob.Service
  if (params.background) {
    yield* background.submit({ sessionID: child.id, prompt: params.prompt })
    return renderBackgroundAck(child.id)
  }

  // 4. Foreground: await settlement and wrap in XML envelope
  const result = yield* sessions.run(child.id, params.prompt)
  return renderOutput({ sessionID: child.id, state: "completed", text: result })
})
```

The output returned to the calling agent is cleanly partitioned using structured XML:
```xml
<task id="ses_98fbc12a" state="completed">
  <summary>Discovered authentication middleware endpoints</summary>
  <task_result>
    Found 3 auth routes in packages/server/src/auth.ts: /login, /refresh, /logout.
  </task_result>
</task>
```

---

## 10. Content-Addressed Workspace Snapshots & Rewind

OpenCode features a built-in time-travel file snapshot system (`packages/core/src/snapshot.ts`) that tracks workspace mutations before and after every agent turn.

```
       Turn Start                             Turn End
           |                                     |
           v                                     v
+----------------------+              +----------------------+
| snapshots.capture()  |              | snapshots.capture()  |
| Snapshot ID: "tree_A"|              | Snapshot ID: "tree_B"|
+----------------------+              +----------------------+
           \                                     /
            \                                   /
             v                                 v
     +------------------------------------------------+
     | snapshots.files({ from: tree_A, to: tree_B })   |
     | -> Emits exact list of modified relative paths |
     | -> Persisted in SessionEvent.Step.Ended        |
     +------------------------------------------------+
```

### Git-Backed Shadow Trees
- Snapshots do **not** pollute the user's primary git repository.
- OpenCode creates a dedicated shadow git store in `~/.local/share/opencode/snapshot/<project_id>/<hash>/`.
- Calling `snapshot.restore({ files })` allows reverting arbitrary file edits made during an agent session, enabling instant rollback if a tool goes rogue or the user rejects the changes.

---

## 11. End-to-End Execution Trace

Here is the exact step-by-step lifecycle of a user prompt executing in OpenCode:

```
Step 1: Ingestion
  User types: "Fix the bug in auth.ts and run the tests"
  -> SessionInputTable inserts prompt with delivery = "steer", promoted_seq = NULL
  -> SessionRunner.run() is triggered

Step 2: Turn Boundary Preparation
  -> SessionInput.promoteSteers(): atomically sets promoted_seq, appends user message to SessionMessageTable
  -> SessionContextEpoch.prepare():
       * Loads systemContext (env, date, ambient AGENTS.md instructions)
       * Reconciles against Snapshot. If unchanged, reuses Baseline Context
  -> SessionHistory.entriesForRunner(): queries SessionMessageTable where seq >= compaction.seq

Step 3: Compaction Evaluation
  -> SessionCompaction.compactIfNeeded():
       * Estimates tokens for baseline + context + tools
       * Total tokens < context - 20k buffer -> proceeds to model turn

Step 4: Provider Turn Execution
  -> snapshots.capture(): captures startSnapshot ID
  -> ToolRegistry.materialize(): resolves active tool definitions for "build" agent
  -> llm.stream(request): begins SSE streaming with provider
  -> LLMEventPublisher incrementally commits assistant text deltas and reasoning to DB

Step 5: Tool Execution & Settlement
  -> Model outputs tool-call: bash(command: "bun test")
  -> publisher.assistantMessageID() resolves call ID
  -> Tool executed inside uninterruptibleMask:
       * PermissionV2.assert() validates execution permission
       * ChildProcess executes "bun test" with 2m timeout
       * Output captured: 2,500 lines
  -> ToolOutputStore.bound():
       * Exceeds MAX_LINES (2,000)
       * Writes full log to tool-output/tool_171928472
       * Emits head/tail preview with disk reference
  -> LLMEvent.toolResult published and recorded in SessionMessageTable

Step 6: Step Settlement & Continuation
  -> snapshots.capture(): captures endSnapshot ID
  -> snapshots.files(): computes exact diff of files modified
  -> SessionEvent.Step.Ended published
  -> needsContinuation = true -> loop repeats for next model turn
  -> Model analyzes test output, responds with "Tests passed successfully", tool calls = none
  -> needsContinuation = false -> Session settles into idle state
```

---

## 12. Architectural Comparison: Claude Code vs. Codex vs. OpenCode

| Architectural Dimension | Claude Code | Codex (codex-rs) | OpenCode |
|-------------------------|-------------|------------------|----------|
| **Primary Language** | TypeScript (Node.js) | Rust | TypeScript (Bun / Node.js) |
| **Concurrency & Async** | Promises, async/await, EventEmitter | Tokio async, mpsc channels, Arc/Mutex | Effect-TS Fibers, FiberSets, Scopes |
| **State Storage** | In-memory arrays, flat file sessions | In-memory `CodexThread` + SQLite graph store | SQLite WAL database via Drizzle ORM |
| **Message Ordering** | Array index | Vector order / aggregate ID | Monotonic sequence integer (`seq`) |
| **System Prompting** | Dynamic monolith re-sent every turn | Tiered system prompt with token limits | Immutable Baseline Context Epochs + Mid-Conversation Updates |
| **Prompt Caching** | Static cache break point heuristic | Prefix-preserving state tracker | Explicit `promptCacheKey` + Epoch baseline reuse |
| **Compaction Strategy** | Single-pass summary replacement | Dual compaction: In-memory vs Remote V2 | Dual: Proactive token budget + Reactive 400 overflow recovery |
| **Tool Execution** | Sequential / Promise.all | Tokio async task spawn | Parallel `FiberSet` with uninterruptible masks |
| **Large Output Handling** | In-memory line slice truncation | In-memory byte truncation | `ToolOutputStore` to disk files with Head/Tail previews |
| **Sandboxing** | macOS Seatbelt sandbox-exec | OS-level: Seatbelt (Mac), Bubblewrap (Linux), Restricted Token (Win) | Process-level permission rulesets (`allow/deny/ask`) + PTY ConPTY |
| **Subagents** | Ephemeral subagent sessions | Multi-agent coordination with thread IDs | Hierarchical `SessionTable.parent_id` + BackgroundJob workers |
| **Time Travel / Revert** | Manual git diff checking | In-memory rollback buffer | Git-backed shadow tree snapshots & rewinds |
