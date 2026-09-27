# Pi Architecture — Deep Dive
## Agent Loop, JSONL Branching Trees, Compaction, Cache Warming, Extensions & TUI — With Real TypeScript Code

> **Source Code References**: All code snippets, types, and architectural structures in this document are directly extracted from:
> - `resource/pi/packages/agent/src/` — The `@earendil-works/pi-agent-core` agent runtime and execution loop
> - `resource/pi/packages/coding-agent/src/core/` — The high-level `AgentSession`, `SessionManager`, compaction, cache warmer, and tools
> - `resource/pi/packages/coding-agent/src/core/compaction/` — Backward-cut token compaction and file operation tracking
> - `resource/pi/packages/coding-agent/src/core/extensions/` — Extensive plugin/extension hooks and lifecycle APIs
> - `resource/pi/packages/ai/src/` — The `@earendil-works/pi-ai` multi-provider LLM abstraction and token/cost calculations
> - `resource/pi/packages/tui/src/` — The differential rendering terminal UI engine, OKLab colors, and image graphics
> - `resource/pi/packages/coding-agent/examples/extensions/subagent/` — Process-isolated subagent architecture (Single, Parallel, Chain)

---

## Table of Contents

1. [Architectural Overview & Monorepo Topology](#1-architectural-overview--monorepo-topology)
2. [The Core Agent Execution Loop](#2-the-core-agent-execution-loop)
3. [Memory & Persistence — Append-Only JSONL Merkle Trees](#3-memory--persistence--append-only-jsonl-merkle-trees)
4. [Prompt Cache Warmer — Autonomous Latency & Cost Optimization](#4-prompt-cache-warmer--autonomous-latency--cost-optimization)
5. [Context Architecture & System Prompt Engineering](#5-context-architecture--system-prompt-engineering)
6. [Context Compaction Engine — Backward Safe Cuts & File Tracking](#6-context-compaction-engine--backward-safe-cuts--file-tracking)
7. [Tool System & File Mutation Queue Concurrency](#7-tool-system--file-mutation-queue-concurrency)
8. [Sandboxing & Process Execution Model](#8-sandboxing--process-execution-model)
9. [Subagent Coordination — Process Isolation & Workflow Chaining](#9-subagent-coordination--process-isolation--workflow-chaining)
10. [Terminal UI (TUI) — Differential Rendering & Terminal Graphics](#10-terminal-ui-tui--differential-rendering--terminal-graphics)
11. [End-to-End Execution Trace](#11-end-to-end-execution-trace)
12. [Four-Way Comparison: Claude Code vs. Codex vs. OpenCode vs. Pi](#12-four-way-comparison-claude-code-vs-codex-vs-opencode-vs-pi)

---

## 1. Architectural Overview & Monorepo Topology

**Pi** (created by Mario Zechner / `@badlogic` and Earendil Works) is a modular, extensible, local-first agent harness and interactive coding agent CLI. In contrast to monolithic CLI tools or framework-heavy functional approaches, Pi is structured as a suite of decoupled, standalone libraries:

```
+------------------------------------------------------------------------+
|                          USER INTERFACES                               |
|   Interactive TUI (Terminal)     RPC Mode (IDEs)    Print/JSON Mode    |
+------------------------------------------------------------------------+
                                   |
                                   v
+------------------------------------------------------------------------+
|                    @earendil-works/pi-coding-agent                     |
|  AgentSession (140KB coordinator)  <--->  SessionManager (JSONL Tree)  |
|  CacheWarmer (Prompt Cache Keepalive)<->  Compaction Engine            |
|  Built-in Tools (bash, edit, read) <--->  ExtensionRunner (69KB types) |
+------------------------------------------------------------------------+
              |                                          |
              v                                          v
+------------------------------------+  +--------------------------------+
|    @earendil-works/pi-agent-core   |  |     @earendil-works/pi-tui     |
|  agentLoop (Double-while loop)     |  | Differential renderer (diff)   |
|  Turn management & steering queue  |  | OKLab color spaces             |
|  declareToolChanges (system delta) |  | Kitty / iTerm2 / Sixel images  |
+------------------------------------+  +--------------------------------+
              |
              v
+------------------------------------------------------------------------+
|                       @earendil-works/pi-ai                            |
|  Multi-provider API (Anthropic, OpenAI, Gemini, Bedrock, Ollama)      |
|  Normalized EventStreams, Token estimators, Prompt cache cost models   |
+------------------------------------------------------------------------+
```

### Packages Architecture

| Package | Role | Core Responsibility |
|---------|------|---------------------|
| `packages/agent` | Agent Runtime | Core `agentLoop` double-loop state machine, message transformation, tool state change diffing. |
| `packages/coding-agent` | Coding Harness | `AgentSession` lifecycle coordinator, JSONL tree storage, prompt cache warming, file mutation queues, extensions. |
| `packages/ai` | Unified LLM Client | Multi-provider streaming client, unified message formats, accurate token/cost calculators, cache pricing models. |
| `packages/tui` | Terminal UI Engine | Custom diff-based terminal engine, sub-character layout, ANSI parsing, Kitty/iTerm2 image graphics, LaTeX math rendering. |
| `packages/durable` | Durable Workflows | Replicated documents, transactional session storage, distributed task execution. |
| `packages/chord` | Application Composition | Distributed service mesh, replicated state, RPC server/client. |

---

## 2. The Core Agent Execution Loop

The execution core of Pi resides in `packages/agent/src/agent-loop.ts`. It works purely with `AgentMessage[]` throughout the turn cycle, only lowering to provider-specific `Message[]` wire representations at the absolute LLM network boundary.

### The Double-While Loop State Machine

Pi enforces a strict distinction between **Steering Messages** (interruptive, high-priority user instructions) and **Follow-Up Messages** (queued prompts evaluated only when the agent becomes idle):

```
[ New Prompt / Continuation ]
            |
            v
+--------------------------------------------------------------------------+
|                            runLoop()                                     |
|                                                                          |
|   WHILE (true)  [Outer Loop: Evaluates follow-up messages]               |
|     |                                                                    |
|     WHILE (hasMoreToolCalls || pendingMessages.length > 0) [Inner Loop]  |
|       1. prepareNextTurn(): snapshots context, handles model/thinking     |
|       2. declareToolChanges(): diffs current executable tools vs transcript|
|          and attaches toolsAdded / toolsRemoved to SystemMessage         |
|       3. prepareRequest(): allows extensions to intercept request        |
|       4. streamAssistantResponse(): converts AgentMessage[] -> Message[]  |
|          and streams LLM tokens via EventStream                          |
|       5. If stopReason === "length": FAIL ALL TOOL CALLS IMMEDIATELY     |
|          (Prevents executing truncated arguments!)                       |
|       6. executeToolCalls(): runs tools sequentially or in parallel      |
|       7. finishTurn(): handles turn decisions ("continue" | "end")       |
|       8. getSteeringMessages(): injects pending steers into current run  |
|                                                                          |
|     getFollowUpMessages(): pulls queued follow-up prompts                |
|     If no follow-ups & no explicit continuation: BREAK and emit agent_end|
+--------------------------------------------------------------------------+
```

### Inner vs. Outer Loop in Real Code

From `packages/agent/src/agent-loop.ts`:

```typescript
// packages/agent/src/agent-loop.ts:178-317
async function runLoop(
  initialContext: AgentContext,
  newMessages: AgentMessage[],
  initialConfig: AgentLoopConfig,
  signal: AbortSignal | undefined,
  emit: AgentEventSink,
  streamFunction: StreamFn,
): Promise<void> {
  let currentContext = initialContext;
  let config = initialConfig;
  let lastCompletedTurn: PrepareNextTurnContext | undefined;
  let explicitContinuation = false;
  let pendingMessages: AgentMessage[] = (await config.getSteeringMessages?.()) || [];

  // Outer loop: continues when queued follow-up messages arrive after agent would stop
  while (true) {
    let hasMoreToolCalls = true;

    // Inner loop: process tool calls and steering messages
    while (hasMoreToolCalls || pendingMessages.length > 0) {
      let preparedMessages: AgentMessage[] = [];
      if (lastCompletedTurn) {
        const nextTurnSnapshot = await config.prepareNextTurn?.(lastCompletedTurn);
        if (nextTurnSnapshot) {
          currentContext = nextTurnSnapshot.context ?? currentContext;
          preparedMessages = nextTurnSnapshot.messages ?? [];
          config = {
            ...config,
            model: nextTurnSnapshot.model ?? config.model,
            reasoning: nextTurnSnapshot.thinkingLevel === "off" ? undefined : nextTurnSnapshot.thinkingLevel,
          };
        }
        if (pendingMessages.length === 0) {
          pendingMessages = (await config.getSteeringMessages?.()) || [];
        }
        await emit({ type: "turn_start" });
      }

      // Prepend dynamic tool state updates
      for (const message of declareToolChanges(currentContext, [...preparedMessages, ...pendingMessages])) {
        await emit({ type: "message_start", message });
        await emit({ type: "message_end", message });
        currentContext.messages.push(message);
        newMessages.push(message);
      }
      pendingMessages = [];

      // Stream assistant response
      const message = await streamAssistantResponse(currentContext, config, signal, emit, streamFunction);
      newMessages.push(message);

      if (message.stopReason === "error" || message.stopReason === "aborted") {
        await emit({ type: "turn_end", message, toolResults: [] });
        await emit({ type: "agent_end", messages: newMessages });
        return;
      }

      const toolCalls = message.content.filter((c) => c.type === "toolCall");
      const toolResults: ToolResultMessage[] = [];
      hasMoreToolCalls = false;

      if (toolCalls.length > 0) {
        // CRITICAL DEFENSE: A "length" stop means output was truncated by token limit!
        // All tool calls may carry truncated JSON arguments. Fail them safely!
        const executedToolBatch =
          message.stopReason === "length"
            ? await failToolCallsFromTruncatedMessage(toolCalls, emit)
            : await executeToolCalls(currentContext, message, config, signal, emit);
        
        toolResults.push(...executedToolBatch.messages);
        hasMoreToolCalls = !executedToolBatch.terminate;

        for (const result of toolResults) {
          currentContext.messages.push(result);
          newMessages.push(result);
        }
      }

      lastCompletedTurn = { message, toolResults, context: currentContext, newMessages };
      const decision = await config.finishTurn?.(lastCompletedTurn, signal);
      await emit({ type: "turn_end", message, toolResults });

      if (decision?.action === "end") {
        await emit({ type: "agent_end", messages: newMessages });
        return;
      }

      explicitContinuation = decision?.action === "continue";
      pendingMessages = (await config.getSteeringMessages?.()) || [];
    }

    // Agent would stop here. Check for queued follow-up messages.
    const followUpMessages = (await config.getFollowUpMessages?.()) || [];
    if (followUpMessages.length > 0) {
      pendingMessages = followUpMessages;
      continue;
    }

    if (explicitContinuation) {
      explicitContinuation = false;
      continue;
    }

    break;
  }

  await emit({ type: "agent_end", messages: newMessages });
}
```

### Dynamic Tool Declaration Diffing (`declareToolChanges`)

When extensions or plugins register or unregister tools at runtime, Pi does not force a full system prompt rewrite. Instead, it computes a mathematical set diff between the executable tools and the transcript:

```typescript
// packages/agent/src/agent-loop.ts:346-361
const changes = getToolStateChanges(
  getCurrentTools([...context.messages, ...baseline]),
  (context.tools ?? []).map(toToolDeclaration),
);

// If changes occurred, a SystemMessage is inserted or patched:
const update = withToolChanges(
  { role: "system", content: "", timestamp: Date.now() },
  { toolsAdded: changes.toolsAdded, toolsRemoved: changes.toolsRemoved }
);
```

---

## 3. Memory & Persistence — Append-Only JSONL Merkle Trees

While OpenCode uses SQLite and Claude Code uses memory arrays, Pi implements a **branching Merkle DAG persisted entirely in append-only `.jsonl` files** (`packages/coding-agent/src/core/session-manager.ts`).

### Why an Append-Only JSONL Tree?
- **Zero In-Place Rewrites**: File corruption risk is virtually zero. Even if a process dies mid-write, previous entries remain 100% valid.
- **Instant Branching**: Rewinding to an earlier state or creating a branch never deletes history. A new branch simply creates a child entry referencing an older `parentId`.
- **Auditability**: Every model change, thinking level change, token usage snapshot, and context edit is immutably preserved in sequence.

```
[SessionHeader (id: root_001, cwd: /project)]
                      |
           [MessageEntry (User)]
                      |
       [MessageEntry (Assistant + ToolCall)]
                      |
           [MessageEntry (ToolResult)]
             /                     \
            /                       \  User rewinds and tries different prompt
           v                         v
[Branch A: MessageEntry]   [Branch B: MessageEntry (parentId: ToolResult)]
          |                                  |
[CompactionEntry]                  [MessageEntry (Assistant)]
```

### Session Entry Variants

```typescript
// packages/coding-agent/src/core/session-manager.ts:57-195
export interface SessionEntryBase {
  type: string;
  id: string;        // UUIDv7 (time-ordered)
  parentId: string | null;
  timestamp: string;
}

export type SessionEntry =
  | SessionMessageEntry         // User, Assistant, or ToolResult message
  | ThinkingLevelChangeEntry    // Dynamic reasoning effort changes (e.g. /thinking high)
  | ModelChangeEntry            // Mid-session model switch (e.g. /model claude-3-7-sonnet)
  | UsageEntry                  // Dedicated token and cost attribution
  | CompactionEntry             // Context compaction boundary with retained summary
  | BranchSummaryEntry          // Carries context from an abandoned branch into a new one
  | CustomEntry                 // Extension state persistence (ignored by LLM context)
  | CustomMessageEntry          // Extension-injected messages (participates in LLM context)
  | ContextEditEntry            // Append-only redaction or replacement of earlier entries
  | LabelEntry                  // Bookmarks and UI checkpoints
  | SessionInfoEntry;           // Custom session display metadata
```

### Append-Only Context Editing (`ContextEditEntry`)

If a user edits a prior prompt or an extension redacts a sensitive secret from a tool result, traditional agents rewrite the chat file. Pi leaves the original entry untouched and appends a `ContextEditEntry`:

```typescript
// packages/coding-agent/src/core/session-manager.ts:175-180
export interface ContextEditEntry extends SessionEntryBase {
  type: "context_edit";
  targetId: string;
  /** Null omits the target from model context. A value replaces only its content. */
  replacement: { content: ContextEditableContent } | null;
}
```

When building model context (`buildSessionContext`), Pi resolves the active leaf backwards to the root, applying any `ContextEditEntry` overrides dynamically!

---

## 4. Prompt Cache Warmer — Autonomous Latency & Cost Optimization

A standout architectural feature of Pi is its **Autonomous Prompt Cache Warmer** (`packages/coding-agent/src/core/cache-warmer.ts`).

### The Problem in Modern LLMs
Modern providers (Anthropic Claude, OpenAI, Google Gemini) offer prompt caching with strict **Time-To-Live (TTL)** windows (e.g., 5 minutes for Anthropic ephemeral cache, 1 hour for long retention). In an interactive coding session, human thinking time frequently exceeds 5 minutes. When the user sends their next prompt:
1. Cache has expired -> 100% full input token billing (e.g., 100,000 tokens billed at fresh write rate).
2. Time-to-First-Token (TTFT) latency spikes to 15–30 seconds while the provider recomputes the KV cache.

### The Economic Model of Cache Warming

Pi continuously evaluates an economic formula before deciding whether to ping the model:

$$\text{Expected Savings} = (P_{\text{continuation}} \times \text{MissCost}) - \text{WarmCost}$$

```typescript
// packages/coding-agent/src/core/cache-warmer.ts:15-26
const MAX_WARMING_AGE_MS = 60 * 60_000;              // Never warm longer than 1 hour
const MAX_IDLE_WARMING_AGE_MS = 30 * 60_000;         // Idle warming horizon
const CACHE_WARMING_MINIMUM_EXPECTED_SAVINGS = 0.05; // Must save at least $0.05
const IDLE_CONTINUATION_PROBABILITY = 0.15;          // 15% probability user continues while idle
```

### How the Warmer Executes
1. Pi determines the exact cache TTL: `getPromptCacheTtlMs(model, options)`.
2. It sets a timer at **90% of TTL** (`getCacheWarmingDelayMs`):
   ```typescript
   export function getCacheWarmingDelayMs(ttlMs: number): number | undefined {
     if (ttlMs <= 10_000) return undefined;
     return Math.max(1, Math.floor(Math.min(ttlMs * 0.9, ttlMs - 10_000)));
   }
   ```
3. When the timer triggers, Pi issues a **1-token output request** (`max_tokens: 1`) using the exact existing prompt prefix.
4. The provider reads the prefix from its existing cache (billing at the 90% discounted cache-read rate) and extends the TTL for another full cycle!
5. When the user eventually types, the model responds instantly with zero TTFT latency and full cache discount.

---

## 5. Context Architecture & System Prompt Engineering

Pi structures system prompts using a modular, XML-tagged section architecture (`packages/coding-agent/src/core/system-prompt.ts`):

```
+--------------------------------------------------------------------------+
|                     SYSTEM PROMPT SECTIONS                               |
|                                                                          |
|  [Preamble] (Untagged baseline identity and personality)                 |
|                                                                          |
|  <project_instructions path="/repo/AGENTS.md">                           |
|    Project conventions, test commands, code style                        |
|  </project_instructions>                                                 |
|                                                                          |
|  <skills>                                                                |
|    Available skill XML blocks and trigger syntax                         |
|  </skills>                                                               |
|                                                                          |
|  <rules>                                                                 |
|    Tool guidelines (bash, edit, read) + custom prompt guidelines         |
|  </rules>                                                                |
|                                                                          |
|  <cwd>/path/to/project</cwd>                                             |
+--------------------------------------------------------------------------+
```

### Tagged Sections Contract

```typescript
// packages/coding-agent/src/core/system-prompt.ts:46-50
/**
 * Ordered system prompt sections, keyed by name. `preamble` is untagged text;
 * every other section is wrapped in a tag of the same name so the model can
 * match later updates to it. These become SystemMessage.sections in the transcript.
 */
export type SystemPromptSections = Record<string, string>;
```

By wrapping distinct context domains in explicit XML tags, Pi allows extensions and session switches to perform atomic section diffing and surgical replacements without disturbing adjacent instructions.

---

## 6. Context Compaction Engine — Backward Safe Cuts & File Tracking

When context approaches window limits, Pi triggers its context compaction engine (`packages/coding-agent/src/core/compaction/compaction.ts`).

### Default Budget Configuration

```typescript
// packages/coding-agent/src/core/compaction/compaction.ts:148-152
export const DEFAULT_COMPACTION_SETTINGS: CompactionSettings = {
  enabled: true,
  reserveTokens: 16384,      // Reserve 16k tokens for assistant generation
  keepRecentTokens: 20000,   // Retain 20,000 tokens of recent history verbatim
};
```

### Backward Safe Cut Selection (`findCutPoint`)

A fatal flaw in naive compaction implementations is cutting conversation between an assistant's tool call and the tool's result, causing providers to reject the request due to orphaned tool calls.

Pi solves this with a reverse cut-point scanner:

```typescript
// packages/coding-agent/src/core/compaction/compaction.ts:453-500
export function findCutPoint(
  entries: SessionEntry[],
  startIndex: number,
  endIndex: number,
  keepRecentTokens: number,
): CutPointResult {
  // Finds only user messages or assistant messages (NEVER tool results)
  const cutPoints = findValidCutPoints(entries, startIndex, endIndex);
  if (cutPoints.length === 0) return { firstKeptEntryIndex: startIndex, turnStartIndex: -1, isSplitTurn: false };

  let accumulatedTokens = 0;
  let cutIndex = cutPoints[0];

  // Walk backwards from newest to oldest
  for (let i = endIndex - 1; i >= startIndex; i--) {
    const entry = entries[i];
    const messageTokens = sessionEntryToContextMessages(entry).reduce(
      (sum, message) => sum + estimateTokens(message),
      0,
    );
    if (messageTokens === 0) continue;
    accumulatedTokens += messageTokens;

    if (accumulatedTokens >= keepRecentTokens) {
      // Pick closest valid boundary at or after this entry
      cutIndex = cutPoints.find((candidate) => candidate >= i) ?? cutPoints[cutPoints.length - 1];
      break;
    }
  }
  return { firstKeptEntryIndex: cutIndex, turnStartIndex, isSplitTurn };
}
```

### Persistent File Operation Tracking

Compaction entries do not simply summarize text; they preserve structured metadata about what files were read and modified:

```typescript
// packages/coding-agent/src/core/compaction/compaction.ts:50-54
export interface CompactionDetails {
  readFiles: string[];
  modifiedFiles: string[];
}
```

When generating the summary, Pi injects the full accumulated list of files touched throughout the entire session lifecycle, ensuring the agent never loses awareness of workspace modifications made before the compaction horizon.

---

## 7. Tool System & File Mutation Queue Concurrency

Pi equips agents with a focused set of low-level tools (`packages/coding-agent/src/core/tools/`):
- `read`: Reads files with line limits and byte offsets.
- `edit`: Precise find-and-replace string patching.
- `write`: File creation and overwriting.
- `bash` / `powershell`: Shell command execution with stream capture.
- `grep`: High-speed regex search with per-line char bounds.
- `find`: File path globbing and pattern discovery.
- `ls`: Directory listing with formatting.

### Concurrency Protection: `withFileMutationQueue`

When multiple tools execute concurrently, two tools attempting to write to or edit the same file can cause race conditions or partial file corruption.

Pi introduces a **canonical path mutation lock** (`packages/coding-agent/src/core/tools/file-mutation-queue.ts`):

```typescript
// packages/coding-agent/src/core/tools/file-mutation-queue.ts:28-60
const fileMutationQueues = new Map<string, Promise<void>>();

export async function withFileMutationQueue<T>(filePath: string, fn: () => Promise<T>): Promise<T> {
  const key = await getMutationQueueKey(filePath); // Resolves realpath on disk
  const currentQueue = fileMutationQueues.get(key) ?? Promise.resolve();

  let releaseNext!: () => void;
  const nextQueue = new Promise<void>((resolveQueue) => {
    releaseNext = resolveQueue;
  });
  const chainedQueue = currentQueue.then(() => nextQueue);
  fileMutationQueues.set(key, chainedQueue);

  await currentQueue;
  try {
    return await fn();
  } finally {
    releaseNext();
    if (fileMutationQueues.get(key) === chainedQueue) {
      fileMutationQueues.delete(key);
    }
  }
}
```

**Key Benefit**: Operations targeting the same file are strictly serialized, while operations on different files run completely in parallel!

---

## 8. Sandboxing & Process Execution Model

### The Pi Philosophy on Permissions
As stated in `README.md`:
> *"Pi does not include a built-in permission system for restricting filesystem, process, network, or credential access. By default, it runs with the permissions of the user and process that launched it."*

Rather than introducing simulated in-process permission prompts that LLMs can frequently social-engineer around, Pi advocates for **true OS and container isolation**:

```
+--------------------------------------------------------------------------+
|                        CONTAINERIZATION PATTERNS                         |
+---------------------+----------------------------------------------------+
| Pattern             | Mechanism                                          |
+---------------------+----------------------------------------------------+
| Gondolin Extension  | Host retains auth & Pi CLI. All bash/read/edit     |
|                     | tools are routed into a local Linux micro-VM.       |
+---------------------+----------------------------------------------------+
| Plain Docker        | The entire `pi` process runs inside a container.   |
+---------------------+----------------------------------------------------+
| OpenShell           | Policy-controlled secure sandbox execution.        |
+---------------------+----------------------------------------------------+
```

### Pluggable Bash Operations (`BashOperations`)

To enable containerization without touching core agent code, `createBashTool` accepts pluggable operations:

```typescript
// packages/coding-agent/src/core/tools/bash.ts:59-78
export interface BashOperations {
  exec: (
    command: string,
    cwd: string,
    options: {
      onData: (data: Buffer) => void;
      signal?: AbortSignal;
      timeout?: number;
      env?: NodeJS.ProcessEnv;
    },
  ) => Promise<{ exitCode: number | null }>;
}
```

An extension (like Gondolin) simply overrides `BashOperations.exec` to transparently route all command execution across SSH, Docker exec, or a micro-VM hypervisor!

---

## 9. Subagent Coordination — Process Isolation & Workflow Chaining

Subagents in Pi are designed around **complete process and context isolation** (`packages/coding-agent/examples/extensions/subagent/index.ts`).

### Why Process Isolation?
- In-process subagents share heap space, environment variables, and memory, risking polluted global state.
- Pi spawns a completely independent `pi` child process in headless JSON mode (`--mode json`).
- Each subagent gets its own dedicated session file, its own context window, its own token usage ledger, and its own toolset.

### Three Execution Topologies

```
1. SINGLE MODE:
   [Parent Agent] ---> Spawns Subagent ---> [Result XML] ---> [Parent Agent]

2. PARALLEL MODE (Max 4 concurrent, up to 8 tasks):
                     +---> [Subagent Worker 1] ---+
   [Parent Agent] ---+---> [Subagent Worker 2] ---+---> [Merged Results]
                     +---> [Subagent Worker 3] ---+

3. CHAIN MODE:
   [Step 1: Explore] -> Output -> [{previous} in Step 2: Plan] -> Output -> [Step 3: Implement]
```

### Subagent Execution Code

```typescript
// packages/coding-agent/examples/extensions/subagent/index.ts:33-36
const MAX_PARALLEL_TASKS = 8;
const MAX_CONCURRENCY = 4;
const PER_TASK_OUTPUT_CAP = 50 * 1024; // 50 KB per task cap
```

When a subagent completes, its execution metrics and findings are wrapped into a clean, model-legible block:

```xml
<subagent id="worker_1" agent="scout" turns="3" cost="$0.0124">
  Found 4 authentication middleware endpoints in packages/server/src/auth.ts.
</subagent>
```

---

## 10. Terminal UI (TUI) — Differential Rendering & Terminal Graphics

Pi features an in-house built, zero-dependency terminal UI library (`@earendil-works/pi-tui`) that operates like a browser DOM engine for the terminal.

### Key Innovations in `pi-tui`:
1. **Differential Rendering (`tui.ts`)**: Maintains an in-memory 2D character/style grid buffer. On every frame, it computes a minimal ANSI diff, only updating changed cells. This prevents terminal flicker even at high-frequency LLM token streaming.
2. **Perceptually Uniform Color (`oklab.ts`)**: Implements the OKLab color model to compute gradients, theme highlights, and contrast ratios that look identical across dark and light terminal backgrounds.
3. **True Terminal Image Rendering (`terminal-image.ts`)**: Directly renders inline images inside the terminal using:
   - **Kitty Graphics Protocol** (native raw image transmission)
   - **iTerm2 Inline Images Protocol**
   - **Sixel Graphics**
4. **LaTeX to Terminal Math (`latex.ts`)**: A 37KB embedded parser that converts mathematical LaTeX equations into clean, aligned Unicode characters directly in terminal output.
5. **Pluggable Editor Components**: Allows swapping the standard text editor with custom components like a full Vim modal editor (`CustomEditor`).

---

## 11. End-to-End Execution Trace

Here is the exact lifecycle of an interactive user prompt in Pi:

```
Step 1: User Input
  User enters: "Refactor auth middleware and verify tests"
  -> AgentSession.prompt() receives text
  -> Appends SessionMessageEntry to append-only JSONL file (id: uuidv7)
  -> Triggers agentLoop()

Step 2: Turn Initialization
  -> prepareNextTurn(): loads model, checks reasoning effort
  -> declareToolChanges(): diffs active toolset, emits system delta if changed
  -> prepareRequest(): extensions can inject custom context or override parameters

Step 3: Streaming LLM Response
  -> messages converted to provider wire format via convertToLlm()
  -> streamAssistantResponse() calls @earendil-works/pi-ai
  -> EventStream pushes text deltas into TUI via differential rendering
  -> Model outputs tool call: bash("npm test")

Step 4: Tool Execution & Concurrency Lock
  -> Checks stopReason: if "length", aborts tool execution immediately!
  -> withFileMutationQueue(): locks target files if editing
  -> executeBashWithOperations(): spawns child process or delegates to micro-VM
  -> OutputAccumulator streams stdout/stderr
  -> truncateHead / truncateTail enforces 2,000 line / 50KB limits
  -> Emits ToolResultMessage and appends to JSONL

Step 5: Completion & Cache Warming
  -> Model analyzes output, concludes "All 12 tests passed."
  -> agent_end event emitted; AgentSession settles to idle
  -> CacheWarmer activates:
       * Estimates time to cache expiration (TTL 90%)
       * Computes expected savings formula
       * Schedules background 1-token output ping to keep KV cache hot!
```

---

## 12. Four-Way Comparison: Claude Code vs. Codex vs. OpenCode vs. Pi

| Architectural Dimension | Claude Code | Codex (`codex-rs`) | OpenCode | Pi (`pi-coding-agent`) |
|-------------------------|-------------|--------------------|----------|------------------------|
| **Primary Language** | TypeScript (Node.js) | Rust | TypeScript (Bun / Node) | TypeScript (Node / Bun) |
| **Runtime Paradigm** | Async/await + Events | Tokio actor threads | Effect-TS functional | Modular decoupled libraries |
| **Session Persistence** | Flat JSON / In-memory | SQLite graph store | SQLite WAL tables | **Append-only JSONL Merkle Tree** |
| **Branching & Rewind** | In-memory stack | Commit stack | Revert snapshot | **Tree DAG via parentId pointers** |
| **Context Updates** | Static full rewrite | Token-budgeted prompt | Baseline Epoch + Mid-Convo | **XML Tagged Sections + Tool Diffs** |
| **Prompt Cache Handling** | Static heuristics | State tracker | Explicit cache keys | **Autonomous Cache Warmer (Economics)** |
| **Compaction Strategy** | Single-pass summary | In-memory vs Remote | Dual (proactive + 400) | **Backward Safe Cuts + File Op Tracking** |
| **Tool Concurrency** | Basic Promise.all | Async task spawn | FiberSet | **Canonical Path Mutation Queue** |
| **Large Tool Outputs** | Memory slice | Memory byte truncate | Managed disk files | **Head/Tail/Middle Truncation + Cap** |
| **Sandboxing Strategy** | macOS Seatbelt | OS Seatbelt / Bubblewrap | Tri-state permissions | **Pluggable micro-VMs (Gondolin / Docker)** |
| **Subagent Architecture** | Ephemeral sessions | Thread coordination | SessionTable.parent_id | **Independent Child Processes (JSON mode)** |
| **Terminal UI Engine** | React / Ink | Crossterm / Ratatui | Ink / Custom | **Custom Differential TUI + Kitty/Sixel** |
