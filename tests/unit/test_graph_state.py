from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from aegis.core.task import Priority, Task, TaskBudget, TaskFrontmatter, TaskStatus
from aegis.graph.state import TeamState, initial_state


def _make_task(task_id: str = "001", title: str = "demo") -> Task:
    fm = TaskFrontmatter(
        id=task_id,
        title=title,
        status=TaskStatus.IN_PROGRESS,
        priority=Priority.P2,
        budget=TaskBudget(usd=2.0, minutes=30),
        created=datetime.now(tz=UTC),
    )
    return Task(frontmatter=fm, body=f"# {title}\n\nbody.\n")


def test_initial_state_populates_identity_fields(tmp_path: Path) -> None:
    task = _make_task()
    repo = tmp_path / "repo"
    wt = tmp_path / "worktrees" / "001-demo"
    state: TeamState = initial_state(
        task=task,
        task_path=tmp_path / ".aegis" / "in-progress" / "001-demo.md",
        worktree_path=wt,
        target_repo_root=repo,
    )
    assert state["task_id"] == "001"
    assert state["worktree_path"] == str(wt)
    assert state["target_repo_root"] == str(repo)
    assert state["plan"] is None
    assert state["test_report"] is None
    assert state["review"] is None
    assert state["pr_branch"] is None
    assert state["awaiting_human"] is False
    assert state["blocked_reason"] is None
    assert state["retry_counts"] == {"dev_on_qa_fail": 0, "dev_on_review": 0}


def test_initial_state_uses_task_budget(tmp_path: Path) -> None:
    task = _make_task()
    state = initial_state(
        task=task,
        task_path=tmp_path / "001-demo.md",
        worktree_path=tmp_path / "wt",
        target_repo_root=tmp_path / "repo",
    )
    assert state["budget_remaining"]["usd"] == 2.0
    assert state["budget_remaining"]["seconds"] == 30 * 60
    assert state["budget_remaining"]["input_tokens"] == 0
    assert state["budget_remaining"]["output_tokens"] == 0
