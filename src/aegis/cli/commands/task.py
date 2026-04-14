from __future__ import annotations

import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import typer

from aegis.cli.commands.init import AEGIS_DIRNAME
from aegis.core.lifecycle import find_task, list_tasks
from aegis.core.task import (
    Priority,
    Task,
    TaskBudget,
    TaskFrontmatter,
    TaskStatus,
    next_task_id,
    serialize_task,
    task_filename,
    write_task,
)


def _aegis_dir_for(target: Path) -> Path:
    d = target / AEGIS_DIRNAME
    if not d.exists():
        raise typer.BadParameter(
            f"No .aegis/ directory at {target}. Run `aegis init` first."
        )
    return d


def run_task_add(
    target: Path,
    *,
    title: str,
    priority: str,
    budget_usd: float,
    budget_minutes: int,
) -> Path:
    aegis_dir = _aegis_dir_for(target)
    task_id = next_task_id(aegis_dir)
    fm = TaskFrontmatter(
        id=task_id,
        title=title,
        status=TaskStatus.BACKLOG,
        priority=Priority(priority),
        budget=TaskBudget(usd=budget_usd, minutes=budget_minutes),
        created=datetime.now(tz=timezone.utc),
    )
    body = f"# {title}\n\n<!-- describe the task here -->\n"
    task = Task(frontmatter=fm, body=body)
    path = aegis_dir / "backlog" / task_filename(task_id, title)
    write_task(task, path)
    return path


def run_task_list(
    target: Path,
    *,
    status: str | None,
) -> list[dict[str, Any]]:
    aegis_dir = _aegis_dir_for(target)
    status_enum = TaskStatus(status) if status else None
    rows: list[dict[str, Any]] = []
    for task, path in list_tasks(aegis_dir, status=status_enum):
        rows.append(
            {
                "id": task.frontmatter.id,
                "title": task.frontmatter.title,
                "status": task.frontmatter.status.value,
                "priority": task.frontmatter.priority.value,
                "path": str(path),
            }
        )
    return rows


def run_task_show(target: Path, *, task_id: str) -> str:
    aegis_dir = _aegis_dir_for(target)
    found = find_task(aegis_dir, task_id)
    if found is None:
        raise typer.BadParameter(f"task {task_id} not found")
    task, _ = found
    return serialize_task(task)


def run_task_edit(target: Path, *, task_id: str) -> None:
    aegis_dir = _aegis_dir_for(target)
    found = find_task(aegis_dir, task_id)
    if found is None:
        raise typer.BadParameter(f"task {task_id} not found")
    _, path = found
    editor = os.environ.get("EDITOR", "vi")
    subprocess.run([editor, str(path)], check=False)


def register(app: typer.Typer) -> None:
    task_app = typer.Typer(help="Task management: add, list, show, edit.")

    @task_app.command("add", help="Create a new task in backlog/.")
    def add(
        title: str = typer.Argument(..., help="Task title"),
        priority: str = typer.Option("P2", "--priority", help="P0|P1|P2|P3"),
        budget_usd: float = typer.Option(2.0, "--budget-usd"),
        budget_min: int = typer.Option(30, "--budget-min"),
    ) -> None:
        path = run_task_add(
            Path.cwd(),
            title=title,
            priority=priority,
            budget_usd=budget_usd,
            budget_minutes=budget_min,
        )
        typer.echo(f"Created {path}")

    @task_app.command("list", help="List tasks (optionally filtered by status).")
    def list_cmd(
        status: str | None = typer.Option(None, "--status"),
    ) -> None:
        rows = run_task_list(Path.cwd(), status=status)
        if not rows:
            typer.echo("(no tasks)")
            return
        for r in rows:
            typer.echo(f"{r['id']}  [{r['status']:11}]  {r['priority']}  {r['title']}")

    @task_app.command("show", help="Print a task's full markdown.")
    def show(task_id: str = typer.Argument(...)) -> None:
        rendered = run_task_show(Path.cwd(), task_id=task_id)
        typer.echo(rendered)

    @task_app.command("edit", help="Open a task in $EDITOR.")
    def edit(task_id: str = typer.Argument(...)) -> None:
        run_task_edit(Path.cwd(), task_id=task_id)

    app.add_typer(task_app, name="task")
