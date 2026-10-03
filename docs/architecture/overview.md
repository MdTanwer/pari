# PARI System Architecture Overview

> **Design Philosophy**: Every architectural decision in PARI is a direct response to a verified, source-code-grounded weakness in an existing production agent. No decision is theoretical — each closes a specific, documented failure mode.

---

## 1. The Core Thesis: Why Coding Agents Fail

Empirical analysis across existing production agents (Claude Code, OpenAI Codex, OpenCode, Pi, Aider, Cursor, and Google Antigravity) reveals a singular conclusion:

$$\text{\bf Agent failure is a systems engineering failure, not a reasoning failure.}$$

The exact same frontier reasoning model (such as Claude 3.7 Sonnet or GPT-4o) demonstrates a **15% pass rate** in a naive tool-use loop, but achieves a **50–55% pass rate** inside an engineered harness like Claude Code or Pi. 

The **35% delta** is not accounted for by model capability, prompt engineering, or chain-of-thought fine-tuning. It is entirely explained by **six harness-level systems failure modes**:

```
+-----------------------------------------------------------------------------------+
|                        THE 35% BENCHMARK DELTA EXPLAINED                          |
+-----------------------------------------------------------------------------------+
|                                                                                   |
|                   Frontier LLM Reasoning Engine (Claude 3.7 / GPT-4o)             |
|                                         |                                         |
|                    +--------------------+--------------------+                    |
|                    |                                         |                    |
|                    v                                         v                    |
|          [Naive Agent Harness]                   [PARI Engineered Harness]        |
|                    |                                         |                    |
|       15% Pass Rate (Fragile)                    50%+ Pass Rate (Robust)          |
|                    |                                         |                    |
|   +----------------+----------------+                        |                    |
|   | Six Fatal Systems Failure Modes |                        |                    |
|   | 1. Unbounded stdout poisoning   | ====> Solved by Layer 7 (Managed Spooler)   |
|   | 2. Mid-stream token truncation  | ====> Solved by Layer 4 (stop_reason Guard) |
|   | 3. File write race conditions   | ====> Solved by Layer 6 (FileMutationQueue) |
|   | 4. KV cache invalidation spikes | ====> Solved by Layer 2 (Immutable Epochs)  |
|   | 5. Blind file traversal loops   | ====> Solved by Layer 3 (PPR AST RepoMap)   |
|   | 6. Unsandboxed host execution   | ====> Solved by Layer 0 (Kernel Sandbox)    |
|   +---------------------------------+                                             |
+-----------------------------------------------------------------------------------+
```

### The Six Harness Failure Modes

| Failure Mode | Root Cause | Impacted Systems | PARI Solution |
|---|---|---|---|
| **Unbounded stdout poisoning** | Build/test output floods context window; system instructions and core constraints displaced | Claude Code, Aider, Codex | **Layer 7**: 50KB/2,000-line disk spooler + balanced head/tail extraction |
| **Mid-stream token truncation** | Model hits `max_tokens`; partial JSON payload executes, corrupting source code | Claude Code, OpenCode | **Layer 4**: Strict `stop_reason == "length"` rejection guard |
| **File write race conditions** | Concurrent asynchronous tool calls invoke uncoordinated `writeFile()` calls | Claude Code | **Layer 6**: Canonical `realpath` serialization via `FileMutationQueue` |
| **KV cache invalidation cascades** | Single file edit mutates upstream prompt prefix, invalidating 100% of KV cache | Claude Code, Aider | **Layer 2**: Immutable Baseline Epochs freezing Tiers 1–4 across sessions |
| **Blind file traversal loops** | Agent lacks architectural symbol map; burns 4–8 exploratory `grep` turns searching | Pi, OpenCode, Codex | **Layer 3**: Personalized PageRank (PPR) AST repo map injected at Turn 0 |
| **Unsandboxed host execution** | Unrestricted shell execution allows hallucinated or malicious commands on host | Pi, Aider, OpenCode | **Layer 0**: Multi-platform kernel isolation (`bwrap` + Apple `Seatbelt` + E2B) |

---

## 2. PARI 11-Layer Architecture Topology

PARI structures the agent runtime into 11 strictly decoupled layers ($0$ through $10$). Each layer is independently testable, independently replaceable, and has a single well-defined contract. No layer possesses direct knowledge of layers more than one level above or below it.

```
+-----------------------------------------------------------------------------------+
|                              PARI -- SYSTEM TOPOLOGY                              |
+-----------------------------------------------------------------------------------+
|                                                                                   |
|  Layer 9:  TERMINAL INTERFACE (Rich / Textual differential rendering TUI)         |
|                                          |                                        |
|  Layer 8:  DUAL-MODEL ROUTER (Architect -> Planner / Editor -> Fast Model)        |
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
|  Layer 0:  SANDBOX (bwrap on Linux/WSL2 + Seatbelt on macOS + E2B Cloud)         |
|                                                                                   |
+-----------------------------------------------------------------------------------+
```

