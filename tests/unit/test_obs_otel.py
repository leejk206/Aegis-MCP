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
    return AegisConfig.model_validate(
        {"project": {"name": "t"}, "observability": {"langfuse": {"enabled": False}}}
    )


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
