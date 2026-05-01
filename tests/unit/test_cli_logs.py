from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from aegis.cli.commands.init import AEGIS_DIRNAME
from aegis.cli.main import app


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


def _write_record(path: Path, *, name: str, role: str, verdict: str | None = None) -> None:
    record = {
        "name": name,
        "trace_id": "0" * 32,
        "span_id": "0" * 16,
        "parent_span_id": None,
        "start_time_ns": 1_000_000_000,
        "end_time_ns": 1_500_000_000,
        "duration_ns": 500_000_000,
        "status": {"code": "OK", "description": None},
        "attributes": {"aegis.role": role, "aegis.task_id": "001",
                       **({"aegis.verdict": verdict} if verdict else {})},
        "events": [],
    }
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(record) + "\n")


def test_logs_prints_existing_lines(tmp_path: Path, runner: CliRunner, monkeypatch) -> None:
    aegis_dir = tmp_path / AEGIS_DIRNAME
    (aegis_dir / "trace").mkdir(parents=True)
    _write_record(aegis_dir / "trace" / "001.jsonl", name="pm_node", role="pm")
    _write_record(
        aegis_dir / "trace" / "001.jsonl", name="qa_node", role="qa", verdict="pass"
    )
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(app, ["logs", "001"])
    assert result.exit_code == 0
    assert "pm_node" in result.stdout
    assert "qa_node" in result.stdout
    assert "verdict=pass" in result.stdout


def test_logs_errors_when_trace_missing(tmp_path: Path, runner: CliRunner, monkeypatch) -> None:
    aegis_dir = tmp_path / AEGIS_DIRNAME
    aegis_dir.mkdir()
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(app, ["logs", "999"])
    assert result.exit_code != 0
    assert "999" in result.stderr


def test_logs_errors_when_aegis_dir_missing(tmp_path: Path, runner: CliRunner, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(app, ["logs", "001"])
    assert result.exit_code != 0
