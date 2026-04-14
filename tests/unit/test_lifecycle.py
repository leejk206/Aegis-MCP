from datetime import UTC, datetime
from pathlib import Path

import pytest

from aegis.core.lifecycle import (
    STATUS_DIRS,
    find_task,
    list_tasks,
    transition,
)
from aegis.core.task import (
    Priority,
    Task,
    TaskBudget,
    TaskFrontmatter,
    TaskStatus,
    write_task,
)


@pytest.fixture
def aegis_dir(tmp_path: Path) -> Path:
    d = tmp_path / ".aegis"
    for sub in STATUS_DIRS.values():
        (d / sub).mkdir(parents=True)
    return d


def _make_task(task_id: str, title: str, status: TaskStatus) -> Task:
    return Task(
        frontmatter=TaskFrontmatter(
            id=task_id,
            title=title,
            status=status,
            priority=Priority.P2,
            budget=TaskBudget(),
            created=datetime(2026, 4, 14, tzinfo=UTC),
        ),
        body=f"# {title}\n",
    )


def test_transition_moves_file_and_updates_status(aegis_dir: Path) -> None:
    task = _make_task("001", "First", TaskStatus.BACKLOG)
    src = aegis_dir / "backlog" / "001-first.md"
    write_task(task, src)

    new_path = transition(src, aegis_dir, TaskStatus.IN_PROGRESS)

    assert not src.exists()
    assert new_path.exists()
    assert new_path.parent.name == "in-progress"

    from aegis.core.task import parse_task

    loaded = parse_task(new_path)
    assert loaded.frontmatter.status == TaskStatus.IN_PROGRESS


def test_transition_creates_target_dir_if_missing(tmp_path: Path) -> None:
    aegis = tmp_path / ".aegis"
    (aegis / "backlog").mkdir(parents=True)
    task = _make_task("001", "x", TaskStatus.BACKLOG)
    src = aegis / "backlog" / "001-x.md"
    write_task(task, src)

    new_path = transition(src, aegis, TaskStatus.BLOCKED)
    assert new_path.parent.name == "blocked"
    assert new_path.exists()


def test_list_tasks_all_statuses(aegis_dir: Path) -> None:
    write_task(_make_task("001", "a", TaskStatus.BACKLOG), aegis_dir / "backlog" / "001-a.md")
    write_task(
        _make_task("002", "b", TaskStatus.IN_PROGRESS),
        aegis_dir / "in-progress" / "002-b.md",
    )
    write_task(_make_task("003", "c", TaskStatus.DONE), aegis_dir / "done" / "003-c.md")

    results = list_tasks(aegis_dir)
    ids = [t.frontmatter.id for t, _ in results]
    assert set(ids) == {"001", "002", "003"}


def test_list_tasks_filtered_by_status(aegis_dir: Path) -> None:
    write_task(_make_task("001", "a", TaskStatus.BACKLOG), aegis_dir / "backlog" / "001-a.md")
    write_task(
        _make_task("002", "b", TaskStatus.IN_PROGRESS),
        aegis_dir / "in-progress" / "002-b.md",
    )

    backlog = list_tasks(aegis_dir, status=TaskStatus.BACKLOG)
    assert len(backlog) == 1
    assert backlog[0][0].frontmatter.id == "001"


def test_find_task_by_id(aegis_dir: Path) -> None:
    write_task(
        _make_task("042", "answer", TaskStatus.REVIEW),
        aegis_dir / "review" / "042-answer.md",
    )
    found = find_task(aegis_dir, "042")
    assert found is not None
    task, path = found
    assert task.frontmatter.title == "answer"
    assert "review" in str(path)


def test_find_task_missing(aegis_dir: Path) -> None:
    assert find_task(aegis_dir, "999") is None
