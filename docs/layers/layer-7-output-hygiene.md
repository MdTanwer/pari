# Layer 7: Output Handling and Context Hygiene

> **Closes Failures**: Unbounded stdout poisoning — the largest single contributor to the 35% performance gap between naive agent loops and production harnesses.  
> **Harvested From**: OpenCode's Managed Tool Output Store (50KB / 2,000-line limits) — enhanced with Structured Compiler/Test Traceback Parsers.

---

## 1. Overview: The Danger of Stdout Poisoning

In software engineering workflows, CLI commands frequently produce massive volumes of output:
* Running `npm install` outputs thousands of lines of package trees and deprecation notices.
* A failing test suite (`pytest`) emits 10,000+ lines of stack traces and internal framework logs.
* A command like `cat bundle.js` or `git log` can produce tens of megabytes of text.

In naive coding agents (Claude Code, Aider, Codex):
1. Raw tool stdout is piped directly into the conversation transcript.
2. The massive text blob consumes the entire model context window.
3. System instructions, core user constraints, and repository symbol maps are **pushed out of context**.
4. The model becomes degraded or hallucinatorily begins repeating snippets from the logs.

PARI implements **Context Hygiene via the `ManagedOutputSpooler` and Structured Traceback Parsers**.

---

## 2. The `ManagedOutputSpooler` Pipeline

All stdout and stderr streams from sandboxed tool executions flow through the `ManagedOutputSpooler` before reaching the agent runtime:

```
MANAGED OUTPUT SPOOLER DATA FLOW:

Raw Command Execution (Kernel Sandbox)
                  |
                  v
[Stream directly to Disk Sidecar: .pari/tool-outputs/<uuid>.txt]
                  |
                  v
Check Output Size Bounds:
  - Total bytes > 50,000 (50 KB)?  OR
  - Total lines > 2,000 lines?
                  |
         +--------+--------+
         |                 |
       [YES]              [NO]
         |                 |
         v                 v
[Extract Balanced View]   [Inject Verbatim Output]
  - Head: First 1,000 lines
  - Truncation Notice: "... [N lines truncated. Full log: .pari/tool-outputs/<uuid>.txt] ..."
  - Tail: Last 1,000 lines
         |
         v
Inject Bounded View into Prompt Context (Tier 7)
(Model can query full file via: read_tool_output(path, offset=N))
```

---

## 3. Paged Inspection API (`read_tool_output`)

When the model genuinely needs to inspect the interior lines of a truncated log file, it does not re-run the command. It invokes the built-in `read_tool_output` tool:

```python
# Tool definition (pari/tools/output_reader.py)
async def read_tool_output(sidecar_path: str, offset_bytes: int = 0, limit_bytes: int = 45000) -> str:
    """Read a slice of a large tool output sidecar file."""
    # Enforce path containment within .pari/tool-outputs/
    safe_path = validate_sidecar_path(sidecar_path)
    
    with open(safe_path, "r", encoding="utf-8", errors="replace") as f:
        f.seek(offset_bytes)
        content = f.read(limit_bytes)
        
    return f"[PAGED OUTPUT: offset={offset_bytes}, bytes_read={len(content)}]\n{content}"
```

* **Retention Policy**: Sidecar files are retained for 7 days in `.pari/tool-outputs/` and cleaned up by an asynchronous garbage collection task during idle sessions.

---

## 4. Structured Traceback Parsing (Anti-Stderr Flooding)

Raw test failures often contain 99% internal framework boilerplate (e.g. pytest internals, node runner internals) and only 1% actionable developer error.

PARI intercepts stdout/stderr for recognized test and compiler toolchains through specialized **Traceback Parsers**:

```
RAW PYTEST OUTPUT (12,000 lines)
               |
               v
PARI PytestTracebackParser
               |
               v
STRUCTURED [TEST FAILURE] BLOCK (30 lines):
+-------------------------------------------------------------+
| [TEST FAILURE] tests/test_auth.py::test_token_expiry        |
| File: src/auth/token.py, Line: 84                            |
| Error: AssertionError: Expected 401 Unauthorized, got 200 OK|
|                                                             |
| Traceback Summary (Most Recent Call First):                 |
|   tests/test_auth.py:28 in test_token_expiry                |
|   src/auth/service.py:52 in validate_request                |
|   src/auth/token.py:84 in is_expired                        |
|                                                             |
| Local Variables:                                            |
|   token_age = 3601, max_ttl = 3600                          |
+-------------------------------------------------------------+
```

### Supported Parsers
1. **Pytest Parser**: Strips internal pluggy/pytest frames; extracts failing assert expressions and local variables.
2. **TypeScript / Cargo Parser**: Extracts file path, line/column number, error code (`TS2345`, `E0308`), and the expected vs. actual type mismatch.
3. **Jest / Vitest Parser**: Extracts failing expect block and diff assertion.

---

## 5. Architectural Comparison

| Dimension | PARI | Claude Code | Aider | OpenCode |
|---|---|---|---|---|
| **Max Inline Output Limit** | **50 KB / 2,000 lines** | In-memory slice | Line truncation | 50 KB / 2,000 lines |
| **Full Output Retention** | **7-day disk sidecars** | Lost on truncate | Lost on truncate | Sidecar files |
| **Paged Inspection** | **Yes (`read_tool_output`)**| No | No | Yes |
| **Structured Test Parsing** | **Yes (pytest/cargo/tsc)** | Raw stderr | Partial | Raw stderr |
| **Context Window Displacement**| **0% (strictly bounded)** | High risk | High risk | Low |
