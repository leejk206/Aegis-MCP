# Phase 5 — Observability (OTel + LangSmith + Langfuse + JSONL) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Wire OpenTelemetry-first instrumentation into the Phase-4 LangGraph runtime so every task run emits spans to (a) a local `.aegis/trace/<task_id>.jsonl` mirror, (b) Langfuse via OTLP/HTTP when enabled, and (c) LangSmith via the `langsmith` SDK's auto-instrumentation when enabled — and replace the Phase-1 stubs `aegis logs` / `aegis trace`.

**Architecture:** A single `bootstrap_tracing(config, aegis_dir)` returns an idempotent OTel `TracerProvider` configured with a `TaskIdSpanProcessor` (stamps `aegis.task_id` on every span from a `ContextVar`) and one or more exporters chosen by `config.observability`. The graph runtime sets the contextvar around each task run and opens a root span; a `traced_node` decorator opens a child span around every role node and records role/verdict/blocker. LangSmith is a parallel pipeline activated by setting `LANGCHAIN_TRACING_V2=true` + `LANGSMITH_API_KEY` before `build_graph()` is invoked, leveraging LangGraph's built-in callback handler. Per-MCP-subprocess child spans (via OTLP context propagation across stdio) are explicitly **out of scope** for this phase — spans stop at the agent-call boundary on the parent process.

**Tech Stack:** `opentelemetry-api`, `opentelemetry-sdk`, `opentelemetry-exporter-otlp-proto-http`, `langsmith`, `langfuse` (used only as a peer dep — Langfuse ingestion goes through OTLP/HTTP, not the Langfuse SDK); existing `aegis.core.config.ObservabilityConfig`, `aegis.graph.{runtime,team_graph}` from Phase 4; `typer` for the new CLI commands.

---

## Pre-flight

Before starting any task, verify the workspace is in the expected post-Phase-4 state.

```bash
git status                                                # clean
git log --oneline -1                                      # 73a9f0b style: ruff format phase 4 modules
git tag -l | grep phase-4-complete                        # phase-4-complete
pytest tests/unit -q                                      # all green (Phase 1+2+3+4 tests)
```

If any check fails, stop and reconcile before proceeding. Phase 5 assumes `aegis.graph.runtime`, `aegis.graph.team_graph`, the five role nodes, the `aegis.core.config.ObservabilityConfig`, and the eight Phase-4 CLI commands all work as written.

The `opentelemetry-*` and `langfuse`/`langsmith` packages may not yet be installed. Each task that imports them runs under `pip install -e .[dev]` after Task 1; if `pytest` reports `ModuleNotFoundError: No module named 'opentelemetry'` or `'langfuse'`, run `pip install -e .[dev]` once at the start of the phase.

---

## Map of files this phase touches

**Created:**

- `src/aegis/obs/jsonl_exporter.py`                    — custom `SpanExporter` writing one JSON line per span to `.aegis/trace/<task_id>.jsonl`
- `src/aegis/obs/otel.py`                              — `bootstrap_tracing`, `TaskIdSpanProcessor`, `aegis_task_id_var`
- `src/aegis/obs/langsmith_exporter.py`                — env-var setup for LangSmith auto-instrumentation
- `src/aegis/obs/langfuse_exporter.py`                 — OTLP/HTTP exporter configured against a Langfuse instance
- `src/aegis/obs/instrumentation.py`                   — `traced_node` decorator wrapping a `NodeFn` with a child span
- `src/aegis/cli/commands/logs.py`                     — `aegis logs <id> [--follow]`
- `src/aegis/cli/commands/trace.py`                    — `aegis trace <id>`
- `docker-compose.yml`                                 — Langfuse self-host stack (Langfuse + Postgres + Redis)
- `tests/unit/test_obs_jsonl_exporter.py`
- `tests/unit/test_obs_otel.py`
- `tests/unit/test_obs_langsmith_exporter.py`
- `tests/unit/test_obs_langfuse_exporter.py`
- `tests/unit/test_obs_instrumentation.py`
- `tests/unit/test_cli_logs.py`
- `tests/unit/test_cli_trace.py`

**Modified:**

- `pyproject.toml`                                     — add `opentelemetry-api`, `opentelemetry-sdk`, `opentelemetry-exporter-otlp-proto-http`, `langsmith`, `langfuse`
- `src/aegis/core/config.py`                           — add `JSONLConfig`, extend `ObservabilityConfig`
- `src/aegis/obs/__init__.py`                          — export `bootstrap_tracing`, `aegis_task_id_var`, `traced_node`
- `src/aegis/graph/runtime.py`                         — bootstrap once per task, set contextvar + root span, write `trace_id` to frontmatter
- `src/aegis/graph/team_graph.py`                      — wrap each role node with `traced_node`
- `src/aegis/cli/main.py`                              — register `logs`, `trace`; drop their stubs
- `src/aegis/cli/commands/stubs.py`                    — remove `logs`, `trace` (keep `web`)
- `Makefile`                                           — add `langfuse` and `langfuse-down` targets
- `README.md`                                          — observability section
- `docs/status.json`                                   — flip Phase 5 to complete and tag

---

## Task 1: Add observability dependencies

**Files:**

- Modify: `pyproject.toml`

- [ ] **Step 1: Add the OTel + LangSmith + Langfuse packages**

Edit the `dependencies` array in `pyproject.toml` to:

```toml
dependencies = [
    "pydantic>=2.7",
    "python-frontmatter>=1.1",
    "pyyaml>=6.0",
    "typer>=0.12",
    "mcp>=1.0",
    "claude-agent-sdk>=0.1.61",
    "langgraph>=0.2.50",
    "langgraph-checkpoint-sqlite>=2.0",
    "opentelemetry-api>=1.27",
    "opentelemetry-sdk>=1.27",
    "opentelemetry-exporter-otlp-proto-http>=1.27",
    "langsmith>=0.1.140",
    "langfuse>=2.50",
]
```

- [ ] **Step 2: Install in development mode**

Run: `pip install -e .[dev]`
Expected: installs without resolver errors.

- [ ] **Step 3: Smoke-import**

Run:

```bash
python -c "from opentelemetry.sdk.trace import TracerProvider; from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter; import langsmith, langfuse; print('ok')"
```

Expected: `ok`.

- [ ] **Step 4: Commit**

```bash
git add pyproject.toml
git commit -m "build: add OTel + LangSmith + Langfuse to phase 5 deps"
```

---

## Task 2: Extend `ObservabilityConfig` with JSONL toggle

The current schema (`src/aegis/core/config.py:100-125`) has `langsmith`, `langfuse`, `otel`. Add a `jsonl` block (default-enabled, no-network) so the local mirror is on by default and can be turned off explicitly.

**Files:**

- Modify: `src/aegis/core/config.py`
- Test: `tests/unit/test_config.py` (extend)

- [ ] **Step 1: Write a failing config test**

Append to `tests/unit/test_config.py`:

```python
def test_observability_default_enables_jsonl_and_langfuse() -> None:
    cfg = AegisConfig(project=ProjectConfig(name="t"))
    assert cfg.observability.jsonl.enabled is True
    assert cfg.observability.langfuse.enabled is True
    assert cfg.observability.langsmith.enabled is False


def test_observability_jsonl_can_be_disabled() -> None:
    cfg = AegisConfig.model_validate(
        {"project": {"name": "t"}, "observability": {"jsonl": {"enabled": False}}}
    )
    assert cfg.observability.jsonl.enabled is False
```

If `ProjectConfig` is not already imported in that file, add `from aegis.core.config import AegisConfig, ProjectConfig` to the test imports.

- [ ] **Step 2: Run the new tests to confirm they fail**

Run: `pytest tests/unit/test_config.py -k "observability_default_enables_jsonl or observability_jsonl_can_be_disabled" -v`
Expected: 2 FAILED with `AttributeError: 'ObservabilityConfig' object has no attribute 'jsonl'`.

- [ ] **Step 3: Add the `JSONLConfig` model and wire it in**

In `src/aegis/core/config.py`, after the existing `OtelConfig` class and before `ObservabilityConfig`:

```python
class JSONLConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    enabled: bool = True
```

