from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from pathlib import Path

import frontmatter
from pydantic import BaseModel, ConfigDict, Field


class TaskStatus(str, Enum):
    BACKLOG = "backlog"
    IN_PROGRESS = "in-progress"
    REVIEW = "review"
    DONE = "done"
    BLOCKED = "blocked"
    REJECTED = "rejected"


class Priority(str, Enum):
    P0 = "P0"
    P1 = "P1"
    P2 = "P2"
    P3 = "P3"


class TaskBudget(BaseModel):
    model_config = ConfigDict(extra="forbid")

    usd: float = 2.00
    minutes: int = 30


class TaskFrontmatter(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    title: str
    status: TaskStatus = TaskStatus.BACKLOG
    priority: Priority = Priority.P2
    budget: TaskBudget = Field(default_factory=TaskBudget)
    created: datetime
    started: datetime | None = None
    completed: datetime | None = None
    worktree: str | None = None
    trace_id: str | None = None
    pr_branch: str | None = None
    dependencies: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)


@dataclass
class Task:
    frontmatter: TaskFrontmatter
    body: str


_SLUG_STRIP = re.compile(r"[^a-z0-9-]+")
_SLUG_RUNS = re.compile(r"-+")


def slugify(title: str) -> str:
    s = title.lower().strip()
    s = re.sub(r"\s+", "-", s)
    s = _SLUG_STRIP.sub("", s)
    s = _SLUG_RUNS.sub("-", s).strip("-")
    return s or "task"


def task_filename(task_id: str, title: str) -> str:
    return f"{task_id}-{slugify(title)}.md"


def parse_task(path: Path) -> Task:
    post = frontmatter.load(str(path))
    fm = TaskFrontmatter.model_validate(dict(post.metadata))
    return Task(frontmatter=fm, body=post.content)


def serialize_task(task: Task) -> str:
    metadata = task.frontmatter.model_dump(mode="json", exclude_none=False)
    post = frontmatter.Post(content=task.body, **metadata)
    return frontmatter.dumps(post)


def write_task(task: Task, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(serialize_task(task), encoding="utf-8")


_STATUS_SUBDIRS = (
    "backlog",
    "in-progress",
    "review",
    "done",
    "blocked",
    "rejected",
)


def next_task_id(aegis_dir: Path) -> str:
    max_id = 0
    pattern = re.compile(r"^(\d+)-")
    for sub in _STATUS_SUBDIRS:
        d = aegis_dir / sub
        if not d.exists():
            continue
        for f in d.glob("*.md"):
            m = pattern.match(f.name)
            if m:
                max_id = max(max_id, int(m.group(1)))
    return f"{max_id + 1:03d}"
