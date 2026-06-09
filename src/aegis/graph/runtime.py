"""End-to-end runtime: worktree -> graph -> lifecycle moves.

This is the only place that touches both LangGraph and the .aegis/
filesystem in the same call. Nodes stay pure; the runtime owns I/O.

Public entry points are sync facades over async helpers: each call
wraps an internal coroutine in :func:`asyncio.run` so callers (CLI
commands, the daemon loop) don't need to reason about event loops.
The async helpers are required because LangGraph 1.1.x dispatches
async role nodes only through ``ainvoke``, which in turn requires
``AsyncSqliteSaver`` for the checkpointer.
"""

from __future__ import annotations

import asyncio
import contextlib
import subprocess
from functools import partial
from pathlib import Path
from typing import Any, cast

from opentelemetry import trace as otel_trace

from aegis.core.config import AegisConfig
from aegis.core.lifecycle import find_task, transition
from aegis.core.task import (
    Task,
    TaskStatus,
    parse_task,
    write_task,
)
from aegis.core.worktree import create_worktree, remove_worktree
from aegis.graph.checkpointer import open_async_checkpointer
from aegis.graph.nodes import dev_node, docs_node, pm_node, qa_node, reviewer_node
from aegis.graph.state import TeamState, initial_state
from aegis.graph.team_graph import build_graph
from aegis.obs import aegis_task_id_var, bootstrap_tracing

__all__ = [
    "run_one_task",
    "resume_after_approve",
    "reject_task",
    "merge_worktree_into_main",
]


def _default_node_overrides(config: AegisConfig) -> dict[str, Any]:
    """Bind the AegisConfig into each role node.

    ``build_graph`` expects node overrides whose keyword-only ``config`` is
    already bound. The CLI / run path supplies no overrides, so without this the
    default nodes are added unbound and LangGraph invokes them missing
    ``config``. Binding here is what makes a real (non-stubbed) run work.
    """
    return {
        "pm": partial(pm_node, config=config),
        "dev": partial(dev_node, config=config),
        "qa": partial(qa_node, config=config),
        "reviewer": partial(reviewer_node, config=config),
        "docs": partial(docs_node, config=config),
    }


def merge_worktree_into_main(repo_root: Path, branch: str) -> None:
    """Fast-forward (or merge) the worktree branch into ``main``.

    Uses the user's local ``main`` branch as the merge target. Failures
    propagate as ``subprocess.CalledProcessError`` -- the runtime catches
    them and marks the task blocked.
    """
    subprocess.run(
        ["git", "checkout", "main"],
        cwd=str(repo_root),
        check=True,
        capture_output=True,
        text=True,
    )
    subprocess.run(
        ["git", "merge", "--no-ff", branch],
        cwd=str(repo_root),
        check=True,
        capture_output=True,
        text=True,
    )


def _worktree_paths(aegis_dir: Path, task: Task) -> tuple[Path, str]:
    fm = task.frontmatter
    slug = f"{fm.id}-{fm.title}".replace(" ", "-").lower()
    wt = aegis_dir / ".worktrees" / slug
    branch = f"aegis/{slug}"
    return wt, branch


def _record_blocked_reason(task_path: Path, reason: str) -> None:
    task = parse_task(task_path)
    if not task.body.endswith("\n"):
        task.body += "\n"
    task.body += f"\n## Blocker\n\n{reason}\n"
    write_task(task, task_path)


async def _run_one_task_async(
    *,
    task_path: Path,
    aegis_dir: Path,
    repo_root: Path,
    config: AegisConfig,
    node_overrides: dict[str, Any] | None,
) -> TeamState:
    bootstrap_tracing(config, aegis_dir)

    task = parse_task(task_path)
    if task.frontmatter.status == TaskStatus.BACKLOG:
        task_path = transition(task_path, aegis_dir, TaskStatus.IN_PROGRESS)
        task = parse_task(task_path)

    worktree_path, branch = _worktree_paths(aegis_dir, task)
    if not worktree_path.exists():
        create_worktree(repo_root, worktree_path, branch)

    state = initial_state(
        task=task,
        task_path=task_path,
        worktree_path=worktree_path,
        target_repo_root=repo_root,
    )
    state["pr_branch"] = branch
    task.frontmatter.worktree = str(worktree_path)
    task.frontmatter.pr_branch = branch
    write_task(task, task_path)

    cfg = {"configurable": {"thread_id": task.frontmatter.id}}
    token = aegis_task_id_var.set(task.frontmatter.id)
    try:
        tracer = otel_trace.get_tracer("aegis.runtime")
        with tracer.start_as_current_span("aegis.task") as root_span:
            root_span.set_attribute("aegis.task_id", task.frontmatter.id)
            root_span.set_attribute("aegis.task_title", task.frontmatter.title)
            trace_id_hex = format(root_span.get_span_context().trace_id, "032x")
            state["trace_id"] = trace_id_hex
            task.frontmatter.trace_id = trace_id_hex
            write_task(task, task_path)

            overrides = (
                node_overrides if node_overrides is not None else _default_node_overrides(config)
            )
            async with open_async_checkpointer(aegis_dir) as saver:
                graph = build_graph(node_overrides=overrides, checkpointer=saver)
                final = await graph.ainvoke(state, config=cfg)
    finally:
        aegis_task_id_var.reset(token)

    review = final.get("review") or {}
    if final.get("blocked_reason"):
        _record_blocked_reason(task_path, final["blocked_reason"])
        transition(task_path, aegis_dir, TaskStatus.BLOCKED)
    elif review.get("verdict") == "approve" and final.get("current_node") != "docs":
        final["awaiting_human"] = True
        transition(task_path, aegis_dir, TaskStatus.REVIEW)
    else:
        try:
            merge_worktree_into_main(repo_root, branch)
            transition(task_path, aegis_dir, TaskStatus.DONE)
            remove_worktree(repo_root, worktree_path)
        except Exception as exc:
            _record_blocked_reason(task_path, f"merge failed: {exc}")
            transition(task_path, aegis_dir, TaskStatus.BLOCKED)
    return cast(TeamState, final)


