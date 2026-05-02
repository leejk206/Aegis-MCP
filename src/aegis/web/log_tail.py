"""Read the last N lines of a JSONL trace file as formatted display strings.

Reuses :func:`aegis.cli.commands.logs._format_line` so the dashboard
shows the same per-span line format as `aegis logs`.
"""

from __future__ import annotations

import json
from collections import deque
from pathlib import Path

from aegis.cli.commands.logs import _format_line

__all__ = ["tail_jsonl"]


def tail_jsonl(path: Path, max_lines: int = 200) -> list[str]:
    if not path.exists():
        return []
    lines: deque[str] = deque(maxlen=max_lines)
    with open(path, encoding="utf-8") as f:
        for raw in f:
            raw = raw.strip()
            if not raw:
                continue
            try:
                rec = json.loads(raw)
            except json.JSONDecodeError:
                continue
            lines.append(_format_line(rec))
    return list(lines)
