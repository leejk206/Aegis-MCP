from __future__ import annotations

import typer

from aegis import __version__
from aegis.cli.commands.stubs import register_stubs

app = typer.Typer(
    name="aegis",
    help="Aegis — personal AI engineering team CLI.",
    no_args_is_help=True,
)


def _version_callback(value: bool) -> None:
    if value:
        typer.echo(f"aegis {__version__}")
        raise typer.Exit()


@app.callback()
def _root(
    version: bool = typer.Option(
        False,
        "--version",
        callback=_version_callback,
        is_eager=True,
        help="Show version and exit.",
    ),
) -> None:
    """Aegis CLI root."""


register_stubs(app)

from aegis.cli.commands.config import register as register_config  # noqa: E402
from aegis.cli.commands.init import register as register_init  # noqa: E402
from aegis.cli.commands.task import register as register_task  # noqa: E402

register_init(app)
register_task(app)
register_config(app)
