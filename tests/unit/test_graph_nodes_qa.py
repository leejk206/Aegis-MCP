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
from aegis.graph.nodes.qa import qa_node
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
    s["plan"] = {"summary": "do it", "verdict": None}
    return s


class _StubAgent:
    def __init__(self, msgs: list[Any]) -> None:
        self._msgs = msgs

    async def run(self, prompt: str) -> list[Any]:
        return self._msgs


def _done(summary: str, verdict: str | None) -> list[Any]:
    args: dict[str, Any] = {"summary": summary}
    if verdict is not None:
        args["verdict"] = verdict
    return [
        {
            "type": "assistant",
            "content": [{"type": "tool_use", "name": "mcp__signals__done", "input": args}],
        }
    ]


def test_qa_pass_records_verdict_and_appends_report(tmp_path: Path) -> None:
    s = _state(tmp_path)
    config = AegisConfig(project=ProjectConfig(name="t"))
    delta = asyncio.run(
        qa_node(
            s,
            config=config,
            agent_factory=lambda st, c: _StubAgent(_done("12 passed", "pass")),
        )
    )
    assert delta["test_report"]["verdict"] == "pass"
    assert delta["current_node"] == "qa"
    body = parse_task(Path(s["task_path"])).body
    assert "## QA report" in body and "12 passed" in body


def test_qa_fail_routes_back_to_dev(tmp_path: Path) -> None:
    s = _state(tmp_path)
    config = AegisConfig(project=ProjectConfig(name="t"))
    delta = asyncio.run(
        qa_node(
            s,
            config=config,
            agent_factory=lambda st, c: _StubAgent(_done("3 failed", "fail")),
        )
    )
    assert delta["test_report"]["verdict"] == "fail"
    assert delta["implementation_status"] == "in_progress"


def test_qa_done_without_verdict_treated_as_fail(tmp_path: Path) -> None:
    s = _state(tmp_path)
    config = AegisConfig(project=ProjectConfig(name="t"))
    delta = asyncio.run(
        qa_node(
            s,
            config=config,
            agent_factory=lambda st, c: _StubAgent(_done("no verdict here", None)),
        )
    )
    assert delta["test_report"]["verdict"] == "fail"
