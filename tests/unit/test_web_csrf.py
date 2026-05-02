from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from aegis.web.csrf import CSRFManager


def test_token_is_64_hex_chars() -> None:
    mgr = CSRFManager()
    assert len(mgr.token) == 64
    int(mgr.token, 16)  # parses as hex


def test_two_managers_have_different_tokens() -> None:
    a = CSRFManager()
    b = CSRFManager()
    assert a.token != b.token


def test_dependency_rejects_missing_header() -> None:
    mgr = CSRFManager()
    app = FastAPI()

    @app.post("/x")
    def _x(_: None = mgr.depends_verify()) -> dict[str, str]:
        return {"ok": "yes"}

    client = TestClient(app)
    response = client.post("/x")
    assert response.status_code == 403


def test_dependency_rejects_wrong_token() -> None:
    mgr = CSRFManager()
    app = FastAPI()

    @app.post("/x")
    def _x(_: None = mgr.depends_verify()) -> dict[str, str]:
        return {"ok": "yes"}

    client = TestClient(app)
    response = client.post("/x", headers={"X-CSRF-Token": "deadbeef"})
    assert response.status_code == 403


def test_dependency_accepts_correct_token() -> None:
    mgr = CSRFManager()
    app = FastAPI()

    @app.post("/x")
    def _x(_: None = mgr.depends_verify()) -> dict[str, str]:
        return {"ok": "yes"}

    client = TestClient(app)
    response = client.post("/x", headers={"X-CSRF-Token": mgr.token})
    assert response.status_code == 200
    assert response.json() == {"ok": "yes"}


def test_dependency_accepts_form_field_when_no_header() -> None:
    mgr = CSRFManager()
    app = FastAPI()

    @app.post("/x")
    def _x(_: None = mgr.depends_verify()) -> dict[str, str]:
        return {"ok": "yes"}

    client = TestClient(app)
    response = client.post("/x", data={"csrf_token": mgr.token})
    assert response.status_code == 200
