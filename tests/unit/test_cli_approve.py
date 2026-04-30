from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import patch

from typer.testing import CliRunner

from aegis.cli.main import app
from aegis.core.config import default_config, dump_config
from aegis.core.task import Priority, Task, TaskBudget, TaskFrontmatter, TaskStatus, write_task


def _seed_review(repo: Path) -> None:
    aegis = repo / ".aegis"
    for sub in ("backlog", "in-progress", "review", "done", "blocked", "rejected", ".worktrees"):
        (aegis / sub).mkdir(parents=True, exist_ok=True)
    cfg_path = aegis / "config.yaml"
    if not cfg_path.exists():
        dump_config(default_config(repo.name), cfg_path)
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


def test_approve_calls_resume(tmp_path: Path, monkeypatch) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / ".git").mkdir()
    _seed_review(repo)
    monkeypatch.chdir(repo)

    with patch("aegis.cli.commands.approve.resume_after_approve") as ra:
        ra.side_effect = lambda **kw: {"current_node": "docs"}
        result = CliRunner().invoke(app, ["approve", "001"])
    assert result.exit_code == 0, result.stdout
    assert ra.call_count == 1
    assert ra.call_args.kwargs["task_id"] == "001"
