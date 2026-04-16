"""``aegis-shell-mcp`` — shell-exec MCP server.

Implements spec §10.3 and §11.5. The server runs only commands that
appear in an allow-list, treats ``command`` and ``args`` as a single
argv vector (no shell interpretation), and validates ``cwd`` lies inside
scope. The allow-list is read from ``ALLOW_CMDS`` env var at call time
so tests can monkeypatch it per-case.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path
from typing import TypedDict

from mcp.server.fastmcp import FastMCP

from aegis.mcp_servers._base import parse_scope_from_args, resolve_in_scope

DEFAULT_ALLOW_CMDS: list[str] = [
    "pytest",
    "python",
    "pip",
    "npm",
    "pnpm",
    "node",
    "ruff",
    "mypy",
    "pre-commit",
]


class ShellResult(TypedDict):
    stdout: str
    stderr: str
    exit_code: int


class ShellCommandDenied(Exception):
    """Raised when a command is not in the allow-list."""


def _load_allow_cmds() -> list[str]:
    env = os.environ.get("ALLOW_CMDS")
    if env is None:
        return DEFAULT_ALLOW_CMDS
    return [c.strip() for c in env.split(",") if c.strip()]


def shell_exec(scope: Path, command: str, args: list[str], cwd: str) -> ShellResult:
    """Run ``command args`` under ``cwd`` (scoped) and capture output."""
    allow = _load_allow_cmds()
    if command not in allow:
        raise ShellCommandDenied(f"command {command!r} not in ALLOW_CMDS {allow}")
    cwd_resolved = resolve_in_scope(scope, cwd)
    if not cwd_resolved.is_dir():
        raise FileNotFoundError(f"cwd {cwd_resolved} does not exist or is not a directory")
    result = subprocess.run(
        [command, *args],
        cwd=str(cwd_resolved),
        capture_output=True,
        text=True,
        check=False,
    )
    return ShellResult(
        stdout=result.stdout,
        stderr=result.stderr,
        exit_code=result.returncode,
    )


def build_server(scope: Path) -> FastMCP:
    server: FastMCP = FastMCP("aegis-shell")

    @server.tool(name="shell_exec")
    def _shell_exec(command: str, args: list[str], cwd: str) -> ShellResult:
        return shell_exec(scope, command, args, cwd)

    return server


def main() -> None:
    scope = parse_scope_from_args()
    server = build_server(scope)
    server.run()


if __name__ == "__main__":  # pragma: no cover
    main()
