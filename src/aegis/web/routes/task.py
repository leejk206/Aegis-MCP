"""GET /task/{task_id} — task detail with markdown body, sidebar, diff preview.
GET /task/{task_id}/logs — HTMX partial returning the last N JSONL trace lines.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from starlette.responses import HTMLResponse

from aegis.core.lifecycle import find_task
from aegis.core.task import TaskStatus
from aegis.web.git_diff import diff_full, diff_stat
from aegis.web.log_tail import tail_jsonl
from aegis.web.render import render_markdown

router = APIRouter()


@router.get("/task/{task_id}", response_class=HTMLResponse)
def task_detail(task_id: str, request: Request) -> HTMLResponse:
    aegis_dir = request.app.state.aegis_dir
    repo_root = request.app.state.repo_root
    found = find_task(aegis_dir, task_id)
    if found is None:
        raise HTTPException(status_code=404, detail=f"task {task_id} not found")
    task, task_path = found
    fm = task.frontmatter
    diff_summary = diff_stat(repo_root, fm.pr_branch) if fm.pr_branch else ""
    diff_body = diff_full(repo_root, fm.pr_branch) if fm.pr_branch else ""
    return request.app.state.templates.TemplateResponse(
        request,
        "task.html",
        {
            "task_id": task_id,
            "title": fm.title,
            "status": fm.status.value,
            "priority": fm.priority.value,
            "branch": fm.pr_branch,
            "worktree": fm.worktree,
            "trace_id": fm.trace_id,
            "body_html": render_markdown(task.body),
            "diff_summary": diff_summary,
            "diff_body": diff_body,
            "is_review": fm.status == TaskStatus.REVIEW,
            "csrf_token": request.app.state.csrf.token,
        },
    )


@router.get("/task/{task_id}/logs", response_class=HTMLResponse)
def task_logs(task_id: str, request: Request) -> HTMLResponse:
    aegis_dir = request.app.state.aegis_dir
    trace_path = aegis_dir / "trace" / f"{task_id}.jsonl"
    lines = tail_jsonl(trace_path, max_lines=200)
    return request.app.state.templates.TemplateResponse(
        request,
        "_logs.html",
        {"task_id": task_id, "lines": lines},
    )
