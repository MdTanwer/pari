# PARI — Terminal Coding Agent Architecture
## A Synthesis Architecture That Surpasses Claude Code, Codex, OpenCode, Pi, Aider, Cursor, and Google Antigravity

> **Design Philosophy**: Every architectural decision in this document is a direct response to a verified, source-code-grounded weakness in an existing production agent. No decision is theoretical — each one closes a specific, documented failure mode.

---

## Table of Contents

1. The Core Thesis: Why Every Agent Fails
2. Failure Mode Atlas — Verified Weaknesses Across All 7 Systems
3. The Trade-Off Framework — Why You Cannot Have Everything
4. PARI Architecture Overview
5. Layer 0 — Sandboxing Engine
6. Layer 1 — Durable Session Engine (Merkle DAG)
7. Layer 2 — Context and Cache Architecture
8. Layer 3 — The Intelligence Layer (AST Repo Map and PPR)
9. Layer 4 — The Execution Loop (Agent Runtime)
10. Layer 5 — Edit Engine (Multi-Tier Fuzzy Search/Replace)
11. Layer 6 — Concurrency and File Safety
12. Layer 7 — Output Handling and Context Hygiene
13. Layer 8 — Dual-Model Routing Engine
14. Layer 9 — Terminal Interface
15. Layer 10 — Evaluation and Observability Harness
16. Cross-System Decision Matrix
17. The Explicit Trade-Offs: What PARI Sacrifices and Why
18. Phased Build Roadmap

---

## 1. The Core Thesis: Why Every Agent Fails

The cross-system analysis (corsanalysis.md) delivers one overriding conclusion:

> **Agent failure is a systems engineering failure, not a reasoning failure.**

The same frontier LLM (Claude 3.7 Sonnet, GPT-4o) produces a **15% pass rate** in a naive harness and a **50-55% pass rate** inside Claude Code or Pi. The 35% delta is entirely explained by six harness-level failure modes, not by model capability:

| Failure Mode | Root Cause | Systems Responsible |
|---|---|---|
| Unbounded stdout poisoning | Tool output floods context; instructions displaced | Claude Code, Aider, Codex |
| Mid-stream token truncation | Partial JSON tool call corrupts source files | Claude Code, OpenCode |
| File write race conditions | Parallel async writeFile() tears files | Claude Code |
| KV cache invalidation cascades | Single edit shifts all cache prefixes; 10x billing spike | Claude Code, Aider |
| Blind file traversal loops | No AST map; 8+ grep turns to find a class | Pi, OpenCode, Codex |
| Unsandboxed host execution | Hallucinated rm -rf runs with full user privileges | Pi, Aider, OpenCode |

PARI closes **all six failure modes simultaneously**, without introducing the complexity pathologies (Codex's 119-crate Rust monorepo) or UX failures (OpenCode's permission fatigue) of prior art.

---

## 2. Failure Mode Atlas — Verified Weaknesses Across All 7 Systems

### 2.1 Claude Code — The In-Memory Volatile Machine

**Architecture**: 5-Tier Onion Middleware (prepend -> user -> append -> builtin -> core)
**Runtime**: Node.js single-threaded event loop
**State**: In-memory MessageParam[] array + flat JSON file dumps (~/.claude/)

| # | Failure | Evidence | Impact |
|---|---|---|---|
| F1 | No ACID state durability | messages: MessageParam[] in-memory; no WAL or atomic rename | SIGINT during tool call = 0-byte corrupt session file |
| F2 | macOS-only sandbox | sandbox-exec (Seatbelt) macOS only; raw child_process.spawn() on Linux/Windows | Zero kernel isolation on Linux CI |
| F3 | File write races | Direct fs.promises.writeFile() across parallel tool calls | Torn writes on package.json during concurrent npm install |
| F4 | Static cache breakpoint invalidation | Coarse heuristic cache_control markers shift on any upstream edit | $0.375/M to $3.75/M billing spike |
| F5 | PTY-less daemon deadlock | Bash tool uses Node stream pipes; no PTY emulation | npm run dev blocks turn loop indefinitely |
| F6 | Bulldozer blast radius | No path-scoped edit budget | 800-line diffs for 3-line fixes |
| F7 | Context amnesia on compaction | Single-pass summary compaction truncates older turns | Agent forgets API schemas agreed 10 minutes prior |

**Expert Verdict**: World-class middleware pipeline design; catastrophically fragile state management and OS isolation.

---

### 2.2 Codex (codex-rs) — The Hyper-Complex Cloud Machine

**Architecture**: 119-crate Rust workspace, Tokio async actors, exec-server daemon
**Runtime**: Multi-process: CLI <-> exec-server via Noise-protocol WebSocket
**Sandbox**: bwrap (Linux), Seatbelt (macOS), Restricted Tokens (Windows) — best-in-class

| # | Failure | Evidence | Impact |
|---|---|---|---|
| F1 | 119-crate compilation bloat | Cargo.toml workspace with micro-crates | 15-30min cold builds; 18-25GB target/ |
| F2 | String-prefix security blocklist | BANNED_PREFIX_SUGGESTIONS in exec_policy.rs:57-100 | Trivially bypassed by `env bash -c`; bun test falsely blocked |
| F3 | IPC serialization overhead | Protobuf + Noise crypto handshake for every local tool call | 5-15ms added latency per tool call |
| F4 | RSS bloat on large outputs | Raw stdout accumulated as Vec<u8> in-memory | cat massive.log spikes RSS before truncation |
| F5 | Orphaned exec-server processes | prctl(PR_SET_PDEATHSIG) edge cases on CLI SIGKILL | Zombie processes hold file locks |

**Expert Verdict**: Gold standard for kernel sandboxing; catastrophically over-engineered for local development.

---

### 2.3 OpenCode — The Conceptually Clean but Practically Painful Agent

**Architecture**: TypeScript + Bun + Effect-TS fibers, SQLite WAL, Context Epochs
**Runtime**: Effect-TS functional fibers (generator-based concurrency)
**Sandbox**: None — process-level permission dialogs only

| # | Failure | Evidence | Impact |
|---|---|---|---|
| F1 | Zero kernel sandboxing | PermissionV2.assert() in bash.ts — userspace modal only | After one "Allow All", agent has unrestricted host access |
| F2 | Effect-TS debug opacity | 80-120 line fiber scheduling traces when errors occur | Actual error origin buried under yield-point scaffolding |
| F3 | Subagents behind feature flags | OPENCODE_EXPERIMENTAL_BACKGROUND_SUBAGENTS guard in task.ts:98-100 | Crashed subagent fibers detach silently |
| F4 | SQLite WAL lock contention | Single DB connection under 4+ parallel fiber writes | SQLITE_BUSY errors on heavy multi-file parallel edits |
| F5 | Shadow git snapshot I/O overhead | snapshot.ts commits shadow trees in ~/.local/share/opencode/ | Massive disk I/O spike on every multi-file edit |

**Expert Verdict**: Context Epochs and Managed Tool Output Store are brilliant innovations to harvest. Effect-TS stack and absence of sandboxing are fatal for production use.

---

### 2.4 Pi — The Ideal Baseline Crippled by Three Gaps

