from __future__ import annotations

import subprocess
from datetime import datetime, timezone
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from aegis.cli.commands.init import run_init
from aegis.core.config import load_config
from aegis.core.task import Task, TaskFrontmatter, TaskStatus, write_task
from aegis.web.app import create_app


def _seed_task(
    aegis_dir: Path,
    *,
    task_id: str,
    title: str,
    status: TaskStatus,
    body: str = "## Goal\n\nDo the thing.\n",
    pr_branch: str | None = None,
    trace_id: str | None = None,
) -> None:
    fm = TaskFrontmatter(
        id=task_id,
        title=title,
        status=status,
        created=datetime.now(timezone.utc),
        pr_branch=pr_branch,
        trace_id=trace_id,
    )
    task = Task(frontmatter=fm, body=body)
    target = aegis_dir / status.value / f"{task_id}-{title.replace(' ', '-')}.md"
    write_task(task, target)


@pytest.fixture
def client(git_repo: Path) -> TestClient:
    aegis_dir = run_init(git_repo)
    _seed_task(
        aegis_dir,
        task_id="001",
        title="add login",
        status=TaskStatus.REVIEW,
        body="## Goal\n\nAdd a **login** page.\n",
        pr_branch="aegis/001-add-login",
        trace_id="aabbccddeeff00112233445566778899",
    )
    config = load_config(aegis_dir / "config.yaml")
    app = create_app(
        aegis_dir=aegis_dir, repo_root=git_repo, config=config,
        host="127.0.0.1", port=8765,
    )
    return TestClient(app, headers={"Host": "127.0.0.1:8765"})


def test_task_detail_renders_markdown(client: TestClient) -> None:
    response = client.get("/task/001")
    assert response.status_code == 200
    assert "<strong>login</strong>" in response.text


def test_task_detail_shows_metadata(client: TestClient) -> None:
    body = client.get("/task/001").text
    assert "review" in body
    assert "aegis/001-add-login" in body
    assert "aabbccddeeff" in body  # trace_id (full or truncated)


def test_task_detail_returns_404_for_unknown_id(client: TestClient) -> None:
    response = client.get("/task/999")
    assert response.status_code == 404


def test_task_detail_shows_diff_when_branch_exists(
    client: TestClient, git_repo: Path
) -> None:
    branch = "aegis/001-add-login"
    subprocess.run(["git", "-C", str(git_repo), "checkout", "-b", branch], check=True)
    (git_repo / "login.py").write_text("def login():\n    return True\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(git_repo), "add", "login.py"], check=True)
    subprocess.run(
        ["git", "-C", str(git_repo), "commit", "-q", "-m", "add login"], check=True
    )
    subprocess.run(["git", "-C", str(git_repo), "checkout", "main"], check=True)
    body = client.get("/task/001").text
    assert "login.py" in body


def test_task_detail_shows_approve_reject_when_review(client: TestClient) -> None:
    body = client.get("/task/001").text
    assert "Approve" in body
    assert "Reject" in body


def test_task_detail_hides_approve_reject_when_not_review(
    git_repo: Path,
) -> None:
    aegis_dir = run_init(git_repo)
    _seed_task(aegis_dir, task_id="002", title="t", status=TaskStatus.BACKLOG)
    config = load_config(aegis_dir / "config.yaml")
    app = create_app(
        aegis_dir=aegis_dir, repo_root=git_repo, config=config,
        host="127.0.0.1", port=8765,
    )
    client = TestClient(app, headers={"Host": "127.0.0.1:8765"})
    body = client.get("/task/002").text
    assert "Approve" not in body
    assert "Reject" not in body


def test_logs_partial_returns_lines(client: TestClient, git_repo: Path) -> None:
    aegis_dir = git_repo / ".aegis"
    trace_path = aegis_dir / "trace" / "001.jsonl"
    import json
    record = {
        "name": "pm_node",
        "trace_id": "0" * 32, "span_id": "0" * 16, "parent_span_id": None,
        "start_time_ns": 1_000_000_000, "end_time_ns": 1_500_000_000,
        "duration_ns": 500_000_000, "status": {"code": "OK", "description": None},
        "attributes": {"aegis.role": "pm"}, "events": [],
    }
    with open(trace_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(record) + "\n")
    response = client.get("/task/001/logs")
    assert response.status_code == 200
    assert "pm_node" in response.text


def test_logs_partial_polls_via_htmx(client: TestClient) -> None:
    # the task page renders an outer div with hx-get/hx-trigger="every 1s"
    response = client.get("/task/001")
    assert "/task/001/logs" in response.text
    assert "hx-trigger=\"every 1s\"" in response.text or "hx-trigger='every 1s'" in response.text
