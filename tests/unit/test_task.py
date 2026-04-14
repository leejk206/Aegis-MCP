from datetime import UTC, datetime
from pathlib import Path

import pytest

from aegis.core.task import (
    Priority,
    Task,
    TaskBudget,
    TaskFrontmatter,
    TaskStatus,
    next_task_id,
    parse_task,
    slugify,
    task_filename,
    write_task,
)


@pytest.fixture
def sample_task() -> Task:
    return Task(
        frontmatter=TaskFrontmatter(
            id="001",
            title="Add rate limiting to login API",
            status=TaskStatus.BACKLOG,
            priority=Priority.P1,
            budget=TaskBudget(usd=2.00, minutes=30),
            created=datetime(2026, 4, 14, 23, 10, 0, tzinfo=UTC),
            tags=["api", "security"],
        ),
        body=(
            "# Add rate limiting to login API\n\n"
            "Login endpoint currently accepts unlimited attempts. "
            "Add per-IP rate limiting.\n"
        ),
    )


def test_slugify_basic() -> None:
    assert slugify("Add rate limiting to login API") == "add-rate-limiting-to-login-api"


def test_slugify_strips_punctuation() -> None:
    assert slugify("Fix bug #42: broken!") == "fix-bug-42-broken"


def test_slugify_empty_fallback() -> None:
    assert slugify("!!!") == "task"
    assert slugify("") == "task"


def test_task_filename_format() -> None:
    assert task_filename("001", "Add rate limiting") == "001-add-rate-limiting.md"


def test_serialize_and_parse_roundtrip(tmp_path: Path, sample_task: Task) -> None:
    path = tmp_path / "001-add-rate-limiting.md"
    write_task(sample_task, path)

    loaded = parse_task(path)
    assert loaded.frontmatter.id == "001"
    assert loaded.frontmatter.title == sample_task.frontmatter.title
    assert loaded.frontmatter.status == TaskStatus.BACKLOG
    assert loaded.frontmatter.priority == Priority.P1
    assert loaded.frontmatter.budget.usd == pytest.approx(2.00)
    assert loaded.frontmatter.tags == ["api", "security"]
    assert "Login endpoint" in loaded.body


def test_serialize_preserves_appended_sections(tmp_path: Path, sample_task: Task) -> None:
    path = tmp_path / "001-task.md"
    sample_task.body += "\n\n## Plan\n1. Add dependency\n2. Wire limiter\n"
    write_task(sample_task, path)
    loaded = parse_task(path)
    assert "## Plan" in loaded.body
    assert "Wire limiter" in loaded.body


def test_next_task_id_empty_dir(tmp_path: Path) -> None:
    assert next_task_id(tmp_path) == "001"


def test_next_task_id_finds_max_across_directories(tmp_path: Path) -> None:
    for sub in ["backlog", "in-progress", "done"]:
        (tmp_path / sub).mkdir()
    stub = "---\nid: '{tid}'\ntitle: x\ncreated: 2026-04-14T00:00:00+00:00\n---\n"
    (tmp_path / "backlog" / "005-new.md").write_text(stub.format(tid="005"))
    (tmp_path / "in-progress" / "012-active.md").write_text(stub.format(tid="012"))
    (tmp_path / "done" / "009-finished.md").write_text(stub.format(tid="009"))
    assert next_task_id(tmp_path) == "013"
