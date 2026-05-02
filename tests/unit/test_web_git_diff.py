from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from aegis.web.git_diff import diff_full, diff_stat


@pytest.fixture
def repo_with_branch(git_repo: Path) -> tuple[Path, str]:
    branch = "aegis/001-add-feature"
    subprocess.run(["git", "-C", str(git_repo), "checkout", "-b", branch], check=True)
    (git_repo / "feature.py").write_text("def f():\n    return 1\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(git_repo), "add", "feature.py"], check=True)
    subprocess.run(
        ["git", "-C", str(git_repo), "commit", "-q", "-m", "add feature"], check=True
    )
    subprocess.run(["git", "-C", str(git_repo), "checkout", "main"], check=True)
    return git_repo, branch


def test_diff_stat_shows_added_file(repo_with_branch: tuple[Path, str]) -> None:
    repo, branch = repo_with_branch
    out = diff_stat(repo, branch)
    assert "feature.py" in out
    assert "+" in out  # diffstat line uses '+' to indicate insertions


def test_diff_full_includes_added_lines(repo_with_branch: tuple[Path, str]) -> None:
    repo, branch = repo_with_branch
    out = diff_full(repo, branch)
    assert "+def f():" in out


def test_diff_stat_returns_empty_for_unknown_branch(git_repo: Path) -> None:
    assert diff_stat(git_repo, "aegis/does-not-exist") == ""


def test_diff_full_returns_empty_for_unknown_branch(git_repo: Path) -> None:
    assert diff_full(git_repo, "aegis/does-not-exist") == ""