And update `ObservabilityConfig`:

```python
class ObservabilityConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    langsmith: LangSmithConfig = Field(default_factory=LangSmithConfig)
    langfuse: LangfuseConfig = Field(default_factory=LangfuseConfig)
    otel: OtelConfig = Field(default_factory=OtelConfig)
    jsonl: JSONLConfig = Field(default_factory=JSONLConfig)
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `pytest tests/unit/test_config.py -v`
Expected: all PASS, including the two new tests.

- [ ] **Step 5: Commit**

```bash
git add src/aegis/core/config.py tests/unit/test_config.py
git commit -m "feat(config): add JSONL observability toggle (default on)"
```

---

## Task 3: JSONL span exporter

A custom `SpanExporter` that writes one JSON line per span to `.aegis/trace/<task_id>.jsonl`. It bins by the `aegis.task_id` span attribute (set by `TaskIdSpanProcessor` in Task 4); spans without the attribute are dropped silently with no exception (we don't want a missing attribute to break agent runs).

**Files:**

- Create: `src/aegis/obs/jsonl_exporter.py`
- Test: `tests/unit/test_obs_jsonl_exporter.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/unit/test_obs_jsonl_exporter.py`:

```python
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
```

- [ ] **Step 2: Run the tests to confirm they fail**

Run: `pytest tests/unit/test_obs_jsonl_exporter.py -v`
Expected: 5 FAILED with `ModuleNotFoundError: No module named 'aegis.obs.jsonl_exporter'`.

- [ ] **Step 3: Implement the exporter**

Create `src/aegis/obs/jsonl_exporter.py`:

```python
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
    if isinstance(value, str) and len(value) > _MAX_STR_BYTES:
        return value[:_MAX_STR_BYTES]
    return value


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
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `pytest tests/unit/test_obs_jsonl_exporter.py -v`
Expected: 5 PASS.

- [ ] **Step 5: Commit**

```bash
git add src/aegis/obs/jsonl_exporter.py tests/unit/test_obs_jsonl_exporter.py
git commit -m "feat(obs): JSONL span exporter for local trace mirror"
```

---

## Task 4: OTel bootstrap with `TaskIdSpanProcessor`

The bootstrap is **idempotent** — it returns the same provider on subsequent calls within the process, so the daemon's per-task call sites never accidentally install a second provider. A `ContextVar[str | None]` named `aegis_task_id_var` carries the active task id; a custom `SpanProcessor.on_start` stamps it onto every started span.

**Files:**

- Create: `src/aegis/obs/otel.py`
- Test: `tests/unit/test_obs_otel.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/unit/test_obs_otel.py`:

```python
from __future__ import annotations

from pathlib import Path

import pytest
from opentelemetry import trace as otel_trace
from opentelemetry.sdk.trace import TracerProvider

from aegis.core.config import AegisConfig, ProjectConfig
from aegis.obs.otel import (
    aegis_task_id_var,
    bootstrap_tracing,
    reset_tracing_for_tests,
)


@pytest.fixture(autouse=True)
def _reset() -> None:
    reset_tracing_for_tests()
    yield
    reset_tracing_for_tests()


def _cfg() -> AegisConfig:
    return AegisConfig(project=ProjectConfig(name="t"))


def test_bootstrap_returns_tracer_provider(tmp_path: Path) -> None:
    provider = bootstrap_tracing(_cfg(), tmp_path)
    assert isinstance(provider, TracerProvider)


def test_bootstrap_is_idempotent(tmp_path: Path) -> None:
    p1 = bootstrap_tracing(_cfg(), tmp_path)
    p2 = bootstrap_tracing(_cfg(), tmp_path)
    assert p1 is p2


def test_task_id_processor_stamps_active_var(tmp_path: Path) -> None:
    bootstrap_tracing(_cfg(), tmp_path)
    tracer = otel_trace.get_tracer("test")
    token = aegis_task_id_var.set("042")
    try:
        with tracer.start_as_current_span("dev_node") as span:
            assert span.attributes["aegis.task_id"] == "042"
    finally:
        aegis_task_id_var.reset(token)


def test_jsonl_exporter_writes_when_enabled(tmp_path: Path) -> None:
    cfg = AegisConfig.model_validate(
        {
            "project": {"name": "t"},
            "observability": {"jsonl": {"enabled": True}, "langfuse": {"enabled": False}},
        }
    )
    bootstrap_tracing(cfg, tmp_path)
    tracer = otel_trace.get_tracer("test")
    token = aegis_task_id_var.set("777")
    try:
        with tracer.start_as_current_span("pm_node"):
            pass
    finally:
        aegis_task_id_var.reset(token)
    otel_trace.get_tracer_provider().force_flush()
    out = (tmp_path / "trace" / "777.jsonl").read_text(encoding="utf-8")
    assert "pm_node" in out


def test_jsonl_disabled_writes_nothing(tmp_path: Path) -> None:
    cfg = AegisConfig.model_validate(
        {
            "project": {"name": "t"},
            "observability": {"jsonl": {"enabled": False}, "langfuse": {"enabled": False}},
        }
    )
    bootstrap_tracing(cfg, tmp_path)
    tracer = otel_trace.get_tracer("test")
    token = aegis_task_id_var.set("888")
    try:
        with tracer.start_as_current_span("pm_node"):
            pass
    finally:
        aegis_task_id_var.reset(token)
    otel_trace.get_tracer_provider().force_flush()
    assert not (tmp_path / "trace" / "888.jsonl").exists()
```

- [ ] **Step 2: Run the tests to confirm they fail**

Run: `pytest tests/unit/test_obs_otel.py -v`
Expected: 5 FAILED with `ModuleNotFoundError: No module named 'aegis.obs.otel'`.

- [ ] **Step 3: Implement the bootstrap**

Create `src/aegis/obs/otel.py`:

```python
"""OpenTelemetry bootstrap for Aegis.

One process owns one :class:`TracerProvider`. Subsequent calls to
:func:`bootstrap_tracing` return the same instance — daemons that run
many tasks in sequence (or in parallel) call this from each task's
runtime entry without worrying about double-init.

Span context is augmented by :class:`TaskIdSpanProcessor` which reads
:data:`aegis_task_id_var` (a :class:`contextvars.ContextVar`) and
stamps ``aegis.task_id`` onto every started span. The runtime sets the
contextvar around each task run; the JSONL exporter routes by it.
"""

from __future__ import annotations

import contextvars
from pathlib import Path

from opentelemetry import trace as otel_trace
from opentelemetry.context import Context
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import ReadableSpan, Span, SpanProcessor, TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, SimpleSpanProcessor

from aegis.core.config import AegisConfig
from aegis.obs.jsonl_exporter import JSONLSpanExporter

__all__ = [
    "aegis_task_id_var",
    "bootstrap_tracing",
    "reset_tracing_for_tests",
    "TaskIdSpanProcessor",
]

aegis_task_id_var: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "aegis_task_id", default=None
)

_provider: TracerProvider | None = None


class TaskIdSpanProcessor(SpanProcessor):
    """Stamp ``aegis.task_id`` from the active contextvar on every span."""

    def on_start(self, span: Span, parent_context: Context | None = None) -> None:
        task_id = aegis_task_id_var.get()
        if task_id is not None:
            span.set_attribute("aegis.task_id", task_id)

    def on_end(self, span: ReadableSpan) -> None:
        return None

    def shutdown(self) -> None:
        return None

    def force_flush(self, timeout_millis: int = 30000) -> bool:
        return True


def _build_provider(config: AegisConfig, aegis_dir: Path) -> TracerProvider:
    resource = Resource.create({"service.name": config.observability.otel.service_name})
    provider = TracerProvider(resource=resource)
    provider.add_span_processor(TaskIdSpanProcessor())

    if config.observability.jsonl.enabled:
        trace_dir = aegis_dir / "trace"
        # SimpleSpanProcessor flushes synchronously — important for the
        # `aegis logs` command to see span data immediately after a node
        # exits, without waiting for a batch interval.
        provider.add_span_processor(SimpleSpanProcessor(JSONLSpanExporter(trace_dir)))

    if config.observability.langfuse.enabled:
        from aegis.obs.langfuse_exporter import build_langfuse_exporter

        exporter = build_langfuse_exporter(config.observability.langfuse)
        if exporter is not None:
            provider.add_span_processor(BatchSpanProcessor(exporter))

    if config.observability.langsmith.enabled:
        from aegis.obs.langsmith_exporter import enable_langsmith

        enable_langsmith(config.observability.langsmith)

    return provider


def bootstrap_tracing(config: AegisConfig, aegis_dir: Path) -> TracerProvider:
    """Idempotently install the global OTel TracerProvider."""
    global _provider
    if _provider is not None:
        return _provider
    provider = _build_provider(config, aegis_dir)
    otel_trace.set_tracer_provider(provider)
    _provider = provider
    return provider


def reset_tracing_for_tests() -> None:
    """Drop the cached provider so the next bootstrap call rebuilds it.

    Tests only — production code must not call this.
    """
    global _provider
    if _provider is not None:
        _provider.shutdown()
    _provider = None
    # Re-install the SDK no-op default so a stale provider is not held
    # by subsequent ``otel_trace.get_tracer_provider()`` calls.
    otel_trace.set_tracer_provider(TracerProvider())
```

