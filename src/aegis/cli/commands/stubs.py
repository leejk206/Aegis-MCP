from __future__ import annotations

import typer


def _not_implemented(command: str, phase: str) -> None:
    typer.echo(
        f"`aegis {command}` is not implemented yet. See Phase {phase} "
        f"in docs/superpowers/specs/2026-04-14-aegis-ai-engineering-team-design.md",
        err=True,
    )
    raise typer.Exit(code=2)


def register_stubs(app: typer.Typer) -> None:
    @app.command(help="Start the read-only dashboard. (Phase 6)")
    def web(
        port: int = typer.Option(8765, "--port"),
        host: str = typer.Option("127.0.0.1", "--host"),
    ) -> None:
        _not_implemented("web", "6")
