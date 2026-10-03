# Phased Build Roadmap (12-Week Execution Plan)

> **Execution Directive**: *Make it safe, durable, and correct before making it smart.*

The 12-week implementation plan is structured into four sequential 3-week phases with strict milestone gates:

```
+-----------------------------------------------------------------------------------+
|                            PARI IMPLEMENTATION PHASES                             |
+-----------------------------------------------------------------------------------+
|  Weeks 1–3:  PHASE 1 — FOUNDATION (Sandbox, Merkle DAG, Queue, Output Spooler)    |
|  Weeks 4–6:  PHASE 2 — AGENT RUNTIME (Double-While Loop, Cache Epochs, Edit Engine)|
|  Weeks 7–9:  PHASE 3 — INTELLIGENCE (Tree-sitter PPR RepoMap, Dual-Model Router)  |
|  Weeks 10–12: PHASE 4 — HARDENING (Micro-Evals, Chaos Testing, SWE-bench Lite)    |
+-----------------------------------------------------------------------------------+
```

---

## Phase 1: Foundation (Weeks 1–3)
**Goal**: Establish ironclad OS isolation, crash-proof session storage, and safe filesystem concurrency before implementing LLM logic.

### Deliverables
* **Layer 0 — Multi-Platform Sandbox Engine**:
  * Implement `BwrapSandboxRunner` for Linux & Windows WSL2 with unprivileged user namespaces and `--die-with-parent`.
  * Implement `MacOSSeatbeltSandboxRunner` with Scheme profile (`pari_rules.sb`).
  * Implement `E2BCloudSandboxRunner` integration for cloud microVM execution.
  * Implement `WindowsSupervisedGuardrailRunner` path-guard fallback.
  * Enforce Linux cgroups v2 resource quotas (`memory.max = 2G`, `cpu.weight = 100`).
* **Layer 1 — Durable Session Engine**:
  * Build append-only JSONL Merkle DAG with UUIDv7 and `parentId` pointers.
  * Implement atomic append guard with POSIX `O_APPEND | O_SYNC` and CRC32 checksums.
  * Implement reverse recovery scan to truncate trailing torn records on startup.
  * Implement `CHECKPOINT_INDEX` record insertion every 50 turns for $O(K)$ resume.
* **Layer 6 — Concurrency & File Safety**:
  * Build `FileMutationQueue` with `asyncio.Lock` mapped by canonical `os.path.realpath`.
  * Implement atomic disk write protocol via `tempfile` and `os.replace`.
  * Implement shadow git worktree initialization (`.pari/shadow-tree`).
* **Layer 7 — Output Hygiene**:
  * Build `ManagedOutputSpooler` with 50KB / 2,000-line limits and disk sidecar writing.
  * Implement balanced head/tail extraction (1,000 lines head + 1,000 lines tail).

**Milestone Gate 1**: System passes chaos testing for concurrent write flooding, hard `SIGKILL` during active writes, and fork-bomb sandbox containment.

---

## Phase 2: Agent Runtime (Weeks 4–6)
**Goal**: Deliver a reliable, interactive agent loop capable of executing commands and applying resilient diffs.

### Deliverables
* **Layer 4 — Execution Loop**:
  * Implement the double-while state machine.
  * Implement the critical `stop_reason == "length"` token truncation guard.
  * Build PTY-aware daemon detector with 10s non-interactive timeout.
  * Implement bounded reflection loop (max 3 retries) with structured error injection.
* **Layer 2 — Context and Cache Architecture**:
  * Build 8-tier context epoch hierarchy with 3 explicit cache breakpoints.
  * Implement autonomous economic cache warmer (`asyncio` background task evaluating $E[\text{ROI}] \ge \$0.05$).
  * Build safe context compaction engine (triggering at 70% context capacity).
* **Layer 5 — Multi-Tier Fuzzy Edit Engine**:
  * Implement Tier 1: Exact string replacement.
  * Implement Tier 2: Synthetic Git OSR cherry-pick in ephemeral repository.
  * Implement Tier 3: Google `diff_match_patch` line fuzzy matching.
  * Implement Tier 4: Assistant prefill continuation and targeted block re-requests.
  * Build `RelativeIndenter` whitespace normalization.
* **Layer 9 — Terminal Interface (TUI)**:
  * Rich differential rendering with streaming markdown and syntax highlighting.
  * Interactive unified diff previews and real-time USD cost tracking.
  * Implement slash commands: `/undo`, `/diff`, `/snapshot`, `/cost`, `/reset`.

**Milestone Gate 2**: Agent successfully executes multi-turn bug fixes on local sample repositories with 0 daemon deadlocks and $>95\%$ edit application success.

---

## Phase 3: Intelligence (Weeks 7–9)
**Goal**: Provide codebase structural awareness from Turn 0 and slash API costs via dual-model routing.

### Deliverables
* **Layer 3 — Intelligence Layer (AST RepoMap)**:
  * Tree-sitter AST symbol extractor with `.scm` tag queries across Python, TypeScript, Rust, and Go.
  * Build weighted bipartite call graph using NetworkX ($50\times$ active files, $10\times$ prompt tokens).
  * Compute Personalized PageRank (PPR) with $d = 0.85$.
  * Implement PARI Hub Suppression Filter ($>50$ inbound references dampened by $0.05\times$).
  * Binary search token packing into a precise 2,048-token context budget.
  * Implement `diskcache.Cache` SQLite store with `mtime` invalidation and worktree-scoped keys.
* **Layer 8 — Dual-Model Routing Engine**:
  * Build Task Classifier analyzing prompt scope and cross-file complexity.
  * Implement Architect / Editor separation (Sonnet Thinking $\rightarrow$ Haiku / DeepSeek V3).
  * Implement Anti-Planning Guard with a hard 4,096-token planning ceiling.
  * Pluggable multi-provider adapter supporting Anthropic, OpenAI, DeepSeek, and Ollama.
* **Session DAG Snapshot / Undo Support**:
  * Connect `/undo` command to Merkle DAG node traversal and working tree rollback.

**Milestone Gate 3**: Agent resolves complex cross-file refactoring tasks without blind grep turns; per-turn token costs drop by $>80\%$ via dual-model routing.

---

## Phase 4: Hardening & Evaluation (Weeks 10–12)
**Goal**: Objectively prove PARI surpasses production baselines on standard benchmarks and withstands security audits.

### Deliverables
* **Layer 10 — Evaluation & Observability Harness**:
  * Build local micro-eval runner (`pari eval run`) with immutable test guards.
  * Implement Cross-Model Verification judge (Graptile Principle).
  * Implement structured JSON logging via `structlog`.
* **Benchmark Validation**:
  * Execute PARI across **SWE-bench Lite** (300 benchmark software issues).
  * Target Metric 1: $\ge 50\%$ benchmark pass rate (surpassing Claude Code and Pi baselines).
  * Target Metric 2: Average resolution cost $\le \$0.25$ per task.
* **Security & Penetration Audit**:
  * Execute prompt injection attacks attempting sandbox escape, privilege escalation, and SSH key exfiltration.
  * Audit `FileMutationQueue` path traversal protections (`../` escapes, symlink attacks).
* **Documentation & Open-Source Release**:
  * Finalize developer manuals, API specs, and deployment templates.

**Milestone Gate 4**: SWE-bench Lite pass rate verified $\ge 50\%$; zero sandbox escape vulnerabilities identified; micro-eval test suite passes cleanly.
