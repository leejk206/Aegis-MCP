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
