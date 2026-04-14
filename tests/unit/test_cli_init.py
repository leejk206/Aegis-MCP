from pathlib import Path

import pytest
import typer

from aegis.cli.commands.init import run_init
from aegis.core.config import load_config


def test_init_creates_directory_structure(git_repo: Path) -> None:
    aegis_dir = run_init(git_repo, force=False)

    assert aegis_dir == (git_repo / ".aegis").resolve()
    assert (aegis_dir / "backlog").is_dir()
    assert (aegis_dir / "in-progress").is_dir()
    assert (aegis_dir / "review").is_dir()
    assert (aegis_dir / "done").is_dir()
    assert (aegis_dir / "blocked").is_dir()
    assert (aegis_dir / "rejected").is_dir()
    assert (aegis_dir / ".worktrees").is_dir()
    assert (aegis_dir / "trace").is_dir()
    assert (aegis_dir / "config.yaml").is_file()

    cfg = load_config(aegis_dir / "config.yaml")
    assert cfg.project.name == git_repo.name


def test_init_refuses_non_git_dir(tmp_path: Path) -> None:
    with pytest.raises(typer.BadParameter):
        run_init(tmp_path, force=False)


def test_init_refuses_existing_without_force(git_repo: Path) -> None:
    run_init(git_repo, force=False)
    with pytest.raises(typer.BadParameter):
        run_init(git_repo, force=False)


def test_init_with_force_overwrites(git_repo: Path) -> None:
    run_init(git_repo, force=False)
    run_init(git_repo, force=True)  # must not raise
    assert (git_repo / ".aegis" / "config.yaml").is_file()


def test_init_appends_gitignore_entries(git_repo: Path) -> None:
    run_init(git_repo, force=False)
    gitignore = (git_repo / ".gitignore").read_text(encoding="utf-8")
    assert ".aegis/.worktrees/" in gitignore
    assert ".aegis/trace/" in gitignore
    assert ".aegis/checkpoint.db" in gitignore
