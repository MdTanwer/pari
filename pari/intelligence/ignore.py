"""Ignore rules shared by search and the repo map.

Hardcoded VCS and dependency directories stay hidden. Each ``.gitignore``
is read once and reused for the rest of the walk.
"""

import re
from pathlib import Path


_IGNORED_DIRS = frozenset(
    {
        ".git",
        ".hg",
        ".svn",
        ".venv",
        "venv",
        "node_modules",
        "__pycache__",
        "dist",
        "build",
        ".pari",
    }
)


class IgnoreRules:
    """Match paths against hardcoded directories and ``.gitignore`` files."""

    def __init__(self, root: Path):
        self.root = root
        self._rules: dict[Path, tuple[_Rule, ...]] = {}
        self.enter(root)

    def enter(self, directory: Path) -> None:
        """Parse ``directory/.gitignore`` the first time this directory is seen."""
        if directory in self._rules:
            return
        gitignore = directory / ".gitignore"
        if not gitignore.is_file():
            self._rules[directory] = ()
            return
        try:
            text = gitignore.read_text(encoding="utf-8", errors="replace")
        except OSError:
            self._rules[directory] = ()
            return
        self._rules[directory] = tuple(_parse(text))

    def ignored(self, path: Path, *, is_dir: bool) -> bool:
        """Return whether search should skip this path."""
        try:
            relative = path.relative_to(self.root)
        except ValueError:
            return True
        if any(part in _IGNORED_DIRS for part in relative.parts):
            return True
        self._load_chain(path if is_dir else path.parent)
        if self._ancestor_ignored(path):
            return True
        return self._decision(path, is_dir) is True

    def _load_chain(self, directory: Path) -> None:
        chain: list[Path] = []
        current = directory
        while True:
            chain.append(current)
            if current == self.root:
                break
            parent = current.parent
            if parent == current:
                break
            current = parent
        for item in reversed(chain):
            self.enter(item)

    def _ancestor_ignored(self, path: Path) -> bool:
        """A file inside an ignored directory stays ignored."""
        ancestors: list[Path] = []
        current = path.parent
        while current != self.root:
            if self.root not in current.parents:
                return True
            ancestors.append(current)
            current = current.parent
        for ancestor in reversed(ancestors):
            if self._decision(ancestor, True) is True:
                return True
        return False

    def _decision(self, path: Path, is_dir: bool) -> bool | None:
        """Last matching rule. True means ignored."""
        parts = path.relative_to(self.root).parts
        decision: bool | None = None
        directory = self.root
        for index in range(len(parts)):
            relative = "/".join(parts[index:])
            for rule in self._rules.get(directory, ()):
                matched = rule.matches(relative, is_dir)
                if matched is not None:
                    decision = matched
            directory = directory / parts[index]
        return decision


class _Rule:
    def __init__(self, negated: bool, directory_only: bool, pattern: re.Pattern[str]):
        self.negated = negated
        self.directory_only = directory_only
        self.pattern = pattern

    def matches(self, relative: str, is_dir: bool) -> bool | None:
        if self.directory_only and not is_dir:
            return None
        if self.pattern.fullmatch(relative) is None:
            return None
        return not self.negated


def _parse(text: str) -> list[_Rule]:
    rules: list[_Rule] = []
    for raw in text.splitlines():
        line = _strip_rule(raw)
        if line is None:
            continue
        rule = _compile(line)
        if rule is not None:
            rules.append(rule)
    return rules


def _strip_rule(raw: str) -> str | None:
    line = raw.strip("\r")
    while line.endswith(" ") and not line.endswith("\\ "):
        line = line[:-1]
    if line.endswith("\\ "):
        line = line[:-2] + " "
    if not line or line.startswith("#"):
        return None
    if line.startswith("\\#") or line.startswith("\\!"):
        line = line[1:]
    return line


def _compile(line: str) -> _Rule | None:
    negated = line.startswith("!")
    if negated:
        line = line[1:]
    directory_only = line.endswith("/")
    if directory_only:
        line = line[:-1]
    anchored = line.startswith("/")
    if anchored:
        line = line[1:]
    if not line:
        return None
    body = _glob_to_regex(line)
    if "/" in line or anchored:
        expression = body
    else:
        expression = "(?:.*/)?" + body
    try:
        pattern = re.compile(expression)
    except re.error:
        return None
    return _Rule(negated, directory_only, pattern)


def _glob_to_regex(pattern: str) -> str:
    parts: list[str] = []
    index = 0
    while index < len(pattern):
        char = pattern[index]
        if char == "\\" and index + 1 < len(pattern):
            parts.append(re.escape(pattern[index + 1]))
            index += 2
            continue
        if char == "*":
            if pattern.startswith("**", index):
                if pattern.startswith("**/", index):
                    parts.append("(?:.*/)?")
                    index += 3
                    continue
                parts.append(".*")
                index += 2
                continue
            parts.append("[^/]*")
            index += 1
            continue
        if char == "?":
            parts.append("[^/]")
            index += 1
            continue
        if char == "[":
            end = pattern.find("]", index + 1)
            if end == -1:
                parts.append(re.escape(char))
                index += 1
                continue
            chunk = pattern[index : end + 1]
            if chunk.startswith("[!"):
                chunk = "[^" + chunk[2:]
            parts.append(chunk)
            index = end + 1
            continue
        parts.append(re.escape(char))
        index += 1
    return "".join(parts)
