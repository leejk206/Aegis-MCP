"""Process-scoped CSRF token: one random 32-byte hex per server boot.

The token is regenerated every time `aegis web` starts, embedded in
templates, and required on every POST. We accept it from either an
`X-CSRF-Token` header (HTMX preferred) or a `csrf_token` form field
(fallback for native form submits). The token is constant-time
compared.
"""

from __future__ import annotations

import secrets

from fastapi import Depends, HTTPException, Request, status
from fastapi.params import Depends as DependsType

__all__ = ["CSRFManager"]


class CSRFManager:
    def __init__(self) -> None:
        self.token: str = secrets.token_hex(32)

    def verify(self, header_token: str | None, form_token: str | None) -> None:
        candidate = header_token or form_token
        if candidate is None or not secrets.compare_digest(candidate, self.token):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="invalid or missing CSRF token",
            )

    def depends_verify(self) -> DependsType:
        token = self.token  # capture by value

        async def _dep(request: Request) -> None:
            x_csrf_token: str | None = request.headers.get("x-csrf-token")
            csrf_token: str | None = None
            content_type = request.headers.get("content-type", "")
            if (
                "application/x-www-form-urlencoded" in content_type
                or "multipart/form-data" in content_type
            ):
                form = await request.form()
                csrf_token = form.get("csrf_token")  # type: ignore[assignment]
            candidate = x_csrf_token or csrf_token
            if candidate is None or not secrets.compare_digest(candidate, token):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="invalid or missing CSRF token",
                )

        return Depends(_dep)
