from __future__ import annotations

from pathlib import Path

from aegis.graph.checkpointer import (
    checkpoint_db_path,
    open_checkpointer,
)


def test_checkpoint_db_path_is_under_aegis_dir(tmp_path: Path) -> None:
    aegis = tmp_path / ".aegis"
    aegis.mkdir()
    p = checkpoint_db_path(aegis)
    assert p == aegis / "checkpoint.db"


def test_open_checkpointer_yields_a_saver(tmp_path: Path) -> None:
    aegis = tmp_path / ".aegis"
    aegis.mkdir()
    with open_checkpointer(aegis) as saver:
        assert saver is not None
        # Saver must support the langgraph BaseCheckpointSaver surface
        assert hasattr(saver, "put")
        assert hasattr(saver, "get_tuple")
    # File should exist after exit
    assert (aegis / "checkpoint.db").exists()
