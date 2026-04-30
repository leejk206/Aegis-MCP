from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from typer.testing import CliRunner

from aegis.cli.main import app
from aegis.core.task import Priority, Task, TaskBudget, TaskFrontmatter, TaskStatus, write_task


def _seed(aegis: Path, task_id: str, status: TaskStatus, title: str = "demo") -> None:
    p = aegis / status.value / f"{task_id}-{title}.md"
    p.parent.mkdir(parents=True, exist_ok=True)
    fm = TaskFrontmatter(
        id=task_id,
        title=title,
        status=status,
        priority=Priority.P2,
        budget=TaskBudget(),
        created=datetime.now(tz=UTC),
    )
    write_task(Task(frontmatter=fm, body=f"# {title}\n"), p)


def test_status_lists_tasks_per_lane(tmp_path: Path, monkeypatch) -> None:
    repo = tmp_path / "repo"
    aegis = repo / ".aegis"
    (repo / ".git").mkdir(parents=True)
    _seed(aegis, "001", TaskStatus.BACKLOG, "alpha")
    _seed(aegis, "002", TaskStatus.IN_PROGRESS, "beta")
    _seed(aegis, "003", TaskStatus.REVIEW, "gamma")
    monkeypatch.chdir(repo)

    runner = CliRunner()
    result = runner.invoke(app, ["status"])
    assert result.exit_code == 0, result.stdout
    out = result.stdout
    assert "001" in out and "002" in out and "003" in out
    assert "backlog" in out.lower()
    assert "review" in out.lower()
