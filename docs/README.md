# PARI Documentation Hub

Welcome to the technical documentation for **PARI** — a next-generation, high-performance terminal coding agent engineered to surpass the architectural and reliability shortcomings of existing systems including Claude Code, OpenAI Codex, OpenCode, Pi, Aider, Cursor, and Google Antigravity.

---

## 🧭 Documentation Map

The documentation is organized into modular sections covering high-level architecture, individual deep-dive engine layers, trade-offs, and practical development guides:

### 1. Architectural Foundations
* [System Overview & Topology](architecture/overview.md) — The 11-layer stack, execution lifecycle, and core thesis.
* [Failure Mode Atlas](architecture/failure-mode-atlas.md) — Comprehensive breakdown of verified failures across 7 frontier systems.
* [The Trade-Off Framework](architecture/trade-offs.md) — The 12 fundamental agent design trade-offs and what PARI sacrifices.
* [Cross-System Decision Matrix](architecture/decision-matrix.md) — Architectural element harvesting, discard rationales, and comparative matrix.

---

### 2. Core Engine Layers (Deep Dives)
Every layer in PARI is strictly decoupled and independently testable:

| Layer | Component | Summary |
|---|---|---|
| **Layer 0** | [Sandboxing Engine](layers/layer-0-sandboxing.md) | Multi-platform kernel isolation: `bwrap` (Linux/WSL2), Apple `Seatbelt` (macOS), and E2B Firecracker MicroVMs (Cloud). |
| **Layer 1** | [Durable Session Engine](layers/layer-1-session-dag.md) | Append-only JSONL Merkle DAG with UUIDv7, atomic CRC32 append guards, and $O(K)$ checkpoint indexing. |
| **Layer 2** | [Context & Cache Architecture](layers/layer-2-context-cache.md) | Immutable Baseline Epochs, 8-tier ChatChunks, autonomous economic cache warmer, and safe compaction. |
| **Layer 3** | [Codebase Navigation](layers/layer-3-intelligence-repomap.md) | v1: Substring ripgrep & globbing (zero lag); v2: Tree-sitter AST & PageRank fallback. |
| **Layer 4** | [Agent Execution Runtime](layers/layer-4-execution-loop.md) | Double-while state machine, token truncation length guard, PTY daemon detection, and structured reflection. |
| **Layer 5** | [Multi-Tier Fuzzy Edit Engine](layers/layer-5-edit-engine.md) | 4-tier diff cascade: Exact Match $\rightarrow$ Synthetic Git OSR $\rightarrow$ Google DMP $\rightarrow$ Prefill Continuation. |
| **Layer 6** | [Concurrency & File Safety](layers/layer-6-concurrency-safety.md) | `FileMutationQueue` realpath serialization, symlink deduplication, and shadow git worktrees. |
| **Layer 7** | [Output Hygiene & Spooler](layers/layer-7-output-hygiene.md) | 50KB / 2,000-line disk spooler, balanced head/tail extraction, and structured traceback parsing. |
| **Layer 8** | [Dual-Model Routing Engine](layers/layer-8-dual-model-router.md) | Architect vs. Editor decoupling, task classification, anti-planning guards, and 85% cost optimization. |
| **Layer 9** | [Terminal Interface & TUI](layers/layer-9-terminal-interface.md) | Rich differential rendering, live streaming, interactive diff reviews, and cost tracking. |
| **Layer 10** | [Evaluation & Observability](layers/layer-10-eval-observability.md) | Built-in micro-eval suite, SWE-bench Lite harness, cross-model Graptile judge, and structlog telemetry. |

---

### 3. Practical Guides & Strategy
* [Developer Pain Points & PARI Solutions](guides/user-pain-and-solutions.md) — Why existing coding agents frustrate developers and how PARI systematically addresses each pain point.
* [Getting Started Guide](guides/getting-started.md) — Environment prerequisites, installation, local setup, and sandbox configuration.
* [Phased Build Roadmap](guides/roadmap.md) — 12-week implementation timeline across Foundation, Runtime, Intelligence, and Hardening.

---

## 🎯 Recommended Reading Paths

### For Systems & Security Engineers
1. [Failure Mode Atlas](architecture/failure-mode-atlas.md)
2. [Layer 0: Sandboxing Engine](layers/layer-0-sandboxing.md)
3. [Layer 6: Concurrency & File Safety](layers/layer-6-concurrency-safety.md)
4. [Layer 1: Durable Session Engine](layers/layer-1-session-dag.md)

### For AI & Agentic Researchers
1. [System Overview & Core Thesis](architecture/overview.md)
2. [Layer 8: Dual-Model Routing Engine](layers/layer-8-dual-model-router.md)
3. [Layer 2: Context & Cache Architecture](layers/layer-2-context-cache.md)
4. [Layer 3: Intelligence & AST RepoMap](layers/layer-3-intelligence-repomap.md)
5. [Layer 10: Evaluation & Observability](layers/layer-10-eval-observability.md)

### For CLI & Product Builders
1. [Developer Pain Points & Solutions](guides/user-pain-and-solutions.md)
2. [Layer 4: Agent Execution Runtime](layers/layer-4-execution-loop.md)
3. [Layer 5: Multi-Tier Fuzzy Edit Engine](layers/layer-5-edit-engine.md)
4. [Layer 9: Terminal Interface & TUI](layers/layer-9-terminal-interface.md)
5. [Getting Started Guide](guides/getting-started.md)
