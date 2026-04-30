from __future__ import annotations

import os
import signal
import subprocess
import sys
from pathlib import Path

import typer

from aegis.cli.commands.init import AEGIS_DIRNAME

PIDFILE = ".daemon.pid"


def _aegis_dir(repo: Path) -> Path:
    d = repo / AEGIS_DIRNAME
    if not d.exists():
        raise typer.BadParameter(f"No {AEGIS_DIRNAME}/ at {repo}.")
    return d


def _is_pid_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def register(app: typer.Typer) -> None:
    daemon_app = typer.Typer(help="Background worker.")

    @daemon_app.command("start", help="Start the daemon (drains backlog in a loop).")
    def start() -> None:
        repo = Path.cwd().resolve()
        aegis = _aegis_dir(repo)
        pidpath = aegis / PIDFILE
        if pidpath.exists():
            pid = int(pidpath.read_text().strip() or "0")
            if pid and _is_pid_alive(pid):
                typer.echo(f"already running (pid {pid})")
                return
        # Use sys.executable to ensure the subprocess uses the same env.
        proc = subprocess.Popen(
            [sys.executable, "-m", "aegis.cli.main", "run", "--once"],
            cwd=str(repo),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
        pidpath.write_text(f"{proc.pid}\n")
        typer.echo(f"daemon started (pid {proc.pid})")

    @daemon_app.command("stop", help="Stop the daemon.")
    def stop() -> None:
        repo = Path.cwd().resolve()
        aegis = _aegis_dir(repo)
        pidpath = aegis / PIDFILE
        if not pidpath.exists():
            typer.echo("daemon is not running")
            return
        pid = int(pidpath.read_text().strip() or "0")
        if pid and _is_pid_alive(pid):
            os.kill(pid, signal.SIGTERM)
        pidpath.unlink(missing_ok=True)
        typer.echo(f"daemon stopped (pid {pid})")

    @daemon_app.command("status", help="Report daemon status.")
    def status() -> None:
        repo = Path.cwd().resolve()
        aegis = _aegis_dir(repo)
        pidpath = aegis / PIDFILE
        if not pidpath.exists():
            typer.echo("daemon: stopped")
            return
        pid = int(pidpath.read_text().strip() or "0")
        if pid and _is_pid_alive(pid):
            typer.echo(f"daemon: running (pid {pid})")
        else:
            typer.echo("daemon: stale pidfile (process gone)")

    @daemon_app.command("restart", help="Restart the daemon.")
    def restart() -> None:
        stop()
        start()

    app.add_typer(daemon_app, name="daemon")
