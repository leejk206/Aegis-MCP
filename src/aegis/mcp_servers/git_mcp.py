"""``aegis-git-mcp`` — git MCP server.

Implements spec §10.1. All tools invoke the ``git`` CLI with
``cwd=scope`` — i.e. the scope directory IS the repo (or worktree) the
tools operate on. Path arguments are interpreted as scope-relative and
validated defensively through ``resolve_in_scope``.

This module is built up across three plan tasks: read tools (status,
diff, log), write tools (add, commit, branch_create, checkout), and
worktree/merge tools (worktree_add, worktree_remove, merge).
"""

from __future__ import annotations

import subprocess
from pathlib import Path

from mcp.server.fastmcp import FastMCP

from aegis.mcp_servers._base import parse_scope_from_args, resolve_in_scope


def _git(scope: Path, args: list[str]) -> str:
    """Run ``git args`` with ``cwd=scope`` and return stdout.

    Uses ``check=True`` so git errors become ``CalledProcessError``; the
    MCP server will surface that as a tool error.
    """
    result = subprocess.run(
        ["git", *args],
        cwd=str(scope),
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout


def git_status(scope: Path, path: str | None = None) -> str:
    args = ["status", "--porcelain"]
    if path is not None:
        resolved = resolve_in_scope(scope, path)
        args.extend(["--", str(resolved)])
    return _git(scope, args)


def git_diff(
    scope: Path,
    path: str | None = None,
    rev_range: str | None = None,
) -> str:
    args = ["diff"]
    if rev_range is not None:
        args.append(rev_range)
    if path is not None:
        resolved = resolve_in_scope(scope, path)
        args.extend(["--", str(resolved)])
    return _git(scope, args)


def git_log(scope: Path, path: str | None = None, limit: int = 20) -> str:
    args = ["log", f"-n{limit}", "--oneline"]
    if path is not None:
        resolved = resolve_in_scope(scope, path)
        args.extend(["--", str(resolved)])
    return _git(scope, args)


def build_server(scope: Path) -> FastMCP:
    """Build a FastMCP server whose tools are bound to ``scope``.

    Only read tools are registered in Task 4; write and worktree tools
    are appended in Tasks 5 and 6.
    """
    server: FastMCP = FastMCP("aegis-git")

    @server.tool(name="git_status")
    def _git_status(path: str | None = None) -> str:
        return git_status(scope, path)

    @server.tool(name="git_diff")
    def _git_diff(
        path: str | None = None, rev_range: str | None = None
    ) -> str:
        return git_diff(scope, path, rev_range)

    @server.tool(name="git_log")
    def _git_log(path: str | None = None, limit: int = 20) -> str:
        return git_log(scope, path, limit)

    return server


def main() -> None:
    scope = parse_scope_from_args()
    server = build_server(scope)
    server.run()


if __name__ == "__main__":  # pragma: no cover
    main()
