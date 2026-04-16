"""``aegis-project-index-mcp`` — lightweight project-index MCP server.

Implements spec §10.4. Content and symbol search shell out to ripgrep
(`rg`). Filename search walks the scope tree in Python. ``file_tree``
returns a depth-limited listing. ``outline`` grep-extracts definition
lines from a single file. All paths are scope-validated.

This is intentionally a "tiny daemon" — no persistent index, no ctags
dependency, no caching layer. Calls are cheap enough at typical repo
sizes that building an index up-front is not worth the complexity.
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Literal

from mcp.server.fastmcp import FastMCP

from aegis.mcp_servers._base import parse_scope_from_args, resolve_in_scope

SearchKind = Literal["content", "symbol", "filename"]


def _run_rg(args: list[str], cwd: Path) -> list[str]:
    result = subprocess.run(
        ["rg", *args],
        cwd=str(cwd),
        capture_output=True,
        text=True,
        check=False,
    )
    # rg exit 1 = no matches, which is not an error for us
    if result.returncode not in (0, 1):
        raise RuntimeError(f"rg failed (exit {result.returncode}): {result.stderr.strip()}")
    return [line for line in result.stdout.splitlines() if line]


def search(scope: Path, query: str, kind: SearchKind = "content") -> list[str]:
    if kind == "content":
        return _run_rg(
            ["--line-number", "--no-heading", "--fixed-strings", query, "."],
            cwd=scope,
        )
    if kind == "symbol":
        pattern = rf"^\s*(def |class |function |fn |public |private ).*{query}"
        return _run_rg(
            ["--line-number", "--no-heading", pattern, "."],
            cwd=scope,
        )
    if kind == "filename":
        return sorted(
            str(p.relative_to(scope)) for p in scope.rglob("*") if p.is_file() and query in p.name
        )
    raise ValueError(f"unknown kind {kind!r}")


def file_tree(scope: Path, path: str = ".", depth: int = 2) -> list[str]:
    root = resolve_in_scope(scope, path)
    root_depth = len(root.parts)
    out: list[str] = []
    for p in sorted(root.rglob("*")):
        rel_depth = len(p.parts) - root_depth
        if rel_depth > depth:
            continue
        rel = p.relative_to(scope)
        out.append(f"{rel}/" if p.is_dir() else str(rel))
    return out


def outline(scope: Path, path: str) -> list[str]:
    resolved = resolve_in_scope(scope, path)
    pattern = r"^\s*(def |class |function |fn |public |private )"
    return _run_rg(
        ["--line-number", "--no-heading", pattern, str(resolved)],
        cwd=scope,
    )


def build_server(scope: Path) -> FastMCP:
    server: FastMCP = FastMCP("aegis-project-index")

    @server.tool(name="search")
    def _search(query: str, kind: SearchKind = "content") -> list[str]:
        return search(scope, query, kind)

    @server.tool(name="file_tree")
    def _file_tree(path: str = ".", depth: int = 2) -> list[str]:
        return file_tree(scope, path, depth)

    @server.tool(name="outline")
    def _outline(path: str) -> list[str]:
        return outline(scope, path)

    return server


def main() -> None:
    scope = parse_scope_from_args()
    server = build_server(scope)
    server.run()


if __name__ == "__main__":  # pragma: no cover
    main()
