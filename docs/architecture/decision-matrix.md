# Cross-System Decision Matrix & Design Hypotheses

> **Methodological Note**: This matrix is a **design hypothesis to benchmark**, not an unverified claim of inherent superiority. Every architectural choice has concrete trade-offs, potential failure modes, and requires rigorous empirical validation on reproducible benchmark suites (e.g. SWE-bench Lite).

---

## 1. Core Terminology Definitions

To evaluate design choices objectively, foundational concepts and mechanisms are defined precisely:

* **OSR (Original-Search-Replace)**: A synthetic 3-way Git merge technique (harvested from Aider). When an LLM search block fails exact string matching due to whitespace drift or line-offset shifts, an ephemeral Git repository is initialized with three commits:
  1. Commit `O`: The original physical file currently on disk.
  2. Commit `S`: What the model assumed the file looked like (the search block).
  3. Commit `R`: What the model desires the file to look like (the replace block).
  Running `git cherry-pick --minimal` delegates fuzzy reconciliation to Git's merge algorithm.
* **DMP (Diff-Match-Patch)**: Google’s `diff_match_patch` library, utilizing Myers' diff algorithm with line-to-character hashing for approximate string matching when code blocks have shifted non-contiguously.
* **Prefill**: An API capability (supported by Anthropic, vLLM, and Ollama) allowing the client harness to pre-populate the start of the assistant's response (e.g. `{"role": "assistant", "content": "```python\n"}`), forcing the model to emit deterministic code without conversational preamble.
* **KI (Knowledge Items)**: Structured, localized repository context files (harvested from Antigravity/Devin patterns) capturing codebase quirks, build commands, and tribal knowledge, persisted as markdown artifacts rather than living in prompt history.
* **PPR (Personalized PageRank)**: Graph centrality algorithm applied over an AST call graph, biasing random walks toward active/mentioned files to extract the most relevant symbol signatures within a token budget.

---

## 2. Benefit, Failure Scenario & Safe Fallback Matrix

Complex features must not be assumed to work flawlessly. The table below defines the intended benefit, the specific failure mode, and the mandatory safe fallback for each architectural choice:

| Architectural Component | Intended Benefit Scenario | Failure Scenario / Vulnerability | Safe Fallback & Recovery Policy |
|---|---|---|---|
| **Sandboxed Workers** (`bwrap` / Seatbelt / E2B) | Isolates build/test tools; prevents malicious command execution or credential theft. | Required build operation blocked by tight mount; isolation misconfigured; performance degradation. | **Fail closed (deny by default)**. Narrowly scope access by workspace root; provide explicit `--no-sandbox` escape hatch with warning and emergency process kill switch. |
| **Event Log + Checkpoints** (JSONL Merkle DAG) | Continuous auditability; instant session resumption without $O(N)$ scanning. | Checkpoint is stale or corrupted; trailing JSON record torn during mid-write crash. | **Scan backwards to last valid CRC32**. Reconstruct DAG up to checkpoint; if broken, fall back to authoritative Git repository state. |
| **Edit Engine** (Exact Match + Fallback Cascade) | High diff application success rate despite LLM whitespace and offset drift. | Ambiguous search matches apply edits to the wrong function; fuzzy matcher scrambles code. | **Stop on ambiguity**. If multiple occurrences exist or confidence is low, reject mutation, leave file untouched, and prompt model for clarification. |
| **Output Spooling** (`ManagedOutputSpooler`) | Protects context window from 10,000-line build/test stdout flooding. | Truncation cuts off critical compiler diagnostic lines; logs leak API secrets. | Bounded head/tail extraction with **secret redaction** before storage. Retain disk pointer and provide paged `read_tool_output` for deep inspection. |
| **Multi-Provider Routing** (Architect / Editor Split) | Up to 85% output cost savings; routes planning to reasoning models and edits to fast models. | Editor model misinterprets tool schemas or lacks instruction-following fidelity. | **Validate outputs against strict schemas**. If the fast model fails verification twice, escalate task back to the frontier model. |
| **Subagent Workers** (`asyncio.TaskGroup`) | Concurrent background research and documentation scraping without UI blocking. | Subagents collide on shared files, deadlock, or burn exponential tokens in swarm loops. | **Strict read-only constraint**. Subagents cannot acquire write locks. Give mutating tasks isolated Git worktrees; merge only upon verified test pass. |
| **Process Cleanup** (`PR_SET_PDEATHSIG` / Job Objects) | Prevents orphan daemon servers from holding ports or consuming memory. | Platform differences leave zombie child processes running in edge-case terminations. | Bind child lifecycle to parent PID via kernel primitives; verify process termination during chaos test suite. |

---

## 3. Engineering Philosophy: Simple Defaults First

Rather than making the most complex mechanism the mandatory default, PARI adheres to a **layered execution pipeline with feature flags**:

