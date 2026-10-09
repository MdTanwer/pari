#!/usr/bin/env bash
set -eo pipefail

# PARI Installer for Linux and macOS
# Usage: curl -fsSL https://pari-cli.in/install.sh | bash
# (Alternative: curl -fsSL https://raw.githubusercontent.com/MdTanwer/pari/main/install.sh | bash)

REPO_URL="https://github.com/MdTanwer/pari.git"
INSTALL_DIR="$HOME/.pari"
BIN_DIR="$HOME/.local/bin"

BOLD="$(tput bold 2>/dev/null || echo '')"
CYAN="$(tput setaf 6 2>/dev/null || echo '')"
GREEN="$(tput setaf 2 2>/dev/null || echo '')"
YELLOW="$(tput setaf 3 2>/dev/null || echo '')"
RED="$(tput setaf 1 2>/dev/null || echo '')"
RESET="$(tput sgr0 2>/dev/null || echo '')"

# 1. Prefer uv if installed (fastest)
if command -v uv >/dev/null 2>&1; then
    if ! uv tool install --force pari-cli >/dev/null; then
        echo "${YELLOW}PyPI package install failed; falling back to GitHub source...${RESET}" >&2
        uv tool install --force "git+${REPO_URL}" >/dev/null
    fi
    echo "pari-cli installed"
    exit 0
fi

# 2. Prefer pipx if installed (isolated)
if command -v pipx >/dev/null 2>&1; then
    if ! pipx install --quiet --force pari-cli >/dev/null; then
        echo "${YELLOW}PyPI package install failed; falling back to GitHub source...${RESET}" >&2
        pipx install --quiet --force "git+${REPO_URL}" >/dev/null
    fi
    echo "pari-cli installed"
    exit 0
fi

# 3. Fallback: Create self-contained virtualenv under ~/.pari/venv
if command -v python3 >/dev/null 2>&1; then
    # Verify Python version >= 3.11
    if ! python3 -c 'import sys; sys.exit(0 if sys.version_info >= (3, 11) else 1)' 2>/dev/null; then
        PY_VER="$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")' 2>/dev/null || echo 'unknown')"
        echo "${RED}Error: Python 3.11+ is required, but python3 is version ${PY_VER}.${RESET}"
        echo "Please install or upgrade Python to 3.11+ from https://www.python.org/ or your package manager."
        exit 1
    fi

    echo "${YELLOW}Notice: Neither uv nor pipx found.${RESET} Setting up isolated environment in ${INSTALL_DIR}..."
    mkdir -p "$INSTALL_DIR"
    mkdir -p "$BIN_DIR"

    # Clean prior venv if corrupt or from an older Python version
    rm -rf "$INSTALL_DIR/venv"
    python3 -m venv "$INSTALL_DIR/venv"

    "$INSTALL_DIR/venv/bin/pip" install --upgrade pip --quiet
    if ! "$INSTALL_DIR/venv/bin/pip" install --upgrade pari-cli --quiet; then
        echo "${YELLOW}PyPI package install failed; falling back to GitHub source...${RESET}"
        "$INSTALL_DIR/venv/bin/pip" install "git+${REPO_URL}" --quiet
    fi

    # Create symlink in ~/.local/bin
    ln -sf "$INSTALL_DIR/venv/bin/pari-cli" "$BIN_DIR/pari-cli"

    # Ensure ~/.local/bin is in user PATH
    SHELL_CONFIG=""
    USER_SHELL="${SHELL##*/}"

    if [[ ":$PATH:" != *":$BIN_DIR:"* ]]; then
        case "$USER_SHELL" in
            zsh)
                SHELL_CONFIG="$HOME/.zshrc"
                ;;
            bash)
                if [ "$(uname -s 2>/dev/null)" = "Darwin" ]; then
                    SHELL_CONFIG="$HOME/.bash_profile"
                else
                    SHELL_CONFIG="$HOME/.bashrc"
                fi
                ;;
            fish)
                if command -v fish >/dev/null 2>&1; then
                    fish -c "fish_add_path '$BIN_DIR'" 2>/dev/null || true
                fi
                echo "${YELLOW}Fish shell detected: run 'fish_add_path ~/.local/bin' if 'pari-cli' is not found.${RESET}"
                ;;
            *)
                echo "${YELLOW}Please add ~/.local/bin to your PATH in your shell configuration.${RESET}"
                ;;
        esac

        if [ -n "$SHELL_CONFIG" ]; then
            if ! grep -q '\.local/bin' "$SHELL_CONFIG" 2>/dev/null; then
                echo 'export PATH="$HOME/.local/bin:$PATH"' >> "$SHELL_CONFIG"
                echo "${YELLOW}Added ~/.local/bin to $SHELL_CONFIG${RESET}"
            fi
        fi
    fi

    # Check for binary shadowing
    if command -v pari-cli >/dev/null 2>&1; then
        RESOLVED_PARI="$(command -v pari-cli)"
        if [ "$RESOLVED_PARI" != "$BIN_DIR/pari-cli" ]; then
            echo "${YELLOW}Note: 'pari-cli' is currently resolving to $RESOLVED_PARI${RESET}"
        fi
    fi

    echo "pari-cli installed"
    exit 0
else
    echo "${RED}Error: Python 3.11+ is required but not found on your system.${RESET}"
    echo "Please install Python from https://www.python.org/ or via your package manager."
    exit 1
fi
