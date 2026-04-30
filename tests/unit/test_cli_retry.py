from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from typer.testing import CliRunner

from aegis.cli.main import app
from aegis.core.lifecycle import list_tasks
from aegis.core.task import (
    Priority,
    Task,
    TaskBudget,
    TaskFrontmatter,
    TaskStatus,
    write_task,
)


def _seed_blocked(repo: Path) -> Path:
    aegis = repo / ".aegis"
    for sub in ("backlog", "blocked", "rejected", "done", "review", "in-progress", ".worktrees"):
        (aegis / sub).mkdir(parents=True, exist_ok=True)
    p = aegis / "blocked" / "001-demo.md"
    fm = TaskFrontmatter(
        id="001",
        title="demo",
        status=TaskStatus.BLOCKED,
        priority=Priority.P2,
        budget=TaskBudget(usd=2.0, minutes=30),
        created=datetime.now(tz=UTC),
    )
    write_task(Task(frontmatter=fm, body="# demo\n"), p)
    return p


def test_retry_moves_to_backlog_and_updates_budget(tmp_path: Path, monkeypatch) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / ".git").mkdir()
    _seed_blocked(repo)
    monkeypatch.chdir(repo)
    result = CliRunner().invoke(app, ["retry", "001", "--budget-usd", "5.0"])
    assert result.exit_code == 0, result.stdout
    backlog = list_tasks(repo / ".aegis", status=TaskStatus.BACKLOG)
    assert len(backlog) == 1
    task, path = backlog[0]
    assert task.frontmatter.budget.usd == 5.0
