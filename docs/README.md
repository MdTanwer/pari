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

### 2. Core Engine Layers (Implementation Status)

To maintain strict engineering honesty, features in this documentation are explicitly labeled by implementation maturity:
* 🟢 **Implemented**: Code and automated test suite exist and pass in the repository.
* 🟡 **v1 Prototype**: Core logic/scaffolding implemented; undergoing integration.
* ⚪ **Planned Design Target**: Architecture specification documented; scheduled in roadmap.

| Layer | Component | Implementation Status | Scope / Deliverable |
|---|---|---|---|
| **Layer 0** | [Sandboxing Engine](layers/layer-0-sandboxing.md) | ⚪ Planned Design Target | v1 target: Linux/WSL2 Bubblewrap (`bwrap`) |
| **Layer 1** | [Durable Session Engine](layers/layer-1-session-dag.md) | 🟡 v1 Prototype | Append-only JSONL event log with CRC32 |
| **Layer 2** | [Context & Cache](layers/layer-2-context-cache.md) | ⚪ Planned Design Target | Immutable Baseline Epochs & prompt structure |
| **Layer 3** | [Codebase Navigation](layers/layer-3-intelligence-repomap.md) | 🟡 v1 Prototype | Substring ripgrep & file globbing (v2: AST PageRank) |
| **Layer 4** | [Agent Execution Runtime](layers/layer-4-execution-loop.md) | ⚪ Planned Design Target | Double-while loop & PTY daemon watchdog |
| **Layer 5** | [Edit Engine](layers/layer-5-edit-engine.md) | 🟡 v1 Prototype | Exact-match with strict fail-on-ambiguity + diffs |
| **Layer 6** | [Concurrency & File Safety](layers/layer-6-concurrency-safety.md) | 🟡 v1 Prototype | Safe path traversal guard & atomic disk replacement |
| **Layer 7** | [Output Hygiene](layers/layer-7-output-hygiene.md) | ⚪ Planned Design Target | 50KB/2k-line spooler with sidecar pointers |
| **Layer 8** | [Dual-Model Router](layers/layer-8-dual-model-router.md) | ⚪ Planned Target (v2) | Architect/Editor task classifier |
| **Layer 9** | [Terminal Interface](layers/layer-9-terminal-interface.md) | 🟡 v1 Prototype | CLI argument parser & environment inspection |
| **Layer 10** | [Evaluation Harness](layers/layer-10-eval-observability.md) | ⚪ Planned Target (Phase 4)| Micro-eval runner & deterministic benchmark |


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