Note: `aegis.obs.langsmith_exporter` and `aegis.obs.langfuse_exporter` don't exist yet. Tasks 5 and 6 create them. The conditional imports above only fire when those config blocks are enabled, so the test suite for Task 4 (which leaves `langfuse.enabled=False` and `langsmith.enabled=False` in the explicit cases) will pass without them. The `_cfg()` helper builds a default config with `langfuse.enabled=True`, but the tests that use `_cfg()` directly (`test_bootstrap_returns_tracer_provider`, `test_bootstrap_is_idempotent`, `test_task_id_processor_stamps_active_var`) will hit the conditional import. We therefore implement Task 5 + 6 BEFORE running these tests — that's the next two tasks. To run Task 4's tests against the bootstrap right now, replace `_cfg()` in the first three tests with a config that disables langfuse: `AegisConfig.model_validate({"project": {"name": "t"}, "observability": {"langfuse": {"enabled": False}}})`.

- [ ] **Step 4: Patch the early test helpers to disable langfuse**

Replace the `_cfg()` helper in `tests/unit/test_obs_otel.py` with:

```python
def _cfg() -> AegisConfig:
    return AegisConfig.model_validate(
        {"project": {"name": "t"}, "observability": {"langfuse": {"enabled": False}}}
    )
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `pytest tests/unit/test_obs_otel.py -v`
Expected: 5 PASS.

- [ ] **Step 6: Commit**

```bash
git add src/aegis/obs/otel.py tests/unit/test_obs_otel.py
git commit -m "feat(obs): OTel bootstrap with TaskIdSpanProcessor"
```

---

## Task 5: LangSmith setup

LangSmith doesn't ride on our OTel pipeline; it has its own callback handler that LangGraph picks up automatically when `LANGCHAIN_TRACING_V2=true` and `LANGSMITH_API_KEY` are set in the environment **before** the graph is constructed. This module's job is only to set those env vars and validate the API key.

**Files:**

- Create: `src/aegis/obs/langsmith_exporter.py`
- Test: `tests/unit/test_obs_langsmith_exporter.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/unit/test_obs_langsmith_exporter.py`:

```python
from __future__ import annotations

import os

import pytest

from aegis.core.config import LangSmithConfig
from aegis.obs.langsmith_exporter import (
    LangSmithNotConfiguredError,
    enable_langsmith,
)


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch) -> None:
    for key in ("LANGCHAIN_TRACING_V2", "LANGCHAIN_PROJECT", "LANGSMITH_API_KEY"):
        monkeypatch.delenv(key, raising=False)


def test_raises_when_api_key_missing(monkeypatch) -> None:
    cfg = LangSmithConfig(enabled=True, project="aegis-test")
    with pytest.raises(LangSmithNotConfiguredError):
        enable_langsmith(cfg)


def test_sets_env_vars_when_api_key_present(monkeypatch) -> None:
    monkeypatch.setenv("LANGSMITH_API_KEY", "ls_xxx")
    cfg = LangSmithConfig(enabled=True, project="aegis-test")
    enable_langsmith(cfg)
    assert os.environ["LANGCHAIN_TRACING_V2"] == "true"
    assert os.environ["LANGCHAIN_PROJECT"] == "aegis-test"


def test_no_project_falls_back_to_default(monkeypatch) -> None:
    monkeypatch.setenv("LANGSMITH_API_KEY", "ls_xxx")
    cfg = LangSmithConfig(enabled=True, project=None)
    enable_langsmith(cfg)
    assert os.environ["LANGCHAIN_PROJECT"] == "aegis"
```

- [ ] **Step 2: Run the tests to confirm they fail**

Run: `pytest tests/unit/test_obs_langsmith_exporter.py -v`
Expected: 3 FAILED with `ModuleNotFoundError: No module named 'aegis.obs.langsmith_exporter'`.

- [ ] **Step 3: Implement the setup module**

Create `src/aegis/obs/langsmith_exporter.py`:

```python
"""LangSmith bootstrap.

LangSmith auto-instruments LangGraph via a callback handler that ships
with the ``langsmith`` package. We don't have to wire it into the OTel
pipeline; we only have to set the env vars LangChain looks for, **before**
``StateGraph.compile()`` runs. That happens in :mod:`aegis.graph.runtime`
right after :func:`bootstrap_tracing`.

If the user enables LangSmith in config but no API key is present in the
environment, we raise :class:`LangSmithNotConfiguredError` — this is loud
on purpose. A silent fallback would let interview/demo runs report
"LangSmith enabled" while emitting nothing.
"""

from __future__ import annotations

import os

from aegis.core.config import LangSmithConfig

__all__ = ["LangSmithNotConfiguredError", "enable_langsmith"]


class LangSmithNotConfiguredError(RuntimeError):
    """Raised when langsmith.enabled=true but no LANGSMITH_API_KEY is set."""


def enable_langsmith(config: LangSmithConfig) -> None:
    if not os.environ.get("LANGSMITH_API_KEY"):
        raise LangSmithNotConfiguredError(
            "observability.langsmith.enabled=true but LANGSMITH_API_KEY is not "
            "in the environment. Set it or set langsmith.enabled=false."
        )
    os.environ["LANGCHAIN_TRACING_V2"] = "true"
    os.environ["LANGCHAIN_PROJECT"] = config.project or "aegis"
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `pytest tests/unit/test_obs_langsmith_exporter.py -v`
Expected: 3 PASS.

- [ ] **Step 5: Commit**

```bash
git add src/aegis/obs/langsmith_exporter.py tests/unit/test_obs_langsmith_exporter.py
git commit -m "feat(obs): LangSmith env-var bootstrap"
```

---

## Task 6: Langfuse OTLP exporter

Langfuse has an OTLP/HTTP ingestion endpoint at `/api/public/otel/v1/traces`. Auth is HTTP Basic with `LANGFUSE_PUBLIC_KEY:LANGFUSE_SECRET_KEY`. We build an `OTLPSpanExporter` configured with that endpoint and Authorization header. If credentials are missing we **skip** the exporter (return `None`) and emit a warning, rather than raising — Langfuse is opt-in by URL but we don't want a missing key to take down the runtime.

**Files:**

- Create: `src/aegis/obs/langfuse_exporter.py`
- Test: `tests/unit/test_obs_langfuse_exporter.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/unit/test_obs_langfuse_exporter.py`:

