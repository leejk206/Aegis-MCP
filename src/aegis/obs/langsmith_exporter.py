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
