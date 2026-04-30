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
    daemon_app = typer.Typer(help="Background worker mode. (Phase 4)")

    @daemon_app.command("start")
    def daemon_start() -> None:
        _not_implemented("daemon start", "4")

    @daemon_app.command("stop")
    def daemon_stop() -> None:
        _not_implemented("daemon stop", "4")

    @daemon_app.command("status")
    def daemon_status() -> None:
        _not_implemented("daemon status", "4")

    @daemon_app.command("restart")
    def daemon_restart() -> None:
        _not_implemented("daemon restart", "4")

    app.add_typer(daemon_app, name="daemon")

    @app.command(help="Inspect a task's full trajectory. (Phase 4)")
    def inspect(task_id: str) -> None:
        _not_implemented("inspect", "4")

    @app.command(help="Tail a task's log. (Phase 5)")
    def logs(task_id: str, follow: bool = typer.Option(False, "--follow")) -> None:
        _not_implemented("logs", "5")

    @app.command(help="Open a task trace in the browser. (Phase 5)")
    def trace(task_id: str) -> None:
        _not_implemented("trace", "5")

    @app.command(help="Start the read-only dashboard. (Phase 6)")
    def web(
        port: int = typer.Option(8765, "--port"),
        host: str = typer.Option("127.0.0.1", "--host"),
    ) -> None:
        _not_implemented("web", "6")
