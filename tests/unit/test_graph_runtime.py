from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import patch

from aegis.core.config import AegisConfig, ProjectConfig
from aegis.core.task import (
    Priority,
    Task,
    TaskBudget,
    TaskFrontmatter,
    TaskStatus,
    parse_task,
    write_task,
)
from aegis.graph.runtime import (
    reject_task,
    resume_after_approve,
    run_one_task,
)


def _bootstrap_repo(tmp_path: Path) -> tuple[Path, Path]:
    repo = tmp_path / "repo"
    repo.mkdir()
    aegis = repo / ".aegis"
    for sub in (
        "backlog",
        "in-progress",
        "review",
        "done",
        "blocked",
        "rejected",
        ".worktrees",
    ):
        (aegis / sub).mkdir(parents=True, exist_ok=True)
    return repo, aegis


def _seed_task(aegis: Path, status: TaskStatus = TaskStatus.IN_PROGRESS) -> Path:
    p = aegis / status.value / "001-demo.md"
    fm = TaskFrontmatter(
        id="001",
        title="demo",
        status=status,
        priority=Priority.P2,
        budget=TaskBudget(),
        created=datetime.now(tz=UTC),
    )
    write_task(Task(frontmatter=fm, body="# demo\n"), p)
    return p


def _stub_nodes(verdict: str = "approve"):
    async def pm(s: dict) -> dict:
        return {
            "plan": {"summary": "p"},
            "implementation_status": "in_progress",
            "current_node": "pm",
        }

    async def dev(s: dict) -> dict:
        return {"implementation_status": "done", "current_node": "dev"}

    async def qa(s: dict) -> dict:
        return {
            "test_report": {"verdict": "pass", "summary": "ok"},
            "current_node": "qa",
        }

    async def reviewer(s: dict) -> dict:
        return {
            "review": {"verdict": verdict, "summary": "r"},
            "current_node": "reviewer",
        }

    async def docs(s: dict) -> dict:
        return {"current_node": "docs", "implementation_status": "done"}

    return {"pm": pm, "dev": dev, "qa": qa, "reviewer": reviewer, "docs": docs}


def test_run_one_task_pauses_at_docs_and_moves_to_review(tmp_path: Path) -> None:
    repo, aegis = _bootstrap_repo(tmp_path)
    p = _seed_task(aegis)

    with (
        patch("aegis.graph.runtime.create_worktree") as cw,
        patch("aegis.graph.runtime.remove_worktree") as rw,
        patch("aegis.graph.runtime.merge_worktree_into_main") as merge,
    ):
        cw.side_effect = lambda repo_root, worktree_path, branch: worktree_path.mkdir(
            parents=True, exist_ok=True
        )
        rw.side_effect = lambda *a, **kw: None
        merge.side_effect = lambda *a, **kw: None

        config = AegisConfig(project=ProjectConfig(name="t"))
        final = run_one_task(
            task_path=p,
            aegis_dir=aegis,
            repo_root=repo,
            config=config,
            node_overrides=_stub_nodes(verdict="approve"),
        )
        assert final["awaiting_human"] is True

    moved = next((aegis / "review").glob("001-*.md"), None)
    assert moved is not None
    # Worktree NOT removed on review pause
    rw.assert_not_called()
    merge.assert_not_called()


def test_run_one_task_blocks_on_blocker(tmp_path: Path) -> None:
    repo, aegis = _bootstrap_repo(tmp_path)
    p = _seed_task(aegis)

    async def pm_block(s: dict) -> dict:
        return {"blocked_reason": "ambiguous", "current_node": "pm"}

    overrides = _stub_nodes()
    overrides["pm"] = pm_block

    with (
        patch("aegis.graph.runtime.create_worktree") as cw,
        patch("aegis.graph.runtime.remove_worktree"),
        patch("aegis.graph.runtime.merge_worktree_into_main"),
    ):
        cw.side_effect = lambda repo_root, worktree_path, branch: worktree_path.mkdir(
            parents=True, exist_ok=True
        )
        config = AegisConfig(project=ProjectConfig(name="t"))
        final = run_one_task(
            task_path=p,
            aegis_dir=aegis,
            repo_root=repo,
            config=config,
            node_overrides=overrides,
        )
        assert final["blocked_reason"] == "ambiguous"

    moved = next((aegis / "blocked").glob("001-*.md"), None)
    assert moved is not None
    refreshed = parse_task(moved)
    assert "ambiguous" in refreshed.body


