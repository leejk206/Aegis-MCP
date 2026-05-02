"""Reserved for future not-yet-implemented commands.

Currently empty — Phase 6 promoted the ``web`` stub to a real command.
"""

from __future__ import annotations

import typer

__all__ = ["register_stubs"]


def register_stubs(app: typer.Typer) -> None:  # noqa: ARG001
    """No-op: kept for forward compatibility with main.py wiring."""
