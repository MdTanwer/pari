# PARI — Next-Generation Terminal Coding Agent

> *A Synthesis Architecture That Surpasses Claude Code, OpenAI Codex, OpenCode, Pi, Aider, Cursor, and Google Antigravity.*  
> *(Named by a college friend, built for world-class systems engineering performance.)*

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![Architecture: 11-Layer Stack](https://img.shields.io/badge/architecture-11--layer-green.svg)](docs/architecture/overview.md)
[![Security: Kernel Sandboxed](https://img.shields.io/badge/sandbox-bwrap%20%7C%20Seatbelt%20%7C%20E2B-orange.svg)](docs/layers/layer-0-sandboxing.md)

---

## ⚡ The Core Thesis

$$\text{\bf Agent failure is a systems engineering failure, not a reasoning failure.}$$

The exact same frontier reasoning model (Claude 3.7 Sonnet, GPT-4o) demonstrates a **15% pass rate** in a naive loop, but achieves a **50–55% pass rate** inside an engineered harness. The 35% delta is not model intelligence; it is accounted for by **six fatal systems failure modes**:

1. **Unbounded stdout poisoning** $\rightarrow$ Solved by Layer 7 (50KB/2k-line disk spooler + balanced head/tail extraction).
2. **Mid-stream token truncation** $\rightarrow$ Solved by Layer 4 (Strict `stop_reason == "length"` rejection guard).
3. **File write race conditions** $\rightarrow$ Solved by Layer 6 (`FileMutationQueue` canonical realpath serialization).
4. **KV cache invalidation cascades** $\rightarrow$ Solved by Layer 2 (Immutable Baseline Epochs freezing Tiers 1–4).
5. **Blind file traversal loops** $\rightarrow$ Solved by Layer 3 (v1: Fast substring ripgrep & globbing / v2: Tree-sitter AST fallback).
6. **Unsandboxed host execution** $\rightarrow$ Solved by Layer 0 (Multi-platform kernel isolation: `bwrap`, `Seatbelt`, E2B MicroVMs).

---

## 🏗️ 11-Layer Architecture Topology

```
+-----------------------------------------------------------------------------------+
|                              PARI -- SYSTEM TOPOLOGY                              |
+-----------------------------------------------------------------------------------+
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
|  Layer 3:  NAVIGATION (v1: Substring Grep & Globbing / v2: Tree-sitter Fallback)  |
|                                          |                                        |
|  Layer 2:  CONTEXT & CACHE (Immutable Epoch + mid-session updates + Warmer)      |
|                                          |                                        |
|  Layer 1:  DURABLE SESSION (Append-only JSONL Merkle DAG + Checkpoint Index)     |
|                                          |                                        |
|  Layer 0:  SANDBOX (bwrap on Linux/WSL2 + Seatbelt on macOS + E2B Cloud)         |
+-----------------------------------------------------------------------------------+
```

---

## 📚 Complete Documentation Suite

All system documentation has been modularized and organized inside the [`docs/`](docs/README.md) directory:

### Architecture Deep Dives
* [Architecture Overview](docs/architecture/overview.md) — System topology, execution lifecycle, and core thesis.
* [Failure Mode Atlas](docs/architecture/failure-mode-atlas.md) — Verified weaknesses across 7 production systems.
* [The Trade-Off Framework](docs/architecture/trade-offs.md) — The 12 design trade-off axes and what PARI sacrifices.
* [Cross-System Decision Matrix](docs/architecture/decision-matrix.md) — Harvested innovations vs. discarded anti-patterns.

### Layer Specifications
* [Layer 0: Sandboxing Engine](docs/layers/layer-0-sandboxing.md) — Multi-platform kernel isolation (`bwrap`, `Seatbelt`, E2B).
* [Layer 1: Durable Session Engine](docs/layers/layer-1-session-dag.md) — Append-only JSONL Merkle DAG with $O(K)$ checkpoints.
* [Layer 2: Context & Cache Architecture](docs/layers/layer-2-context-cache.md) — Immutable Baseline Epochs & Economic Warmer.
* [Layer 3: Codebase Intelligence & Navigation](docs/layers/layer-3-intelligence-repomap.md) — v1 ripgrep & globbing / v2 Tree-sitter AST fallback.

* [Layer 4: Agent Execution Loop](docs/layers/layer-4-execution-loop.md) — Double-while state machine & PTY daemon detection.
* [Layer 5: Multi-Tier Fuzzy Edit Engine](docs/layers/layer-5-edit-engine.md) — 4-tier diff cascade (Exact $\rightarrow$ Git OSR $\rightarrow$ DMP $\rightarrow$ Prefill).
* [Layer 6: Concurrency & File Safety](docs/layers/layer-6-concurrency-safety.md) — `FileMutationQueue` realpath locks & shadow worktrees.
* [Layer 7: Output Hygiene](docs/layers/layer-7-output-hygiene.md) — 50KB/2k-line spooler & structured traceback parsing.
* [Layer 8: Dual-Model Routing Engine](docs/layers/layer-8-dual-model-router.md) — Architect vs. Editor decoupling (85% cost reduction).
* [Layer 9: Terminal Interface & TUI](docs/layers/layer-9-terminal-interface.md) — Rich differential streaming & zero idle CPU drain.
* [Layer 10: Evaluation & Observability](docs/layers/layer-10-eval-observability.md) — Local micro-eval suite & Cross-Model Verification.

### Developer Guides
* [Developer Pain Points & Solutions](docs/guides/user-pain-and-solutions.md) — Real developer frustrations and PARI's direct fixes.
* [Getting Started Guide](docs/guides/getting-started.md) — Installation, environment setup, and running locally.
* [Phased Build Roadmap](docs/guides/roadmap.md) — 12-week implementation timeline across four phases.

---

## 🚀 Quick Start

### Installation
```bash
git clone https://github.com/MdTanwer/pari.git
cd pari
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```

### Launch Interactive Session
```bash
# Export your API key
export ANTHROPIC_API_KEY="sk-ant-..."

# Launch PARI in your active project workspace
pari
```

---

## ⚖️ License

MIT License. See [LICENSE](LICENSE) for details.
