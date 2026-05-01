"""Build the LangGraph ``StateGraph`` for the Aegis team.

Topology mirrors spec §5.2. Nodes can be overridden for tests via the
``node_overrides`` argument; in production they default to the real
nodes from :mod:`aegis.graph.nodes`.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from langgraph.graph import END, START, StateGraph

from aegis.graph.nodes import dev_node, docs_node, pm_node, qa_node, reviewer_node
from aegis.graph.state import TeamState
from aegis.obs import traced_node

__all__ = [
    "build_graph",
    "DEFAULT_MAX_DEV_QA_RETRIES",
    "DEFAULT_MAX_REVIEWER_RETRIES",
]

DEFAULT_MAX_DEV_QA_RETRIES = 2
DEFAULT_MAX_REVIEWER_RETRIES = 1

NodeFn = Callable[[TeamState], Awaitable[dict[str, Any]]]


def _route_after_pm(state: TeamState) -> str:
    if state.get("blocked_reason"):
        return "blocked"
    return "dev"


def _route_after_qa(state: TeamState, *, max_retries: int) -> str:
    if state.get("blocked_reason"):
        return "blocked"
    report = state.get("test_report") or {}
    if report.get("verdict") == "pass":
        return "reviewer"
    # fail
    counts = state.get("retry_counts") or {}
    if counts.get("dev_on_qa_fail", 0) >= max_retries:
        return "blocked"
    return "dev_retry"


def _route_after_reviewer(state: TeamState, *, max_retries: int) -> str:
    if state.get("blocked_reason"):
        return "blocked"
    review = state.get("review") or {}
    if review.get("verdict") == "approve":
        return "docs"
    counts = state.get("retry_counts") or {}
    if counts.get("dev_on_review", 0) >= max_retries:
        return "blocked"
    return "dev_retry_review"


def _bump_qa_retry(state: TeamState) -> dict[str, Any]:
    counts = dict(state.get("retry_counts") or {})
    counts["dev_on_qa_fail"] = counts.get("dev_on_qa_fail", 0) + 1
    return {"retry_counts": counts}


def _bump_review_retry(state: TeamState) -> dict[str, Any]:
    counts = dict(state.get("retry_counts") or {})
    counts["dev_on_review"] = counts.get("dev_on_review", 0) + 1
    return {"retry_counts": counts}


def _qa_loop_blocker(state: TeamState) -> dict[str, Any]:
    return {"blocked_reason": "QA loop exceeded max retries"}


def _review_loop_blocker(state: TeamState) -> dict[str, Any]:
    return {"blocked_reason": "Reviewer rework loop exceeded max retries"}


def build_graph(
    *,
    node_overrides: dict[str, NodeFn] | None = None,
    max_dev_qa_retries: int = DEFAULT_MAX_DEV_QA_RETRIES,
    max_reviewer_retries: int = DEFAULT_MAX_REVIEWER_RETRIES,
    checkpointer: Any | None = None,
) -> Any:
    overrides = node_overrides or {}
    # The default ``*_node`` functions take a keyword-only ``config`` argument
    # which the runtime layer must bind (via ``functools.partial``) before
    # passing them in as overrides. The defaults below are therefore only
    # useful when callers supply pre-bound overrides — kept here as a
    # convenience and to satisfy LangGraph's "every node has an action".
    pm: Any = traced_node("pm")(overrides.get("pm", pm_node))
    dev: Any = traced_node("dev")(overrides.get("dev", dev_node))
    qa: Any = traced_node("qa")(overrides.get("qa", qa_node))
    reviewer: Any = traced_node("reviewer")(overrides.get("reviewer", reviewer_node))
    docs: Any = traced_node("docs")(overrides.get("docs", docs_node))

    graph = StateGraph(TeamState)
    graph.add_node("pm", pm)
    graph.add_node("dev", dev)
    graph.add_node("qa", qa)
    graph.add_node("reviewer", reviewer)
    graph.add_node("docs", docs)

    # Bookkeeping nodes that exist only to mutate retry counters or
    # write the blocker reason. They keep the node functions pure.
    graph.add_node("dev_retry", _bump_qa_retry)
    graph.add_node("dev_retry_review", _bump_review_retry)
    graph.add_node("qa_loop_blocker", _qa_loop_blocker)
    graph.add_node("review_loop_blocker", _review_loop_blocker)

    graph.add_edge(START, "pm")
    graph.add_conditional_edges(
        "pm",
        _route_after_pm,
        {"dev": "dev", "blocked": END},
    )
    graph.add_edge("dev", "qa")
    graph.add_conditional_edges(
        "qa",
        lambda s: _route_after_qa(s, max_retries=max_dev_qa_retries),
        {
            "reviewer": "reviewer",
            "dev_retry": "dev_retry",
            "blocked": "qa_loop_blocker",
        },
    )
    graph.add_edge("dev_retry", "dev")
    graph.add_edge("qa_loop_blocker", END)
    graph.add_conditional_edges(
        "reviewer",
        lambda s: _route_after_reviewer(s, max_retries=max_reviewer_retries),
        {
            "docs": "docs",
            "dev_retry_review": "dev_retry_review",
            "blocked": "review_loop_blocker",
        },
    )
    graph.add_edge("dev_retry_review", "dev")
    graph.add_edge("review_loop_blocker", END)
    graph.add_edge("docs", END)

    kwargs: dict[str, Any] = {}
    if checkpointer is not None:
        kwargs["checkpointer"] = checkpointer
        kwargs["interrupt_before"] = ["docs"]
    return graph.compile(**kwargs)
