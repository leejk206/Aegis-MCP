from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import patch

from typer.testing import CliRunner

from aegis.cli.main import app
from aegis.core.config import default_config, dump_config
from aegis.core.task import Priority, Task, TaskBudget, TaskFrontmatter, TaskStatus, write_task


def _seed(repo: Path, task_id: str = "001") -> Path:
    aegis = repo / ".aegis"
    for sub in ("backlog", "in-progress", "review", "done", "blocked", "rejected", ".worktrees"):
        (aegis / sub).mkdir(parents=True, exist_ok=True)
    cfg_path = aegis / "config.yaml"
    if not cfg_path.exists():
        dump_config(default_config(repo.name), cfg_path)
    p = aegis / "backlog" / f"{task_id}-demo.md"
    fm = TaskFrontmatter(
        id=task_id,
        title="demo",
        status=TaskStatus.BACKLOG,
        priority=Priority.P2,
        budget=TaskBudget(),
        created=datetime.now(tz=UTC),
    )
    write_task(Task(frontmatter=fm, body="# demo\n"), p)
    return p


def test_run_invokes_runtime_for_each_backlog_task(tmp_path: Path, monkeypatch) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / ".git").mkdir()
    _seed(repo, "001")
    _seed(repo, "002")
    monkeypatch.chdir(repo)

    with patch("aegis.cli.commands.run.run_one_task") as ru:
        ru.side_effect = lambda **kw: {"current_node": "reviewer"}
        runner = CliRunner()
        result = runner.invoke(app, ["run", "--once"])
    assert result.exit_code == 0, result.stdout
    assert ru.call_count == 2


def test_run_specific_task(tmp_path: Path, monkeypatch) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / ".git").mkdir()
    _seed(repo, "001")
    _seed(repo, "002")
    monkeypatch.chdir(repo)

    with patch("aegis.cli.commands.run.run_one_task") as ru:
        ru.side_effect = lambda **kw: {"current_node": "reviewer"}
        runner = CliRunner()
        result = runner.invoke(app, ["run", "--task", "001"])
    assert result.exit_code == 0, result.stdout
    assert ru.call_count == 1
    # The task_path passed should reference 001
    called_path: Path = ru.call_args.kwargs["task_path"]
    assert "001" in called_path.name