```python
from __future__ import annotations

import base64

import pytest

from aegis.core.config import LangfuseConfig
from aegis.obs.langfuse_exporter import build_langfuse_exporter


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch) -> None:
    for key in ("LANGFUSE_PUBLIC_KEY", "LANGFUSE_SECRET_KEY"):
        monkeypatch.delenv(key, raising=False)


def test_returns_none_when_keys_missing(monkeypatch) -> None:
    cfg = LangfuseConfig(enabled=True, url="http://localhost:3000")
    assert build_langfuse_exporter(cfg) is None


def test_builds_otlp_exporter_with_basic_auth(monkeypatch) -> None:
    monkeypatch.setenv("LANGFUSE_PUBLIC_KEY", "pk_test")
    monkeypatch.setenv("LANGFUSE_SECRET_KEY", "sk_test")
    cfg = LangfuseConfig(enabled=True, url="http://langfuse.local:3000")
    exporter = build_langfuse_exporter(cfg)
    assert exporter is not None
    expected_token = base64.b64encode(b"pk_test:sk_test").decode("ascii")
    # OTLPSpanExporter stores headers on its session
    assert exporter._session.headers["Authorization"] == f"Basic {expected_token}"
    assert exporter._endpoint == "http://langfuse.local:3000/api/public/otel/v1/traces"


def test_strips_trailing_slash_from_url(monkeypatch) -> None:
    monkeypatch.setenv("LANGFUSE_PUBLIC_KEY", "pk_test")
    monkeypatch.setenv("LANGFUSE_SECRET_KEY", "sk_test")
    cfg = LangfuseConfig(enabled=True, url="http://localhost:3000/")
    exporter = build_langfuse_exporter(cfg)
    assert exporter is not None
    assert exporter._endpoint == "http://localhost:3000/api/public/otel/v1/traces"
```

- [ ] **Step 2: Run the tests to confirm they fail**

Run: `pytest tests/unit/test_obs_langfuse_exporter.py -v`
Expected: 3 FAILED with `ModuleNotFoundError: No module named 'aegis.obs.langfuse_exporter'`.

- [ ] **Step 3: Implement the exporter factory**

Create `src/aegis/obs/langfuse_exporter.py`:

```python
"""Langfuse OTLP/HTTP exporter factory.

Langfuse exposes an OTLP HTTP collector at
``<url>/api/public/otel/v1/traces`` with Basic-auth using
``LANGFUSE_PUBLIC_KEY`` and ``LANGFUSE_SECRET_KEY``. We build a stock
:class:`OTLPSpanExporter` pointed at that endpoint; if the keys are
absent we return ``None`` and let the caller skip wiring this exporter.
"""

from __future__ import annotations

import base64
import logging
import os

from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter

from aegis.core.config import LangfuseConfig

__all__ = ["build_langfuse_exporter"]

_log = logging.getLogger(__name__)


def build_langfuse_exporter(config: LangfuseConfig) -> OTLPSpanExporter | None:
    public = os.environ.get("LANGFUSE_PUBLIC_KEY")
    secret = os.environ.get("LANGFUSE_SECRET_KEY")
    if not public or not secret:
        _log.warning(
            "observability.langfuse.enabled=true but LANGFUSE_PUBLIC_KEY/"
            "LANGFUSE_SECRET_KEY not set; skipping Langfuse exporter."
        )
        return None
    token = base64.b64encode(f"{public}:{secret}".encode()).decode("ascii")
    base = config.url.rstrip("/")
    endpoint = f"{base}/api/public/otel/v1/traces"
    return OTLPSpanExporter(endpoint=endpoint, headers={"Authorization": f"Basic {token}"})
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `pytest tests/unit/test_obs_langfuse_exporter.py -v`
Expected: 3 PASS.

- [ ] **Step 5: Re-run the OTel bootstrap tests with default config**

The `_cfg()` helper in `tests/unit/test_obs_otel.py` was patched in Task 4 Step 4 to disable langfuse. Now that the langfuse module exists, optionally restore `_cfg()` to the simple form:

```python
def _cfg() -> AegisConfig:
    return AegisConfig(project=ProjectConfig(name="t"))
```

Add `from aegis.core.config import ProjectConfig` to the test imports if needed. Then ensure `LANGFUSE_PUBLIC_KEY`/`LANGFUSE_SECRET_KEY` are not set in the environment — `build_langfuse_exporter` returns `None` and the bootstrap proceeds. Run: `pytest tests/unit/test_obs_otel.py -v`. Expected: 5 PASS.

- [ ] **Step 6: Commit**

```bash
git add src/aegis/obs/langfuse_exporter.py tests/unit/test_obs_langfuse_exporter.py tests/unit/test_obs_otel.py
git commit -m "feat(obs): Langfuse OTLP/HTTP exporter factory"
```

---

## Task 7: Public `aegis.obs` surface

Re-export the bootstrap entry points so callers can write `from aegis.obs import bootstrap_tracing, aegis_task_id_var, traced_node` (the last symbol comes in Task 8 — we add a forward reference here).

**Files:**

- Modify: `src/aegis/obs/__init__.py`

- [ ] **Step 1: Replace the placeholder docstring with the public re-exports**

Replace the entire contents of `src/aegis/obs/__init__.py` with:

```python
"""OpenTelemetry bootstrap and exporters for Aegis."""

from __future__ import annotations

from aegis.obs.otel import aegis_task_id_var, bootstrap_tracing

__all__ = ["aegis_task_id_var", "bootstrap_tracing"]
```

We extend `__all__` in Task 8 once `traced_node` exists.

- [ ] **Step 2: Smoke-import**

Run: `python -c "from aegis.obs import bootstrap_tracing, aegis_task_id_var; print('ok')"`
Expected: `ok`.

- [ ] **Step 3: Commit**

```bash
git add src/aegis/obs/__init__.py
git commit -m "feat(obs): expose bootstrap_tracing and aegis_task_id_var"
```

---

## Task 8: `traced_node` decorator

Wraps an async LangGraph node function with a child span named after the node. Sets `aegis.role`, `aegis.node`, `aegis.task_id` (the last via the contextvar that's already stamped by `TaskIdSpanProcessor`, but we set it explicitly here too for callers who don't use the processor — defense in depth). On node return, records the signal verdict (`pm.summary`, `qa.verdict`, etc.) by inspecting the returned state delta. On exception, marks the span as ERROR and re-raises.

**Files:**

- Create: `src/aegis/obs/instrumentation.py`
- Test: `tests/unit/test_obs_instrumentation.py`
- Modify: `src/aegis/obs/__init__.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/unit/test_obs_instrumentation.py`:

```python
from __future__ import annotations

from pathlib import Path

import pytest
from opentelemetry import trace as otel_trace

from aegis.core.config import AegisConfig, ProjectConfig
from aegis.obs import aegis_task_id_var, bootstrap_tracing
from aegis.obs.instrumentation import traced_node
from aegis.obs.otel import reset_tracing_for_tests


@pytest.fixture(autouse=True)
def _setup(tmp_path: Path):
    reset_tracing_for_tests()
    cfg = AegisConfig.model_validate(
        {"project": {"name": "t"}, "observability": {"langfuse": {"enabled": False}}}
    )
    bootstrap_tracing(cfg, tmp_path)
    yield tmp_path
    reset_tracing_for_tests()


@pytest.mark.asyncio
async def test_traced_node_emits_span_with_role(_setup: Path) -> None:
    @traced_node("dev")
    async def fake_dev(state):
        return {"implementation_status": "done", "current_node": "dev"}

    token = aegis_task_id_var.set("042")
    try:
        delta = await fake_dev({"task_id": "042"})
    finally:
        aegis_task_id_var.reset(token)
    assert delta == {"implementation_status": "done", "current_node": "dev"}
    otel_trace.get_tracer_provider().force_flush()
    out = (_setup / "trace" / "042.jsonl").read_text(encoding="utf-8")
    assert '"name": "dev_node"' in out
    assert '"aegis.role": "dev"' in out


@pytest.mark.asyncio
async def test_traced_node_records_verdict_when_present(_setup: Path) -> None:
    @traced_node("qa")
    async def fake_qa(state):
        return {"test_report": {"verdict": "pass", "summary": "all green"}}

    token = aegis_task_id_var.set("050")
    try:
        await fake_qa({"task_id": "050"})
    finally:
        aegis_task_id_var.reset(token)
    otel_trace.get_tracer_provider().force_flush()
    out = (_setup / "trace" / "050.jsonl").read_text(encoding="utf-8")
    assert '"aegis.verdict": "pass"' in out


