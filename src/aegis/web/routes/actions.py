"""POST /task/{id}/approve and /reject — call the runtime layer.

Runs the (potentially long) graph resume on a worker thread so the
event loop stays responsive. The Origin/Host whitelist + CSRF token
together gate every POST.
"""

from __future__ import annotations

import anyio
from fastapi import APIRouter, HTTPException, Request
from starlette.responses import JSONResponse

from aegis.core.lifecycle import find_task
from aegis.core.task import TaskStatus
from aegis.graph.runtime import reject_task, resume_after_approve

router = APIRouter()


@router.post("/task/{task_id}/approve")
async def approve(
    task_id: str,
    request: Request,
) -> JSONResponse:
    await _verify_csrf(request)
    aegis_dir = request.app.state.aegis_dir
    repo_root = request.app.state.repo_root
    config = request.app.state.config
    found = find_task(aegis_dir, task_id)
    if found is None:
        raise HTTPException(status_code=404, detail=f"task {task_id} not found")
    task, _ = found
    if task.frontmatter.status != TaskStatus.REVIEW:
        raise HTTPException(
            status_code=409,
            detail=f"task {task_id} is in {task.frontmatter.status.value}, not review",
        )
    await anyio.to_thread.run_sync(
        lambda: resume_after_approve(
            task_id=task_id,
            aegis_dir=aegis_dir,
            repo_root=repo_root,
            config=config,
        )
    )
    return JSONResponse({"approved": task_id})


@router.post("/task/{task_id}/reject")
async def reject(
    task_id: str,
    request: Request,
) -> JSONResponse:
    await _verify_csrf(request)
    reason: str | None = None
    ctype = request.headers.get("content-type", "")
    if ctype.startswith("application/x-www-form-urlencoded") or ctype.startswith(
        "multipart/form-data"
    ):
        form = await request.form()
        value = form.get("reason")
        if isinstance(value, str):
            reason = value
    aegis_dir = request.app.state.aegis_dir
    repo_root = request.app.state.repo_root
    found = find_task(aegis_dir, task_id)
    if found is None:
        raise HTTPException(status_code=404, detail=f"task {task_id} not found")
    await anyio.to_thread.run_sync(
        lambda: reject_task(
            task_id=task_id,
            aegis_dir=aegis_dir,
            repo_root=repo_root,
            reason=reason,
        )
    )
    return JSONResponse({"rejected": task_id})


async def _verify_csrf(request: Request) -> None:
    header_token = request.headers.get("x-csrf-token")
    form_token: str | None = None
    if not header_token:
        ctype = request.headers.get("content-type", "")
        if ctype.startswith("application/x-www-form-urlencoded") or ctype.startswith(
            "multipart/form-data"
        ):
            form = await request.form()
            value = form.get("csrf_token")
            if isinstance(value, str):
                form_token = value
    request.app.state.csrf.verify(header_token, form_token)
