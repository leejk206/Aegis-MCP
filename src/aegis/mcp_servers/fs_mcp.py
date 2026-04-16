"""``aegis-fs-mcp`` — filesystem MCP server.

Implements spec §10.2. All seven tools are scope-enforced via
``resolve_in_scope``. Tool impls are exposed as free functions so they
can be unit-tested without a running MCP client; ``build_server`` binds
the scope into FastMCP closures for stdio delivery.
"""

from __future__ import annotations

import shutil
from pathlib import Path

from mcp.server.fastmcp import FastMCP

from aegis.mcp_servers._base import parse_scope_from_args, resolve_in_scope


def fs_read(scope: Path, path: str) -> str:
    """Return the text content of ``path``."""
    resolved = resolve_in_scope(scope, path)
    return resolved.read_text(encoding="utf-8")


def fs_list(scope: Path, path: str) -> list[str]:
    """Return a sorted list of entry names in the directory ``path``."""
    resolved = resolve_in_scope(scope, path)
    return sorted(p.name for p in resolved.iterdir())


def fs_glob(scope: Path, pattern: str) -> list[str]:
    """Return scope-relative paths matching ``pattern`` under scope.

    The glob is always rooted at scope — callers cannot escape via the
    pattern itself because ``Path.glob`` anchors to the path it is called
    on. This is defense in depth on top of ``resolve_in_scope``.
    """
    return sorted(
        str(p.relative_to(scope))
        for p in scope.glob(pattern)
    )


def fs_write(scope: Path, path: str, content: str) -> int:
    """Write ``content`` to ``path``, creating parents as needed."""
    resolved = resolve_in_scope(scope, path)
    resolved.parent.mkdir(parents=True, exist_ok=True)
    return resolved.write_text(content, encoding="utf-8")


def fs_mkdir(scope: Path, path: str) -> None:
    """Create ``path`` as a directory, including parents. Idempotent."""
    resolved = resolve_in_scope(scope, path)
    resolved.mkdir(parents=True, exist_ok=True)


def fs_delete(scope: Path, path: str) -> None:
    """Delete ``path``. Removes a directory tree if ``path`` is a dir."""
    resolved = resolve_in_scope(scope, path)
    if resolved.is_dir():
        shutil.rmtree(resolved)
    else:
        resolved.unlink()


def fs_move(scope: Path, src: str, dst: str) -> None:
    """Move ``src`` to ``dst``. Both must lie within scope."""
    src_resolved = resolve_in_scope(scope, src)
    dst_resolved = resolve_in_scope(scope, dst)
    dst_resolved.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(src_resolved), str(dst_resolved))


def build_server(scope: Path) -> FastMCP:
    """Build a FastMCP server whose tools are bound to ``scope``."""
    server: FastMCP = FastMCP("aegis-fs")

    @server.tool(name="fs_read")
    def _fs_read(path: str) -> str:
        return fs_read(scope, path)

    @server.tool(name="fs_list")
    def _fs_list(path: str) -> list[str]:
        return fs_list(scope, path)

    @server.tool(name="fs_glob")
    def _fs_glob(pattern: str) -> list[str]:
        return fs_glob(scope, pattern)

    @server.tool(name="fs_write")
    def _fs_write(path: str, content: str) -> int:
        return fs_write(scope, path, content)

    @server.tool(name="fs_mkdir")
    def _fs_mkdir(path: str) -> None:
        fs_mkdir(scope, path)

    @server.tool(name="fs_delete")
    def _fs_delete(path: str) -> None:
        fs_delete(scope, path)

    @server.tool(name="fs_move")
    def _fs_move(src: str, dst: str) -> None:
        fs_move(scope, src, dst)

    return server


def main() -> None:
    scope = parse_scope_from_args()
    server = build_server(scope)
    server.run()


if __name__ == "__main__":  # pragma: no cover
    main()
