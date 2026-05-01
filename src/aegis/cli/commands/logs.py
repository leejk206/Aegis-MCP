"""``aegis logs <id> [--follow]`` — tail a task's JSONL span log."""

from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import typer

from aegis.cli.commands.init import AEGIS_DIRNAME

__all__ = ["register"]


def _format_line(record: dict[str, Any]) -> str:
    start_ns = int(record.get("start_time_ns") or 0)
    duration_ms = int(record.get("duration_ns") or 0) // 1_000_000
    ts = datetime.fromtimestamp(start_ns / 1e9, tz=timezone.utc).strftime("%H:%M:%S")
    name = record.get("name", "?")
    attrs = record.get("attributes") or {}
    verdict = attrs.get("aegis.verdict")
    blocker = attrs.get("aegis.blocked_reason")
    pieces = [f"[{ts}]", name, f"({duration_ms}ms)"]
    if verdict:
        pieces.append(f"verdict={verdict}")
    if blocker:
        pieces.append(f"blocked={blocker}")
    return " ".join(pieces)


def _print_existing(path: Path) -> int:
    """Print every line in ``path``; return the byte offset reached."""
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue
            typer.echo(_format_line(record))
        return f.tell()


def _follow(path: Path, offset: int) -> None:
    while True:
        try:
            with open(path, encoding="utf-8") as f:
                f.seek(offset)
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        record = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    typer.echo(_format_line(record))
                offset = f.tell()
        except FileNotFoundError:
            pass
        time.sleep(0.25)


def register(app: typer.Typer) -> None:
    @app.command(help="Tail a task's JSONL trace.")
    def logs(
        task_id: str = typer.Argument(...),
        follow: bool = typer.Option(False, "--follow", "-f"),
    ) -> None:
        repo = Path.cwd().resolve()
        aegis = repo / AEGIS_DIRNAME
        if not aegis.exists():
            raise typer.BadParameter(f"No {AEGIS_DIRNAME}/ here.")
        trace_path = aegis / "trace" / f"{task_id}.jsonl"
        if not trace_path.exists():
            typer.echo(f"no trace for task {task_id}", err=True)
            raise typer.Exit(code=1)
        offset = _print_existing(trace_path)
        if follow:
            try:
                _follow(trace_path, offset)
            except KeyboardInterrupt:
                raise typer.Exit(code=0)
