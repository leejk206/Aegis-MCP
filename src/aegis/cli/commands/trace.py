"""``aegis trace <id>`` — open a task trace in the configured dashboard."""

from __future__ import annotations

import os
import webbrowser
from pathlib import Path

import typer

from aegis.cli.commands.init import AEGIS_DIRNAME
from aegis.core.config import load_config
from aegis.core.lifecycle import find_task

__all__ = ["register"]


def _resolve_url(config, trace_id: str) -> str | None:
    if config.observability.langsmith.enabled and os.environ.get("LANGSMITH_API_KEY"):
        project = config.observability.langsmith.project or "aegis"
        return f"https://smith.langchain.com/o/-/projects/p/{project}/r/{trace_id}"
    if config.observability.langfuse.enabled:
        base = config.observability.langfuse.url.rstrip("/")
        return f"{base}/trace/{trace_id}"
    return None


def register(app: typer.Typer) -> None:
    @app.command(help="Open a task's trace in the configured dashboard.")
    def trace(task_id: str = typer.Argument(...)) -> None:
        repo = Path.cwd().resolve()
        aegis = repo / AEGIS_DIRNAME
        if not aegis.exists():
            raise typer.BadParameter(f"No {AEGIS_DIRNAME}/ here.")
        config = load_config(aegis / "config.yaml")
        found = find_task(aegis, task_id)
        if found is None:
            raise typer.BadParameter(f"task {task_id} not found")
        task, _ = found
        trace_id = task.frontmatter.trace_id
        if not trace_id:
            typer.echo(f"task {task_id} has no trace_id yet (run it first)", err=True)
            raise typer.Exit(code=1)
        url = _resolve_url(config, trace_id)
        if url is None:
            typer.echo(
                "no remote dashboard configured (langsmith/langfuse both off). "
                f"Use `aegis logs {task_id}` for the local mirror."
            )
            return
        webbrowser.open(url)
        typer.echo(url)