@pytest.mark.asyncio
async def test_traced_node_records_blocker(_setup: Path) -> None:
    @traced_node("dev")
    async def fake_dev(state):
        return {"blocked_reason": "no signal"}

    token = aegis_task_id_var.set("060")
    try:
        await fake_dev({"task_id": "060"})
    finally:
        aegis_task_id_var.reset(token)
    otel_trace.get_tracer_provider().force_flush()
    out = (_setup / "trace" / "060.jsonl").read_text(encoding="utf-8")
    assert '"aegis.blocked_reason": "no signal"' in out


@pytest.mark.asyncio
async def test_traced_node_records_exception(_setup: Path) -> None:
    @traced_node("pm")
    async def boom(state):
        raise RuntimeError("oops")

    token = aegis_task_id_var.set("070")
    try:
        with pytest.raises(RuntimeError, match="oops"):
            await boom({"task_id": "070"})
    finally:
        aegis_task_id_var.reset(token)
    otel_trace.get_tracer_provider().force_flush()
    out = (_setup / "trace" / "070.jsonl").read_text(encoding="utf-8")
    assert '"code": "ERROR"' in out
```

The tests use `pytest-asyncio`. Ensure it's available. If not already in the dev deps, add it in this task (add `"pytest-asyncio>=0.23"` to `pyproject.toml` `[project.optional-dependencies].dev` and add `asyncio_mode = "auto"` under `[tool.pytest.ini_options]`). If it is already installed transitively, skip this paragraph.

Verify by running: `python -c "import pytest_asyncio; print(pytest_asyncio.__version__)"`. If it errors, edit `pyproject.toml` accordingly and re-run `pip install -e .[dev]`.

- [ ] **Step 2: Run the tests to confirm they fail**

Run: `pytest tests/unit/test_obs_instrumentation.py -v`
Expected: 4 FAILED with `ModuleNotFoundError: No module named 'aegis.obs.instrumentation'`.

- [ ] **Step 3: Implement the decorator**

Create `src/aegis/obs/instrumentation.py`:

```python
"""``traced_node`` — wrap a LangGraph node fn with an OTel child span."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from functools import wraps
from typing import Any

from opentelemetry import trace as otel_trace
from opentelemetry.trace import Status, StatusCode

__all__ = ["traced_node"]

NodeFn = Callable[..., Awaitable[dict[str, Any]]]

_TRACER_NAME = "aegis.graph"


def _record_delta(span: Any, delta: dict[str, Any]) -> None:
    if not isinstance(delta, dict):
        return
    if "blocked_reason" in delta and delta["blocked_reason"]:
        span.set_attribute("aegis.blocked_reason", str(delta["blocked_reason"]))
    review = delta.get("review") or {}
    test_report = delta.get("test_report") or {}
    if review.get("verdict"):
        span.set_attribute("aegis.verdict", str(review["verdict"]))
    elif test_report.get("verdict"):
        span.set_attribute("aegis.verdict", str(test_report["verdict"]))
    if "implementation_status" in delta:
        span.set_attribute("aegis.implementation_status", str(delta["implementation_status"]))


def traced_node(role: str) -> Callable[[NodeFn], NodeFn]:
    """Return a decorator that wraps an async node fn with a child span.

    The span is named ``<role>_node`` and tagged with ``aegis.role``.
    The decorated function is otherwise transparent — its kwargs and
    return value pass through unchanged.
    """
    span_name = f"{role}_node"

    def decorate(fn: NodeFn) -> NodeFn:
        @wraps(fn)
        async def wrapper(state: dict[str, Any], **kwargs: Any) -> dict[str, Any]:
            tracer = otel_trace.get_tracer(_TRACER_NAME)
            with tracer.start_as_current_span(span_name) as span:
                span.set_attribute("aegis.role", role)
                if isinstance(state, dict) and state.get("task_id"):
                    span.set_attribute("aegis.task_id", str(state["task_id"]))
                try:
                    delta = await fn(state, **kwargs)
                except Exception as exc:
                    span.record_exception(exc)
                    span.set_status(Status(StatusCode.ERROR, str(exc)))
                    raise
                _record_delta(span, delta)
                return delta

        return wrapper

    return decorate
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `pytest tests/unit/test_obs_instrumentation.py -v`
Expected: 4 PASS.

- [ ] **Step 5: Re-export `traced_node` from `aegis.obs`**

Edit `src/aegis/obs/__init__.py` to:

```python
"""OpenTelemetry bootstrap and exporters for Aegis."""

from __future__ import annotations

from aegis.obs.instrumentation import traced_node
from aegis.obs.otel import aegis_task_id_var, bootstrap_tracing

__all__ = ["aegis_task_id_var", "bootstrap_tracing", "traced_node"]
```

- [ ] **Step 6: Commit**

```bash
git add src/aegis/obs/__init__.py src/aegis/obs/instrumentation.py tests/unit/test_obs_instrumentation.py
git commit -m "feat(obs): traced_node decorator for graph nodes"
```

---

## Task 9: Wire bootstrap + tracing into the runtime

The runtime is the only place that knows the active task id, the `AegisConfig`, and the `aegis_dir`. It calls `bootstrap_tracing` once, sets the contextvar around the graph invocation, opens a root span, and writes the OTel `trace_id` back to the task frontmatter (so `aegis trace <id>` can resolve a URL).

**Files:**

- Modify: `src/aegis/graph/runtime.py`
- Test: `tests/unit/test_graph_runtime.py` (extend)

- [ ] **Step 1: Write a failing runtime test**

Append to `tests/unit/test_graph_runtime.py`:

```python
from aegis.obs.otel import reset_tracing_for_tests


def test_run_one_task_writes_trace_id_to_frontmatter(tmp_repo, monkeypatch):
    """After a graph run, the task's frontmatter has a non-null trace_id."""
    reset_tracing_for_tests()
    # tmp_repo is the existing fixture from this file; it provides a
    # task in `backlog/`, an aegis_dir, and a stub graph that drives
    # the task to completion. See the existing tests in this file for
    # the fixture shape — replicate its setup here.
    aegis_dir, repo_root, task_path, config, node_overrides = tmp_repo
    from aegis.graph.runtime import run_one_task

    run_one_task(
        task_path=task_path,
        aegis_dir=aegis_dir,
        repo_root=repo_root,
        config=config,
        node_overrides=node_overrides,
    )
    from aegis.core.task import parse_task

    # Find the task wherever it's been moved to.
    moved = next((aegis_dir).rglob(f"{task_path.stem.split('-', 1)[0]}-*.md"))
    task = parse_task(moved)
    assert task.frontmatter.trace_id is not None
    assert len(task.frontmatter.trace_id) == 32  # 128-bit OTel id, hex
    reset_tracing_for_tests()
```

> If the existing `test_graph_runtime.py` already provides a fixture similar to `tmp_repo`, reuse it verbatim; otherwise inline a minimal one mirroring the patterns in `tests/unit/test_graph_runtime.py`. Read the file first and adapt — the assertion about `trace_id` is the only new behavior.

- [ ] **Step 2: Run the new test to confirm it fails**

Run: `pytest tests/unit/test_graph_runtime.py::test_run_one_task_writes_trace_id_to_frontmatter -v`
Expected: FAIL — `task.frontmatter.trace_id` is still `None`.

- [ ] **Step 3: Patch `aegis/graph/runtime.py`**

At the top of the module, alongside the existing imports, add:

```python
from opentelemetry import trace as otel_trace

