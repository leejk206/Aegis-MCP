"""``aegis web`` — start the read-only dashboard (uvicorn, foreground)."""

from __future__ import annotations

from pathlib import Path

import typer
import uvicorn

from aegis.cli.commands.init import AEGIS_DIRNAME
from aegis.core.config import load_config
from aegis.web.app import create_app


def register(app_root: typer.Typer) -> None:
    @app_root.command(help="Start the read-only dashboard.")
    def web(
        port: int = typer.Option(8765, "--port"),
        host: str = typer.Option("127.0.0.1", "--host"),
    ) -> None:
        repo = Path.cwd().resolve()
        aegis = repo / AEGIS_DIRNAME
        if not aegis.exists():
            raise typer.BadParameter(f"No {AEGIS_DIRNAME}/ here. Run `aegis init` first.")
        config = load_config(aegis / "config.yaml")
        fastapi_app = create_app(
            aegis_dir=aegis,
            repo_root=repo,
            config=config,
            host=host,
            port=port,
        )
        typer.echo(f"Aegis dashboard on http://{host}:{port}")
        uvicorn.run(fastapi_app, host=host, port=port, log_level="info")
