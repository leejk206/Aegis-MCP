from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from aegis.cli.main import app


def _bootstrap(repo: Path) -> Path:
    aegis = repo / ".aegis"
    aegis.mkdir(parents=True)
    return aegis


def test_stop_no_arg_creates_global_flag(tmp_path: Path, monkeypatch) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / ".git").mkdir()
    _bootstrap(repo)
    monkeypatch.chdir(repo)

    result = CliRunner().invoke(app, ["stop"])
    assert result.exit_code == 0
    assert (repo / ".aegis" / ".stop").exists()


def test_stop_with_id_creates_task_flag(tmp_path: Path, monkeypatch) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / ".git").mkdir()
    _bootstrap(repo)
    monkeypatch.chdir(repo)

    result = CliRunner().invoke(app, ["stop", "001"])
    assert result.exit_code == 0
    assert (repo / ".aegis" / ".stop.001").exists()
