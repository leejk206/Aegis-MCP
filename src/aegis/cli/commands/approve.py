from __future__ import annotations

from pathlib import Path

import typer

from aegis.cli.commands.init import AEGIS_DIRNAME
from aegis.core.config import load_config
from aegis.graph.runtime import resume_after_approve


def register(app: typer.Typer) -> None:
    @app.command(help="Approve a review/-bound task: merge and run Docs.")
    def approve(task_id: str = typer.Argument(...)) -> None:
        repo = Path.cwd().resolve()
        aegis = repo / AEGIS_DIRNAME
        if not aegis.exists():
            raise typer.BadParameter(f"No {AEGIS_DIRNAME}/ here.")
        config = load_config(aegis / "config.yaml")
        resume_after_approve(
            task_id=task_id,
            aegis_dir=aegis,
            repo_root=repo,
            config=config,
        )
        typer.echo(f"approved {task_id}: merged and Docs ran")
