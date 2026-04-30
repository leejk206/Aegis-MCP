from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from typer.testing import CliRunner

from aegis.cli.main import app


def _bootstrap(repo: Path) -> Path:
    aegis = repo / ".aegis"
    aegis.mkdir(parents=True)
    return aegis


def test_daemon_start_writes_pidfile(tmp_path: Path, monkeypatch) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / ".git").mkdir()
    _bootstrap(repo)
    monkeypatch.chdir(repo)
    with patch("aegis.cli.commands.daemon.subprocess.Popen") as pop:
        proc = pop.return_value
        proc.pid = 4242
        result = CliRunner().invoke(app, ["daemon", "start"])
    assert result.exit_code == 0
    assert (repo / ".aegis" / ".daemon.pid").read_text().strip() == "4242"


def test_daemon_status_reports_running(tmp_path: Path, monkeypatch) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / ".git").mkdir()
    aegis = _bootstrap(repo)
    monkeypatch.chdir(repo)
    (aegis / ".daemon.pid").write_text("4242\n")
    with patch("aegis.cli.commands.daemon._is_pid_alive", return_value=True):
        result = CliRunner().invoke(app, ["daemon", "status"])
    assert result.exit_code == 0
    assert "running" in result.stdout.lower()


def test_daemon_stop_removes_pidfile(tmp_path: Path, monkeypatch) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / ".git").mkdir()
    aegis = _bootstrap(repo)
    monkeypatch.chdir(repo)
    (aegis / ".daemon.pid").write_text("4242\n")
    with (
        patch("aegis.cli.commands.daemon.os.kill") as kill,
        patch("aegis.cli.commands.daemon._is_pid_alive", return_value=True),
    ):
        result = CliRunner().invoke(app, ["daemon", "stop"])
    assert result.exit_code == 0
    kill.assert_called()
    assert not (aegis / ".daemon.pid").exists()
