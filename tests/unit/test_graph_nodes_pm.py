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
from aegis.graph.nodes.pm import pm_node
from aegis.graph.state import initial_state


def _setup(tmp_path: Path) -> tuple[dict[str, Any], Path, AegisConfig]:
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
    task = Task(frontmatter=fm, body="# demo\n\n## Why\nbecause.\n")
    write_task(task, p)
    config = AegisConfig(project=ProjectConfig(name="t"))
    state = initial_state(
        task=task, task_path=p, worktree_path=tmp_path, target_repo_root=tmp_path
    )
    return state, p, config


class _StubAgent:
    def __init__(self, msgs: list[Any]) -> None:
        self._msgs = msgs
        self.invoked_with: str | None = None

    async def run(self, prompt: str) -> list[Any]:
        self.invoked_with = prompt
        return self._msgs


def _done_msgs(summary: str, verdict: str | None = None) -> list[Any]:
    args: dict[str, Any] = {"summary": summary}
    if verdict is not None:
        args["verdict"] = verdict
    return [
        {
            "type": "assistant",
            "content": [
                {"type": "tool_use", "name": "mcp__signals__done", "input": args}
            ],
        }
    ]


def _block_msgs(reason: str) -> list[Any]:
    return [
        {
            "type": "assistant",
            "content": [
                {
                    "type": "tool_use",
                    "name": "mcp__signals__block",
                    "input": {"reason": reason},
                }
            ],
        }
    ]


def test_pm_done_appends_plan_and_advances_status(tmp_path: Path) -> None:
    state, task_path, config = _setup(tmp_path)
    stub = _StubAgent(_done_msgs("- step 1\n- step 2\n"))

    delta = asyncio.run(
        pm_node(state, config=config, agent_factory=lambda s, c: stub)
    )
    assert delta["implementation_status"] == "in_progress"
    assert delta["current_node"] == "pm"
    assert delta["plan"]["summary"].startswith("- step 1")

    refreshed = parse_task(task_path)
    assert "## Plan" in refreshed.body
    assert "- step 1" in refreshed.body


def test_pm_block_sets_blocked_reason(tmp_path: Path) -> None:
    state, _, config = _setup(tmp_path)
    stub = _StubAgent(_block_msgs("ambiguous criteria"))
    delta = asyncio.run(
        pm_node(state, config=config, agent_factory=lambda s, c: stub)
    )
    assert delta["blocked_reason"] == "ambiguous criteria"
    assert delta["current_node"] == "pm"


def test_pm_no_signal_treated_as_block(tmp_path: Path) -> None:
    state, _, config = _setup(tmp_path)
    stub = _StubAgent(
        [{"type": "assistant", "content": [{"type": "text", "text": "..."}]}]
    )
    delta = asyncio.run(
        pm_node(state, config=config, agent_factory=lambda s, c: stub)
    )
    assert "blocked_reason" in delta
    assert "did not signal" in delta["blocked_reason"].lower()