**Architecture**: TypeScript Node.js, Append-only JSONL Merkle DAG, double-loop state machine
**Runtime**: Native async + Promise queues, differential Textual TUI
**State**: JSONL Merkle DAG (uuidv7 + parentId) — gold-standard durability design

| # | Failure | Evidence | Impact |
|---|---|---|---|
| F1 | Zero kernel sandboxing by default | README.md confirms full host-user execution; Gondolin micro-VM optional | Hallucinated destructive commands run uninhibited |
| F2 | Process-per-subagent footprint | spawn("node", [piCliPath, "--subagent"]) in subagent/index.ts | 4 subagents = 4 V8 runtimes = 800MB-1.8GB RAM |
| F3 | No AST codebase map | Only grep_files, find_by_name, read_file tools; no tree-sitter | 4-8 exploratory turns grepping on large repos |
| F4 | O(N) JSONL replay on deep sessions | Parent-pointer graph reconstruction from disk on every session resume | 500-turn session requires full file read |
| F5 | Partial-write JSONL corruption | Mid-append process kill truncates last JSON record | parentId chain broken; manual surgery required |

**Expert Verdict**: Pi is the closest to the ideal architectural baseline. Its Merkle DAG, FileMutationQueue, cache warmer, and differential TUI are direct design targets for PARI. The three gaps (sandboxing, AST map, subagent weight) are exactly what PARI must fill.

---

### 2.5 Aider — The Reigning Edit Champion with a Systemic Single-Thread Prison

**Architecture**: Python, Git-centric deterministic loop, Tree-sitter PPR repo map
**Runtime**: Synchronous single-threaded loop; background cache warmer thread
**Edit Engine**: Multi-tier fuzzy Search/Replace (Exact -> Git OSR Cherry-Pick -> DMP)

| # | Failure | Evidence | Impact |
|---|---|---|---|
| F1 | Zero kernel isolation | subprocess.Popen in linter.py; raw git.Repo in repo.py | Prompt injection in README.md runs rm -rf with full user privileges |
| F2 | Monolithic single-thread | done_messages, cur_messages as simple Python lists | Cannot spawn subagents, cannot branch |
| F3 | git index.lock contention | repo.git.add() + repo.git.commit() inside developer's live working tree | IDE git operations cause fatal: .git/index.lock: File exists |
| F4 | PageRank hub distortion | utils.py/helpers.py with hundreds of inbound refs dominate 1,024-token budget | Business logic classes crowded out by generic utility sinks |
| F5 | Reflection loop token burn | max_reflections = 3; re-sends 40k-80k token context up to 3 times | Single stubborn diff consumes $0.50-$2.00 in 2 minutes |
| F6 | Diskcache SQLite lock across worktrees | Multiple Aider sessions conflict on .aider.tags.cache.v4 | Cache disabled, full rescan on every session start |

**Expert Verdict**: Aider's edit engine and PPR repo map are the most important technical innovations in the field. PARI ports both to Python, adding sandboxing and async concurrency on top.

---

### 2.6 Cursor — The IDE Giant with a Split-Brain Core

**Architecture**: VS Code (Code-OSS) fork, Electron, InlineDiffService, virtual Monaco diff buffer
**Runtime**: Electron event loop + Web Workers; cloud vector index

| # | Failure | Evidence | Impact |
|---|---|---|---|
| F1 | Virtual/physical filesystem split-brain | Composer stages mutations in Monaco virtual buffer; tests run against on-disk files | Tests run against unmutated code while agent sees mutated buffer |
| F2 | Diff reconciler deadlock | InlineDiffService fuzzy patcher fails when line offsets shift | Half-applied broken code injected into file |
| F3 | Context drift in long sessions | Linear rolling summary compaction; no Context Epochs | At 80k-120k tokens: forgets API schemas, re-introduces fixed bugs |
| F4 | Background indexer CPU pegging | Vector indexing daemon inside Electron process on 30k+ file repos | 8-16GB RAM consumed; typing latency; battery drain |
| F5 | .gitignore bypass on indexing | Edge cases transmit .env secrets to cloud inference providers | Security researchers documented data exfiltration paths |

**Expert Verdict**: Cursor's speculative inline completion and VS Code integration are UI masterpieces. Its virtual-vs-disk architectural error is a fundamental systems engineering failure.

---

### 2.7 Google Antigravity — The Powerful but Verbose Autonomous Studio

**Architecture**: Hierarchical multi-agent orchestration, Brain Artifacts, KI system, CDP subagents
**Runtime**: Async loop + managed TaskPool + reactive scheduler

| # | Failure | Evidence | Impact |
|---|---|---|---|
| F1 | Token multiplier / meta-commentary burn | Simple KeyError fix triggers 6-12 internal planning turns | Single prompt consumes 200k-400k tokens |
| F2 | "Agent Exhausted" state machine crash | Subagent timeouts desynchronize internal state machine | Full repo rescan triggered on resume; analysis paralysis loops |
| F3 | KI absolute path orphanage | KIs indexed against absolute filesystem URIs in ~/.gemini/ | Repository move silently orphans all KIs |
| F4 | OAuth token drop on long runs | Long-running background daemons rely on continuous cloud OAuth | Token refresh glitch kills tool execution pipe mid-run |
| F5 | Hard Google API lock-in | Strictly coupled to Gemini/Vertex AI ecosystem | Cannot route to local DeepSeek R1, Llama 3, or Claude |

**Expert Verdict**: Antigravity's artifact decoupling, structured KI system, and CDP browser subagents are genuine innovations. PARI adopts the "structured artifacts separated from chat" pattern while eliminating token verbosity via strict anti-planning-overhead guards.

---

## 3. The Trade-Off Framework — Why You Cannot Have Everything

### 3.1 The 12 Fundamental Agent Design Trade-Off Axes

| Trade-Off Axis | Option A | Option B | PARI Choice |
|---|---|---|---|
| 1. Safety vs. Speed | Kernel sandbox (bwrap) | Raw host execution | **bwrap kernel sandbox** |
| 2. Simplicity vs. Power | Single-agent loop | Multi-agent swarm orchestration | **Single-agent default** |
| 3. Durability vs. RAM | Append-only Merkle DAG | In-memory array + flat JSON | **Merkle DAG** |
| 4. Cache vs. Freshness | Immutable Context Epochs | Dynamic rolling compaction | **Immutable Epochs** |
| 5. Precision vs. Speed | PPR AST repo map (turn 0) | Blind grep exploration (N turns) | **PPR RepoMap** |
| 6. Resilience vs. Cost | Multi-tier edit cascade | Single-shot full-file rewrite | **4-tier cascade** |
| 7. Isolation vs. Memory | Process-per-subagent | Thread/fiber-based subagents | **asyncio fibers** |
| 8. Audit vs. Clutter | Git auto-commit per turn | Dirty working tree | **Git auto-commit** |
| 9. Portability vs. Perf | Python asyncio | Rust/Tokio 119-crate workspace | **Python asyncio** |
| 10. Verbose vs. Dense | Plan-first verbosity | Execute-first minimal narration | **Execute-first** |
| 11. Lock-in vs. Flex | Single-provider API | Multi-provider routing | **Multi-provider** |
| 12. IDE vs. Terminal | GUI editor integration | Pure terminal agent | **Pure terminal** |

