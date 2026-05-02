"""FastAPI app factory for the Aegis read-only dashboard.

Owns: middleware stack, Jinja2 environment, CSRF manager wiring,
route registration. Holds no global state — each `create_app` call
returns a self-contained app keyed to one `.aegis/` directory.
"""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from aegis.core.config import AegisConfig
from aegis.web.csrf import CSRFManager
from aegis.web.middleware import OriginHostMiddleware, build_allowed_hosts

__all__ = ["create_app"]

_TEMPLATES_DIR = Path(__file__).parent / "templates"
_STATIC_DIR = Path(__file__).parent / "static"


def create_app(
    *,
    aegis_dir: Path,
    repo_root: Path,
    config: AegisConfig,
    host: str = "127.0.0.1",
    port: int = 8765,
) -> FastAPI:
    app = FastAPI(title="Aegis", docs_url=None, redoc_url=None, openapi_url=None)
    app.add_middleware(
        OriginHostMiddleware,
        allowed_hosts=build_allowed_hosts(host, port),
    )

    templates = Jinja2Templates(directory=str(_TEMPLATES_DIR))
    csrf = CSRFManager()

    app.state.aegis_dir = aegis_dir
    app.state.repo_root = repo_root
    app.state.config = config
    app.state.templates = templates
    app.state.csrf = csrf

    if _STATIC_DIR.exists():
        app.mount("/static", StaticFiles(directory=str(_STATIC_DIR)), name="static")

    _register_routes(app)
    return app


def _register_routes(app: FastAPI) -> None:
    """Mount all route modules."""
    from aegis.web.routes.actions import router as actions_router
    from aegis.web.routes.config_view import router as config_router
    from aegis.web.routes.kanban import router as kanban_router
    from aegis.web.routes.task import router as task_router

    app.include_router(kanban_router)
    app.include_router(task_router)
    app.include_router(actions_router)
    app.include_router(config_router)
