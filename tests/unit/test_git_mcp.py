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


from aegis.mcp_servers.git_mcp import (
    git_add,
    git_branch_create,
    git_checkout,
    git_commit,
)


def test_git_add_stages_file(tmp_path: Path) -> None:
    _init_repo_with_commit(tmp_path)
    (tmp_path / "new.txt").write_text("data")
    git_add(tmp_path, ["new.txt"])
    status = git_status(tmp_path)
    assert "A  new.txt" in status


def test_git_add_multiple_files(tmp_path: Path) -> None:
    _init_repo_with_commit(tmp_path)
    (tmp_path / "x.txt").write_text("1")
    (tmp_path / "y.txt").write_text("2")
    git_add(tmp_path, ["x.txt", "y.txt"])
    status = git_status(tmp_path)
    assert "x.txt" in status
    assert "y.txt" in status


def test_git_add_rejects_outside_scope(tmp_path: Path) -> None:
    _init_repo_with_commit(tmp_path)
    with pytest.raises(ScopeViolation):
        git_add(tmp_path, ["../escape.txt"])


def test_git_commit_creates_commit(tmp_path: Path) -> None:
    _init_repo_with_commit(tmp_path)
    (tmp_path / "new.txt").write_text("data")
    _run(["add", "new.txt"], tmp_path)
    git_commit(tmp_path, "add new.txt")
    log = git_log(tmp_path)
    assert "add new.txt" in log


def test_git_branch_create_creates_branch(tmp_path: Path) -> None:
    _init_repo_with_commit(tmp_path)
    git_branch_create(tmp_path, "feature/x")
    result = subprocess.run(
        ["git", "branch", "--list", "feature/x"],
        cwd=str(tmp_path), capture_output=True, text=True, check=True,
    )
    assert "feature/x" in result.stdout


def test_git_checkout_switches_branch(tmp_path: Path) -> None:
    _init_repo_with_commit(tmp_path)
    git_branch_create(tmp_path, "other")
    git_checkout(tmp_path, "other")
    result = subprocess.run(
        ["git", "symbolic-ref", "--short", "HEAD"],
        cwd=str(tmp_path), capture_output=True, text=True, check=True,
    )
    assert result.stdout.strip() == "other"


from aegis.mcp_servers.git_mcp import (
    git_merge,
    git_worktree_add,
    git_worktree_remove,
)


def test_git_worktree_add_creates_worktree(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    _init_repo_with_commit(repo)
    wt_rel = ".worktrees/feature-1"
    git_worktree_add(repo, wt_rel, "aegis/feature-1")
    wt_path = repo / wt_rel
    assert wt_path.is_dir()
    assert (wt_path / "a.txt").read_text() == "one\n"


def test_git_worktree_remove_cleans_up(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    _init_repo_with_commit(repo)
    wt_rel = ".worktrees/feature-2"
    git_worktree_add(repo, wt_rel, "aegis/feature-2")
    git_worktree_remove(repo, wt_rel)
    assert not (repo / wt_rel).exists()


def test_git_worktree_add_rejects_outside_scope(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    _init_repo_with_commit(repo)
    with pytest.raises(ScopeViolation):
        git_worktree_add(repo, "../evil-wt", "aegis/evil")


def test_git_merge_fast_forward(tmp_path: Path) -> None:
    _init_repo_with_commit(tmp_path)
    _run(["checkout", "-q", "-b", "feature"], tmp_path)
    (tmp_path / "new.txt").write_text("x")
    _run(["add", "new.txt"], tmp_path)
    _run(["commit", "-q", "-m", "feat"], tmp_path)
    _run(["checkout", "-q", "main"], tmp_path)
    out = git_merge(tmp_path, "feature", "main")
    assert "feat" in out or "merge" in out.lower() or "fast-forward" in out.lower()
    assert (tmp_path / "new.txt").exists()
    log = git_log(tmp_path)
    assert "feat" in log


def test_build_server_with_all_tools_does_not_raise(tmp_path: Path) -> None:
    _init_repo_with_commit(tmp_path)
    server = build_server(tmp_path)
    assert server is not None
