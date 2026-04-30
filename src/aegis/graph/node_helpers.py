from __future__ import annotations

from pathlib import Path

from aegis.agents import AegisAgent
from aegis.agents.registry import RoleName
from aegis.core.config import AegisConfig
from aegis.core.task import parse_task, write_task
from aegis.graph.state import TeamState

__all__ = ["Stopped", "check_stop_flag", "append_section", "make_agent"]


class Stopped(Exception):
    """Raised when a stop flag forces a node to abort cleanly."""


def check_stop_flag(aegis_dir: Path, task_id: str) -> None:
    if (aegis_dir / ".stop").exists():
        raise Stopped("global .stop flag is set")
    if (aegis_dir / f".stop.{task_id}").exists():
        raise Stopped(f"task-specific .stop.{task_id} flag is set")


def append_section(task_path: Path, header: str, body: str) -> None:
    """Append a ``## <header>`` block to the task's markdown body.

    Frontmatter is preserved verbatim.
    """
    task = parse_task(task_path)
    new_body = task.body
    if not new_body.endswith("\n"):
        new_body += "\n"
    new_body += f"\n## {header}\n\n{body.rstrip()}\n"
    task.body = new_body
    write_task(task, task_path)


def make_agent(
    role: RoleName,
    state: TeamState,
    config: AegisConfig,
    *,
    shell_allow_cmds: str | None = None,
) -> AegisAgent:
    return AegisAgent(
        role=role,
        worktree=Path(state["worktree_path"]),
        config=config,
        shell_allow_cmds=shell_allow_cmds,
    )
