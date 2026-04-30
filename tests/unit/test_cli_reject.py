from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import patch

from typer.testing import CliRunner

from aegis.cli.main import app
from aegis.core.task import Priority, Task, TaskBudget, TaskFrontmatter, TaskStatus, write_task


def _seed(repo: Path) -> None:
    aegis = repo / ".aegis"
    for sub in ("backlog", "review", "rejected", "done", "blocked", "in-progress", ".worktrees"):
        (aegis / sub).mkdir(parents=True, exist_ok=True)
    p = aegis / "review" / "001-demo.md"
    fm = TaskFrontmatter(
        id="001",
        title="demo",
        status=TaskStatus.REVIEW,
        priority=Priority.P2,
        budget=TaskBudget(),
        created=datetime.now(tz=UTC),
    )
    write_task(Task(frontmatter=fm, body="# demo\n"), p)


def test_reject_invokes_runtime(tmp_path: Path, monkeypatch) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / ".git").mkdir()
    _seed(repo)
    monkeypatch.chdir(repo)
    with patch("aegis.cli.commands.reject.reject_task") as rj:
        result = CliRunner().invoke(app, ["reject", "001", "auth broke"])
    assert result.exit_code == 0
    assert rj.call_args.kwargs["task_id"] == "001"
    assert rj.call_args.kwargs["reason"] == "auth broke"