```
PARI EXECUTION TIERS:

1. SIMPLE DEFAULT PATH (Deterministic & Safe):
   - Codebase Navigation (v1): High-speed substring ripgrep, regex search, and file globbing (`find_files`, `grep_search`). Zero parser lag.
   - Exact string search/replace with strict FAIL-ON-AMBIGUITY.
   - Canonical realpath lock + atomic tempfile-then-rename write.
   - Single-agent execution loop with host-enforced timeouts.
   - Append-only JSONL event transcript with CRC32 verification.
   - Deterministic test verification (compiler exit codes).

2. CONFIGURABLE ENHANCEMENTS (Behind Feature Flags / v2):
   - Context Navigation (v2 Fallback): Tree-sitter AST symbol extractor & Personalized PageRank (`--repomap=ppr`) when grep/globbing is insufficient.
   - Edit Fallbacks: --edit-fallback=git-osr,dmp (activates fuzzy tiers).
   - Cache Warmer:  --cache-warmer=auto (activates idle background pings).
   - Model Routing: --route=dual (activates Architect/Editor separation).
```

### Host Enforcement vs. Soft Prompt Guidance

Prompt instructions (e.g. *"Do not plan for more than 4,000 tokens"*) shape tone, but **host-enforced policies guarantee limits**:
* **Enforced by Host**:
  * Hard API `max_tokens` parameters.
  * Subprocess timeouts and 10s PTY daemon watchdogs.
  * cgroups v2 memory limits (`2GB`) and PID caps (`256`).
  * Sandbox filesystem boundaries (`--bind`).
* **Guided by Prompt**:
  * Output formatting idioms (SEARCH/REPLACE block style).
  * Terse natural-language narration.

---

## 4. Architectural Harvesting & Discard Matrix

| System | Harvested Innovation | Discarded Architecture & Why |
|---|---|---|
| **Codex (`codex-rs`)** | **Kernel sandboxing primitives**: `bwrap` namespace flags, `PR_SET_PDEATHSIG` process tree lifecycle binding. | **119-crate Rust workspace**: 25-minute compilation times, 20GB `target/` directories, IPC serialization overhead, and fragile string-prefix blocklists. |
| **OpenCode** | **Context Epoch architecture**: Structuring prompts into immutable baseline prefixes and dynamic turn buffers. Managed tool output limits. | **Effect-TS fiber stack**: 100-line generator stack traces, SQLite WAL contention under parallel writes, and missing kernel sandbox. |
| **Pi** | **Append-only JSONL Merkle DAG**: Immutable session history, `uuidv7` parent-pointers, `FileMutationQueue` canonical realpath serialization, and Autonomous Economic Cache Warmer. | **$O(N)$ session replay latency**: Absence of checkpoints, `spawn("node", ...)` process-per-subagent RAM bloat, and lack of an AST repository map. |
| **Claude Code** | **Structured Middleware Pipeline**: Pre-turn validation hooks, clean prompt assembly stages, and interactive command handling. | **In-memory session volatility**: Fragile flat JSON dumps, zero kernel sandboxing on Linux/Windows, and unbounded tool output context displacement. |
| **Aider** | **Personalized PageRank (PPR) AST RepoMap**: Tree-sitter symbol graph and **3-Tier Fuzzy Edit Cascade** (Exact $\rightarrow$ Git OSR $\rightarrow$ DMP). | **Monolithic single-threaded loop**: Direct working tree git commit pollution, `.git/index.lock` collisions, and PageRank hub distortion from utility helpers. |
| **Google Antigravity** | **Structured Artifact Decoupling**: Separating long-form plans, specs, and diff artifacts from the primary conversational context stream. | **Token Multiplier Planning Burn**: 200k–400k tokens burned in recursive self-reflection, Google Cloud OAuth dependencies, and vendor API lock-in. |
| **Cursor** | **Atomic Physical Disk Mutation**: Inverted from Cursor's virtual buffer model to guarantee single source of truth. | **Virtual/Physical Split-Brain**: Electron background CPU indexer pegging, Monaco in-memory diff desynchronization, and `.gitignore` cloud leakage. |

---

## 5. 12-Dimension Cross-System Comparison

