from __future__ import annotations

import subprocess
from pathlib import Path


class WorktreeError(Exception):
    """Raised when a git worktree operation fails."""


class ScopeViolation(WorktreeError):
    """Raised when a path escapes its declared scope."""


def _run_git(args: list[str], cwd: Path) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=str(cwd),
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise WorktreeError(
            f"git {' '.join(args)} failed (exit {result.returncode}): "
            f"{result.stderr.strip() or result.stdout.strip()}"
        )
    return result.stdout


def create_worktree(repo_root: Path, worktree_path: Path, branch: str) -> None:
    wt = worktree_path.resolve()
    wt.parent.mkdir(parents=True, exist_ok=True)
    _run_git(["worktree", "add", "-b", branch, str(wt)], cwd=repo_root)


def remove_worktree(repo_root: Path, worktree_path: Path) -> None:
    wt = worktree_path.resolve()
    _run_git(["worktree", "remove", "--force", str(wt)], cwd=repo_root)


def list_worktrees(repo_root: Path) -> list[dict[str, str]]:
    out = _run_git(["worktree", "list", "--porcelain"], cwd=repo_root)
    worktrees: list[dict[str, str]] = []
    current: dict[str, str] = {}
    for line in out.splitlines():
        if not line:
            if current:
                worktrees.append(current)
                current = {}
            continue
        if " " in line:
            key, _, value = line.partition(" ")
            current[key] = value
        else:
            current[line] = ""
    if current:
        worktrees.append(current)
    return worktrees


def validate_path_in_scope(path: Path, scope: Path) -> Path:
    resolved = path.resolve()
    scope_resolved = scope.resolve()
    try:
        resolved.relative_to(scope_resolved)
    except ValueError as exc:
        raise ScopeViolation(f"{resolved} is outside scope {scope_resolved}") from exc
    return resolved
