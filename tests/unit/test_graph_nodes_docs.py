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
from aegis.graph.nodes.docs import docs_node
from aegis.graph.state import initial_state


def _state(tmp_path: Path) -> dict[str, Any]:
    aegis = tmp_path / ".aegis"
    aegis.mkdir()
    (aegis / "review").mkdir()
    p = aegis / "review" / "001-demo.md"
    fm = TaskFrontmatter(
        id="001",
        title="demo",
        status=TaskStatus.REVIEW,
        priority=Priority.P2,
        budget=TaskBudget(),
        created=datetime.now(tz=UTC),
    )
    task = Task(frontmatter=fm, body="# demo\n")
    write_task(task, p)
    return initial_state(
        task=task, task_path=p, worktree_path=tmp_path, target_repo_root=tmp_path
    )


class _StubAgent:
    def __init__(self, msgs: list[Any]) -> None:
        self._msgs = msgs

    async def run(self, prompt: str) -> list[Any]:
        return self._msgs


def test_docs_done(tmp_path: Path) -> None:
    s = _state(tmp_path)
    cfg = AegisConfig(project=ProjectConfig(name="t"))
    msgs = [
        {
            "type": "assistant",
            "content": [
                {
                    "type": "tool_use",
                    "name": "mcp__signals__done",
                    "input": {"summary": "updated CHANGELOG"},
                },
            ],
        }
    ]
    delta = asyncio.run(
        docs_node(s, config=cfg, agent_factory=lambda st, c: _StubAgent(msgs))
    )
    assert delta["current_node"] == "docs"
    assert delta["implementation_status"] == "done"
