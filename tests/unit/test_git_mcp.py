from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from aegis.core.worktree import ScopeViolation
from aegis.mcp_servers.git_mcp import (
    build_server,
    git_diff,
    git_log,
    git_status,
)


def _run(args: list[str], cwd: Path) -> None:
    subprocess.run(["git", *args], cwd=str(cwd), check=True, capture_output=True)


def _init_repo_with_commit(repo: Path) -> None:
    _run(["init", "-q", "-b", "main"], repo)
    _run(["config", "user.email", "t@t"], repo)
    _run(["config", "user.name", "t"], repo)
    _run(["config", "commit.gpgsign", "false"], repo)
    (repo / "a.txt").write_text("one\n")
    _run(["add", "a.txt"], repo)
    _run(["commit", "-q", "-m", "first"], repo)


def test_git_status_clean(tmp_path: Path) -> None:
    _init_repo_with_commit(tmp_path)
    assert git_status(tmp_path) == ""


def test_git_status_shows_untracked(tmp_path: Path) -> None:
    _init_repo_with_commit(tmp_path)
    (tmp_path / "new.txt").write_text("x")
    out = git_status(tmp_path)
    assert "new.txt" in out
    assert out.startswith("??")


def test_git_status_shows_modified(tmp_path: Path) -> None:
    _init_repo_with_commit(tmp_path)
    (tmp_path / "a.txt").write_text("two\n")
    out = git_status(tmp_path)
    assert "a.txt" in out
    assert " M" in out or "M " in out


def test_git_diff_shows_changes(tmp_path: Path) -> None:
    _init_repo_with_commit(tmp_path)
    (tmp_path / "a.txt").write_text("changed\n")
    out = git_diff(tmp_path)
    assert "-one" in out
    assert "+changed" in out


def test_git_diff_rev_range(tmp_path: Path) -> None:
    _init_repo_with_commit(tmp_path)
    (tmp_path / "a.txt").write_text("two\n")
    _run(["add", "a.txt"], tmp_path)
    _run(["commit", "-q", "-m", "second"], tmp_path)
    out = git_diff(tmp_path, rev_range="HEAD~1..HEAD")
    assert "-one" in out
    assert "+two" in out


def test_git_log_returns_oneline(tmp_path: Path) -> None:
    _init_repo_with_commit(tmp_path)
    out = git_log(tmp_path)
    assert "first" in out
    assert len(out.splitlines()) == 1


def test_git_log_respects_limit(tmp_path: Path) -> None:
    _init_repo_with_commit(tmp_path)
    for i in range(5):
        (tmp_path / f"f{i}.txt").write_text(str(i))
        _run(["add", f"f{i}.txt"], tmp_path)
        _run(["commit", "-q", "-m", f"c{i}"], tmp_path)
    out = git_log(tmp_path, limit=3)
    assert len(out.splitlines()) == 3


def test_git_status_scoped_path_escape_rejected(tmp_path: Path) -> None:
    _init_repo_with_commit(tmp_path)
    with pytest.raises(ScopeViolation):
        git_status(tmp_path, path="../outside")


def test_build_server_does_not_raise(tmp_path: Path) -> None:
    _init_repo_with_commit(tmp_path)
    server = build_server(tmp_path)
    assert server is not None
