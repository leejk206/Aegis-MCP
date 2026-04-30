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

from aegis.cli.commands.approve import register as register_approve  # noqa: E402
from aegis.cli.commands.config import register as register_config  # noqa: E402
from aegis.cli.commands.daemon import register as register_daemon  # noqa: E402
from aegis.cli.commands.init import register as register_init  # noqa: E402
from aegis.cli.commands.inspect import register as register_inspect  # noqa: E402
from aegis.cli.commands.reject import register as register_reject  # noqa: E402
from aegis.cli.commands.retry import register as register_retry  # noqa: E402
from aegis.cli.commands.run import register as register_run  # noqa: E402
from aegis.cli.commands.status import register as register_status  # noqa: E402
from aegis.cli.commands.stop import register as register_stop  # noqa: E402
from aegis.cli.commands.task import register as register_task  # noqa: E402

register_init(app)
register_task(app)
register_config(app)
register_run(app)
register_status(app)
register_stop(app)
register_approve(app)
register_reject(app)
register_retry(app)
register_inspect(app)
register_daemon(app)
