# Layer 6: Concurrency and File Safety

> **Closes Failures**: Claude Code F3 (uncoordinated async file write races), Aider F3 (`.git/index.lock` collisions with developer IDEs).  
> **Harvested From**: Pi's `FileMutationQueue` (canonical realpath serialization) — ported to Python `asyncio` with Shadow Worktree Git isolation.

---

## 1. Overview & Failure Mechanics

As coding agents become more concurrent (handling parallel tool calls or running background test watchers), file writes can overlap in catastrophic ways:
1. **Claude Code F3**: Asynchronous tool handlers execute `fs.promises.writeFile()` simultaneously. Two parallel edits to `package.json` or `pyproject.toml` interleave writes at the kernel level, creating a torn, corrupt JSON/TOML file.
2. **Symlink Aliasing**: A write to `src/auth.py` and a concurrent write to `src/handlers/../auth.py` target the same physical file under different string paths. Naive path-keyed locks fail to detect the collision.
3. **Aider F3 (`index.lock`)**: Aider commits directly to the developer's live git working tree. If the developer's IDE (VS Code, Cursor, JetBrains) runs `git status` or a background fetch at the same time, Git aborts with:
   ```
   fatal: Unable to create '.git/index.lock': File exists.
   ```

PARI guarantees absolute file integrity via a **Canonical Realpath `FileMutationQueue`** and **Shadow Git Worktrees**.

---

## 2. The `FileMutationQueue` Architecture

PARI routes every file write through a central `FileMutationQueue`. The queue maintains an in-memory dictionary of `asyncio.Lock` instances keyed strictly by the file's canonical resolved path:

```
+-----------------------------------------------------------------------------------+
|               FILE MUTATION QUEUE: CANONICAL REALPATH SERIALIZATION               |
+-----------------------------------------------------------------------------------+
|                                                                                   |
|  Call 1: './src/auth.py'        ----+                                             |
|                                     |                                             |
|  Call 2: './src/api/../auth.py' ----+--> [Canonical Realpath Resolver]            |
|                                     |         |                                   |
|                                     |         +--> '/home/tanw9/pari/src/auth.py' |
|                                     |                    |                        |
|                                     |              [Lock A: File 1]               |
|                                     |                    |                        |
|                                     |              Call 1 executes                |
|                                     |              Call 2 waits (Serialized)      |
|                                     |                                             |
|  Call 3: './src/models/user.py' ----+--> [Canonical Realpath Resolver]            |
|                                               |                                   |
|                                               +--> '.../src/models/user.py'       |
|                                                          |                        |
|                                                    [Lock B: File 2]               |
|                                                          |                        |
|                                                    Call 3 runs concurrently       |
|                                                                                   |
+-----------------------------------------------------------------------------------+
```

### Python Implementation (`pari/concurrency/queue.py`)

```python
import asyncio
import os
from pathlib import Path
from typing import Dict

class FileMutationQueue:
    def __init__(self, workspace_root: str):
        self.workspace_root = os.path.realpath(workspace_root)
        self._locks: Dict[str, asyncio.Lock] = {}
        self._global_registry_lock = asyncio.Lock()

    async def get_lock(self, file_path: str) -> asyncio.Lock:
        """Resolve canonical path and return a dedicated asyncio.Lock."""
        # 1. Resolve canonical path handling symlinks
        try:
            canonical_path = await asyncio.to_thread(os.path.realpath, file_path)
        except FileNotFoundError:
            # ENOENT Fallback: File does not exist yet; use absolute normalized path
            canonical_path = os.path.abspath(file_path)

        # 2. Enforce sandbox boundary: path traversal protection via Path.is_relative_to()
        try:
            Path(canonical_path).resolve().relative_to(Path(self.workspace_root).resolve())
        except ValueError:
            raise PermissionError(
                f"Security violation: Path '{canonical_path}' is outside workspace '{self.workspace_root}'"
            )

        # 3. Thread-safe lock registration

        async with self._global_registry_lock:
            if canonical_path not in self._locks:
                self._locks[canonical_path] = asyncio.Lock()
            return self._locks[canonical_path]

    async def write_atomic(self, file_path: str, content: str) -> None:
        """Acquire canonical lock and execute atomic tempfile-then-rename."""
        lock = await self.get_lock(file_path)
        async with lock:
            await asyncio.to_thread(self._atomic_disk_write, file_path, content)

    def _atomic_disk_write(self, target_path: str, content: str) -> None:
        import tempfile
        parent_dir = os.path.dirname(os.path.abspath(target_path))
        os.makedirs(parent_dir, exist_ok=True)
        
        # Write to temporary file in same filesystem directory
        fd, temp_file = tempfile.mkstemp(dir=parent_dir, prefix=".pari_tmp_")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                f.write(content)
            # Atomic rename replaces target atomically
            os.replace(temp_file, target_path)
        except Exception:
            if os.path.exists(temp_file):
                os.remove(temp_file)
            raise
```

---

## 3. Git Operation Isolation & Shadow Worktrees

To eliminate `.git/index.lock` collisions with IDEs while maintaining session rollbacks:

### 1. Dedicated Shadow Worktree
Instead of running `git add` and `git commit` directly in the developer's active working tree:
* PARI provisions an isolated shadow worktree at `.pari/shadow-tree`:
  ```bash
  git worktree add --detach .pari/shadow-tree HEAD
  ```
* Internal agent snapshots and temporary commit diffs execute inside `.pari/shadow-tree`.
* The developer's live working directory `.git/index` is never locked by PARI.

---

### 2. Exponential Backoff with Jitter
For operations that must touch the main repository:
* If Git exits with status `128` (`index.lock` exists), PARI retries up to 3 times with exponential backoff:
  $$t_{\text{wait}} = 50\text{ ms} \times 2^{\text{attempt}} + \text{jitter}(0, 20\text{ ms})$$

---

### 3. Stale Lock Detection & Auto-Reaping
If a background IDE process crashes, a stale `.git/index.lock` can freeze all future Git operations:
* PARI inspects the modification time (`mtime`) of `.git/index.lock`.
* If the lock file is older than **$5.0\text{ seconds}$**, it is classified as a dead lock left by a terminated process.
* PARI unlinks the stale lock file and logs a warning before proceeding.

---

## 4. Concurrency Safety Comparison

| Feature | PARI | Claude Code | Aider | OpenCode |
|---|---|---|---|---|
| **Write Serialization** | Canonical `realpath` Lock | None (Uncoordinated) | Single-threaded | Fiber Lock |
| **Symlink Collisions** | Deduplicated via `realpath` | Torn Writes | Serialized | Aliasing Risk |
| **Atomic Rename** | `tempfile` + `os.replace` | Direct `writeFile` | Atomic commit | Direct write |
| **Git `index.lock` Collisions** | Shadow Worktree + Backoff | N/A | Frequent crashes | Shadow Tree |
| **Path Traversal Protection**| Kernel check + Path Guard | None | None | Modal confirm |
