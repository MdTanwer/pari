# Layer 9: Terminal Interface & TUI

> **Closes Failures**: Terminal UX degradation, uninformative hanging states, and Cursor F4 (background CPU pegging indexers).  
> **Harvested From**: Pi's differential TUI rendering and Aider's `prompt_toolkit` interactive command loop.

---

## 1. Overview & Terminal-First Philosophy

Autonomous coding agents must live where senior software engineers work: inside the terminal, alongside `tmux`, `ssh`, `neovim`, and Git. 

Building heavy Electron desktop apps (like Cursor) introduces massive RAM overhead (8–16 GB), constant background vector indexing that pegs laptop CPUs, and dangerous virtual/physical buffer desynchronizations.

PARI delivers a **Pure Terminal Interface** built with **Rich** and **prompt_toolkit** that provides a desktop-grade visual experience with zero background CPU overhead.

---

## 2. Key TUI Capabilities

```
+-----------------------------------------------------------------------------------+
| PARI :: claude-3-7-sonnet | Session: 0192abc... | Cost: $0.142 (Tokens: 14.2k)    |
+-----------------------------------------------------------------------------------+
| > User: Fix the token expiration check in auth/service.py                         |
|                                                                                   |
| [*] Architect: Plan assembled (280 tokens). Routing to Editor model...            |
|                                                                                   |
| [-] Tool Invocation: file_edit [src/auth/service.py]                              |
|     Applied Tier 2 (Git OSR Fuzzy Merge): 4 lines modified, 0 torn writes        |
|                                                                                   |
| [-] Inline Diff Preview:                                                          |
|     --- a/src/auth/service.py                                                     |
|     +++ b/src/auth/service.py                                                     |
|     @@ -42,3 +42,4 @@                                                             |
|     -    if token.is_expired():                                                   |
|     +    current_time = time.time()                                               |
|     +    if token.expires_at <= current_time:                                     |
|              raise TokenExpiredError("Token has expired")                         |
|                                                                                   |
| [*] Automated Verification: pytest tests/test_auth.py [PASSED: 14/14 tests]       |
+-----------------------------------------------------------------------------------+
| pari> _                                                                           |
+-----------------------------------------------------------------------------------+
```

### 1. Live Differential Token Streaming
* Renders LLM output tokens as they stream in via markdown-aware Rich renderables.
* Automatically syntax-highlights code blocks in real time based on language grammar.
* Formats tool calls into collapsible status boxes that visually collapse once execution completes, keeping the terminal clean.

### 2. Interactive Unified Diff Preview
* Before persisting modifications to disk, PARI can render colored unified diffs (`git diff --color`) directly in the terminal buffer.
* Displays a compact `git diff --stat` summary upon turn completion.

### 3. Real-Time Token & Cost Meter
* The status bar continuously tracks:
  * Tokens sent (input / cached / uncached).
  * Tokens received (output / reasoning).
  * Exact USD cost calculated against provider pricing schemas.
  * Real-world cache hit ratio (e.g. `Cache Hit: 88.4%`).

### 4. Interactive Slash Commands

| Command | Action | Implementation |
|---|---|---|
| `/undo` | Roll back files changed in the last turn, stop child processes, and disclose side effects | Restores pre-edit snapshots, kills tracked child PIDs, and warns on logged dependency/API changes |
| `/snapshot [name]` | Save a named restore point in the DAG | Emits a labeled snapshot tag in `.pari/sessions/` |
| `/diff` | Render current uncommitted working tree diff | Executes `git diff` against working tree |
| `/add <path>` | Pin a reference file into Tier 4 Context Epoch | Loads file into Immutable Baseline Context |
| `/drop <path>` | Remove a file from Tier 4 Context Epoch | Rebuilds Baseline Context Epoch |
| `/model <name>` | Dynamically switch active model provider | Updates Layer 8 Router configuration |
| `/cost` | Display detailed financial breakdown | Summarizes input/output token spend across session |
| `/reset` | Clear conversation history; maintain repo map | Appends new `SESSION_START` root record |

> **Note on `/undo` Scope (v1)**: `/undo` guarantees physical file restoration and child process cleanup. It logs and warns about environment/dependency changes (e.g. `npm install`), but does not automatically execute uninstalls. It cannot reverse third-party API calls or remote database mutations.


---

## 3. Zero Background CPU Drain (Closing Cursor F4)

Cursor continually executes in-process vector embedding daemons that consume battery, generate fan noise, and spike RAM.

PARI maintains **Zero Idle CPU Drain**:
* The AST symbol graph (Layer 3) is generated **on-demand** upon session launch ($< 800\text{ ms}$).
* File updates during the session are tracked via `watchfiles.watch` only while the agent is executing an active turn.
* Between user prompts, all background watcher threads sleep. CPU utilization during idle periods is mathematically **$0.0\%$**.
