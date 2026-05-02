"""GET / — 4-column kanban (backlog / in-progress / review / blocked)."""

from __future__ import annotations

from fastapi import APIRouter, Request
from starlette.responses import HTMLResponse

from aegis.core.lifecycle import list_tasks
from aegis.core.task import TaskStatus

router = APIRouter()

_KANBAN_STATUSES: list[tuple[TaskStatus, str]] = [
    (TaskStatus.BACKLOG, "Backlog"),
    (TaskStatus.IN_PROGRESS, "In progress"),
    (TaskStatus.REVIEW, "Review"),
    (TaskStatus.BLOCKED, "Blocked"),
]


@router.get("/", response_class=HTMLResponse)
def kanban(request: Request) -> HTMLResponse:
    aegis_dir = request.app.state.aegis_dir
    columns: list[dict[str, object]] = []
    for status, label in _KANBAN_STATUSES:
        rows = list_tasks(aegis_dir, status=status)
        columns.append(
            {
                "status": status.value,
                "label": label,
                "cards": [
                    {
                        "id": task.frontmatter.id,
                        "title": task.frontmatter.title,
                        "priority": task.frontmatter.priority.value,
                    }
                    for task, _ in rows
                ],
            }
        )
    csrf_token = request.app.state.csrf.token
    return request.app.state.templates.TemplateResponse(
        request, "kanban.html", {"columns": columns, "csrf_token": csrf_token}
    )
