from __future__ import annotations

from pathlib import Path

import pytest

from aegis.core.worktree import ScopeViolation
from aegis.mcp_servers.fs_mcp import (
    build_server,
    fs_delete,
    fs_glob,
    fs_list,
    fs_mkdir,
    fs_move,
    fs_read,
    fs_write,
)


def test_fs_read_returns_text(tmp_path: Path) -> None:
    (tmp_path / "a.txt").write_text("hello", encoding="utf-8")
    assert fs_read(tmp_path, "a.txt") == "hello"


def test_fs_read_absolute_path(tmp_path: Path) -> None:
    target = tmp_path / "b.txt"
    target.write_text("bye", encoding="utf-8")
    assert fs_read(tmp_path, str(target)) == "bye"


def test_fs_read_rejects_outside_scope(tmp_path: Path) -> None:
    with pytest.raises(ScopeViolation):
        fs_read(tmp_path, "../outside.txt")


def test_fs_list_returns_sorted_names(tmp_path: Path) -> None:
    (tmp_path / "b").write_text("")
    (tmp_path / "a").write_text("")
    (tmp_path / "c").mkdir()
    assert fs_list(tmp_path, ".") == ["a", "b", "c"]


def test_fs_list_subdir(tmp_path: Path) -> None:
    sub = tmp_path / "sub"
    sub.mkdir()
    (sub / "x").write_text("")
    assert fs_list(tmp_path, "sub") == ["x"]


def test_fs_list_rejects_outside_scope(tmp_path: Path) -> None:
    with pytest.raises(ScopeViolation):
        fs_list(tmp_path, "/etc")


def test_fs_glob_matches_within_scope(tmp_path: Path) -> None:
    (tmp_path / "a.py").write_text("")
    (tmp_path / "b.py").write_text("")
    (tmp_path / "c.txt").write_text("")
    sub = tmp_path / "sub"
    sub.mkdir()
    (sub / "d.py").write_text("")
    assert fs_glob(tmp_path, "*.py") == ["a.py", "b.py"]
    assert fs_glob(tmp_path, "**/*.py") == ["a.py", "b.py", "sub/d.py"]


def test_fs_glob_returns_empty_for_no_match(tmp_path: Path) -> None:
    assert fs_glob(tmp_path, "*.rs") == []


def test_fs_write_creates_file(tmp_path: Path) -> None:
    fs_write(tmp_path, "a.txt", "content")
    assert (tmp_path / "a.txt").read_text(encoding="utf-8") == "content"


def test_fs_write_creates_parent_dirs(tmp_path: Path) -> None:
    fs_write(tmp_path, "nested/deep/file.txt", "x")
    assert (tmp_path / "nested" / "deep" / "file.txt").read_text(encoding="utf-8") == "x"


def test_fs_write_rejects_outside_scope(tmp_path: Path) -> None:
    with pytest.raises(ScopeViolation):
        fs_write(tmp_path, "../leak.txt", "nope")


def test_fs_mkdir_creates_directory(tmp_path: Path) -> None:
    fs_mkdir(tmp_path, "newdir")
    assert (tmp_path / "newdir").is_dir()


def test_fs_mkdir_is_idempotent(tmp_path: Path) -> None:
    fs_mkdir(tmp_path, "again")
    fs_mkdir(tmp_path, "again")  # no error
    assert (tmp_path / "again").is_dir()


def test_fs_mkdir_creates_parents(tmp_path: Path) -> None:
    fs_mkdir(tmp_path, "a/b/c")
    assert (tmp_path / "a" / "b" / "c").is_dir()


def test_fs_delete_removes_file(tmp_path: Path) -> None:
    (tmp_path / "kill.txt").write_text("")
    fs_delete(tmp_path, "kill.txt")
    assert not (tmp_path / "kill.txt").exists()


def test_fs_delete_removes_directory_tree(tmp_path: Path) -> None:
    sub = tmp_path / "dead"
    sub.mkdir()
    (sub / "leaf").write_text("")
    fs_delete(tmp_path, "dead")
    assert not sub.exists()


def test_fs_delete_rejects_outside_scope(tmp_path: Path) -> None:
    with pytest.raises(ScopeViolation):
        fs_delete(tmp_path, "../../nope")


def test_fs_move_renames_file(tmp_path: Path) -> None:
    (tmp_path / "src.txt").write_text("data")
    fs_move(tmp_path, "src.txt", "dst.txt")
    assert not (tmp_path / "src.txt").exists()
    assert (tmp_path / "dst.txt").read_text(encoding="utf-8") == "data"


def test_fs_move_creates_dst_parent(tmp_path: Path) -> None:
    (tmp_path / "a.txt").write_text("x")
    fs_move(tmp_path, "a.txt", "sub/b.txt")
    assert (tmp_path / "sub" / "b.txt").read_text(encoding="utf-8") == "x"


def test_fs_move_rejects_src_outside_scope(tmp_path: Path) -> None:
    outside = tmp_path.parent / "elsewhere.txt"
    outside.write_text("")
    with pytest.raises(ScopeViolation):
        fs_move(tmp_path, str(outside), "here.txt")
    outside.unlink()


def test_fs_move_rejects_dst_outside_scope(tmp_path: Path) -> None:
    (tmp_path / "a.txt").write_text("")
    with pytest.raises(ScopeViolation):
        fs_move(tmp_path, "a.txt", "../escaped.txt")


def test_build_server_does_not_raise(tmp_path: Path) -> None:
    server = build_server(tmp_path)
    assert server is not None
