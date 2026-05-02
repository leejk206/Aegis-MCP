"""Reject requests whose Host or Origin headers fall outside a whitelist.

Defense against DNS rebinding (Host check) and cross-site POST CSRF
(Origin check). The whitelist is built from the bound (host, port)
plus the canonical localhost aliases.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from urllib.parse import urlparse

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import PlainTextResponse, Response

__all__ = ["OriginHostMiddleware", "build_allowed_hosts"]

_SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}


def build_allowed_hosts(host: str, port: int) -> set[str]:
    return {
        f"{host}:{port}",
        f"127.0.0.1:{port}",
        f"localhost:{port}",
    }


class OriginHostMiddleware(BaseHTTPMiddleware):
    def __init__(self, app: object, *, allowed_hosts: set[str]) -> None:
        super().__init__(app)  # type: ignore[arg-type]
        self.allowed_hosts = allowed_hosts

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        host = request.headers.get("host", "")
        if host not in self.allowed_hosts:
            return PlainTextResponse("Misdirected Request", status_code=421)
        if request.method not in _SAFE_METHODS:
            origin = request.headers.get("origin", "")
            if not origin:
                return PlainTextResponse("Origin header required", status_code=403)
            parsed = urlparse(origin)
            if parsed.netloc not in self.allowed_hosts:
                return PlainTextResponse("Origin not allowed", status_code=403)
        return await call_next(request)
