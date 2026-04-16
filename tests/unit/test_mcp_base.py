from __future__ import annotations

from pathlib import Path

import pytest

from aegis.core.worktree import ScopeViolation
from aegis.mcp_servers._base import parse_scope_from_args, resolve_in_scope


def test_parse_scope_returns_absolute_resolved_path(tmp_path: Path) -> None:
    scope = parse_scope_from_args(["--scope", str(tmp_path)])
    assert scope == tmp_path.resolve()
    assert scope.is_absolute()


def test_parse_scope_missing_argument_exits() -> None:
    with pytest.raises(SystemExit):
        parse_scope_from_args([])


def test_parse_scope_unknown_flag_exits(tmp_path: Path) -> None:
    with pytest.raises(SystemExit):
        parse_scope_from_args(["--scope", str(tmp_path), "--nope"])


def test_resolve_in_scope_relative_path(tmp_path: Path) -> None:
    (tmp_path / "a.txt").write_text("hi")
    resolved = resolve_in_scope(tmp_path, "a.txt")
    assert resolved == (tmp_path / "a.txt").resolve()


def test_resolve_in_scope_nested_relative_path(tmp_path: Path) -> None:
    (tmp_path / "sub").mkdir()
    resolved = resolve_in_scope(tmp_path, "sub/x.txt")
    assert resolved == (tmp_path / "sub" / "x.txt").resolve()
    assert not resolved.exists()  # non-existent paths still resolvable


def test_resolve_in_scope_absolute_inside(tmp_path: Path) -> None:
    target = tmp_path / "b.txt"
    target.write_text("ok")
    resolved = resolve_in_scope(tmp_path, str(target))
    assert resolved == target.resolve()


def test_resolve_in_scope_rejects_parent_escape(tmp_path: Path) -> None:
    with pytest.raises(ScopeViolation):
        resolve_in_scope(tmp_path, "../evil.txt")


def test_resolve_in_scope_rejects_absolute_outside(tmp_path: Path) -> None:
    outside = tmp_path.parent / "outside.txt"
    with pytest.raises(ScopeViolation):
        resolve_in_scope(tmp_path, str(outside))