from aegis.obs import aegis_task_id_var, bootstrap_tracing
```

Modify `_run_one_task_async` to bootstrap tracing, scope the contextvar, open a root span, and persist `trace_id`. Replace the existing function body:

```python
async def _run_one_task_async(
    *,
    task_path: Path,
    aegis_dir: Path,
    repo_root: Path,
    config: AegisConfig,
    node_overrides: dict[str, Any] | None,
) -> TeamState:
    bootstrap_tracing(config, aegis_dir)

    task = parse_task(task_path)
    if task.frontmatter.status == TaskStatus.BACKLOG:
        task_path = transition(task_path, aegis_dir, TaskStatus.IN_PROGRESS)
        task = parse_task(task_path)

    worktree_path, branch = _worktree_paths(aegis_dir, task)
    if not worktree_path.exists():
        create_worktree(repo_root, worktree_path, branch)

    state = initial_state(
        task=task,
        task_path=task_path,
        worktree_path=worktree_path,
        target_repo_root=repo_root,
    )
    state["pr_branch"] = branch
    task.frontmatter.worktree = str(worktree_path)
    task.frontmatter.pr_branch = branch
    write_task(task, task_path)

    cfg = {"configurable": {"thread_id": task.frontmatter.id}}
    token = aegis_task_id_var.set(task.frontmatter.id)
    try:
        tracer = otel_trace.get_tracer("aegis.runtime")
        with tracer.start_as_current_span("aegis.task") as root_span:
            root_span.set_attribute("aegis.task_id", task.frontmatter.id)
            root_span.set_attribute("aegis.task_title", task.frontmatter.title)
            trace_id_hex = format(root_span.get_span_context().trace_id, "032x")
            state["trace_id"] = trace_id_hex
            task.frontmatter.trace_id = trace_id_hex
            write_task(task, task_path)

            async with open_async_checkpointer(aegis_dir) as saver:
                graph = build_graph(node_overrides=node_overrides, checkpointer=saver)
                final = await graph.ainvoke(state, config=cfg)
    finally:
        aegis_task_id_var.reset(token)

    review = final.get("review") or {}
    if final.get("blocked_reason"):
        _record_blocked_reason(task_path, final["blocked_reason"])
        transition(task_path, aegis_dir, TaskStatus.BLOCKED)
    elif review.get("verdict") == "approve" and final.get("current_node") != "docs":
        final["awaiting_human"] = True
        transition(task_path, aegis_dir, TaskStatus.REVIEW)
    else:
        try:
            merge_worktree_into_main(repo_root, branch)
            transition(task_path, aegis_dir, TaskStatus.DONE)
            remove_worktree(repo_root, worktree_path)
        except Exception as exc:
            _record_blocked_reason(task_path, f"merge failed: {exc}")
            transition(task_path, aegis_dir, TaskStatus.BLOCKED)
    return cast(TeamState, final)
```

Apply the same pattern to `_resume_after_approve_async`: call `bootstrap_tracing`, set the contextvar, open a root span named `aegis.task.resume` keyed by the existing `task_id`, but don't overwrite the frontmatter's `trace_id` (resume reuses the original).

```python
async def _resume_after_approve_async(
    *,
    task_id: str,
    aegis_dir: Path,
    repo_root: Path,
    config: AegisConfig,
    node_overrides: dict[str, Any] | None,
) -> TeamState:
    bootstrap_tracing(config, aegis_dir)

    found = find_task(aegis_dir, task_id)
    if found is None:
        raise FileNotFoundError(f"task {task_id} not found")
    task, task_path = found
    if task.frontmatter.status != TaskStatus.REVIEW:
        raise ValueError(f"task {task_id} is in {task.frontmatter.status.value}, not review")

    worktree_path, branch = _worktree_paths(aegis_dir, task)
    cfg = {"configurable": {"thread_id": task_id}}
    token = aegis_task_id_var.set(task_id)
    try:
        tracer = otel_trace.get_tracer("aegis.runtime")
        with tracer.start_as_current_span("aegis.task.resume") as root_span:
            root_span.set_attribute("aegis.task_id", task_id)
            async with open_async_checkpointer(aegis_dir) as saver:
                graph = build_graph(node_overrides=node_overrides, checkpointer=saver)
                final = await graph.ainvoke(None, config=cfg)
    finally:
        aegis_task_id_var.reset(token)

    if final.get("blocked_reason"):
        _record_blocked_reason(task_path, final["blocked_reason"])
        transition(task_path, aegis_dir, TaskStatus.BLOCKED)
        return cast(TeamState, final)
    merge_worktree_into_main(repo_root, branch)
    transition(task_path, aegis_dir, TaskStatus.DONE)
    if worktree_path.exists():
        remove_worktree(repo_root, worktree_path)
    return cast(TeamState, final)
```

- [ ] **Step 4: Run the runtime tests to verify they pass**

Run: `pytest tests/unit/test_graph_runtime.py -v`
Expected: all PASS, including the new trace_id test.

- [ ] **Step 5: Commit**

```bash
git add src/aegis/graph/runtime.py tests/unit/test_graph_runtime.py
git commit -m "feat(obs): runtime bootstraps OTel and persists trace_id"
```

---

## Task 10: Wire `traced_node` into `team_graph`

Each role node currently passes through unwrapped. Wrap them at graph-build time so production runs emit one child span per node. Test stubs (passed via `node_overrides`) must remain wrappable too.

**Files:**

- Modify: `src/aegis/graph/team_graph.py`
- Test: `tests/unit/test_graph_team_graph.py` (extend)

- [ ] **Step 1: Write a failing test**

Append to `tests/unit/test_graph_team_graph.py`:

```python
from pathlib import Path

from opentelemetry import trace as otel_trace

from aegis.core.config import AegisConfig
from aegis.obs import aegis_task_id_var, bootstrap_tracing
from aegis.obs.otel import reset_tracing_for_tests


async def _stub_pm(state):
    return {"plan": {"summary": "x"}, "current_node": "pm"}


async def _stub_dev(state):
    return {"implementation_status": "done", "current_node": "dev"}


async def _stub_qa(state):
    return {"test_report": {"verdict": "pass"}, "current_node": "qa"}


async def _stub_reviewer(state):
    return {"review": {"verdict": "approve"}, "current_node": "reviewer"}


async def _stub_docs(state):
    return {"current_node": "docs"}


@pytest.mark.asyncio
async def test_each_node_emits_a_traced_span(tmp_path: Path):
    reset_tracing_for_tests()
    cfg = AegisConfig.model_validate(
        {"project": {"name": "t"}, "observability": {"langfuse": {"enabled": False}}}
    )
    bootstrap_tracing(cfg, tmp_path)

    from aegis.graph.team_graph import build_graph
    from aegis.graph.state import TeamState

    overrides = {
        "pm": _stub_pm, "dev": _stub_dev, "qa": _stub_qa,
        "reviewer": _stub_reviewer, "docs": _stub_docs,
    }
    graph = build_graph(node_overrides=overrides)
    state: TeamState = {
        "task_id": "t1", "task_path": "x", "worktree_path": ".",
        "target_repo_root": ".", "plan": None, "implementation_status": "pending",
        "test_report": None, "review": None, "pr_branch": None,
        "budget_remaining": {"usd": 1.0, "seconds": 60.0, "input_tokens": 0.0, "output_tokens": 0.0},
        "retry_counts": {}, "trace_id": "", "awaiting_human": False,
        "blocked_reason": None, "current_node": None, "history": [],
    }
    token = aegis_task_id_var.set("t1")
    try:
        await graph.ainvoke(state)
    finally:
        aegis_task_id_var.reset(token)

    otel_trace.get_tracer_provider().force_flush()
    out = (tmp_path / "trace" / "t1.jsonl").read_text(encoding="utf-8")
    for role in ("pm", "dev", "qa", "reviewer", "docs"):
        assert f'"name": "{role}_node"' in out
    reset_tracing_for_tests()
```

(Add `import pytest` at the top of the file if it's not already imported.)

- [ ] **Step 2: Run the new test to confirm it fails**

Run: `pytest tests/unit/test_graph_team_graph.py::test_each_node_emits_a_traced_span -v`
Expected: FAIL — `t1.jsonl` does not exist (no spans emitted) or contains only the root span.

- [ ] **Step 3: Wrap each node in `build_graph`**

In `src/aegis/graph/team_graph.py`, add the import:

```python
from aegis.obs import traced_node
```

And in `build_graph`, replace the override resolution lines (currently around `pm: Any = overrides.get("pm", pm_node)` …) with:

```python
    pm: Any = traced_node("pm")(overrides.get("pm", pm_node))
    dev: Any = traced_node("dev")(overrides.get("dev", dev_node))
    qa: Any = traced_node("qa")(overrides.get("qa", qa_node))
    reviewer: Any = traced_node("reviewer")(overrides.get("reviewer", reviewer_node))
    docs: Any = traced_node("docs")(overrides.get("docs", docs_node))
