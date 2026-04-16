from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from aegis.core.worktree import ScopeViolation
from aegis.mcp_servers.project_index_mcp import (
    build_server,
    file_tree,
    outline,
    search,
)

requires_rg = pytest.mark.skipif(shutil.which("rg") is None, reason="ripgrep not installed")


def _seed_project(root: Path) -> None:
    (root / "src").mkdir()
    (root / "src" / "main.py").write_text(
        "def hello():\n    return 'world'\n\nclass Widget:\n    pass\n"
    )
    (root / "src" / "util.py").write_text("def compute(x):\n    return x + 1\n")
    (root / "tests").mkdir()
    (root / "tests" / "test_main.py").write_text("def test_hello():\n    assert True\n")
    (root / "README.md").write_text("# project\n")


@requires_rg
def test_search_content(tmp_path: Path) -> None:
    _seed_project(tmp_path)
    hits = search(tmp_path, "hello")
    assert any("main.py" in h for h in hits)
    assert any("test_main.py" in h for h in hits)


@requires_rg
def test_search_content_no_match(tmp_path: Path) -> None:
    _seed_project(tmp_path)
    assert search(tmp_path, "nonexistent_token_zzz") == []


def test_search_filename(tmp_path: Path) -> None:
    _seed_project(tmp_path)
    hits = search(tmp_path, "util", kind="filename")
    assert any("util.py" in h for h in hits)
    assert not any("main.py" in h for h in hits)


@requires_rg
def test_search_symbol(tmp_path: Path) -> None:
    _seed_project(tmp_path)
    hits = search(tmp_path, "Widget", kind="symbol")
    assert any("class Widget" in h for h in hits)


def test_search_unknown_kind_raises(tmp_path: Path) -> None:
    _seed_project(tmp_path)
    with pytest.raises(ValueError):
        search(tmp_path, "foo", kind="bogus")


def test_file_tree_depth_1(tmp_path: Path) -> None:
    _seed_project(tmp_path)
    tree = file_tree(tmp_path, depth=1)
    # Top-level entries only
    assert any("README.md" in line for line in tree)
    assert any("src" in line for line in tree)
    assert any("tests" in line for line in tree)
    # No nested files at depth 1
    assert not any("main.py" in line for line in tree)


def test_file_tree_depth_2(tmp_path: Path) -> None:
    _seed_project(tmp_path)
    tree = file_tree(tmp_path, depth=2)
    assert any("src/main.py" in line for line in tree)
    assert any("tests/test_main.py" in line for line in tree)


def test_file_tree_rejects_outside_scope(tmp_path: Path) -> None:
    _seed_project(tmp_path)
    with pytest.raises(ScopeViolation):
        file_tree(tmp_path, path="..", depth=1)


@requires_rg
def test_outline_python_file(tmp_path: Path) -> None:
    _seed_project(tmp_path)
    lines = outline(tmp_path, "src/main.py")
    assert any("def hello" in line for line in lines)
    assert any("class Widget" in line for line in lines)


def test_outline_rejects_outside_scope(tmp_path: Path) -> None:
    _seed_project(tmp_path)
    with pytest.raises(ScopeViolation):
        outline(tmp_path, "../outside.py")


def test_build_server_does_not_raise(tmp_path: Path) -> None:
    _seed_project(tmp_path)
    server = build_server(tmp_path)
    assert server is not None
