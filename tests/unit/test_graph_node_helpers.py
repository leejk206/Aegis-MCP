from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

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
from aegis.graph.node_helpers import (
    Stopped,
    append_section,
    check_stop_flag,
    make_agent,
)
from aegis.graph.state import initial_state


def _task_at(path: Path, task_id: str = "001") -> Task:
    fm = TaskFrontmatter(
        id=task_id,
        title="demo",
        status=TaskStatus.IN_PROGRESS,
        priority=Priority.P2,
        budget=TaskBudget(),
        created=datetime.now(tz=UTC),
    )
    task = Task(frontmatter=fm, body="# demo\n\nbody.\n")
    write_task(task, path)
    return task


def test_check_stop_flag_global(tmp_path: Path) -> None:
    aegis = tmp_path / ".aegis"
    aegis.mkdir()
    check_stop_flag(aegis, "001")  # no flag → no raise
    (aegis / ".stop").touch()
    with pytest.raises(Stopped):
        check_stop_flag(aegis, "001")


def test_check_stop_flag_task_specific(tmp_path: Path) -> None:
    aegis = tmp_path / ".aegis"
    aegis.mkdir()
    (aegis / ".stop.001").touch()
    with pytest.raises(Stopped):
        check_stop_flag(aegis, "001")
    # Different task is unaffected
    check_stop_flag(aegis, "002")


def test_append_section_preserves_frontmatter(tmp_path: Path) -> None:
    p = tmp_path / "001-demo.md"
    _task_at(p)
    append_section(p, "Plan", "- bullet 1\n- bullet 2\n")
    rendered = parse_task(p)
    assert "## Plan" in rendered.body
    assert "- bullet 1" in rendered.body
    # Frontmatter survived
    assert rendered.frontmatter.id == "001"


def test_make_agent_instantiates_correct_role(tmp_path: Path) -> None:
    p = tmp_path / "001-demo.md"
    _task_at(p)
    config = AegisConfig(project=ProjectConfig(name="t"))
    state = initial_state(
        task=_task_at(p),
        task_path=p,
        worktree_path=tmp_path,
        target_repo_root=tmp_path,
    )
    agent = make_agent("dev", state, config)
    assert agent.role == "dev"
    assert agent.worktree == tmp_path.resolve()
