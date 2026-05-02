"""GET /config — read-only YAML view of `.aegis/config.yaml`."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from starlette.responses import HTMLResponse

router = APIRouter()


@router.get("/config", response_class=HTMLResponse)
def config_view(request: Request) -> HTMLResponse:
    aegis_dir = request.app.state.aegis_dir
    yaml_path = aegis_dir / "config.yaml"
    if not yaml_path.exists():
        raise HTTPException(status_code=404, detail="config.yaml not found")
    yaml_text = yaml_path.read_text(encoding="utf-8")
    return request.app.state.templates.TemplateResponse(
        request,
        "config.html",
        {
            "yaml_text": yaml_text,
            "csrf_token": request.app.state.csrf.token,
        },
    )