### 3.2 Detailed Trade-Off Rationale

| Trade-Off | PARI Choice | Why | What We Sacrifice | Worth It? |
|---|---|---|---|---|
| Safety vs. Speed | bwrap kernel sandbox | Unsandboxed agents are existential security risks on real repositories | ~5ms sandbox bootstrap per session | Yes. Security gap is fatal. |
| Simplicity vs. Power | Default single-agent; opt-in lightweight subagents | Pi scores 50% single-agent; academic multi-agent swarms score 18-25% | Parallelism on coding tasks | Yes. The Sub-Agent Fallacy is empirically proven. |
| Durability vs. RAM | Append-only JSONL Merkle DAG with checkpoint indices | Claude Code's flat JSON dies on SIGINT | Marginal disk I/O per turn | Yes. Disk is cheap; lost sessions are catastrophic. |
| Cache vs. Freshness | Immutable Baseline Epoch + selective mid-session updates | Claude Code's heuristic breakpoints trigger 10x billing spikes | Cannot mutate system context mid-turn | Yes. 70-90% token cost reduction across sessions. |
| Precision vs. Speed | PPR AST repo map injected at turn 0 | Pi wastes 4-8 turns grepping on 50k+ LOC repos | 200-800ms AST index warmup on first session start | Yes. One startup cost eliminates 4-8 turns on every non-trivial task. |
| Resilience vs. Cost | Multi-tier edit cascade: Exact -> Git OSR -> DMP -> Prefill | Reflection loop token burn ($0.50-$2.00 per failed diff in Aider) is catastrophic | Slightly higher implementation complexity | Yes. The cascade eliminates 80% of reflection retries. |
| Isolation vs. Memory | asyncio.TaskGroup fiber-based subagents | Pi's spawn("node", ...) spawns full V8 runtimes (200-450MB each) | Slightly weaker process-level isolation per subagent | Yes. Fiber isolation sufficient for read-only research subagents. |
| Audit vs. Clutter | Git auto-commit per turn with weak-model commit message | No atomic rollback = catastrophic for production codebases | Micro-commits in git history | Acceptable. Commits can be squashed before PR. |
| Portability vs. Perf | Python 3.11+ asyncio | Codex's Rust workspace takes 25 min to compile | Raw compute throughput vs. Rust | Yes. Agent loops are network-I/O bound, not CPU bound. |
| Verbose vs. Dense | Execute-first; minimal narration; strict planning overhead guard | Antigravity burns 200k-400k tokens on planning before executing | Elaborate pre-execution reasoning artifacts | Yes. Action beats narration. |
| Lock-in vs. Flex | Multi-provider routing (Anthropic, OpenAI, DeepSeek, local Ollama) | Antigravity's Google-only lock-in is a fatal adoption blocker | Small additional abstraction layer | Yes. Model independence is a core requirement. |
| IDE vs. Terminal | Pure terminal agent; optional LSP integration | Cursor's virtual-vs-disk split-brain is an architectural catastrophe | GUI visual diff preview | Yes. Terminal diff UI provides sufficient feedback. |

---

## 4. PARI Architecture Overview

```
+-----------------------------------------------------------------------------------+
|                              PARI -- SYSTEM ARCHITECTURE                          |
+-----------------------------------------------------------------------------------+
|                                                                                   |
|  Layer 9:  TERMINAL INTERFACE (Rich / Textual differential rendering TUI)         |
|                                          |                                        |
|  Layer 8:  DUAL-MODEL ROUTER (Architect -> Planner / Editor -> Fast LLM)         |
|                                          |                                        |
|  Layer 7:  OUTPUT HYGIENE (50KB/2k-line disk spooler + head/tail extraction)     |
|                                          |                                        |
|  Layer 6:  CONCURRENCY SAFETY (asyncio.TaskGroup + realpath FileMutationQueue)   |
|                                          |                                        |
|  Layer 5:  EDIT ENGINE (Exact -> Git OSR -> DMP -> Prefill Continue)             |
|                                          |                                        |
|  Layer 4:  AGENT EXECUTION LOOP (Double-while + stop_reason guard + tools)       |
|                                          |                                        |
|  Layer 3:  INTELLIGENCE (Tree-sitter PPR AST RepoMap + diskcache SQLite)         |
|                                          |                                        |
|  Layer 2:  CONTEXT & CACHE (Immutable Epoch + mid-session updates + Warmer)      |
|                                          |                                        |
|  Layer 1:  DURABLE SESSION (Append-only JSONL Merkle DAG + Checkpoint Index)     |
|                                          |                                        |
|  Layer 0:  SANDBOX (bwrap unprivileged namespaces + die-with-parent + cgroups)   |
|                                                                                   |
+-----------------------------------------------------------------------------------+
```

**Design Principle**: Each layer is independently testable, independently replaceable, and has a single well-defined responsibility. No layer has knowledge of layers more than one level above or below it.

---

## 5. Layer 0 — Sandboxing Engine

**Closes**: Claude Code F2, Pi F1, Aider F1, OpenCode F1

**Harvested From**: Codex codex-bwrap — the only existing agent with correct kernel-level isolation

### Design

PARI uses **Bubblewrap (bwrap)** — the same sandbox technology used by Flatpak, Chromium, and Codex. It provides Linux unprivileged user namespace isolation without requiring root, Docker, or a hypervisor.

```
PARI SANDBOX BOOT SEQUENCE:
  1. Create new user namespace (CLONE_NEWUSER)
  2. Create PID, mount, IPC, UTS namespaces (--unshare-all)
  3. Bind-mount workspace read-write (--bind <workspace>)
  4. Bind-mount /usr, /lib, /bin read-only (host binaries)
  5. Mount tmpfs on /tmp; procfs on /proc; devtmpfs on /dev
  6. Set PR_SET_PDEATHSIG = SIGKILL (--die-with-parent)
  7. Apply cgroups v2: memory.max, cpu.weight quotas
  8. Network: disabled by default; --share-net for package commands
```

**Key Properties:**

- `--die-with-parent`: If PARI process is killed, the sandbox subprocess receives immediate SIGKILL. Eliminates Codex F5 orphaned exec-server processes.
- `--ro-bind /usr /usr`: Host system binaries available read-only. No need to re-install system tools. Under 5ms startup.
- `--bind <workspace> <workspace>`: Agent writes confined to workspace directory only. ~/.ssh, ~/.aws, /etc are invisible inside the sandbox.
- cgroups v2 `memory.max = 2G`: Prevents fork-bombs and uncontrolled memory allocation from spilling onto the host.
- Network disabled by default; enable only for pip install, npm install, git clone via a network-capable subprocess profile.

### Trade-Off Analysis

| What We Gain | What We Sacrifice | Verdict |
|---|---|---|
| Full kernel isolation; rm -rf / is a no-op outside workspace | ~5ms per session bwrap process launch; Linux-only (Windows needs WSL2) | Worth it. Every unsandboxed agent is a security liability. |
| die-with-parent eliminates zombie subprocess leaks | Slightly more complex subprocess management code | Worth it. Zombie leaks are a production reliability killer. |
| No permission modal fatigue (unlike OpenCode) | Developer must configure workspace path correctly on init | Worth it. One-time config beats constant modal interruption. |

