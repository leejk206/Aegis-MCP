from typer.testing import CliRunner

from aegis.cli.main import app

runner = CliRunner()


def test_cli_shows_version() -> None:
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert "0.1.0" in result.output


def test_cli_help_lists_subcommands() -> None:
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    for name in ["run", "daemon", "approve", "web"]:
        assert name in result.output


def test_cli_stub_run_reports_not_implemented() -> None:
    result = runner.invoke(app, ["run"])
    assert result.exit_code != 0
    assert "Phase 4" in result.output
