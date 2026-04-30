"""Canonical LangGraph ``TeamState`` and the ``initial_state`` factory.

``TeamState`` is the single source of truth for every node in the
Phase-4 team graph. Field names mirror spec §5.1 with two additions:

* ``blocked_reason``: set when a node bails out via the ``signals.block``
  tool; the runtime uses it to write the task into ``blocked/``.
* ``current_node``: last node to write — used by the runtime layer for
  observability, not by the graph's routing.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, TypedDict

from aegis.core.task import Task

__all__ = ["TeamState", "initial_state"]


class TeamState(TypedDict):
    # Identity
    task_id: str
    task_path: str

    # Execution environment
    worktree_path: str
    target_repo_root: str

    # Agent outputs
    plan: dict[str, Any] | None
    implementation_status: str  # pending | in_progress | done | blocked
    test_report: dict[str, Any] | None
    review: dict[str, Any] | None
    pr_branch: str | None

    # Control
    budget_remaining: dict[str, float]
    retry_counts: dict[str, int]
    trace_id: str
    awaiting_human: bool
    blocked_reason: str | None
    current_node: str | None

    # History
    history: list[dict[str, Any]]


def initial_state(
    *,
    task: Task,
    task_path: Path,
    worktree_path: Path,
    target_repo_root: Path,
    trace_id: str = "",
) -> TeamState:
    """Return a fresh ``TeamState`` populated from ``task``'s frontmatter."""
    fm = task.frontmatter
    return TeamState(
        task_id=fm.id,
        task_path=str(task_path),
        worktree_path=str(worktree_path),
        target_repo_root=str(target_repo_root),
        plan=None,
        implementation_status="pending",
        test_report=None,
        review=None,
        pr_branch=None,
        budget_remaining={
            "usd": float(fm.budget.usd),
            "seconds": float(fm.budget.minutes) * 60.0,
            "input_tokens": 0.0,
            "output_tokens": 0.0,
        },
        retry_counts={"dev_on_qa_fail": 0, "dev_on_review": 0},
        trace_id=trace_id,
        awaiting_human=False,
        blocked_reason=None,
        current_node=None,
        history=[],
    )
