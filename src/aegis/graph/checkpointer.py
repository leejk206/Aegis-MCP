"""Thin wrapper around ``langgraph.checkpoint.sqlite.SqliteSaver``.

The wrapper hides one detail: in current LangGraph releases the saver
is constructed via ``SqliteSaver.from_conn_string(...)`` and used as a
context manager. The runtime always opens the saver with the same
``<aegis_dir>/checkpoint.db`` path, so this module centralises that
convention.
"""
from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from langgraph.checkpoint.sqlite import SqliteSaver

__all__ = ["checkpoint_db_path", "open_checkpointer"]


def checkpoint_db_path(aegis_dir: Path) -> Path:
    return aegis_dir / "checkpoint.db"


@contextmanager
def open_checkpointer(aegis_dir: Path) -> Iterator[SqliteSaver]:
    aegis_dir.mkdir(parents=True, exist_ok=True)
    db = checkpoint_db_path(aegis_dir)
    with SqliteSaver.from_conn_string(str(db)) as saver:
        yield saver
