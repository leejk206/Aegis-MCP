from pathlib import Path

import pytest

from aegis.cli.commands.init import run_init
from aegis.cli.commands.task import (
    run_task_add,
    run_task_list,
    run_task_show,
)
from aegis.core.task import TaskStatus


@pytest.fixture
def initialized_repo(git_repo: Path) -> Path:
    run_init(git_repo, force=False)
    return git_repo


def test_task_add_creates_backlog_file(initialized_repo: Path) -> None:
    path = run_task_add(
        initialized_repo,
        title="Add rate limiting",
        priority="P1",
        budget_usd=2.0,
        budget_minutes=30,
    )
    assert path.parent.name == "backlog"
    assert path.name.startswith("001-")
    assert path.name.endswith(".md")

    from aegis.core.task import parse_task

    task = parse_task(path)
    assert task.frontmatter.id == "001"
    assert task.frontmatter.title == "Add rate limiting"
    assert task.frontmatter.priority.value == "P1"
    assert task.frontmatter.status == TaskStatus.BACKLOG


def test_task_add_assigns_incrementing_ids(initialized_repo: Path) -> None:
    p1 = run_task_add(
        initialized_repo, title="one", priority="P2", budget_usd=2.0, budget_minutes=30
    )
    p2 = run_task_add(
        initialized_repo, title="two", priority="P2", budget_usd=2.0, budget_minutes=30
    )
    assert p1.name.startswith("001-")
    assert p2.name.startswith("002-")


def test_task_list_returns_all_tasks(initialized_repo: Path) -> None:
    run_task_add(initialized_repo, title="a", priority="P2", budget_usd=2.0, budget_minutes=30)
    run_task_add(initialized_repo, title="b", priority="P2", budget_usd=2.0, budget_minutes=30)
    rows = run_task_list(initialized_repo, status=None)
    assert len(rows) == 2
    assert {r["id"] for r in rows} == {"001", "002"}


def test_task_list_filtered_by_status(initialized_repo: Path) -> None:
    run_task_add(initialized_repo, title="x", priority="P2", budget_usd=2.0, budget_minutes=30)
    rows = run_task_list(initialized_repo, status="done")
    assert rows == []
    rows = run_task_list(initialized_repo, status="backlog")
    assert len(rows) == 1


def test_task_show_returns_content(initialized_repo: Path) -> None:
    run_task_add(
        initialized_repo,
        title="answer everything",
        priority="P0",
        budget_usd=3.0,
        budget_minutes=45,
    )
    rendered = run_task_show(initialized_repo, task_id="001")
    assert "answer everything" in rendered
    assert "P0" in rendered