| Architectural Dimension | Claude Code | Codex (`codex-rs`) | OpenCode | Pi | Aider | Cursor | Google Antigravity | PARI (Design Target) |
|---|---|---|---|---|---|---|---|---|
| **1. Kernel Sandbox** | macOS only (`sandbox-exec`) | `bwrap` / Seatbelt / Restricted Tokens | None (Interactive permission modal) | None (Raw host execution) | None (Raw host execution) | None (Raw host execution) | Supervised Process Group | **bwrap (Linux/WSL2) + Seatbelt (macOS) + E2B (Cloud)** |
| **2. Session Durability** | In-memory + flat JSON | SQLite Database | SQLite with WAL mode | Append-only JSONL Merkle DAG | Git commit log only | In-memory workspace state | JSONL Event Transcripts | **Append-only JSONL Merkle DAG + Checkpoint Indices** |
| **3. Cache Stability** | Heuristic single breakpoint | Prefix tracker | Immutable Epochs | Autonomous Economic Warmer | 3-tier prefix hierarchy | Provider-dependent | Implicit session caching | **Immutable Epochs + 8-Tier Hierarchy + Warmer (Behind Flag)** |
| **4. Codebase Navigation** | Substring grep & globbing | File search tools | Glob & grep tools | Grep & find tools (4–8 blind turns) | Tree-sitter PageRank (1k tokens) | Cloud vector embeddings | Grep & Knowledge Items (KI) | **v1: Substring grep & globbing / v2: Tree-sitter AST fallback** |
| **5. Edit Engine Resilience** | Direct write | Direct write | Direct write | Direct write | 3-tier cascade (Exact/OSR/DMP) | Monaco fuzzy matcher | Direct write | **Exact Match Default + Fallback Cascade (Exact/OSR/DMP/Prefill)** |
| **6. File Write Safety** | Uncoordinated async writes | Async process spawn | Fiber mutexes | `FileMutationQueue` (realpath) | Synchronous serial writes | Monaco virtual buffer | Managed TaskPool | **`FileMutationQueue` (canonical realpath) + Atomic Rename** |
| **7. Tool Output Handling** | In-memory slice truncation | Memory truncate | 50KB / 2k-line limits | Head/tail truncation | Line limit truncation | Character truncation | Paged reading tools | **50KB / 2k-line Disk Spooler + Structured Traceback Parser** |
| **8. Model Routing** | Monolithic frontier model | Monolithic frontier model | Monolithic frontier model | Monolithic frontier model | Architect / Editor split | Monolithic frontier model | Autonomous hierarchical | **Task Classifier + Architect/Editor Split (Configurable)** |
| **9. Provider Independence** | Anthropic Claude only | OpenAI + Anthropic | Multi-provider | Multi-provider | Multi-provider (LiteLLM) | Proprietary cloud wrapper | Google Gemini / Vertex only | **Unified Model Adapter (Anthropic, OpenAI, DeepSeek, Ollama)** |
| **10. Evaluation Harness** | None | None | None | None | None | None | None | **Built-in Micro-Eval Suite + Cross-Model Verification** |
| **11. Subagent Footprint** | Ephemeral turns | Async actor pool | Experimental fibers | Independent Node/V8 processes | None | None | CDP browser subagents | **Lightweight `asyncio.TaskGroup` Fibers (Read-only)** |
| **12. Process Tree Safety** | Orphan leaks on crash | Edge-case subreaper leaks | Fiber detach on error | Orphan leaks on crash | None | None | OAuth session disconnects | **Guaranteed `die-with-parent` (`PR_SET_PDEATHSIG` / Job Objects)** |

---

## 6. The v1 `/undo` Contract: File Rollback, Process Cleanup & Disclosed Side Effects

A terminal coding agent can strictly control what it launches, but **cannot magically reverse arbitrary shell side effects**. Promising that `/undo` restores the entire system creates a false sense of security.

For PARI v1, the `/undo` contract is explicitly defined across four boundaries:

```
+-----------------------------------------------------------------------------------+
|                        PARI v1 /undo EXECUTION CONTRACT                           |
+-----------------------------------------------------------------------------------+
|                                                                                   |
|  1. FILE ROLLBACK (Fully Automated):                                              |
|     - PARI captures a pre-edit hash/snapshot before mutating any file.            |
|     - /undo restores exact pre-mutation file states for files PARI modified.      |
|                                                                                   |
|  2. PROCESS CLEANUP (Fully Automated):                                            |
|     - All child PIDs and process groups spawned during the turn are tracked.      |
|     - /undo (or shutdown) terminates running child processes and daemons.         |
|                                                                                   |
|  3. SIDE-EFFECT LOGGING & DISCLOSURE (Logged & Warned, Not Auto-Reversed):        |
|     - Commands modifying dependencies/environments (npm, pip, cargo, migrations)  |
|       are detected and logged to .pari/side-effects.jsonl.                        |
|     - PARI warns the user and suggests manual cleanup commands.                   |
|     - PARI does NOT execute automatic uninstall/rollback commands to avoid       |
|       unintended secondary destruction.                                           |
|                                                                                   |
|  4. EXPLICIT LIMITATION DISCLAIMER:                                               |
|     - /undo CANNOT reverse third-party API calls (e.g. Stripe, AWS, Slack).       |
|     - /undo CANNOT reverse external database mutations or dropped remote tables.  |
|                                                                                   |
+-----------------------------------------------------------------------------------+
```

### Example Terminal `/undo` Interaction
```
pari> /undo
[Undo Complete]: Restored 2 modified files (src/auth/service.py, tests/test_auth.py).
[Process Cleanup]: Terminated 1 background server (PID 48210: 'npm run dev').

[Side-Effect Warning]:
  Turn 14 executed: 'npm install jsonwebtoken'
  Note: Dependency changes are logged but not automatically uninstalled.
  Suggested manual cleanup: npm uninstall jsonwebtoken
```

