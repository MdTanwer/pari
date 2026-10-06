#!/usr/bin/env bash
set -e

# PARI Installer for Linux and macOS
# Usage: curl -fsSL https://raw.githubusercontent.com/MdTanwer/pari/main/install.sh | bash

REPO_URL="https://github.com/MdTanwer/pari.git"
INSTALL_DIR="$HOME/.pari"
BIN_DIR="$HOME/.local/bin"

BOLD="$(tput bold 2>/dev/null || echo '')"
CYAN="$(tput setaf 6 2>/dev/null || echo '')"
GREEN="$(tput setaf 2 2>/dev/null || echo '')"
YELLOW="$(tput setaf 3 2>/dev/null || echo '')"
RESET="$(tput sgr0 2>/dev/null || echo '')"

echo "${CYAN}${BOLD}"
echo "  ___   _   ___ ___ "
echo " | _ \ /_\ | _ \_ _|"
echo " |  _// _ \|   /| | "
echo " |_| /_/ \_\_|_\___|"
echo "${RESET}"
echo "Installing ${BOLD}PARI — Terminal Coding Agent${RESET}..."
echo ""

# 1. Prefer uv if installed (fastest)
if command -v uv >/dev/null 2>&1; then
    echo "${GREEN}✓ Found uv.${RESET} Installing pari via uv tool..."
    uv tool install --force pari 2>/dev/null || uv tool install --force "git+${REPO_URL}"
    echo ""
    echo "${GREEN}${BOLD}✓ PARI installed successfully!${RESET}"
    echo "Run ${CYAN}pari${RESET} to get started."
    exit 0
fi

# 2. Prefer pipx if installed (isolated)
if command -v pipx >/dev/null 2>&1; then
    echo "${GREEN}✓ Found pipx.${RESET} Installing pari via pipx..."
    pipx install --force pari 2>/dev/null || pipx install --force "git+${REPO_URL}"
    echo ""
    echo "${GREEN}${BOLD}✓ PARI installed successfully!${RESET}"
    echo "Run ${CYAN}pari${RESET} to get started."
    exit 0
fi

# 3. Fallback: Create self-contained virtualenv under ~/.pari/venv
if command -v python3 >/dev/null 2>&1; then
    echo "${YELLOW}Notice: Neither uv nor pipx found.${RESET} Setting up isolated environment in ${INSTALL_DIR}..."
    mkdir -p "$INSTALL_DIR"
    mkdir -p "$BIN_DIR"

    python3 -m venv "$INSTALL_DIR/venv"
    "$INSTALL_DIR/venv/bin/pip" install --upgrade pip --quiet
    "$INSTALL_DIR/venv/bin/pip" install pari --quiet 2>/dev/null || "$INSTALL_DIR/venv/bin/pip" install "git+${REPO_URL}" --quiet

    # Create symlink in ~/.local/bin
    ln -sf "$INSTALL_DIR/venv/bin/pari" "$BIN_DIR/pari"

    # Verify if ~/.local/bin is in PATH
    if [[ ":$PATH:" != *":$BIN_DIR:"* ]]; then
        SHELL_CONFIG=""
        if [ -n "$ZSH_VERSION" ] || [ "$SHELL" = "*/zsh" ]; then
            SHELL_CONFIG="$HOME/.zshrc"
        elif [ -n "$BASH_VERSION" ] || [ "$SHELL" = "*/bash" ]; then
            SHELL_CONFIG="$HOME/.bashrc"
        fi

        if [ -n "$SHELL_CONFIG" ]; then
            echo "export PATH=\"\$HOME/.local/bin:\$PATH\"" >> "$SHELL_CONFIG"
            echo "${YELLOW}Added ~/.local/bin to $SHELL_CONFIG${RESET}"
        fi
    fi

    echo ""
    echo "${GREEN}${BOLD}✓ PARI installed successfully in ~/.local/bin/pari!${RESET}"
    echo "Run ${CYAN}pari${RESET} (or restart your terminal if needed)."
    exit 0
else
    echo "Error: Python 3.11+ is required but not found on your system."
    echo "Please install Python from https://www.python.org/ or via your package manager."
    exit 1
fi
