"""A minimal :class:`SpanExporter` that writes one JSON line per span.

Spans are routed by the ``aegis.task_id`` attribute to
``<trace_dir>/<task_id>.jsonl``. Spans without that attribute are
dropped silently; in practice every Aegis-emitted span is stamped by
the :class:`~aegis.obs.otel.TaskIdSpanProcessor`, so the only orphans
in the wild are stray library spans (e.g. langgraph internals running
outside a task scope).
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from opentelemetry.sdk.trace import ReadableSpan
from opentelemetry.sdk.trace.export import SpanExporter, SpanExportResult

__all__ = ["JSONLSpanExporter"]

_MAX_STR_BYTES = 32 * 1024


def _truncate(value: Any) -> Any:
    if not isinstance(value, str):
        return value
    encoded = value.encode("utf-8")
    if len(encoded) <= _MAX_STR_BYTES:
        return value
    truncated = bytearray()
    for char in value:
        char_bytes = char.encode("utf-8")
        if len(truncated) + len(char_bytes) > _MAX_STR_BYTES:
            break
        truncated.extend(char_bytes)
    return truncated.decode("utf-8")


def _attrs_to_dict(attributes: Any) -> dict[str, Any]:
    if not attributes:
        return {}
    return {str(k): _truncate(v) for k, v in dict(attributes).items()}


def _serialize(span: ReadableSpan) -> dict[str, Any]:
    ctx = span.get_span_context()
    parent = span.parent
    duration_ns = (span.end_time or 0) - (span.start_time or 0)
    return {
        "name": span.name,
        "trace_id": format(ctx.trace_id, "032x"),
        "span_id": format(ctx.span_id, "016x"),
        "parent_span_id": format(parent.span_id, "016x") if parent else None,
        "start_time_ns": span.start_time,
        "end_time_ns": span.end_time,
        "duration_ns": duration_ns,
        "status": {
            "code": span.status.status_code.name,
            "description": span.status.description,
        },
        "attributes": _attrs_to_dict(span.attributes),
        "events": [
            {"name": e.name, "time_ns": e.timestamp, "attributes": _attrs_to_dict(e.attributes)}
            for e in (span.events or [])
        ],
    }


class JSONLSpanExporter(SpanExporter):
    """Writes spans as JSONL files under ``<trace_dir>/<task_id>.jsonl``."""

    def __init__(self, trace_dir: Path) -> None:
        self._trace_dir = trace_dir
        self._trace_dir.mkdir(parents=True, exist_ok=True)

    def export(self, spans: Sequence[ReadableSpan]) -> SpanExportResult:
        # Group by task_id to minimize file opens.
        by_task: dict[str, list[dict[str, Any]]] = {}
        for span in spans:
            attrs = span.attributes or {}
            task_id = attrs.get("aegis.task_id")
            if task_id is None:
                continue
            by_task.setdefault(str(task_id), []).append(_serialize(span))
        for task_id, records in by_task.items():
            path = self._trace_dir / f"{task_id}.jsonl"
            with open(path, "a", encoding="utf-8") as f:
                for record in records:
                    f.write(json.dumps(record, ensure_ascii=False) + "\n")
        return SpanExportResult.SUCCESS

    def shutdown(self) -> None:
        return None

    def force_flush(self, timeout_millis: int = 30000) -> bool:
        return True
