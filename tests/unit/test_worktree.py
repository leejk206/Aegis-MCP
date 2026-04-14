from pathlib import Path

import pytest

from aegis.core.worktree import (
    ScopeViolation,
    WorktreeError,
    create_worktree,
    list_worktrees,
    remove_worktree,
    validate_path_in_scope,
)


def test_create_and_list_worktree(tmp_path: Path, git_repo: Path) -> None:
    wt_path = tmp_path / "wt-001"
    create_worktree(git_repo, wt_path, branch="aegis/001-test")
    assert wt_path.exists()
    assert (wt_path / "README.md").exists()

    worktrees = list_worktrees(git_repo)
    paths = [w.get("worktree", "") for w in worktrees]
    assert any(str(wt_path.resolve()) == p for p in paths)


def test_remove_worktree(tmp_path: Path, git_repo: Path) -> None:
    wt_path = tmp_path / "wt-002"
    create_worktree(git_repo, wt_path, branch="aegis/002-test")
    assert wt_path.exists()

    remove_worktree(git_repo, wt_path)
    assert not wt_path.exists()


def test_create_worktree_fails_on_nonrepo(tmp_path: Path) -> None:
    with pytest.raises(WorktreeError):
        create_worktree(tmp_path, tmp_path / "wt", branch="b")


def test_validate_path_in_scope_accepts_inside(tmp_path: Path) -> None:
    scope = tmp_path / "scope"
    scope.mkdir()
    (scope / "a").mkdir()
    result = validate_path_in_scope(scope / "a", scope)
    assert result == (scope / "a").resolve()


def test_validate_path_in_scope_rejects_outside(tmp_path: Path) -> None:
    scope = tmp_path / "scope"
    scope.mkdir()
    other = tmp_path / "other"
    other.mkdir()
    with pytest.raises(ScopeViolation):
        validate_path_in_scope(other, scope)


def test_validate_path_in_scope_rejects_parent(tmp_path: Path) -> None:
    scope = tmp_path / "scope" / "inner"
    scope.mkdir(parents=True)
    with pytest.raises(ScopeViolation):
        validate_path_in_scope(scope.parent, scope)
