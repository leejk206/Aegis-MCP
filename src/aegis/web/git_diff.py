"""Read-only `git diff main..<branch>` helpers for the dashboard.

Returns an empty string instead of raising when the branch does not
exist, so the task-detail page can render before a worktree is set up.
The truncation cap on `diff_full` exists so a runaway diff cannot blow
up the rendered HTML.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

__all__ = ["diff_stat", "diff_full"]

_MAIN = "main"
_FULL_DIFF_BYTE_CAP = 256 * 1024  # 256 KB


def _run(repo_root: Path, args: list[str]) -> str:
    try:
        result = subprocess.run(
            ["git", "-C", str(repo_root), *args],
            capture_output=True,
            text=True,
            check=False,
        )
    except FileNotFoundError:
        return ""
    if result.returncode != 0:
        return ""
    return result.stdout


def diff_stat(repo_root: Path, branch: str) -> str:
    return _run(repo_root, ["diff", "--stat", f"{_MAIN}..{branch}"])


def diff_full(repo_root: Path, branch: str) -> str:
    out = _run(repo_root, ["diff", f"{_MAIN}..{branch}"])
    if len(out.encode("utf-8")) > _FULL_DIFF_BYTE_CAP:
        encoded = out.encode("utf-8")[:_FULL_DIFF_BYTE_CAP]
        out = encoded.decode("utf-8", errors="ignore")
        out += "\n... [diff truncated at 256 KB] ...\n"
    return out
