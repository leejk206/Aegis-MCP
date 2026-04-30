from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from typer.testing import CliRunner

from aegis.cli.main import app
from aegis.core.task import Priority, Task, TaskBudget, TaskFrontmatter, TaskStatus, write_task


def _seed(repo: Path) -> None:
    aegis = repo / ".aegis"
    aegis.mkdir(parents=True)
    (aegis / "blocked").mkdir()
    p = aegis / "blocked" / "001-demo.md"
    fm = TaskFrontmatter(
        id="001",
        title="demo",
        status=TaskStatus.BLOCKED,
        priority=Priority.P2,
        budget=TaskBudget(),
        created=datetime.now(tz=UTC),
    )
    write_task(Task(frontmatter=fm, body="# demo\n\n## Blocker\n\nbecause.\n"), p)


def test_inspect_prints_markdown(tmp_path: Path, monkeypatch) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / ".git").mkdir()
    _seed(repo)
    monkeypatch.chdir(repo)
    result = CliRunner().invoke(app, ["inspect", "001"])
    assert result.exit_code == 0, result.stdout
    assert "001" in result.stdout
    assert "Blocker" in result.stdout
