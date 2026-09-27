# Terminal Coding Agent Architecture Analyses

Comprehensive architectural deep-dives, reverse-engineering analyses, and blueprints comparing state-of-the-art terminal coding agents with real source code references.

---

## Analysis Index

### 1. [Claude Code Architecture & Blueprint](file:///c:/Users/tanw9/pari/resource/analysis/terminal_agent_architecture.md)
*Source: `resource/claude-code` (TypeScript / Node.js)*
- 5-Tier Onion Middleware Pipeline (`prepend` -> `user` -> `append` -> `builtin` -> `core`)
- Microkernel Engine Context (`$`)
- Built-in Tool Inventory & Behavior Contracts
- Multi-Surface Terminal UI & Event Bus
- Mod / Plugin Isolation & Bash Subprocess Execution
- 6-Layer Architecture Blueprint for a Next-Generation Agent

### 2. [Claude Code Layer Integration Deep Dive](file:///c:/Users/tanw9/pari/resource/analysis/how_layers_work_together.md)
*Source: `resource/claude-code`*
- How memory, context window compaction, agent turn loop, and sandboxing operate together
- Complete message lifecycle from user input through token compaction to terminal rendering

### 3. [Codex Architecture Deep Dive](file:///c:/Users/tanw9/pari/resource/analysis/codex_architecture.md)
*Source: `resource/codex/codex-rs` (Rust / Tokio)*
- 119 Rust crates in a unified workspace
- `CodexThread` state snapshotting and `ThreadManager` multi-agent coordination
- 3-Layer Memory Architecture (In-memory vector, SQLite `AgentGraphStore`, persistent disk cache)
- Dual Compaction: In-memory truncation vs. Remote V2 summarization
- OS-Level Sandboxing: macOS Seatbelt, Linux Bubblewrap, Windows Restricted Token
- BANNED_PREFIX_SUGGESTIONS shell execution policy

### 4. [OpenCode Architecture Deep Dive](file:///c:/Users/tanw9/pari/resource/analysis/opencode_architecture.md)
*Source: `resource/opencode` (TypeScript / Effect-TS / Bun)*
- Effect-TS functional runtime: Services, Layers, Scopes, and FiberSet concurrency
- Double-while `SessionRunner` drain loop (prompt steering vs. queued prompts)
- SQLite WAL relational schema (`SessionTable`, `SessionMessageTable`, `SessionContextEpochTable`)
- Immutable Baseline Context Epochs and Mid-Conversation System Messages
- Dual Compaction: Proactive token budget reservation (20k) + reactive 400 overflow recovery
- `ToolOutputStore` with Managed Tool Output Files (50KB / 2k line head-and-tail previews)
- Git-backed content-addressed workspace snapshots and time-travel rewind

### 5. [Pi Architecture Deep Dive](file:///c:/Users/tanw9/pari/resource/analysis/pi_architecture.md)
*Source: `resource/pi` (TypeScript / Node.js / Bun)*
- Core `agentLoop` double-loop with length-stop defense (fails tool calls when prompt output is truncated)
- Dynamic tool declaration diffing (`declareToolChanges` sets `toolsAdded` / `toolsRemoved`)
- Append-only JSONL Merkle Trees with branching DAGs and append-only `ContextEditEntry` redactions
- Autonomous Prompt Cache Warmer: Economics-driven 1-token output pings at 90% TTL
- Backward Safe-Cut Compaction with cumulative `readFiles` and `modifiedFiles` tracking
- Canonical path mutation lock (`withFileMutationQueue`) for race-free parallel file operations
- Pluggable `BashOperations.exec` for micro-VM isolation (Gondolin extension)
- Process-isolated subagents in headless JSON mode (Single, Parallel, Chain)
- Custom differential terminal rendering with OKLab color spaces, Kitty/Sixel graphics, and LaTeX math

---

## Architectural Comparison Matrix

| Architectural Dimension | Claude Code | Codex (`codex-rs`) | OpenCode | Pi (`pi-coding-agent`) |
|-------------------------|-------------|--------------------|----------|------------------------|
| **Primary Language** | TypeScript (Node.js) | Rust | TypeScript (Bun / Node) | TypeScript (Node / Bun) |
| **Runtime Paradigm** | Async/await + Events | Tokio actor threads | Effect-TS functional | Modular decoupled libraries |
| **Session Persistence** | Flat JSON / In-memory | SQLite graph store | SQLite WAL tables | **Append-only JSONL Merkle DAG** |
| **Branching & Rewind** | In-memory stack | Commit stack | Revert snapshot | **Tree DAG via `parentId` pointers** |
| **Context Updates** | Static full rewrite | Token-budgeted prompt | Baseline Epoch + Mid-Convo | **XML Tagged Sections + Tool Diffs** |
| **Prompt Cache Handling** | Static heuristics | Prefix state tracker | Explicit cache keys | **Autonomous Cache Warmer (Economics)** |
| **Compaction Strategy** | Single-pass summary | In-memory vs Remote | Dual (proactive + 400) | **Backward Safe Cuts + File Op Tracking** |
| **Tool Concurrency** | Basic `Promise.all` | Async task spawn | Parallel `FiberSet` | **Canonical Path Mutation Queue** |
| **Large Tool Outputs** | Memory slice | Memory byte truncate | Managed disk files | **Head / Tail / Middle Truncation + Cap** |
| **Sandboxing Strategy** | macOS Seatbelt | OS Seatbelt / Bubblewrap | Tri-state rule engine | **Pluggable micro-VMs (Gondolin / Docker)** |
| **Subagent Architecture** | Ephemeral sessions | Thread coordination | `SessionTable.parent_id` | **Independent Child Processes (JSON mode)** |
| **Terminal UI Engine** | React / Ink | Crossterm / Ratatui | Ink / Custom | **Custom Differential TUI + Kitty/Sixel** |