def test_resume_after_approve_runs_docs_and_moves_to_done(tmp_path: Path) -> None:
    repo, aegis = _bootstrap_repo(tmp_path)
    p = _seed_task(aegis)

    config = AegisConfig(project=ProjectConfig(name="t"))
    with (
        patch("aegis.graph.runtime.create_worktree") as cw,
        patch("aegis.graph.runtime.remove_worktree") as rw,
        patch("aegis.graph.runtime.merge_worktree_into_main") as merge,
    ):
        cw.side_effect = lambda repo_root, worktree_path, branch: worktree_path.mkdir(
            parents=True, exist_ok=True
        )
        rw.side_effect = lambda *a, **kw: None
        merge.side_effect = lambda *a, **kw: None

        # First run pauses at review/.
        run_one_task(
            task_path=p,
            aegis_dir=aegis,
            repo_root=repo,
            config=config,
            node_overrides=_stub_nodes(verdict="approve"),
        )
        # Now resume from interrupt.
        final = resume_after_approve(
            task_id="001",
            aegis_dir=aegis,
            repo_root=repo,
            config=config,
            node_overrides=_stub_nodes(verdict="approve"),
        )
    # Behavioural outcome: task ends in done/, merge + remove called.
    assert final["current_node"] == "docs"
    moved = next((aegis / "done").glob("001-*.md"), None)
    assert moved is not None
    merge.assert_called()
    rw.assert_called()


def test_reject_moves_to_rejected_and_removes_worktree(tmp_path: Path) -> None:
    repo, aegis = _bootstrap_repo(tmp_path)
    review_path = aegis / "review" / "001-demo.md"
    review_path.parent.mkdir(parents=True, exist_ok=True)
    fm = TaskFrontmatter(
        id="001",
        title="demo",
        status=TaskStatus.REVIEW,
        priority=Priority.P2,
        budget=TaskBudget(),
        created=datetime.now(tz=UTC),
    )
    write_task(Task(frontmatter=fm, body="# demo\n"), review_path)

    with patch("aegis.graph.runtime.remove_worktree") as rw:
        rw.side_effect = lambda *a, **kw: None
        reject_task(task_id="001", aegis_dir=aegis, repo_root=repo, reason="auth broke")

    assert next((aegis / "rejected").glob("001-*.md"), None) is not None


def test_run_one_task_writes_trace_id_to_frontmatter(tmp_path: Path) -> None:
    """After a graph run, the task's frontmatter has a non-null trace_id."""
    from aegis.obs.otel import reset_tracing_for_tests

    reset_tracing_for_tests()
    repo, aegis = _bootstrap_repo(tmp_path)
    p = _seed_task(aegis)

    with (
        patch("aegis.graph.runtime.create_worktree") as cw,
        patch("aegis.graph.runtime.remove_worktree") as rw,
        patch("aegis.graph.runtime.merge_worktree_into_main") as merge,
    ):
        cw.side_effect = lambda repo_root, worktree_path, branch: worktree_path.mkdir(
            parents=True, exist_ok=True
        )
        rw.side_effect = lambda *a, **kw: None
        merge.side_effect = lambda *a, **kw: None

        config = AegisConfig.model_validate(
            {"project": {"name": "t"}, "observability": {"langfuse": {"enabled": False}}}
        )
        run_one_task(
            task_path=p,
            aegis_dir=aegis,
            repo_root=repo,
            config=config,
            node_overrides=_stub_nodes(verdict="approve"),
        )

    moved = next((aegis / "review").glob("001-*.md"), None)
    assert moved is not None
    refreshed = parse_task(moved)
    assert refreshed.frontmatter.trace_id is not None
    assert len(refreshed.frontmatter.trace_id) == 32  # 128-bit OTel id, hex
    reset_tracing_for_tests()
