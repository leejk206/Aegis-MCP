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
    # The OTel SDK guards set_tracer_provider with a Once flag so it can only
    # fire once per process. For test isolation we must bypass that guard and
    # reset the module-level globals directly.
    from opentelemetry.util._once import Once

    otel_trace._TRACER_PROVIDER_SET_ONCE = Once()  # type: ignore[attr-defined]
    otel_trace._TRACER_PROVIDER = None  # type: ignore[attr-defined]
