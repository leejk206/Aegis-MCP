from __future__ import annotations

from pathlib import Path

import typer

from aegis.cli.commands.init import AEGIS_DIRNAME
from aegis.core.lifecycle import find_task, transition
from aegis.core.task import TaskStatus, write_task


def register(app: typer.Typer) -> None:
    @app.command(help="Retry a blocked or rejected task.")
    def retry(
        task_id: str = typer.Argument(...),
        budget_usd: float | None = typer.Option(None, "--budget-usd"),
        from_node: str | None = typer.Option(None, "--from"),
    ) -> None:
        repo = Path.cwd().resolve()
        aegis = repo / AEGIS_DIRNAME
        if not aegis.exists():
            raise typer.BadParameter(f"No {AEGIS_DIRNAME}/ here.")
        found = find_task(aegis, task_id)
        if found is None:
            raise typer.BadParameter(f"task {task_id} not found")
        task, task_path = found
        if task.frontmatter.status not in (TaskStatus.BLOCKED, TaskStatus.REJECTED):
            raise typer.BadParameter(
                f"task {task_id} is in {task.frontmatter.status.value}; "
                f"only blocked/rejected can be retried"
            )
        if budget_usd is not None:
            task.frontmatter.budget.usd = budget_usd
            write_task(task, task_path)
        new_path = transition(task_path, aegis, TaskStatus.BACKLOG)
        if from_node:
            typer.echo(
                f"(retry --from {from_node} accepted but Phase 5 will honor it; "
                f"Phase 4 reruns from PM)"
            )
        typer.echo(f"retrying {task_id}: moved to {new_path.relative_to(aegis)}")
