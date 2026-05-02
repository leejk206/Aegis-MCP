from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from aegis.cli.commands.init import AEGIS_DIRNAME
from aegis.cli.main import app


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


def test_web_errors_when_aegis_dir_missing(
    tmp_path: Path, runner: CliRunner, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(app, ["web"])
    assert result.exit_code != 0


def test_web_invokes_uvicorn_with_app(
    tmp_path: Path, runner: CliRunner, monkeypatch: pytest.MonkeyPatch
) -> None:
    aegis_dir = tmp_path / AEGIS_DIRNAME
    aegis_dir.mkdir()
    (aegis_dir / "config.yaml").write_text(
        "version: 1\nproject:\n  name: test\n", encoding="utf-8"
    )
    monkeypatch.chdir(tmp_path)
    with patch("aegis.cli.commands.web.uvicorn.run") as mock:
        result = runner.invoke(app, ["web", "--port", "8888"])
        assert result.exit_code == 0
        assert mock.called
        call_kwargs = mock.call_args.kwargs
        assert call_kwargs["host"] == "127.0.0.1"
        assert call_kwargs["port"] == 8888


def test_web_help_message_lists_options(runner: CliRunner) -> None:
    result = runner.invoke(app, ["web", "--help"])
    assert result.exit_code == 0
    assert "--port" in result.stdout
    assert "--host" in result.stdout
