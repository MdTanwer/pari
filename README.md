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

## 🚀 Installation & Quick Start

Official Website & Documentation: **[https://pari-cli.in](https://pari-cli.in)**

Choose your platform's installation command:

### 1. macOS & Linux (`curl`)
```bash
curl -fsSL https://pari-cli.in/install.sh | bash
```

### 2. Windows (`irm` in PowerShell)
```powershell
irm https://www.pari-cli.in/install.ps1 | iex
```

### 3. Via `pip` / `pipx` / `uv`
```bash
# Recommended (isolated CLI)
pipx install pari-cli

# Fast via uv
uv tool install pari-cli

# Standard pip
pip install pari-cli
```

---

### 💻 Launch Interactive Session
```bash
# Export your API key
export ANTHROPIC_API_KEY="sk-ant-..."

# Launch PARI anywhere in your project workspace
pari-cli
```

---

## ⚖️ License

MIT License. See [LICENSE](LICENSE) for details.