def run_one_task(
    *,
    task_path: Path,
    aegis_dir: Path,
    repo_root: Path,
    config: AegisConfig,
    node_overrides: dict[str, Any] | None = None,
) -> TeamState:
    """Run one task end-to-end. Pauses at the human gate (review/)."""
    return asyncio.run(
        _run_one_task_async(
            task_path=task_path,
            aegis_dir=aegis_dir,
            repo_root=repo_root,
            config=config,
            node_overrides=node_overrides,
        )
    )


async def _resume_after_approve_async(
    *,
    task_id: str,
    aegis_dir: Path,
    repo_root: Path,
    config: AegisConfig,
    node_overrides: dict[str, Any] | None,
) -> TeamState:
    bootstrap_tracing(config, aegis_dir)

    found = find_task(aegis_dir, task_id)
    if found is None:
        raise FileNotFoundError(f"task {task_id} not found")
    task, task_path = found
    if task.frontmatter.status != TaskStatus.REVIEW:
        raise ValueError(f"task {task_id} is in {task.frontmatter.status.value}, not review")

    worktree_path, branch = _worktree_paths(aegis_dir, task)
    cfg = {"configurable": {"thread_id": task_id}}
    token = aegis_task_id_var.set(task_id)
    try:
        tracer = otel_trace.get_tracer("aegis.runtime")
        with tracer.start_as_current_span("aegis.task.resume") as root_span:
            root_span.set_attribute("aegis.task_id", task_id)
            overrides = (
                node_overrides if node_overrides is not None else _default_node_overrides(config)
            )
            async with open_async_checkpointer(aegis_dir) as saver:
                graph = build_graph(node_overrides=overrides, checkpointer=saver)
                # The checkpoint still holds the task_path from the first run
                # (.aegis/in-progress/...), but the task file has since moved to
                # review/. Refresh it so resumed nodes (e.g. Docs) read the file
                # from its current location instead of crashing on a stale path.
                await graph.aupdate_state(cfg, {"task_path": str(task_path)})
                final = await graph.ainvoke(None, config=cfg)
    finally:
        aegis_task_id_var.reset(token)

    if final.get("blocked_reason"):
        _record_blocked_reason(task_path, final["blocked_reason"])
        transition(task_path, aegis_dir, TaskStatus.BLOCKED)
        return cast(TeamState, final)
    merge_worktree_into_main(repo_root, branch)
    transition(task_path, aegis_dir, TaskStatus.DONE)
    if worktree_path.exists():
        remove_worktree(repo_root, worktree_path)
    return cast(TeamState, final)


def resume_after_approve(
    *,
    task_id: str,
    aegis_dir: Path,
    repo_root: Path,
    config: AegisConfig,
    node_overrides: dict[str, Any] | None = None,
) -> TeamState:
    return asyncio.run(
        _resume_after_approve_async(
            task_id=task_id,
            aegis_dir=aegis_dir,
            repo_root=repo_root,
            config=config,
            node_overrides=node_overrides,
        )
    )


def reject_task(
    *,
    task_id: str,
    aegis_dir: Path,
    repo_root: Path,
    reason: str | None = None,
) -> Path:
    found = find_task(aegis_dir, task_id)
    if found is None:
        raise FileNotFoundError(f"task {task_id} not found")
    task, task_path = found
    if reason:
        if not task.body.endswith("\n"):
            task.body += "\n"
        task.body += f"\n## Rejection reason\n\n{reason}\n"
        write_task(task, task_path)
    new_path = transition(task_path, aegis_dir, TaskStatus.REJECTED)
    worktree_path, _ = _worktree_paths(aegis_dir, task)
    if worktree_path.exists():
        # Best-effort: rejected tasks may have already-clean worktrees.
        with contextlib.suppress(Exception):
            remove_worktree(repo_root, worktree_path)
    return new_path
