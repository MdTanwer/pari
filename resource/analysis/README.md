# Architecture Analysis

This directory contains the detailed architectural analysis of Claude Code and the blueprint for building a superior terminal coding agent.

- [terminal_agent_architecture.md](file:///c:/Users/tanw9/pari/resource/analysis/terminal_agent_architecture.md) — Comprehensive breakdown (1,000+ lines) detailing:
  - 5-Tier Onion Middleware Pipeline (`prepend` -> `user` -> `append` -> `builtin` -> `core`)
  - Microkernel Engine Context (`$`)
  - Built-in Tool Inventory & Behavior Contracts
  - Multi-Surface Terminal UI & Event Bus
  - Sandboxed Mod / Plugin Runtime
  - Subagents, Concurrency & Worktree Isolation
  - Token Compaction & Session Lifecycle
  - Architectural Bottlenecks of Claude Code
  - Blueprint & 6-Layer Architecture for a Better Native Agent (Rust core, Tree-sitter + LSP, Shadow Workspaces)
  - 7-Phase Implementation Roadmap
