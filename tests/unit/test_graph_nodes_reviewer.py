from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from aegis.core.config import AegisConfig, ProjectConfig
from aegis.core.task import (
    Priority,
    Task,
    TaskBudget,
    TaskFrontmatter,
    TaskStatus,
    parse_task,
    write_task,
)
from aegis.graph.nodes.reviewer import reviewer_node
from aegis.graph.state import initial_state


def _state(tmp_path: Path) -> dict[str, Any]:
    aegis = tmp_path / ".aegis"
    aegis.mkdir()
    (aegis / "in-progress").mkdir()
    p = aegis / "in-progress" / "001-demo.md"
    fm = TaskFrontmatter(
        id="001",
        title="demo",
        status=TaskStatus.IN_PROGRESS,
        priority=Priority.P2,
        budget=TaskBudget(),
        created=datetime.now(tz=UTC),
    )
    task = Task(frontmatter=fm, body="# demo\n")
    write_task(task, p)
    s = initial_state(task=task, task_path=p, worktree_path=tmp_path, target_repo_root=tmp_path)
    s["pr_branch"] = "aegis/001-demo"
    return s


class _StubAgent:
    def __init__(self, msgs: list[Any]) -> None:
        self._msgs = msgs

    async def run(self, prompt: str) -> list[Any]:
        return self._msgs


def _done(summary: str, verdict: str) -> list[Any]:
    return [
        {
            "type": "assistant",
            "content": [
                {
                    "type": "tool_use",
                    "name": "mcp__signals__done",
                    "input": {"summary": summary, "verdict": verdict},
                },
            ],
        }
    ]


def test_reviewer_approve(tmp_path: Path) -> None:
    s = _state(tmp_path)
    cfg = AegisConfig(project=ProjectConfig(name="t"))
    delta = asyncio.run(
        reviewer_node(
            s,
            config=cfg,
            agent_factory=lambda st, c: _StubAgent(_done("LGTM", "approve")),
        )
    )
    assert delta["review"]["verdict"] == "approve"
    assert delta["current_node"] == "reviewer"
    body = parse_task(Path(s["task_path"])).body
    assert "## Review" in body and "LGTM" in body


def test_reviewer_rework_resets_implementation(tmp_path: Path) -> None:
    s = _state(tmp_path)
    cfg = AegisConfig(project=ProjectConfig(name="t"))
    delta = asyncio.run(
        reviewer_node(
            s,
            config=cfg,
            agent_factory=lambda st, c: _StubAgent(_done("rename foo", "rework")),
        )
    )
    assert delta["review"]["verdict"] == "rework"
    assert delta["implementation_status"] == "in_progress"