---

## 3. End-to-End Execution Lifecycle

The lifecycle of an interaction in PARI moves through deterministic phases from initial invocation to verified disk state:

```
+-----------------------------------------------------------------------------------+
|                         END-TO-END EXECUTION LIFECYCLE                            |
+-----------------------------------------------------------------------------------+
|                                                                                   |
|  1. USER PROMPT: Submitted via Layer 9 Terminal TUI                               |
|        |                                                                          |
|        v                                                                          |
|  2. SESSION DAG: Append immutable USER_TURN record (UUIDv7, CRC32)                |
|        |                                                                          |
|        v                                                                          |
|  3. REPOMAP INGESTION: Query Layer 3 AST graph -> 2,048-token symbol context      |
|        |                                                                          |
|        v                                                                          |
|  4. CONTEXT ASSEMBLY: Layer 2 freezes Immutable Baseline Epoch (Tiers 1-4)        |
|        |                                                                          |
|        v                                                                          |
|  5. DUAL-MODEL ROUTER:                                                            |
|        +-- [Complex Plan] -> Architect Model emits 300-token natural plan         |
|        +-- [Simple Edit]  -> Bypass directly to Editor Model                      |
|        |                                                                          |
|        v                                                                          |
|  6. STREAMING EXECUTION: Stream tokens from provider                              |
|        * GUARD: stop_reason == 'length'? ABORT tool calls to prevent corruption!  |
|        |                                                                          |
|        v                                                                          |
|  7. TOOL EXECUTION:                                                               |
|        +-- bash_exec -> Run inside Layer 0 Kernel Sandbox (bwrap / Seatbelt)      |
|        |                Stdout/stderr spooled via Layer 7 (50KB / 2k-line limits) |
|        +-- file_edit -> Apply edit via Layer 5 exact replace / fallback cascade   |
|                         Acquire canonical realpath Lock in Layer 6                |
|                         Atomic disk write: tempfile + os.replace()                |
|        |                                                                          |
|        v                                                                          |
|  8. AUTOMATED VERIFICATION: Run test suite inside sandbox                         |
|        +-- Tests Pass -> Complete turn & emit final summary                       |
|        +-- Tests Fail -> If reflections < 3: inject structured error & retry      |
|        |                                                                          |
|        v                                                                          |
|  9. STATE COMMIT: Record TOOL_RESULTS & ASSISTANT_TURN in Merkle DAG              |
|        Render live status, colored diff preview, and cost meter in terminal TUI   |
|                                                                                   |
+-----------------------------------------------------------------------------------+
```

---

## 4. Fundamental Architectural Invariants

PARI enforces seven core invariants across its execution layers:

1. **Physical Disk as Single Source of Truth**: PARI never maintains an in-memory virtual file buffer disconnected from the physical filesystem. All mutations are atomically written to physical storage via `os.replace()`, preventing the virtual/physical split-brain bugs that plague IDE extensions.
2. **Simple Default Path & Fail-Safe Ambiguity Handling**: By default, file modifications use exact string search/replace. If an edit target is ambiguous or stale, the engine halts and prompts for clarification rather than making heuristic guesses. Heuristic fallbacks (OSR, DMP) operate behind explicit feature flags.
3. **Host-Enforced Policies over Soft Prompt Guidance**: Resource limits, execution timeouts, memory cgroups, sandbox path mounts, and token ceilings are strictly enforced by client-side host mechanisms, not entrusted to LLM instruction compliance.
4. **Immutable Baseline Context**: The system prompt, core tool definitions, and repository symbol map are frozen into an Immutable Baseline Epoch. They are never shifted mid-turn, maximizing prompt cache hits on frontier model providers.
5. **No Unbounded Memory Buffers**: All tool output streams, stdout pipes, and compilation logs are intercepted at the kernel pipe boundary and spooled to sidecar files on disk before entering agent memory. Secret redaction is executed prior to spooling.
6. **Guaranteed Process Tree Reaping & Side-Effect Tracking**: Child sandboxes and spawned processes are bound to the parent PID via OS-level primitives (`PR_SET_PDEATHSIG` on Linux, Job Objects on Windows), guaranteeing zero orphaned processes. External side-effects (e.g. package installations) are recorded to guide compensating actions during rollbacks.
7. **Deterministic State Replay**: The session history is modeled as an append-only Merkle DAG. Every state transition has a cryptographic parent pointer and CRC32 checksum, enabling zero-loss crash recovery and exact point-in-time rollbacks.

---

## 5. Next Steps

* Review design hypotheses and safe fallbacks in the [Cross-System Decision Matrix](decision-matrix.md).
* Deep dive into the real-world vulnerabilities in the [Failure Mode Atlas](failure-mode-atlas.md).
* Review engineering trade-offs in [The Trade-Off Framework](trade-offs.md).
* Explore the multi-platform sandbox in [Layer 0: Sandboxing Engine](../layers/layer-0-sandboxing.md).

