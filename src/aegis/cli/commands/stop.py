from __future__ import annotations

from pathlib import Path

import typer

from aegis.cli.commands.init import AEGIS_DIRNAME


def register(app: typer.Typer) -> None:
    @app.command(help="Halt all (or one) task at the next checkpoint.")
    def stop(task_id: str | None = typer.Argument(None)) -> None:
        repo = Path.cwd().resolve()
        aegis = repo / AEGIS_DIRNAME
        if not aegis.exists():
            raise typer.BadParameter(f"No {AEGIS_DIRNAME}/ at {repo}.")
        flag = aegis / (".stop" if task_id is None else f".stop.{task_id}")
        flag.touch()
        scope = "all tasks" if task_id is None else f"task {task_id}"
        typer.echo(f"Stop signal raised for {scope}: {flag}")