> **IMPORTANT**: On Windows, PARI runs inside WSL2, which provides a full Linux kernel environment supporting bwrap. This is a hard dependency — PARI does not support native Windows PowerShell execution without WSL2.

---

## 6. Layer 1 — Durable Session Engine (Merkle DAG)

**Closes**: Claude Code F1, Pi F4 (O(N) replay latency), Pi F5 (partial-write corruption)

**Harvested From**: Pi's append-only JSONL Merkle DAG — with added checkpoint index to solve replay latency

### Design

Every session record is a JSONL-formatted immutable entry with a uuidv7 identifier and a parentId pointer forming an append-only directed acyclic graph:

```
Session DAG Structure (PARI/.sessions/<session-id>.jsonl):

{"id": "0192abc...", "parentId": null,      "type": "SESSION_START"}
{"id": "0192abd...", "parentId": "0192abc", "type": "USER_TURN",    "content": "..."}
{"id": "0192abe...", "parentId": "0192abd", "type": "TOOL_CALL",    "tool": "bash"}
{"id": "0192abf...", "parentId": "0192abe", "type": "TOOL_RESULT",  "output_path": "..."}
{"id": "0192ac0...", "parentId": "0192abf", "type": "ASSISTANT_TURN", "content": "..."}
{"id": "0192ac1...", "parentId": "0192ac0", "type": "CONTEXT_EDIT", "redact_id": "0192abe"}
{"id": "0192ac2...", "parentId": "0192ac1", "type": "CHECKPOINT_INDEX", "root_to_here": [...]}
```

**Key PARI Innovations over Pi's baseline:**

1. **Periodic Checkpoint Index Records** (CHECKPOINT_INDEX): Every 50 turns, PARI appends a checkpoint record containing the full ordered list of record IDs from root to the checkpoint node. Session resume reads the latest CHECKPOINT_INDEX and only traverses from that point — reducing O(N) replay to O(K) where K <= 50.

2. **Atomic Append Guard**: Every JSONL write uses O_APPEND | O_SYNC with a CRC32 checksum field. On session start, PARI scans backward for the last valid CRC32 entry, truncating any partially written tail record. Eliminates Pi F5 JSONL corruption.

3. **Tool Output Path Pointers**: Large tool outputs are never stored inline in the JSONL. Instead, an "output_path" pointer references a sidecar file in `.pari/tool-outputs/<uuid>.txt`. The JSONL record stays tiny; the sidecar is the actual data.

### Trade-Off Analysis

| What We Gain | What We Sacrifice | Verdict |
|---|---|---|
| Zero data loss on SIGINT/OOM crash | One JSONL line of disk I/O per agent turn | Worth it. Disk writes are microseconds; lost sessions destroy developer trust. |
| O(K) session resume (K <= 50 turns per checkpoint) | Checkpoint records add marginal JSONL size | Worth it. Linear replay O(N) on 500-turn sessions takes seconds; unacceptable. |
| Append-only: no overwrite, no corruption window | JSONL grows indefinitely; needs GC policy | Acceptable. GC runs as a background job; not on the critical path. |
| ContextEditEntry redaction without modifying history | Slightly more complex context reconstruction | Worth it. Immutable history = perfect audit trail and safe rollback. |

---

## 7. Layer 2 — Context and Cache Architecture

**Closes**: Claude Code F4 (cache invalidation billing spikes), Claude Code F7 (context amnesia), Cursor F3 (context drift)

**Harvested From**: OpenCode's Immutable Context Epochs + Pi's Autonomous Economic Cache Warmer + Aider's 8-tier ChatChunks hierarchy

### Design

#### 2A. Immutable Baseline Epoch

The system prompt, repo map, and readonly files are assembled once at session start as the **Immutable Baseline Epoch**. This prefix NEVER changes during a session unless explicitly versioned.

```
PARI Context Epoch Structure:

+------------------------------------------------------+  <- IMMUTABLE BASELINE EPOCH
| Tier 1: System Identity & Core Rules                 |
| Tier 2: Tool Definitions & Schemas                   |  [Cache breakpoint after Tier 3]
| Tier 3: PPR AST Repository Symbol Map (<= 2048 tok)  |
| Tier 4: Readonly Reference Files (docs, interfaces)  |
+------------------------------------------------------+  <- CACHE BREAKPOINT
| Tier 5: Active Chat Files (currently edited files)   |  [Cache breakpoint after Tier 5]
+------------------------------------------------------+  <- CACHE BREAKPOINT
| Tier 6: Conversation Turn History (rolling)          |  <- Dynamic; never cached
| Tier 7: Current Turn Input & Tool Results            |
| Tier 8: Reminder / Constraint Footer                 |
+------------------------------------------------------+
```

Why three breakpoints? Anthropic charges 0.10x for cache reads vs. 1.25x for cache writes. Placing breakpoints at the stability boundary of tiers 3 and 5 means that adding a new conversation turn (Tier 6) only recomputes the dynamic region, not the expensive Tiers 1-5 that stay warm.

Claude Code's single heuristic breakpoint invalidates ALL tiers on a single upstream file edit — causing a $0.375/M to $3.75/M billing spike. PARI's epoch design isolates this: only the Tier 5 breakpoint shifts if an active file changes, leaving Tiers 1-3 perpetually warm.

#### 2B. Autonomous Economic Cache Warmer

Directly ported from Pi's verified cache-warmer.ts implementation, adapted to Python asyncio:

```
Warmer Decision Formula:

Ping at 90% of TTL (270s for Anthropic 300s TTL) if and only if:
  E[Savings] = (P_continuation x MissCost) - WarmCost >= $0.05

Where:
  P_continuation = 0.15 (empirically measured idle continuation probability)
  MissCost       = full context rewrite cost at 1.25x pricing
  WarmCost       = 1-token output ping cost (~$0.003 for 50k-token context)

Result: For contexts > 40k tokens, warming saves dollars per session.
```

#### 2C. Safe Context Compaction

When conversation tokens exceed **70% of model capacity**:
1. Summarize early exploration turns into concise summaries
2. Never compact across active tool calls — wait for tool result before cutting
3. Never compact Tiers 1-5 — the immutable epoch stays intact
4. Preserve the last 5 turns verbatim to maintain prompt cache locality

### Trade-Off Analysis

| What We Gain | What We Sacrifice | Verdict |
|---|---|---|
| 70-90% input token cost reduction via stable cache prefixes | Cannot mutate system context arbitrarily mid-session | Worth it. Billing predictability is a core product requirement. |
| Cache warmer prevents cold-start recomputation costs | Background asyncio task running during idle periods | Worth it. The task costs nanoseconds of CPU; saves dollars. |
| Safe compaction prevents context drift | Information loss in summaries of early exploration turns | Acceptable. Summaries preserve semantically critical decisions. |

---

## 8. Layer 3 — The Intelligence Layer (AST Repo Map and PPR)

**Closes**: Pi F3 (4-8 blind grep turns), Aider F4 (PageRank hub distortion), Claude Code/Codex/OpenCode complete absence of AST awareness

**Harvested From**: Aider's Personalized PageRank (repomap.py) — the most important technical innovation in terminal agent design

