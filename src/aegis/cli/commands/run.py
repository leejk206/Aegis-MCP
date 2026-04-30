from __future__ import annotations

from pathlib import Path

import typer

from aegis.cli.commands.init import AEGIS_DIRNAME
from aegis.core.config import load_config
from aegis.core.lifecycle import find_task, list_tasks
from aegis.core.task import TaskStatus
from aegis.graph.runtime import run_one_task


def _aegis_dir(repo_root: Path) -> Path:
    d = repo_root / AEGIS_DIRNAME
    if not d.exists():
        raise typer.BadParameter(f"No {AEGIS_DIRNAME}/ at {repo_root}; run `aegis init` first.")
    return d


def _config_for(aegis_dir: Path):
    return load_config(aegis_dir / "config.yaml")


def register(app: typer.Typer) -> None:
    @app.command(help="Run the team graph in the foreground.")
    def run(
        task: str | None = typer.Option(None, "--task", help="Run only this task id."),
        once: bool = typer.Option(False, "--once", help="Drain backlog once and exit."),
        parallel: int | None = typer.Option(None, "--parallel", help="Reserved for Phase 5."),
    ) -> None:
        repo = Path.cwd().resolve()
        aegis = _aegis_dir(repo)
        config = _config_for(aegis)

        if task is not None:
            found = find_task(aegis, task)
            if found is None:
                raise typer.BadParameter(f"task {task} not found")
            _, task_path = found
            run_one_task(
                task_path=task_path,
                aegis_dir=aegis,
                repo_root=repo,
                config=config,
            )
            return

        # Drain backlog
        backlog = list_tasks(aegis, status=TaskStatus.BACKLOG)
        if not backlog:
            typer.echo("backlog is empty")
            return
        for _, task_path in backlog:
            run_one_task(
                task_path=task_path,
                aegis_dir=aegis,
                repo_root=repo,
                config=config,
            )
        if not once and parallel:
            typer.echo("(--parallel is reserved for Phase 5; treating as --once)")
