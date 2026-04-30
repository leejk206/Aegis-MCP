"""Thin wrappers around the LangGraph SQLite checkpointers.

Two wrappers are exposed:

* :func:`open_checkpointer` returns the sync ``SqliteSaver`` for callers
  that drive the graph synchronously (still used by the checkpointer
  unit tests and any sync utility code).
* :func:`open_async_checkpointer` returns the async ``AsyncSqliteSaver``
  required when the graph runs async nodes (``ainvoke``); the runtime
  driver in :mod:`aegis.graph.runtime` always uses this variant.

Both flavours write to the same ``<aegis_dir>/checkpoint.db`` file, so a
task started under one wrapper can be resumed under the other.
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Iterator
from contextlib import asynccontextmanager, contextmanager
from pathlib import Path

from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

__all__ = [
    "checkpoint_db_path",
    "open_checkpointer",
    "open_async_checkpointer",
]


def checkpoint_db_path(aegis_dir: Path) -> Path:
    return aegis_dir / "checkpoint.db"


@contextmanager
def open_checkpointer(aegis_dir: Path) -> Iterator[SqliteSaver]:
    aegis_dir.mkdir(parents=True, exist_ok=True)
    db = checkpoint_db_path(aegis_dir)
    with SqliteSaver.from_conn_string(str(db)) as saver:
        yield saver


@asynccontextmanager
async def open_async_checkpointer(aegis_dir: Path) -> AsyncIterator[AsyncSqliteSaver]:
    aegis_dir.mkdir(parents=True, exist_ok=True)
    db = checkpoint_db_path(aegis_dir)
    async with AsyncSqliteSaver.from_conn_string(str(db)) as saver:
        yield saver
