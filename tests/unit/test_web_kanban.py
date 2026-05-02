from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from aegis.cli.commands.init import run_init
from aegis.core.config import load_config
from aegis.core.task import Task, TaskFrontmatter, TaskStatus, write_task
from aegis.web.app import create_app


def _seed_task(aegis_dir: Path, *, task_id: str, title: str, status: TaskStatus) -> None:
    fm = TaskFrontmatter(
        id=task_id,
        title=title,
        status=status,
        created=datetime.now(UTC),
    )
    task = Task(frontmatter=fm, body="## Goal\n\nDo the thing.\n")
    target = aegis_dir / status.value / f"{task_id}-{title.replace(' ', '-')}.md"
    write_task(task, target)


@pytest.fixture
def client(git_repo: Path) -> TestClient:
    aegis_dir = run_init(git_repo)
    _seed_task(aegis_dir, task_id="001", title="add login", status=TaskStatus.BACKLOG)
    _seed_task(aegis_dir, task_id="002", title="fix bug", status=TaskStatus.IN_PROGRESS)
    _seed_task(aegis_dir, task_id="003", title="ship feature", status=TaskStatus.REVIEW)
    _seed_task(aegis_dir, task_id="004", title="hung task", status=TaskStatus.BLOCKED)
    config = load_config(aegis_dir / "config.yaml")
    app = create_app(
        aegis_dir=aegis_dir, repo_root=git_repo, config=config,
        host="127.0.0.1", port=8765,
    )
    return TestClient(app, headers={"Host": "127.0.0.1:8765"})


def test_kanban_shows_all_four_columns(client: TestClient) -> None:
    response = client.get("/")
    assert response.status_code == 200
    body = response.text
    assert "Backlog" in body
    assert "In progress" in body
    assert "Review" in body
    assert "Blocked" in body


def test_kanban_lists_each_task(client: TestClient) -> None:
    body = client.get("/").text
    assert "add login" in body
    assert "fix bug" in body
    assert "ship feature" in body
    assert "hung task" in body


def test_kanban_card_links_to_detail(client: TestClient) -> None:
    body = client.get("/").text
    assert 'href="/task/001"' in body
    assert 'href="/task/003"' in body


def test_kanban_does_not_show_done_or_rejected(client: TestClient, git_repo: Path) -> None:
    aegis_dir = git_repo / ".aegis"
    _seed_task(aegis_dir, task_id="005", title="done task", status=TaskStatus.DONE)
    _seed_task(aegis_dir, task_id="006", title="rejected task", status=TaskStatus.REJECTED)
    body = client.get("/").text
    assert "done task" not in body
    assert "rejected task" not in body