```

- [ ] **Step 4: Run the team-graph tests to verify they pass**

Run: `pytest tests/unit/test_graph_team_graph.py -v`
Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add src/aegis/graph/team_graph.py tests/unit/test_graph_team_graph.py
git commit -m "feat(obs): emit per-node child spans in team graph"
```

---

## Task 11: `aegis logs <id> [--follow]`

Tails `.aegis/trace/<id>.jsonl`. Without `--follow`, prints the file and exits. With `--follow`, polls every 250 ms and prints new lines until SIGINT. Each line is rendered as one human-readable summary: `[HH:MM:SS] role_node (Δms) verdict=...`.

**Files:**

- Create: `src/aegis/cli/commands/logs.py`
- Test: `tests/unit/test_cli_logs.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/unit/test_cli_logs.py`:

```python
from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from aegis.cli.commands.init import AEGIS_DIRNAME
from aegis.cli.commands.logs import register
from aegis.cli.main import app


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner(mix_stderr=False)


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
```

- [ ] **Step 2: Run the tests to confirm they fail**

Run: `pytest tests/unit/test_cli_logs.py -v`
Expected: 3 FAILED with `ModuleNotFoundError: No module named 'aegis.cli.commands.logs'` (or unknown command).

- [ ] **Step 3: Implement the command**

Create `src/aegis/cli/commands/logs.py`:

```python
"""``aegis logs <id> [--follow]`` — tail a task's JSONL span log."""

from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import typer

from aegis.cli.commands.init import AEGIS_DIRNAME

__all__ = ["register"]


def _format_line(record: dict[str, Any]) -> str:
    start_ns = int(record.get("start_time_ns") or 0)
    duration_ms = int(record.get("duration_ns") or 0) // 1_000_000
    ts = datetime.fromtimestamp(start_ns / 1e9, tz=timezone.utc).strftime("%H:%M:%S")
    name = record.get("name", "?")
    attrs = record.get("attributes") or {}
    verdict = attrs.get("aegis.verdict")
    blocker = attrs.get("aegis.blocked_reason")
    pieces = [f"[{ts}]", name, f"({duration_ms}ms)"]
    if verdict:
        pieces.append(f"verdict={verdict}")
    if blocker:
        pieces.append(f"blocked={blocker}")
    return " ".join(pieces)


def _print_existing(path: Path) -> int:
    """Print every line in ``path``; return the byte offset reached."""
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue
            typer.echo(_format_line(record))
        return f.tell()


def _follow(path: Path, offset: int) -> None:
    while True:
        try:
            with open(path, encoding="utf-8") as f:
                f.seek(offset)
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        record = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    typer.echo(_format_line(record))
                offset = f.tell()
        except FileNotFoundError:
            pass
        time.sleep(0.25)


def register(app: typer.Typer) -> None:
    @app.command(help="Tail a task's JSONL trace.")
    def logs(
        task_id: str = typer.Argument(...),
        follow: bool = typer.Option(False, "--follow", "-f"),
    ) -> None:
        repo = Path.cwd().resolve()
        aegis = repo / AEGIS_DIRNAME
        if not aegis.exists():
            raise typer.BadParameter(f"No {AEGIS_DIRNAME}/ here.")
        trace_path = aegis / "trace" / f"{task_id}.jsonl"
        if not trace_path.exists():
            typer.echo(f"no trace for task {task_id}", err=True)
            raise typer.Exit(code=1)
        offset = _print_existing(trace_path)
        if follow:
            try:
                _follow(trace_path, offset)
            except KeyboardInterrupt:
                raise typer.Exit(code=0)
```

- [ ] **Step 4: Wire the command into the CLI app**

Edit `src/aegis/cli/main.py` to add (alongside the other `register_*` imports):

```python
from aegis.cli.commands.logs import register as register_logs  # noqa: E402
```

And in the registration block:

```python
register_logs(app)
```

- [ ] **Step 5: Drop the old `logs` stub**

Edit `src/aegis/cli/commands/stubs.py` to remove the `def logs(...)` block. Keep the surrounding code (`_not_implemented`, the `web` stub, the `trace` stub for now) intact.

- [ ] **Step 6: Run the tests to verify they pass**

Run: `pytest tests/unit/test_cli_logs.py tests/unit/test_cli_main.py -v`
Expected: all PASS. The `test_cli_main.py` suite verifies the registered command list — update it if it pins exact names; the registration order has expanded by one.

- [ ] **Step 7: Commit**

```bash
git add src/aegis/cli/commands/logs.py src/aegis/cli/commands/stubs.py src/aegis/cli/main.py tests/unit/test_cli_logs.py
git commit -m "feat(cli): implement aegis logs (tails JSONL trace)"
```

---

## Task 12: `aegis trace <id>`

Opens the user's browser to a task trace URL. Resolves which dashboard to use:

- LangSmith preferred if `observability.langsmith.enabled` is true and `LANGSMITH_API_KEY` is in the environment.
- Otherwise Langfuse if `observability.langfuse.enabled`.
- Otherwise prints a hint that no remote dashboard is configured and points at `aegis logs <id>`.

The URL embeds the trace ID we wrote into the task frontmatter in Task 9.

**Files:**

- Create: `src/aegis/cli/commands/trace.py`
- Test: `tests/unit/test_cli_trace.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/unit/test_cli_trace.py`:

```python
from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from aegis.cli.main import app


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner(mix_stderr=False)


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
```

- [ ] **Step 2: Run the tests to confirm they fail**

Run: `pytest tests/unit/test_cli_trace.py -v`
Expected: 3 FAILED with `ModuleNotFoundError: No module named 'aegis.cli.commands.trace'` (or unknown command).

- [ ] **Step 3: Implement the command**

Create `src/aegis/cli/commands/trace.py`:

```python
"""``aegis trace <id>`` — open a task trace in the configured dashboard."""

from __future__ import annotations

import os
import webbrowser
from pathlib import Path

import typer

from aegis.cli.commands.init import AEGIS_DIRNAME
from aegis.core.config import load_config
from aegis.core.lifecycle import find_task

__all__ = ["register"]


def _resolve_url(config, trace_id: str) -> str | None:
    if config.observability.langsmith.enabled and os.environ.get("LANGSMITH_API_KEY"):
        project = config.observability.langsmith.project or "aegis"
        return f"https://smith.langchain.com/o/-/projects/p/{project}/r/{trace_id}"
    if config.observability.langfuse.enabled:
        base = config.observability.langfuse.url.rstrip("/")
        return f"{base}/trace/{trace_id}"
    return None


def register(app: typer.Typer) -> None:
    @app.command(help="Open a task's trace in the configured dashboard.")
    def trace(task_id: str = typer.Argument(...)) -> None:
        repo = Path.cwd().resolve()
        aegis = repo / AEGIS_DIRNAME
        if not aegis.exists():
            raise typer.BadParameter(f"No {AEGIS_DIRNAME}/ here.")
        config = load_config(aegis / "config.yaml")
        found = find_task(aegis, task_id)
        if found is None:
            raise typer.BadParameter(f"task {task_id} not found")
        task, _ = found
        trace_id = task.frontmatter.trace_id
        if not trace_id:
            typer.echo(f"task {task_id} has no trace_id yet (run it first)", err=True)
            raise typer.Exit(code=1)
        url = _resolve_url(config, trace_id)
        if url is None:
            typer.echo(
                "no remote dashboard configured (langsmith/langfuse both off). "
                f"Use `aegis logs {task_id}` for the local mirror."
            )
            return
        webbrowser.open(url)
        typer.echo(url)
```

- [ ] **Step 4: Wire it into the CLI app**

Edit `src/aegis/cli/main.py`:

```python
from aegis.cli.commands.trace import register as register_trace  # noqa: E402
```

```python
register_trace(app)
```

- [ ] **Step 5: Drop the old `trace` stub**

Edit `src/aegis/cli/commands/stubs.py` to remove the `def trace(...)` block. Keep `web`. The whole file should now contain only the `web` stub (plus `_not_implemented` and `register_stubs`).

- [ ] **Step 6: Run the tests to verify they pass**

Run: `pytest tests/unit/test_cli_trace.py tests/unit/test_cli_main.py -v`
Expected: all PASS.

- [ ] **Step 7: Commit**

