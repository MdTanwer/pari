# Getting Started with PARI

This guide walks you through installing, configuring, and executing PARI for local terminal coding.

---

## 1. System Prerequisites

### Supported Platforms
* **Linux**: Ubuntu 20.04+, Debian 11+, Fedora 38+, Arch Linux.
* **macOS**: macOS 12 (Monterey) or higher (Apple Silicon and Intel).
* **Windows**: Recommended via **WSL2** (Ubuntu/Debian) for native Bubblewrap kernel isolation; native Windows supported with Supervised Guardrail mode.

### Required Software
* **Python**: Python `3.11` or higher.
* **Git**: `git` version `2.25` or higher.
* **Sandbox Primitives**:
  * *Linux / WSL2*: `bubblewrap` (`sudo apt-get install bubblewrap` or `sudo dnf install bubblewrap`).
  * *macOS*: Built-in native Apple Seatbelt (`sandbox-exec` available by default).

---

## 2. Installation & Setup

### Step 1: Clone Repository & Create Virtual Environment
```bash
# Clone the repository
git clone https://github.com/MdTanwer/pari.git
cd pari

# Create a dedicated Python 3.11+ virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Upgrade pip
pip install --upgrade pip setuptools wheel
```

### Step 2: Install Package Dependencies
```bash
# Install core dependencies with Tree-sitter and Rich support
pip install -e .
```

### Step 3: Configure Environment Variables
Create a `.env` file in the project root or export keys into your shell profile:

```bash
# Required: At least one LLM provider
export ANTHROPIC_API_KEY="sk-ant-..."
export OPENAI_API_KEY="sk-proj-..."
export DEEPSEEK_API_KEY="sk-..."

# Optional: For Cloud Sandbox Mode (Hardware MicroVMs)
export E2B_API_KEY="e2b_..."

# Optional: Preferred Sandbox Mode (auto, bwrap, seatbelt, cloud)
export PARI_SANDBOX="auto"
```

---

## 3. Running PARI

### Interactive Terminal Session
To launch an interactive coding session inside your current repository:
```bash
pari
```

### Verify CLI Installation
```bash
# View all available CLI flags and options
pari --help

# Run self-check to verify environment and sandbox availability
pari --dry-run
```

### Common CLI Options
```bash
# Launch with explicit active reference files loaded into Tier 4 Context
pari --add src/auth/service.py --add docs/api_spec.md

# Specify target workspace explicitly
pari --workspace /path/to/project

# Enable optional v2 AST PageRank context fallback
pari --repomap ppr

# Enable optional edit fallback cascade
pari --edit-fallback cascade
```

---

## 4. In-Session Interactive Slash Commands

Once inside the interactive prompt, you can use built-in slash commands to inspect and control the agent state:

```
pari> /help

Available Commands:
  /undo              Guarded rollback of files changed in last turn & process cleanup
  /diff              Display unified git diff of current uncommitted changes
  /snapshot <name>   Create a labeled restore checkpoint in the session DAG
  /add <path>        Pin a file or documentation into Tier 4 Context Epoch
  /drop <path>       Unpin a file from Tier 4 Context Epoch
  /model <name>      Dynamically switch active model provider
  /cost              Display detailed breakdown of token consumption and USD spend
  /reset             Clear conversation history while maintaining session root
  /exit              Exit session cleanly (session state is durable in .pari/)
```

---

## 5. Verifying Installation

To verify that the PARI v1 core CLI and environment are functioning properly on your system:

```bash
# Run environment self-check
pari --dry-run
```

This will:
1. Detect and verify the platform sandbox (`bwrap` on Linux/WSL2).
2. Validate workspace path resolution and permission boundaries.
3. Verify that dependencies and CLI entrypoints are active.