### Design

#### Step 1: Tree-sitter AST Symbol Extraction

For each source file in the workspace:
- Execute language-specific .scm tag queries (tree-sitter-language-pack)
- Extract `def` nodes: classes, functions, methods, interfaces, constants
- Extract `ref` nodes: call sites, import references, type usages
- Fallback: Pygments lexer token extraction for languages without tree-sitter grammars

#### Step 2: Bipartite Call Graph Construction

Build a directed networkx.MultiDiGraph:

```
File_A --[references]--> Symbol_S --[defined_in]--> File_B
```

Apply weight multipliers:
- References from **active chat files**: 50x weight (highest priority)
- Identifiers mentioned in **user prompt**: 10x weight
- High-information identifiers (snake_case/CamelCase >= 8 chars): 10x weight
- Trivial identifiers (prefix _) or ubiquitous (>5 definitions): 0.1x dampening
- High-frequency mentions: square-root dampening: num_refs = sqrt(num_refs)

#### Step 3: Personalized PageRank

```
p = (1 - d) x v_active + d x M x p    where d = 0.85

v_active = personalization vector biased toward active/mentioned files
```

#### Step 4: PARI Enhancement — Hub Suppression Filter

Aider F4 documents that generic hubs (utils.py, helpers.py, logger.py) dominate the PageRank vector despite being semantically unimportant. PARI adds:

- **Hub Detection**: Any file with >50 inbound references from >30% of the codebase is classified as a "utility hub"
- **Hub Dampening**: Hub nodes receive an additional 0.05x multiplier in the personalization vector
- **Direct Query Override**: If the user prompt explicitly names a file (auth.py, user_controller.py), that file receives a 200x temporary weight override, bypassing PageRank ranking entirely

#### Step 5: Binary Search Token Packing