```bash
git add src/aegis/cli/commands/trace.py src/aegis/cli/commands/stubs.py src/aegis/cli/main.py tests/unit/test_cli_trace.py
git commit -m "feat(cli): implement aegis trace (open trace in dashboard)"
```

---

## Task 13: Self-host Langfuse via `docker-compose.yml`

Ship a `docker-compose.yml` so `make langfuse` brings up a local Langfuse stack on `localhost:3000`. This is dev-only — Aegis runs fine without it because of the JSONL mirror.

**Files:**

- Create: `docker-compose.yml`
- Modify: `Makefile`

- [ ] **Step 1: Write `docker-compose.yml`**

Create `docker-compose.yml`:

```yaml
version: "3.9"
services:
  langfuse-postgres:
    image: postgres:16-alpine
    restart: unless-stopped
    environment:
      POSTGRES_USER: langfuse
      POSTGRES_PASSWORD: langfuse
      POSTGRES_DB: langfuse
    volumes:
      - langfuse-pg:/var/lib/postgresql/data

  langfuse-redis:
    image: redis:7-alpine
    restart: unless-stopped

  langfuse:
    image: langfuse/langfuse:latest
    restart: unless-stopped
    depends_on: [langfuse-postgres, langfuse-redis]
    ports:
      - "3000:3000"
    environment:
      DATABASE_URL: postgresql://langfuse:langfuse@langfuse-postgres:5432/langfuse
      REDIS_HOST: langfuse-redis
      NEXTAUTH_SECRET: local-dev-secret-change-me
      NEXTAUTH_URL: http://localhost:3000
      SALT: local-dev-salt-change-me
      TELEMETRY_ENABLED: "false"

volumes:
  langfuse-pg:
```

- [ ] **Step 2: Add Makefile targets**

Append to `Makefile`:

```make
.PHONY: langfuse langfuse-down

langfuse:
	docker compose up -d

langfuse-down:
	docker compose down
```

- [ ] **Step 3: Verify the compose file parses**

Run: `docker compose config --quiet`
Expected: exits 0 silently. (If `docker` is not installed in this environment, skip the verification — the test plan does not depend on a running container; the file just has to be syntactically valid.)

- [ ] **Step 4: Commit**

```bash
git add docker-compose.yml Makefile
git commit -m "build: docker-compose stack for self-hosted Langfuse"
```

---

## Task 14: README observability section

A short section explaining: JSONL is on by default; LangSmith opt-in via env; Langfuse opt-in via `make langfuse` + env keys; `aegis logs` and `aegis trace` are the entry points.

**Files:**

- Modify: `README.md`

- [ ] **Step 1: Read the current README**

Run: `wc -l README.md` and read it. Find a sensible insertion point (typically after the CLI commands section).

- [ ] **Step 2: Insert the observability section**

Insert (preserving the surrounding markdown):

```markdown
## Observability

Aegis emits OpenTelemetry spans for every role-node invocation. Three
sinks are available:

- **JSONL local mirror** (always on by default). One file per task at
  `.aegis/trace/<task_id>.jsonl`. View with `aegis logs <id> [--follow]`.
- **Langfuse** (self-hosted). Enable `observability.langfuse.enabled`
  in `.aegis/config.yaml`, run `make langfuse` to start the stack on
  `localhost:3000`, then set `LANGFUSE_PUBLIC_KEY` and
  `LANGFUSE_SECRET_KEY` in your environment.
- **LangSmith** (SaaS). Enable `observability.langsmith.enabled` and set
  `LANGSMITH_API_KEY`. LangGraph's built-in callback handler handles the
  rest.

Open a remote trace with `aegis trace <id>` — Aegis prefers LangSmith
when both are configured, and falls back to a hint about `aegis logs`
when neither is.
```

- [ ] **Step 3: Commit**

```bash
git add README.md
git commit -m "docs: observability section in README"
```

---

## Task 15: Update `docs/status.json` and tag `phase-5-complete`

**Files:**

- Modify: `docs/status.json`

- [ ] **Step 1: Verify the full unit suite is green**

Run: `pytest tests/unit -q`
Expected: all PASS — no regressions from Phases 1–4 and all Phase 5 tests pass.

- [ ] **Step 2: Patch `docs/status.json`**

In `docs/status.json`, locate the Phase 5 entry (`"id": 5`) and change:

```json
      "status": "not_started",
```

to:

```json
      "status": "complete",
      "tag": "phase-5-complete",
      "deliverables": [
        "obs/jsonl_exporter.py — JSONL span exporter",
        "obs/otel.py — TracerProvider bootstrap + TaskIdSpanProcessor",
        "obs/langsmith_exporter.py — LangSmith env-var bootstrap",
        "obs/langfuse_exporter.py — Langfuse OTLP/HTTP exporter factory",
        "obs/instrumentation.py — traced_node decorator",
        "graph/runtime.py — root span + trace_id persistence",
        "graph/team_graph.py — per-node child spans",
        "CLI: logs, trace",
        "docker-compose.yml — Langfuse self-host stack"
      ],
```

(Adjust the surrounding JSON shape to match other completed phases — match field order with phases 1-4. Drop the `cli_stubs_for_phase_5` array since the stubs are gone.)

In the `snapshot.tags` array, append `"phase-5-complete"`. Update `as_of_date` to `2026-05-01` (or the actual completion date) and `head_subject` after the final commit.

In the `not_implemented` CLI list, remove the `logs` and `trace` entries (keep `web`).

In the `next_phase` block, replace with:

```json
  "next_phase": {
    "phase": 6,
    "scope": "Read-only web dashboard (kanban + task view + approval endpoints), wire `aegis web`",
    "after_that": null
  }
```

- [ ] **Step 3: Commit**

```bash
git add docs/status.json
git commit -m "docs(status): mark phase 5 complete"
```

- [ ] **Step 4: Tag the phase**

Run:

```bash
git tag phase-5-complete
git tag -l | grep phase-5-complete
```

Expected: `phase-5-complete` appears in the output. Do **not** push the tag — that's the user's call.

---

## Self-review checklist

After completing every task:

1. **Spec coverage (§12 of the spec):**
   - §12.1 OTel abstraction → Task 4 (`bootstrap_tracing` + `TaskIdSpanProcessor`) + Task 8 (`traced_node`) + Task 10 (per-node spans).
   - §12.2 LangSmith exporter → Task 5.
   - §12.3 Langfuse exporter → Task 6 + Task 13 (compose stack).
   - §12.4 Local JSONL mirror → Task 3 + Task 9 (per-task routing).
   - "Every Claude Agent SDK tool call is a child span" — *partially* met: spans wrap the agent invocation at the node level, not individual SDK tool calls. Per-tool-call spans require either an SDK callback hook (not currently exposed) or per-MCP-subprocess instrumentation with W3C context propagation across stdio. Documented as out-of-scope; revisit when the SDK exposes hooks.
   - Cost capture per span (§12.1 last bullet) — **not** implemented in this phase. Aegis doesn't yet thread `usage` data through the message stream into `state`. Add a separate task in Phase 6 once the dashboard surfaces it.
2. **CLI coverage (§7.4):** `aegis logs <id> [--follow]` → Task 11; `aegis trace <id>` → Task 12. Both stubs removed.
3. **Frontmatter `trace_id` (spec §6.3):** populated in Task 9.
4. **Idempotency:** `bootstrap_tracing` returns the same provider on repeated calls — verified in Task 4 step 1.
5. **No placeholders:** every code block above is self-contained.
6. **Type/name consistency:** `aegis_task_id_var` (Task 4) matches use in Task 8 + Task 9 + Task 10. `traced_node(role)` (Task 8) consumed by Task 10 with the same signature. `JSONLSpanExporter(trace_dir=)` (Task 3) consumed by Task 4 with the same kw. `build_langfuse_exporter(config)` (Task 6) consumed by `aegis.obs.otel._build_provider` with the same signature.
7. **Cost-of-failure note (deferred items):**
   - Cost-per-span (above) — write up as a Phase 6 task.
   - Per-MCP-tool child spans (above) — same.
   - Trace context propagation across stdio to MCP subprocesses — same.
