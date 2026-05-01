from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock

from opentelemetry.sdk.trace.export import SpanExportResult

from aegis.obs.jsonl_exporter import JSONLSpanExporter


def _fake_span(
    *,
    name: str,
    task_id: str | None,
    attributes: dict | None = None,
    start_ns: int = 1000,
    end_ns: int = 2000,
    status_desc: str | None = None,
):
    span = MagicMock()
    span.name = name
    attrs = dict(attributes or {})
    if task_id is not None:
        attrs["aegis.task_id"] = task_id
    span.attributes = attrs
    span.start_time = start_ns
    span.end_time = end_ns
    ctx = MagicMock()
    ctx.trace_id = 0x1A
    ctx.span_id = 0x2B
    span.get_span_context.return_value = ctx
    parent = MagicMock()
    parent.span_id = 0x3C
    span.parent = parent
    status = MagicMock()
    status.status_code.name = "OK"
    status.description = status_desc
    span.status = status
    span.events = []
    return span


def test_writes_one_json_line_per_span(tmp_path: Path) -> None:
    exporter = JSONLSpanExporter(trace_dir=tmp_path)
    span = _fake_span(name="dev_node", task_id="001")
    result = exporter.export([span])
    assert result == SpanExportResult.SUCCESS
    out = (tmp_path / "001.jsonl").read_text(encoding="utf-8")
    line, _ = out.split("\n", 1) if "\n" in out else (out, "")
    record = json.loads(line)
    assert record["name"] == "dev_node"
    assert record["attributes"]["aegis.task_id"] == "001"
    assert record["trace_id"] == format(0x1A, "032x")
    assert record["span_id"] == format(0x2B, "016x")
    assert record["parent_span_id"] == format(0x3C, "016x")
    assert record["duration_ns"] == 1000


def test_appends_subsequent_spans(tmp_path: Path) -> None:
    exporter = JSONLSpanExporter(trace_dir=tmp_path)
    exporter.export([_fake_span(name="pm_node", task_id="002")])
    exporter.export([_fake_span(name="dev_node", task_id="002")])
    lines = (tmp_path / "002.jsonl").read_text(encoding="utf-8").strip().split("\n")
    assert len(lines) == 2
    assert json.loads(lines[0])["name"] == "pm_node"
    assert json.loads(lines[1])["name"] == "dev_node"


def test_drops_spans_without_task_id(tmp_path: Path) -> None:
    exporter = JSONLSpanExporter(trace_dir=tmp_path)
    result = exporter.export([_fake_span(name="orphan", task_id=None)])
    assert result == SpanExportResult.SUCCESS
    assert list(tmp_path.iterdir()) == []


def test_routes_per_task_id(tmp_path: Path) -> None:
    exporter = JSONLSpanExporter(trace_dir=tmp_path)
    exporter.export(
        [
            _fake_span(name="a", task_id="003"),
            _fake_span(name="b", task_id="004"),
        ]
    )
    assert (tmp_path / "003.jsonl").exists()
    assert (tmp_path / "004.jsonl").exists()


def test_truncates_string_attributes_over_32kb(tmp_path: Path) -> None:
    huge = "x" * (40 * 1024)
    exporter = JSONLSpanExporter(trace_dir=tmp_path)
    exporter.export(
        [_fake_span(name="big", task_id="005", attributes={"prompt": huge})]
    )
    record = json.loads((tmp_path / "005.jsonl").read_text(encoding="utf-8").strip())
    assert len(record["attributes"]["prompt"]) == 32 * 1024
    assert record["attributes"]["prompt"].endswith("…[truncated]") is False  # exact byte cut, no marker fanout