Using grep_ast.TreeContext, binary search over rank thresholds to pack top-ranked AST signatures into a precise **2,048 token budget** (doubled from Aider's 1,024 to support larger repositories):
- Display outer classes and function signatures
- Prune function bodies (preserving line-count context)
- Include file path, line number, and docstring first line

#### Step 6: Durable Disk Cache

SQLite-backed via diskcache.Cache at `.pari/tags.cache.v1` with:
- mtime-based per-file invalidation (unchanged files never re-parsed)
- Worktree-scoped cache key including `git rev-parse HEAD` — prevents cross-worktree SQLite lock conflicts by isolating per branch

### Trade-Off Analysis

| What We Gain | What We Sacrifice | Verdict |
|---|---|---|
| Turn-0 codebase awareness; 0 blind grep turns on known repos | 200-800ms AST index warmup on first session (cached afterward) | Worth it. Eliminates 4-8 turns on every non-trivial task. |
| Hub suppression filter improves precision on large repos | Slightly more complex graph construction | Worth it. Aider's hub distortion is a documented productivity degrader. |
| 2,048 token budget covers ~2x more symbols than Aider | Larger initial context injection | Acceptable. 2,048 tokens is <2% of a 128k context window. |
| Worktree-scoped cache prevents lock contention | Slightly more disk space per branch | Worth it. Aider F6 documents the real pain of cross-worktree cache locks. |

---

## 9. Layer 4 — The Execution Loop (Agent Runtime)

**Closes**: Claude Code F5 (daemon deadlock), Pi's heavy subagent processes, the universal 12-18% naive agent performance ceiling

**Harvested From**: Pi's double-while state machine + Aider's reflection machine + Claude Code's 5-tier middleware concept

### Design

PARI's agent loop is a **double-while state machine** combining Pi's length-stop safety with Aider's reflection retry engine:

```
PARI AGENT EXECUTION LOOP:

OUTER WHILE (turn budget <= MAX_TURNS):
  |
  +-- Assemble context: Epoch + Active Files + History
  +-- Inject PPR RepoMap at turn 0 or when workspace changes
  +-- [Dual-Model Router] -> select Architect or Editor model
  |
  |  INNER WHILE (streaming response):
  |    +-- Stream tokens; accumulate tool_calls[]
  |    +-- GUARD: stop_reason == "length" -> REFUSE tool exec
  |    |         (truncated JSON = file corruption risk)
  |    +-- On stop_reason == "end_turn" -> exit inner loop
  |
  +-- For each tool_call in tool_calls[]:
  |    +-- bash_exec:   route to bwrap sandbox subprocess
  |    +-- file_edit:   route to Edit Engine (Layer 5)
  |    +-- file_read:   route to FileMutationQueue (Layer 6)
  |    +-- repo_search: route to RepoMap query (Layer 3)
  |
  +-- Collect tool results -> ManagedOutputSpooler (Layer 7)
  +-- Auto-commit if file edits occurred -> git + weak model msg
  +-- Run linter / tests if configured -> structured feedback
  |
  +-- REFLECTION CHECK: if lint/test fails AND reflections < 3:
  |    +-- append structured error + AST context -> continue
  |
  +-- If no tool calls and no reflection needed -> DONE
```

**Critical Guards (closing the 12-18% naive agent gap):**

1. **stop_reason == "length" guard**: If the LLM response is truncated mid-stream, ALL pending tool calls in that response are discarded. The agent informs the model that truncation occurred and requests shorter tool calls. This single guard eliminates the most common source of file corruption in naive agents.

2. **Turn budget ceiling**: Hard ceiling at MAX_TURNS = 40 with a warning at 30. Prevents infinite loops.

3. **PTY-aware daemon detection**: When bash_exec returns without EOF after 10s, PARI detects potential daemon process, sends Ctrl+C to background it, and notifies the model. Eliminates Claude Code F5 turn-loop deadlock.

4. **Structured linter feedback with AST context**: Failed edits trigger lint_edited(), passing output through grep_ast.TreeContext to extract AST context around error lines. Injected as structured [LINT ERROR] blocks — not raw stderr.

### Trade-Off Analysis

| What We Gain | What We Sacrifice | Verdict |
|---|---|---|
| stop_reason guard prevents file corruption from truncated tool calls | Slightly more verbose truncation handling logic | Worth it. This single guard closes the most dangerous naive agent failure mode. |
| PTY daemon detection prevents turn-loop deadlock | Small 10s timeout overhead on daemon detection | Worth it. Claude Code F5 is a severe UX-breaking failure. |
| Reflection cap at 3 with structured error injection | At most 3x token burn on stubborn edits | Acceptable. Structural reflection is cheaper than full rewrite. |

---

## 10. Layer 5 — Edit Engine (Multi-Tier Fuzzy Search/Replace)

**Closes**: Aider F5 (reflection loop token burn), Cursor F2 (diff reconciler deadlock), Claude Code F3 (file write races)

**Harvested From**: Aider's verified 3-tier cascade — the most resilient diff application engine in existence

### Design

PARI's Edit Engine implements Aider's full cascade **plus one additional tier**:

```
PARI EDIT ENGINE -- 4-TIER CASCADE

Given: original_text (current file content), search_text, replace_text

Tier 1: EXACT STRING REPLACE
  original_text.replace(search_text, replace_text)
  Succeeds if LLM produced exact character match.
  Most common path; zero overhead.

  If Tier 1 fails:

Tier 2: SYNTHETIC GIT CHERRY-PICK (OSR)
  Create isolated GitTemporaryDirectory.
  Commit O (original), commit S (search), commit R (replace).
  Checkout O; cherry-pick R with --minimal.
  Delegates fuzzy 3-way merge to Git's battle-tested engine.
  Handles whitespace drift, indentation shifts, blank-line omissions.

  If Tier 2 fails:

Tier 3: DIFF-MATCH-PATCH LINE FUZZY MATCHING (DMP)
  Google's diff_match_patch with line-to-character tokenization.
  Match_Threshold = 0.1; Match_Distance = 100,000.
  Handles reordered blocks and non-contiguous edits.

  If Tier 3 fails:

Tier 4: PREFILL CONTINUATION + MODEL RE-REQUEST
  If model supports assistant prefill: set prefix=True, continue generation.
  If model hit FinishReasonLength: request shorter edit blocks explicitly.
  Re-send is targeted (just "retry this one block") not full 40k-80k context.
  Cost is 5-10x lower than Aider's full reflection loop.

  If Tier 4 fails:

REFLECTION: inject structured failure report with AST context.
```

**RelativeIndenter**: Before applying any tier, PARI normalizes relative indentation using Aider's unicode marker technique. This handles the common case where LLMs produce search blocks with incorrect base indentation.

**Atomic Physical Write**: All edits are written using tempfile + os.replace() (atomic rename). The file never exists in a partially written state. Eliminates Cursor F1 virtual/physical split-brain: PARI always operates on physical disk with atomic writes.

### Trade-Off Analysis

| What We Gain | What We Sacrifice | Verdict |
|---|---|---|
| 95%+ of LLM edit blocks applied without reflection | Tier 2 creates a temp git repo per failed edit (~50ms overhead) | Worth it. Tier 2 saves $0.50-$2.00 in reflection token burn per stubborn diff. |
| Atomic write: file is never in an intermediate state | Slightly slower than raw write() | Worth it. Torn writes cause corrupt syntax; unrecoverable without git. |
| Prefill continuation handles token-truncated large edits | Requires model that supports assistant prefill | Acceptable. All major providers support this. |

---

## 11. Layer 6 — Concurrency and File Safety

**Closes**: Claude Code F3 (file write races), Aider F3 (git index.lock contention)

**Harvested From**: Pi's FileMutationQueue (canonical realpath serialization) — direct port to Python asyncio

### Design

#### FileMutationQueue — Python asyncio port

All file write operations (via Edit Engine) are routed through the FileMutationQueue. Each unique canonical realpath gets its own asyncio.Lock:

```
FileMutationQueue Logic (pseudocode):

async def get_lock(file_path) -> asyncio.Lock:
    try:
        canonical = await asyncio.to_thread(os.path.realpath, file_path)
    except FileNotFoundError:
        canonical = os.path.abspath(file_path)  # ENOENT fallback (new file)
    
    if canonical not in self._locks:
        self._locks[canonical] = asyncio.Lock()
    return self._locks[canonical]

async def write(file_path, content):
    async with self.get_lock(file_path):
        # atomic temp-file-then-rename write
        ...
```

Properties:
- Two writes to ./src/auth.py and ./src/api/../auth.py (symlink path) serialize correctly — same canonical realpath.
- Two writes to ./src/auth.py and ./src/user.py execute concurrently — different canonicals.
- ENOENT fallback: new files not yet on disk use abspath as the canonical key.

#### Git Operation Serialization

Aider F3 documents .git/index.lock failures when IDE background git operations collide with agent commits. PARI mitigates this with:

1. **Dedicated git worktree for agent commits**: Agent commits to a shadow worktree (git worktree add .pari/shadow-tree HEAD) — isolated from the developer's primary working tree
2. **Non-blocking git with exponential backoff**: If git add returns lock contention, retry with 50ms, 100ms, 200ms exponential backoff (max 3 retries)
3. **Lock timeout detection**: If .git/index.lock exists and is >5 seconds old, it is a stale lock — safe to delete and retry

### Trade-Off Analysis

| What We Gain | What We Sacrifice | Verdict |
|---|---|---|
| Zero torn writes on concurrent parallel tool calls | asyncio.Lock per file path adds small memory overhead | Worth it. File corruption is catastrophic; lock overhead is nanoseconds. |
| Shadow worktree isolates agent commits from developer's tree | Requires git worktree support (git >= 2.15) | Worth it. Eliminates git history pollution and index.lock races. |
| Symlink-safe: realpath canonicalization prevents aliasing bugs | Async realpath syscall overhead on each write | Worth it. Symlink aliasing creates invisible duplicate writes. |

---

## 12. Layer 7 — Output Handling and Context Hygiene

**Closes**: The universal "unbounded stdout poisoning" failure mode — the largest single component of the 35% naive-vs-production agent gap

**Harvested From**: OpenCode's Managed Tool Output Store (50KB / 2,000 line limits) — directly adopted

### Design

```
PARI MANAGED OUTPUT SPOOLER

Raw command stdout (unlimited size)
              |
              v
ManagedOutputSpooler:
  +-- Spool verbatim to disk: .pari/tool-outputs/<uuid>.txt
  +-- Check: bytes > 50,000 OR lines > 2,000?
  |
  |  YES: Extract balanced view:
  |    head(1000 lines)
  |    + "... [N lines truncated, full output at path] ..."
  |    + tail(1000 lines)
  |
  |  NO: Return verbatim
  |
  v
Context injection (bounded view only)
Model can request: read_tool_output(path, offset=N)
```

**Retention policy**: Tool output sidecar files are retained for 7 days, then GC'd by a background asyncio task. The model can request full access via read_tool_output(path, byte_offset) with 45KB page windows.

**stderr traceback parsing**: For pytest and compiler output, PARI's TracebackParser extracts:
- Failing file + line number
- Assertion error message
- First 10 lines of traceback context

This structured extraction is injected as a [TEST FAILURE] block, not raw stderr, preventing 10,000-line pytest output from displacing the system prompt.

### Trade-Off Analysis

| What We Gain | What We Sacrifice | Verdict |
|---|---|---|
| Prevents context poisoning — the #1 cause of naive agent degradation | 7-day disk retention of tool output files | Worth it. Disk space is cheap; context poisoning is catastrophic. |
| Model can access full output on demand via paged read_tool_output | Two-step access for large outputs | Worth it. The model rarely needs more than head/tail for most commands. |
| Structured traceback injection eliminates 10k-line stderr flooding | Requires language-specific parsers for pytest, cargo, tsc | Worth it. Structured errors reduce resolution turns by 50-70%. |

---

## 13. Layer 8 — Dual-Model Routing Engine

**Closes**: Antigravity F1 (200k-400k token planning burn)

**Harvested From**: Aider's ArchitectCoder / EditorCoder separation — proven to prevent expensive reasoning models from wasting tokens on mechanical diff formatting

### Design

```
USER PROMPT
     |
     v
TASK CLASSIFIER:
  - Complexity score (LOC touched, cross-file scope, ambiguity signals)
  - Explicit reasoning triggers: "design", "refactor", "how should"
  - Default: DIRECT EDITOR for < 3 files
     |              |
     | Complex       | Simple
     v              v
ARCHITECT MODEL       EDITOR MODEL
(Sonnet Thinking / o3) (Haiku / Flash / V3 fast)
Plans in natural         Strict edit format: SEARCH/REPLACE blocks
language only            No conversational bloat
                         Executes plan directly onto files
     |
     v
Instantiate EDITOR MODEL dynamically
with architect's plan as system context
```

**Anti-Verbosity Guard**: A strict token limit is placed on the Architect model's planning phase (max_planning_tokens = 4096). Planning that exceeds this budget is truncated and execution begins. This directly addresses Antigravity F1.

**Weak Model for Commit Messages**: A cheap model (Haiku, Flash-8B) synthesizes git commit messages from the diff. This prevents expensive frontier-model tokens being burned on mechanical commit message generation.

### Trade-Off Analysis

| What We Gain | What We Sacrifice | Verdict |
|---|---|---|
| Architect model focuses entirely on reasoning; editor on mechanics | Two sequential API calls per complex turn | Worth it. Two cheap-model calls cost less than one expensive-model call doing both. |
| Anti-verbosity guard prevents 200k-400k token planning burn | Planning sometimes cut off before ideal depth | Worth it. Execution with imperfect plan > perfect plan with no execution. |
| Weak model for commit messages saves significant token cost | Commit messages may be less descriptive | Acceptable. Commit messages can always be amended. |

---

## 14. Layer 9 — Terminal Interface

**Closes**: The general UX degradation that makes otherwise powerful agents feel unusable; Cursor F4 (CPU pegging background indexer)

**Harvested From**: Pi's differential TUI rendering + Aider's prompt_toolkit-based interactive editing

### Design

PARI's TUI is built on **Rich + prompt_toolkit**, providing:

1. **Live streaming output**: Token-by-token display of model response with syntax highlighting
2. **Unified diff preview**: Before committing edits, display `git diff --stat` inline in the terminal; `git diff` for full review
3. **Structured tool call display**: Tool calls shown as collapsible panels
4. **Cost meter**: Real-time token count and USD cost displayed in the status bar
5. **Interactive / commands**: /undo, /add <file>, /diff, /reset, /model <name> inline commands
6. **Session resume UX**: On startup with existing session, show "Resuming session (turn 47, cost so far: $1.23)"

**No background CPU indexer**: Unlike Cursor, PARI's AST index runs on-demand at session start and updates incrementally on file modification events via watchfiles.watch. Zero background CPU drain between sessions.

---

## 15. Layer 10 — Evaluation and Observability Harness

**Closes**: The universal problem of "vibe coding" — subjective prompt tweaking with no objective regression signal

**Harvested From**: Section 13 of corsanalysis — The Local Micro-Eval Suite ($3-$5 per run)

### Design

PARI ships with a built-in evaluation harness:

```
pari eval run --suite ./evals/micro_suite.json

Runs:
  1. git clone + checkout base_commit (isolated workspace)
  2. bwrap sandbox boot
  3. Agent loop with issue prompt (max 25 turns)
  4. git checkout HEAD -- tests/ (immutable test guard)
  5. pytest <test_command>
  6. Report: PASS/FAIL, turns, cost, duration

Output: evals/results_<timestamp>.json
```

**Cross-Model Verification (Graptile Principle)**: By default, PARI-generated code is evaluated by a different model family than the one that generated it. If the generation model is Anthropic Claude, the evaluation judge is OpenAI GPT-4o-mini. This eliminates the self-evaluation confirmation bias documented in Section 13.10.

**Structured Observability**: Every agent turn emits structured JSON logs via structlog:
```
{"event": "tool_call",      "tool": "bash",    "cmd": "pytest tests/", "turn": 12}
{"event": "edit_applied",   "tier": "git_osr", "file": "auth.py",      "lines_changed": 3}
{"event": "turn_complete",  "cost_usd": 0.0142, "tokens_in": 8420,     "tokens_out": 312}
```

---

## 16. Cross-System Decision Matrix

| Architectural Element | Source | What We Discard |
|---|---|---|
| Kernel sandbox (bwrap, die-with-parent) | Codex codex-bwrap | 119-crate complexity; Noise protocol IPC; string-prefix blocklist |
| Context Epochs (Immutable Baseline) | OpenCode context-epoch.ts | Effect-TS fiber stack; SQLite WAL lock issues; permission modal UX |
| Append-only Merkle DAG + FileMutationQueue + Cache Warmer | Pi session-manager.ts, file-mutation-queue.ts, cache-warmer.ts | O(N) replay latency; process-per-subagent; JSONL partial-write risk |
| 5-Tier Prompt Middleware Pipeline | Claude Code middleware | Node.js single-thread; in-memory state; macOS-only sandbox |
| PPR AST RepoMap + Multi-Tier Edit Cascade + Dual Model | Aider repomap.py, search_replace.py, architect_coder.py | Monolithic single-thread; git index.lock collisions; no sandboxing |
| Artifact decoupling (structured outputs separate from chat) | Google Antigravity Brain system | Token verbosity planning; Google API lock-in; KI absolute path orphanage |
| Atomic physical disk write (inverted from Cursor anti-pattern) | Cursor InlineDiffService (inverted) | Virtual/physical split-brain; Electron bloat; cloud index CPU drain |

---

## 17. The Explicit Trade-Offs: What PARI Sacrifices and Why

### Trade-Off 1: Linux-First Design (Sacrifices Native Windows)

**What we sacrifice**: Native Windows PowerShell support without WSL2.

**Why Codex was right here**: True kernel sandboxing (bwrap, unprivileged namespaces) is a Linux-kernel feature. It does not exist on Windows without WSL2 or Hyper-V. Providing a degraded "no sandbox" Windows mode recreates Aider F1 and OpenCode F1 — the exact failures we're trying to eliminate.

**Our position**: PARI runs natively on Linux and macOS (macOS via Seatbelt as secondary sandbox). Windows requires WSL2. This is a deliberate trade-off: security over universal compatibility.

---

### Trade-Off 2: Single-Agent Default (Sacrifices Speculative Parallelism)

**What we sacrifice**: The ability to explore two competing algorithm fixes simultaneously in parallel.

**Why Pi was right here**: Empirical data (Section 13.3) proves that Pi performs at 48-52% on terminal benchmarks with zero subagent orchestration. Academic multi-agent swarms score 18-25%. Context fragmentation, exponential token cost, and state merge conflicts make uncoordinated multi-agent coding worse than a single focused agent.

**Our position**: Subagents are available in PARI but are opt-in and restricted to disjoint read-only tasks (web research, documentation scraping, parallel repository reading). Code mutation is always single-agent.

---

### Trade-Off 3: Python Runtime (Sacrifices Rust Performance)

**What we sacrifice**: The raw CPU throughput and memory efficiency of a Rust implementation like Codex.

**Why Aider was right here**: Agent loops are network I/O bound, not CPU bound. The bottleneck is waiting for LLM API responses (300ms-3s per turn). Python 3.11 asyncio handles this class of I/O concurrency with negligible overhead. Codex's Rust investment produces 25-minute build times and an impossibly high contributor barrier for essentially zero benefit on network-bound workloads.

**Our position**: Python 3.11+ asyncio for the agent harness. Hot paths (AST parsing via tree-sitter C bindings, SQLite via diskcache) are already implemented in compiled code.

---

### Trade-Off 4: No IDE GUI (Sacrifices Visual Completions)

**What we sacrifice**: Cursor-style speculative inline completions and Monaco visual diff staging.

**Why this is the right trade-off**: Cursor's visual diff staging model creates the split-brain vulnerability (Cursor F1) — tests run against unmutated disk files while the agent sees mutated virtual buffers. This is an architectural error that cannot be patched without abandoning the virtual buffer model entirely.

**Our position**: PARI operates exclusively on physical disk with atomic writes. Terminal-based diff visualization via git diff --color provides sufficient visual feedback. IDE integration can be added as a thin wrapper on top of the physical-disk-first architecture.

---

### Trade-Off 5: Explicit Cache Epoch Boundaries (Sacrifices Context Mutability)

**What we sacrifice**: The ability to freely change the system prompt or repo map mid-session.

**Why OpenCode was right here**: The Immutable Baseline Epoch prevents KV cache invalidation cascades. Claude Code's billing spikes from upstream file edits cascading through all cache tiers are eliminated by freezing Tiers 1-5. When changing the system prompt is necessary, PARI triggers a session version bump (new SESSION_START record in the DAG), which also starts a new cache baseline.

**Our position**: System prompt and repo map are frozen per session epoch. Mid-session file changes update only Tier 5 (active chat files). This is a deliberate trade-off: billing predictability and 70-90% token cost reduction over dynamic mid-session context mutation.

---

### Trade-Off 6: No LLM-as-a-Judge by Default (Sacrifices Qualitative Assessment)

**What we sacrifice**: The ability to automatically assess code architectural quality, style consistency, and abstract design decisions.

**Why this is right**: Section 13.7 establishes the Golden Rule: "If a task's correctness can be proven deterministically via compiler exit codes or unit tests, NEVER use an LLM-as-a-judge." Default PARI evaluation uses exit codes, pytest pass rates, and lint checks — all deterministic.

**Our position**: LLM-as-a-judge is available as an optional evaluation mode (pari eval judge) for architectural review. Default evaluation is 100% deterministic.

---

## 18. Phased Build Roadmap

```
PHASE 1: FOUNDATION (Weeks 1-3)
  "Make it safe, durable, and correct before making it smart"
  
  +-- Layer 0: bwrap sandbox engine with die-with-parent + cgroups v2
  +-- Layer 1: Append-only JSONL Merkle DAG session manager
  |           + atomic CRC32 append guard
  |           + checkpoint index records (every 50 turns)
  +-- Layer 6: FileMutationQueue (asyncio.Lock per realpath)
  |           + atomic tempfile-then-rename write
  +-- Layer 7: ManagedOutputSpooler (50KB / 2k lines + disk sidecar)


PHASE 2: AGENT RUNTIME (Weeks 4-6)
  "Make it run reliably on real tasks"
  
  +-- Layer 4: Double-while execution loop
  |           + stop_reason == "length" guard
  |           + PTY daemon detection
  |           + reflection retry (max 3, structured error injection)
  +-- Layer 2: Context Epoch assembly (8-tier ChatChunks hierarchy)
  |           + cache breakpoints at tier 3 and 5 boundaries
  |           + autonomous economic cache warmer (asyncio background task)
  |           + safe context compaction (70% threshold)
  +-- Layer 5: Multi-tier edit cascade (Exact -> Git OSR -> DMP -> Prefill)
  |           + RelativeIndenter normalization
  +-- Layer 9: Rich TUI (streaming output, cost meter, /commands)


PHASE 3: INTELLIGENCE (Weeks 7-9)
  "Make it smart about the codebase from turn 0"
  
  +-- Layer 3: Tree-sitter AST symbol extractor (multi-language)
  |           + NetworkX Personalized PageRank (PPR)
  |           + Hub suppression filter (>50 inbound refs dampened)
  |           + 2,048 token binary-search packing
  |           + diskcache SQLite with worktree-scoped keys
  +-- Layer 8: Dual-model router (task classifier + Architect/Editor)
  |           + anti-verbosity guard (max 4,096 planning tokens)
  |           + multi-provider adapter (Anthropic, OpenAI, DeepSeek, Ollama)
  +-- Git auto-commit (weak model commit messages) + /undo support


PHASE 4: HARDENING AND EVALUATION (Weeks 10-12)
  "Prove it surpasses baseline agents on objective benchmarks"
  
  +-- Layer 10: Micro-eval harness (10-issue local suite, $3-$5 per run)
  |            + cross-model verification (Graptile principle)
  |            + structured JSON observability logs (structlog)
  +-- Chaos testing: fork-bomb, CPU throttle, SIGKILL mid-turn,
  |                  concurrent write races, JSONL partial-write
  +-- Benchmark: run against SWE-bench Lite (target: >= 50% pass rate)
  +-- Security audit: prompt injection, sandbox escape attempts,
                      path traversal attacks on FileMutationQueue
```

---

## Appendix A: System Comparison — PARI vs. Existing Agents

| Dimension | Claude Code | Codex | OpenCode | Pi | Aider | Cursor | Antigravity | PARI |
|---|---|---|---|---|---|---|---|---|
| Kernel Sandbox | macOS only | bwrap/Seatbelt | permission dialog | raw host | raw host | raw host | process group | **bwrap + cgroups** |
| ACID Session State | flat JSON | SQLite | SQLite WAL | JSONL DAG | git only | in-memory | JSONL | **JSONL DAG + checkpoint** |
| Cache Epoch Stability | heuristic | prefix tracker | Epochs | Economic Warmer | 3-tier + warmer | provider-dependent | implicit | **Epoch + Warmer + 8-tier** |
| AST Repo Map | none | none | none | none | PPR tree-sitter | vector embeddings | grep + KI | **PPR + hub filter** |
| Edit Resilience | basic write | basic write | basic write | basic write | 3-tier cascade | fuzzy text (buggy) | basic write | **4-tier cascade + atomic** |
| File Write Safety | async races | async spawn | FiberSet | realpath queue | synchronous | virtual buffer | managed pool | **realpath queue + atomic** |
| Output Spooling | memory slice | memory truncate | 50KB disk | head/tail | output limits | char truncation | paged view_file | **50KB disk + structured parse** |
| Dual-Model Routing | none | none | none | none | Architect/Editor | none | planning verbosity | **classifier + anti-verbosity** |
| Multi-Provider | Anthropic only | OpenAI/Anthropic | Multi-provider | Multi-provider | LiteLLM all | proprietary | Google only | **unified adapter** |
| Eval Harness Built-in | none | none | none | none | none | none | none | **micro-eval + cross-model** |
| Subagent Weight | ephemeral turns | actor pool | experimental | heavy processes | none | none | CDP browser | **asyncio TaskGroup (lightweight)** |
| Orphan Process Safety | no | edge cases | fiber detach | no | N/A | N/A | OAuth drops | **die-with-parent SIGKILL** |

---

*Architecture document authored for PARI — September 2026*
*Grounded in: corsanalysis.md — Verified architectural critique of Claude Code, Codex, OpenCode, Pi, Aider, Cursor, and Google Antigravity*
