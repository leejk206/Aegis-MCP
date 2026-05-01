"""OpenTelemetry bootstrap and exporters for Aegis."""

from __future__ import annotations

from aegis.obs.instrumentation import traced_node
from aegis.obs.otel import aegis_task_id_var, bootstrap_tracing

__all__ = ["aegis_task_id_var", "bootstrap_tracing", "traced_node"]
