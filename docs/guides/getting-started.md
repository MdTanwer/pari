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

### Common CLI Options
```bash
# Launch with explicit active reference files loaded into Tier 4 Context
pari --add src/auth/service.py --add docs/api_spec.md

# Configure Dual-Model Router profiles explicitly
pari --architect claude-3-7-sonnet --editor claude-3-5-haiku

# Run using open-weights models via DeepSeek API
pari --architect deepseek-r1 --editor deepseek-v3

# Force Cloud MicroVM Sandboxing (useful in CI/CD)
pari --sandbox cloud

# Resume a previous session by session ID
pari --resume 0192abc0-1111-7000-8000-000000000001
```

---

## 4. In-Session Interactive Slash Commands

Once inside the interactive prompt, you can use built-in slash commands to inspect and control the agent state:

```
pari> /help

Available Commands:
  /undo              Revert repository changes from the most recent turn
  /diff              Display unified git diff of current uncommitted changes
  /snapshot <name>   Create a labeled restore checkpoint in the session DAG
  /add <path>        Pin a file or documentation into Tier 4 Context Epoch
  /drop <path>       Unpin a file from Tier 4 Context Epoch
  /model <name>      Dynamically switch active model provider
  /cost              Display detailed breakdown of token consumption and USD spend
  /reset             Clear conversation history while preserving repo AST cache
  /exit              Exit session cleanly (session state is durable in .pari/)
```

---

## 5. Verifying Installation with Micro-Evals

To verify that all 11 layers of PARI are functioning properly on your system:

```bash
# Run the local 10-issue verification suite
pari eval run --suite ./evals/micro_suite.json
```

This will:
1. Boot the platform sandbox (`bwrap` or `Seatbelt`).
2. Construct the Tree-sitter AST repository map.
3. Execute the double-while execution loop with test assertions.
4. Verify diff application via the 4-tier edit cascade.
5. Print a structured verification report to the terminal.
