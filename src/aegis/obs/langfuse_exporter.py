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
