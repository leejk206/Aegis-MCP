from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from aegis.web.middleware import OriginHostMiddleware


def _app(allowed_hosts: set[str]) -> FastAPI:
    app = FastAPI()
    app.add_middleware(OriginHostMiddleware, allowed_hosts=allowed_hosts)

    @app.get("/")
    def _home() -> dict[str, str]:
        return {"ok": "yes"}

    @app.post("/x")
    def _x() -> dict[str, str]:
        return {"ok": "yes"}

    return app


def test_get_with_allowed_host_passes() -> None:
    client = TestClient(_app({"127.0.0.1:8765"}))
    response = client.get("/", headers={"Host": "127.0.0.1:8765"})
    assert response.status_code == 200


def test_get_with_disallowed_host_rejected() -> None:
    client = TestClient(_app({"127.0.0.1:8765"}))
    response = client.get("/", headers={"Host": "evil.com"})
    assert response.status_code == 421


def test_post_without_origin_rejected() -> None:
    client = TestClient(_app({"127.0.0.1:8765"}))
    response = client.post("/x", headers={"Host": "127.0.0.1:8765"})
    assert response.status_code == 403


def test_post_with_allowed_origin_passes() -> None:
    client = TestClient(_app({"127.0.0.1:8765"}))
    response = client.post(
        "/x",
        headers={"Host": "127.0.0.1:8765", "Origin": "http://127.0.0.1:8765"},
    )
    assert response.status_code == 200


def test_post_with_disallowed_origin_rejected() -> None:
    client = TestClient(_app({"127.0.0.1:8765"}))
    response = client.post(
        "/x",
        headers={"Host": "127.0.0.1:8765", "Origin": "http://evil.com"},
    )
    assert response.status_code == 403
