from __future__ import annotations

from pathlib import Path

import typer

from aegis.cli.commands.init import AEGIS_DIRNAME
from aegis.core.lifecycle import list_tasks
from aegis.core.task import TaskStatus


def register(app: typer.Typer) -> None:
    @app.command(help="Print the kanban view of all tasks.")
    def status(
        watch: bool = typer.Option(False, "--watch", help="Reserved for Phase 5."),
    ) -> None:
        repo = Path.cwd().resolve()
        aegis = repo / AEGIS_DIRNAME
        if not aegis.exists():
            typer.echo(f"No {AEGIS_DIRNAME}/ here. Run `aegis init` first.")
            raise typer.Exit(code=2)

        for status_value in TaskStatus:
            rows = list_tasks(aegis, status=status_value)
            if not rows:
                continue
            typer.echo(f"\n[{status_value.value.upper()}]")
            for task, _ in rows:
                fm = task.frontmatter
                typer.echo(f"  {fm.id}  {fm.priority.value}  {fm.title}")
        if watch:
            typer.echo("\n(--watch is reserved for Phase 5)")
