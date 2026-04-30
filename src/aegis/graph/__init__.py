"""Aegis LangGraph team graph and runtime entry points.

``build_graph`` is exposed lazily via ``__getattr__`` to avoid a circular
import: the ``aegis.agents`` tools layer pulls in ``aegis.graph.signals``
during package init, which would otherwise re-enter this module before
``aegis.graph.team_graph`` (and its node imports back into
``aegis.agents``) finished loading.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from aegis.graph.state import TeamState, initial_state

if TYPE_CHECKING:  # pragma: no cover - type-checkers only
    from aegis.graph.team_graph import build_graph

__all__ = ["TeamState", "initial_state", "build_graph"]


def __getattr__(name: str) -> Any:
    if name == "build_graph":
        from aegis.graph.team_graph import build_graph

        return build_graph
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
