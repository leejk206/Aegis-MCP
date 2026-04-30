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
    write_task,
)
from aegis.graph.nodes.dev import dev_node
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
    task = Task(frontmatter=fm, body="# demo\n\n## Plan\n- step 1\n")
    write_task(task, p)
    s = initial_state(task=task, task_path=p, worktree_path=tmp_path, target_repo_root=tmp_path)
    s["plan"] = {"summary": "- step 1", "verdict": None}
    return s


class _StubAgent:
    def __init__(self, msgs: list[Any]) -> None:
        self._msgs = msgs

    async def run(self, prompt: str) -> list[Any]:
        return self._msgs


def _done(summary: str = "committed.") -> list[Any]:
    return [
        {
            "type": "assistant",
            "content": [
                {
                    "type": "tool_use",
                    "name": "mcp__signals__done",
                    "input": {"summary": summary},
                }
            ],
        }
    ]


def test_dev_done_marks_implementation_complete(tmp_path: Path) -> None:
    state = _state(tmp_path)
    config = AegisConfig(project=ProjectConfig(name="t"))
    delta = asyncio.run(
        dev_node(state, config=config, agent_factory=lambda s, c: _StubAgent(_done()))
    )
    assert delta["implementation_status"] == "done"
    assert delta["current_node"] == "dev"


def test_dev_block_records_reason(tmp_path: Path) -> None:
    state = _state(tmp_path)
    config = AegisConfig(project=ProjectConfig(name="t"))
    msgs = [
        {
            "type": "assistant",
            "content": [
                {
                    "type": "tool_use",
                    "name": "mcp__signals__block",
                    "input": {"reason": "test fixture missing"},
                }
            ],
        }
    ]
    delta = asyncio.run(dev_node(state, config=config, agent_factory=lambda s, c: _StubAgent(msgs)))
    assert delta["blocked_reason"] == "test fixture missing"


def test_dev_passes_shell_allow_cmds(tmp_path: Path) -> None:
    state = _state(tmp_path)
    config = AegisConfig(project=ProjectConfig(name="t"))
    seen: dict[str, str | None] = {}

    def fac(s: Any, c: Any) -> _StubAgent:
        from aegis.graph.node_helpers import make_agent

        agent = make_agent(
            "dev",
            s,
            c,
            shell_allow_cmds="pytest,ruff,mypy,python,pip,npm,pnpm,node",
        )
        seen["allow"] = agent.shell_allow_cmds
        return _StubAgent(_done())

    asyncio.run(dev_node(state, config=config, agent_factory=fac))
    assert "pytest" in (seen["allow"] or "")
