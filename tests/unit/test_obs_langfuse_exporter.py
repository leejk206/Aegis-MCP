from __future__ import annotations

import base64

import pytest

from aegis.core.config import LangfuseConfig
from aegis.obs.langfuse_exporter import build_langfuse_exporter


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch) -> None:
    for key in ("LANGFUSE_PUBLIC_KEY", "LANGFUSE_SECRET_KEY"):
        monkeypatch.delenv(key, raising=False)


def test_returns_none_when_keys_missing(monkeypatch) -> None:
    cfg = LangfuseConfig(enabled=True, url="http://localhost:3000")
    assert build_langfuse_exporter(cfg) is None


def test_builds_otlp_exporter_with_basic_auth(monkeypatch) -> None:
    monkeypatch.setenv("LANGFUSE_PUBLIC_KEY", "pk_test")
    monkeypatch.setenv("LANGFUSE_SECRET_KEY", "sk_test")
    cfg = LangfuseConfig(enabled=True, url="http://langfuse.local:3000")
    exporter = build_langfuse_exporter(cfg)
    assert exporter is not None
    expected_token = base64.b64encode(b"pk_test:sk_test").decode("ascii")
    # OTLPSpanExporter stores headers on its session
    assert exporter._session.headers["Authorization"] == f"Basic {expected_token}"
    assert exporter._endpoint == "http://langfuse.local:3000/api/public/otel/v1/traces"


def test_strips_trailing_slash_from_url(monkeypatch) -> None:
    monkeypatch.setenv("LANGFUSE_PUBLIC_KEY", "pk_test")
    monkeypatch.setenv("LANGFUSE_SECRET_KEY", "sk_test")
    cfg = LangfuseConfig(enabled=True, url="http://localhost:3000/")
    exporter = build_langfuse_exporter(cfg)
    assert exporter is not None
    assert exporter._endpoint == "http://localhost:3000/api/public/otel/v1/traces"
