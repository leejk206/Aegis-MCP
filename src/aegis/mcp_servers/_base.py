"""Shared helpers for Aegis MCP servers.

Every server module uses ``parse_scope_from_args`` to read ``--scope`` from
argv and ``resolve_in_scope`` to turn a tool's ``path`` argument into a
validated absolute path. Scope enforcement is defense in depth per spec
§10 — the graph runner also scopes paths, but the server never trusts it.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from aegis.core.worktree import validate_path_in_scope


def parse_scope_from_args(argv: list[str] | None = None) -> Path:
    """Parse ``--scope`` from argv and return an absolute, resolved Path."""
    parser = argparse.ArgumentParser(description="Aegis MCP server")
    parser.add_argument(
        "--scope",
        type=Path,
        required=True,
        help="Absolute path the server is allowed to read/write. Any path"
        " outside this directory is refused.",
    )
    args = parser.parse_args(argv)
    scope: Path = args.scope.resolve()
    return scope


def resolve_in_scope(scope: Path, path: str) -> Path:
    """Turn a tool ``path`` argument into a validated absolute Path.

    Relative paths are interpreted as scope-relative. Absolute paths are
    used as-is. In both cases the final resolved path must lie inside
    ``scope`` or ``ScopeViolation`` is raised by ``validate_path_in_scope``.
    Non-existent paths are permitted — this is called before ``fs_write``
    or ``fs_mkdir`` for files that are about to be created.
    """
    p = Path(path)
    if not p.is_absolute():
        p = scope / p
    return validate_path_in_scope(p, scope)
