from __future__ import annotations

from pathlib import Path

import typer

from aegis.cli.commands.init import AEGIS_DIRNAME
from aegis.graph.runtime import reject_task


def register(app: typer.Typer) -> None:
    @app.command(help="Reject a review/-bound task and discard its worktree.")
    def reject(
        task_id: str = typer.Argument(...),
        reason: str | None = typer.Argument(None),
    ) -> None:
        repo = Path.cwd().resolve()
        aegis = repo / AEGIS_DIRNAME
        if not aegis.exists():
            raise typer.BadParameter(f"No {AEGIS_DIRNAME}/ here.")
        reject_task(
            task_id=task_id,
            aegis_dir=aegis,
            repo_root=repo,
            reason=reason,
        )
        typer.echo(f"rejected {task_id}")
