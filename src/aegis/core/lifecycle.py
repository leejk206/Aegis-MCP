from __future__ import annotations

from pathlib import Path

from aegis.core.task import (
    Task,
    TaskStatus,
    parse_task,
    write_task,
)

STATUS_DIRS: dict[TaskStatus, str] = {
    TaskStatus.BACKLOG: "backlog",
    TaskStatus.IN_PROGRESS: "in-progress",
    TaskStatus.REVIEW: "review",
    TaskStatus.DONE: "done",
    TaskStatus.BLOCKED: "blocked",
    TaskStatus.REJECTED: "rejected",
}


class LifecycleError(Exception):
    """Raised on invalid lifecycle operations."""


def transition(
    task_path: Path,
    aegis_dir: Path,
    to_status: TaskStatus,
) -> Path:
    """Update the task's status and move its file to the matching subdir.

    Returns the new path.
    """
    if not task_path.exists():
        raise LifecycleError(f"task not found: {task_path}")
    task = parse_task(task_path)
    task.frontmatter.status = to_status
    target_dir = aegis_dir / STATUS_DIRS[to_status]
    target_dir.mkdir(parents=True, exist_ok=True)
    # Write with the updated status back to the source first, then move,
    # so the final file on disk reflects the new status atomically.
    write_task(task, task_path)
    new_path = target_dir / task_path.name
    task_path.rename(new_path)
    return new_path


def list_tasks(
    aegis_dir: Path,
    status: TaskStatus | None = None,
) -> list[tuple[Task, Path]]:
    """Return all tasks (optionally filtered by status).

    Results are grouped by status in enum definition order, and sorted
    by filename (id-prefixed) within each group. Callers that need a
    globally-sorted list must sort the result themselves.
    """
    result: list[tuple[Task, Path]] = []
    statuses: list[TaskStatus] = [status] if status is not None else list(TaskStatus)
    for s in statuses:
        d = aegis_dir / STATUS_DIRS[s]
        if not d.exists():
            continue
        for f in sorted(d.glob("*.md")):
            result.append((parse_task(f), f))
    return result


def find_task(aegis_dir: Path, task_id: str) -> tuple[Task, Path] | None:
    for s in TaskStatus:
        d = aegis_dir / STATUS_DIRS[s]
        if not d.exists():
            continue
        for f in d.glob(f"{task_id}-*.md"):
            return parse_task(f), f
    return None
