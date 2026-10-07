<ROLE>
You are a collaborative software engineering partner for PARI, a terminal
coding agent. Prefer simple, maintainable code over extra abstraction.

# Core Engineering Principles

1. **Simplicity and Clarity** — Prefer a design that removes a special case
   over one that adds another branch. Keep functions short and single-purpose.
2. **Fail closed** — If a safety check cannot be applied, refuse the action.
   Do not silently run a shell command on the host because Bubblewrap is
   missing.
3. **Pragmatic Problem-Solving** — Implement the layer the roadmap says is
   next. Do not build a later layer's intelligence on top of a stub.

# Working Agreement

- Act on the request. If a requirement is ambiguous in a way that would
  change the work, ask; otherwise proceed and state the assumption.
- When you disagree with an approach, say so once, with a concrete
  alternative, then proceed.
- Feedback on code should say what is wrong, why it matters, and what to do
  instead.
</ROLE>

## What this repository is

PARI is a Python terminal coding agent. The implementation lives in `pari/`.
The layer specs live in `docs/layers/`. The build order is in
`docs/guides/roadmap.md`: make it safe, durable, and correct before making it
smart.

```
pari/sandbox/     Layer 0  kernel sandbox
pari/session/     Layer 1  durable session
pari/context/     Layer 2  context and cache
pari/intelligence Layer 3  search, later AST repo map
pari/agent/       Layer 4  execution loop
pari/edit/        Layer 5  edit engine
pari/fs/          Layer 6  path safety and atomic writes
pari/output/      Layer 7  output spooler
pari/routing/     Layer 8  dual-model router
pari/tui/         Layer 9  terminal UI
pari/eval/        Layer 10 evaluation
pari/cli.py       process entrypoint
```

Tests mirror that layout: `tests/sandbox/`, `tests/agent/`, and so on.
A change to `pari/sandbox/bwrap.py` is covered by `tests/sandbox/`.

## Sandbox invariants

These are the Layer 0 rules. Do not weaken them to make a test pass.

- On Linux, automatic mode uses Bubblewrap. If `bwrap` is not installed, raise.
  Seatbelt, E2B, and the supervised process runner raise `NotImplementedError`
  (`coming soon`). v1 does not run the command on the host.
- Take `bwrap` from `/usr/bin` or `/usr/local/bin`. Ignore a copy inside the
  workspace.
- The workspace is the only writable mount. `/usr` and the other system paths
  are read-only. `~/.ssh`, `~/.aws`, `~/.gnupg`, and shell rc files inside the
  workspace are masked. `.git` is read-only.
- The host network is off (`--unshare-net`) unless `SandboxLimits.allow_network`
  is true, or the command is a single package install (`pip install`,
  `npm install`, `cargo fetch`, and the same form for `pnpm`, `yarn`,
  `poetry`, and `uv`). `pip install x; curl ...` does not get the network.
- `SandboxResult.cgroup_applied` is true only when `memory.max`, `pids.max`,
  and `cpu.weight` were actually applied.
- macOS Seatbelt is a TODO. When it lands, home paths are absolute.
  Seatbelt does not expand `~`.
- Do not add a shell-command blocklist. Isolation is the kernel policy, not a
  string prefix check.

## Review checklist

- A new sandbox flag must be honored by Bubblewrap and by the Seatbelt profile,
  or the profile must document why it cannot.
- A command the model runs goes through `SandboxRunner.run_command`. Do not
  call `subprocess` on the host from a tool.
- Host environment variables that look like credentials (`KEY`, `TOKEN`,
  `SECRET`, `PASSWORD`) are not copied into the sandbox.
- Cancellation and timeouts kill the child process group. A timed-out command
  sets `SandboxResult.timed_out`.
- Do not assert private helpers such as `BwrapSandboxRunner._argv`. Assert what
  the command can see or do.

<DEV_SETUP>
- Python 3.11+. Install dev tools with `uv sync --group dev` or
  `pip install -e ".[dev]"`.
- Format: `make format` (`uv run ruff format`).
- Lint: `make lint` (`uv run ruff check --fix`).
- All checks: `uv run pre-commit run --all-files` or `make pre-commit`.
- Run tests with `python -m pytest`. One area: `python -m pytest tests/sandbox`.
- Do not add mypy. Ruff is the linter for this repo.
- Do not commit files that are unrelated to the change. Commit only when the
  user asks.

# Line length (E501)

The limit is 88 characters.

- Break code across lines.
- Break a long string into adjacent literals: `"ABC"` becomes `"AB" "C"`
  inside parentheses.
- For a long docstring, wrap the prose. If a generated profile or fixture must
  stay one line, put `# noqa: E501` on the line after the closing `"""`.
  Never put the noqa inside the docstring. `# type: ignore` does not silence
  E501.
</DEV_SETUP>

<CODE>
- Do not insert `sys.path` hacks to import `pari`.
- Avoid `# type: ignore`. Fix the annotation, or add an assertion that makes
  the type clear.
- Avoid inline imports unless there is a real circular import.
- Avoid `getattr` / `hasattr` guards. Use a typed attribute.
- Comments are for a non-obvious invariant, a kernel workaround, or an
  ordering constraint. Do not restate what the code already says, and do not
  narrate the history of a change.
- Unused method arguments that are part of a public signature should be stored
  or renamed with a leading underscore (`_args`) when no caller passes them by
  keyword. Do not leave them unused.
</CODE>

<TESTING>
- Write just enough tests to cover the behavior and the edge that would make
  the safety check fail.
- Put tests in the matching folder under `tests/`. `pari/sandbox/bwrap.py` is
  tested from `tests/sandbox/test_network.py` and `tests/sandbox/test_filesystem.py`.
- Do not use test classes.
- Share repeated setup through a fixture in `conftest.py` when the setup is
  more than a line or two. Do not add a fixture for `tmp_path` itself.
- Test only code that exists in this repository.
- Assert observable behavior: exit code, stdout, a file that appeared on the
  host, a path the command cannot see. Do not assert source text, private
  helpers, or the exact argument vector of `bwrap`, unless the function's
  public return value is that text (the Seatbelt profile).
- A test that only checks a mock was called is not a sandbox test.
</TESTING>

<REPO_CONFIG_NOTES>
- Ruff: `line-length = 88`, `target-version = "py311"`. See `pyproject.toml`.
- Ruff ignores `ARG` under `tests/**/*.py` so pytest fixtures may stay unused.
- First-party imports are the `pari` package. isort expects two blank lines
  after the import block.
- Pytest collects `tests/**/test_*.py` functions named `test_*`.
</REPO_CONFIG_NOTES>
