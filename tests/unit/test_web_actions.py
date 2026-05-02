from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from aegis.cli.commands.init import run_init
from aegis.core.config import load_config
from aegis.core.task import Task, TaskFrontmatter, TaskStatus, write_task
from aegis.web.app import create_app


def _seed_review_task(aegis_dir: Path, *, task_id: str = "001") -> None:
    fm = TaskFrontmatter(
        id=task_id,
        title="t",
        status=TaskStatus.REVIEW,
        created=datetime.now(timezone.utc),
        pr_branch=f"aegis/{task_id}-t",
    )
    task = Task(frontmatter=fm, body="body\n")
    write_task(task, aegis_dir / "review" / f"{task_id}-t.md")


@pytest.fixture
def app_and_client(git_repo: Path) -> tuple[object, TestClient]:
    aegis_dir = run_init(git_repo)
    _seed_review_task(aegis_dir)
    config = load_config(aegis_dir / "config.yaml")
    app = create_app(
        aegis_dir=aegis_dir, repo_root=git_repo, config=config,
        host="127.0.0.1", port=8765,
    )
    client = TestClient(
        app,
        headers={"Host": "127.0.0.1:8765", "Origin": "http://127.0.0.1:8765"},
    )
    return app, client


def test_approve_without_csrf_rejected(app_and_client: tuple[object, TestClient]) -> None:
    _, client = app_and_client
    response = client.post("/task/001/approve")
    assert response.status_code == 403


def test_approve_with_csrf_calls_runtime(app_and_client: tuple[object, TestClient]) -> None:
    app, client = app_and_client
    token = app.state.csrf.token
    with patch("aegis.web.routes.actions.resume_after_approve") as mock:
        response = client.post("/task/001/approve", headers={"X-CSRF-Token": token})
        assert response.status_code == 200
        assert mock.called
        kwargs = mock.call_args.kwargs
        assert kwargs["task_id"] == "001"


def test_reject_with_csrf_calls_runtime(app_and_client: tuple[object, TestClient]) -> None:
    app, client = app_and_client
    token = app.state.csrf.token
    with patch("aegis.web.routes.actions.reject_task") as mock:
        response = client.post(
            "/task/001/reject",
            headers={"X-CSRF-Token": token},
            data={"reason": "not needed"},
        )
        assert response.status_code == 200
        assert mock.called
        kwargs = mock.call_args.kwargs
        assert kwargs["task_id"] == "001"
        assert kwargs["reason"] == "not needed"


def test_reject_without_csrf_rejected(app_and_client: tuple[object, TestClient]) -> None:
    _, client = app_and_client
    response = client.post("/task/001/reject")
    assert response.status_code == 403


def test_approve_without_origin_rejected(git_repo: Path) -> None:
    aegis_dir = run_init(git_repo)
    _seed_review_task(aegis_dir)
    config = load_config(aegis_dir / "config.yaml")
    app = create_app(
        aegis_dir=aegis_dir, repo_root=git_repo, config=config,
        host="127.0.0.1", port=8765,
    )
    client = TestClient(app, headers={"Host": "127.0.0.1:8765"})  # no Origin
    response = client.post(
        "/task/001/approve", headers={"X-CSRF-Token": app.state.csrf.token}
    )
    assert response.status_code == 403
