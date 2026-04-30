from __future__ import annotations

from pathlib import Path

import typer

from aegis.cli.commands.init import AEGIS_DIRNAME
from aegis.core.lifecycle import find_task
from aegis.core.task import serialize_task


def register(app: typer.Typer) -> None:
    @app.command(help="Print a task's full markdown.")
    def inspect(task_id: str = typer.Argument(...)) -> None:
        repo = Path.cwd().resolve()
        aegis = repo / AEGIS_DIRNAME
        if not aegis.exists():
            raise typer.BadParameter(f"No {AEGIS_DIRNAME}/ here.")
        found = find_task(aegis, task_id)
        if found is None:
            raise typer.BadParameter(f"task {task_id} not found")
        task, _ = found
        typer.echo(serialize_task(task))
