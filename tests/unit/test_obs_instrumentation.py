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
