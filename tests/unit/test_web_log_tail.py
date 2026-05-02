from __future__ import annotations

import json
from pathlib import Path

from aegis.web.log_tail import tail_jsonl


def _write(path: Path, *records: dict) -> None:
    with open(path, "a", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(r) + "\n")


def _record(name: str, *, verdict: str | None = None) -> dict:
    return {
        "name": name,
        "trace_id": "0" * 32,
        "span_id": "0" * 16,
        "parent_span_id": None,
        "start_time_ns": 1_000_000_000,
        "end_time_ns": 1_500_000_000,
        "duration_ns": 500_000_000,
        "status": {"code": "OK", "description": None},
        "attributes": {**({"aegis.verdict": verdict} if verdict else {})},
        "events": [],
    }


def test_tail_returns_formatted_lines_in_order(tmp_path: Path) -> None:
    p = tmp_path / "001.jsonl"
    _write(p, _record("pm_node"), _record("dev_node"), _record("qa_node", verdict="pass"))
    out = tail_jsonl(p)
    assert len(out) == 3
    assert "pm_node" in out[0]
    assert "qa_node" in out[2]
    assert "verdict=pass" in out[2]


def test_tail_caps_at_max_lines(tmp_path: Path) -> None:
    p = tmp_path / "002.jsonl"
    _write(p, *(_record(f"n{i}") for i in range(50)))
    out = tail_jsonl(p, max_lines=10)
    assert len(out) == 10
    assert "n40" in out[0]
    assert "n49" in out[-1]


def test_tail_returns_empty_for_missing_file(tmp_path: Path) -> None:
    assert tail_jsonl(tmp_path / "missing.jsonl") == []


def test_tail_skips_malformed_lines(tmp_path: Path) -> None:
    p = tmp_path / "003.jsonl"
    p.write_text("not json\n", encoding="utf-8")
    _write(p, _record("pm_node"))
    out = tail_jsonl(p)
    assert len(out) == 1
    assert "pm_node" in out[0]
