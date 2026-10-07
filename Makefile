SHELL := /usr/bin/env bash
.SHELLFLAGS := -eu -o pipefail -c

ECHO := printf '%b\n'
GREEN := \033[32m
YELLOW := \033[33m
CYAN := \033[36m
RESET := \033[0m
UNDERLINE := \033[4m

.PHONY: format lint pre-commit help

.DEFAULT_GOAL := help

format:
	@$(ECHO) "$(YELLOW)Formatting code with ruff...$(RESET)"
	@uv run ruff format pari tests
	@$(ECHO) "$(GREEN)Code formatted successfully.$(RESET)"

lint:
	@$(ECHO) "$(YELLOW)Linting code with ruff...$(RESET)"
	@uv run ruff check --fix pari tests
	@$(ECHO) "$(GREEN)Linting completed.$(RESET)"

pre-commit:
	@$(ECHO) "$(YELLOW)Running pre-commit...$(RESET)"
	uv run pre-commit run --all-files
	@$(ECHO) "$(GREEN)Pre-commit completed.$(RESET)"

help:
	@$(ECHO) "$(CYAN)PARI Makefile$(RESET)"
	@$(ECHO) ""
	@$(ECHO) "$(UNDERLINE)Usage:$(RESET) make <COMMAND>"
	@$(ECHO) ""
	@$(ECHO) "$(UNDERLINE)Commands:$(RESET)"
	@$(ECHO) "  $(GREEN)format$(RESET)       Format code with ruff"
	@$(ECHO) "  $(GREEN)lint$(RESET)         Lint code with ruff"
	@$(ECHO) "  $(GREEN)pre-commit$(RESET)   Run pre-commit on all files"
	@$(ECHO) "  $(GREEN)help$(RESET)         Show this help message"
