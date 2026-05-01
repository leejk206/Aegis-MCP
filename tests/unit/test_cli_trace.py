from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from aegis.cli.main import app


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


def _bootstrap_project(tmp_path: Path, *, langfuse: bool, langsmith: bool) -> None:
    aegis_dir = tmp_path / ".aegis"
    aegis_dir.mkdir()
    (aegis_dir / "config.yaml").write_text(
        f"""
project: {{ name: t }}
observability:
  langfuse: {{ enabled: {str(langfuse).lower()}, url: 'http://localhost:3000' }}
  langsmith: {{ enabled: {str(langsmith).lower()}, project: aegis-test }}
""",
        encoding="utf-8",
    )
    (aegis_dir / "in-progress").mkdir()
    task_md = aegis_dir / "in-progress" / "001-x.md"
    task_md.write_text(
        "---\n"
        "id: '001'\n"
        "title: x\n"
        "status: in-progress\n"
        "priority: P2\n"
        "budget: { usd: 1.0, minutes: 5 }\n"
        "created: 2026-05-01T00:00:00Z\n"
        "trace_id: abcdef0123456789abcdef0123456789\n"
        "---\n\n# x\n",
        encoding="utf-8",
    )


def test_trace_opens_langsmith_when_enabled(tmp_path, runner, monkeypatch) -> None:
    _bootstrap_project(tmp_path, langfuse=False, langsmith=True)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("LANGSMITH_API_KEY", "ls_xxx")
    with patch("webbrowser.open") as opener:
        result = runner.invoke(app, ["trace", "001"])
    assert result.exit_code == 0
    opener.assert_called_once()
    url = opener.call_args[0][0]
    assert "smith.langchain.com" in url
    assert "abcdef0123456789abcdef0123456789" in url


def test_trace_opens_langfuse_when_only_langfuse_enabled(tmp_path, runner, monkeypatch) -> None:
    _bootstrap_project(tmp_path, langfuse=True, langsmith=False)
    monkeypatch.chdir(tmp_path)
    with patch("webbrowser.open") as opener:
        result = runner.invoke(app, ["trace", "001"])
    assert result.exit_code == 0
    url = opener.call_args[0][0]
    assert "localhost:3000" in url
    assert "abcdef0123456789abcdef0123456789" in url


def test_trace_falls_back_to_logs_hint(tmp_path, runner, monkeypatch) -> None:
    _bootstrap_project(tmp_path, langfuse=False, langsmith=False)
    monkeypatch.chdir(tmp_path)
    with patch("webbrowser.open") as opener:
        result = runner.invoke(app, ["trace", "001"])
    opener.assert_not_called()
    assert "aegis logs 001" in result.stdout
    assert result.exit_code == 0
