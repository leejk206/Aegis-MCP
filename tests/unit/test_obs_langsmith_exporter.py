from __future__ import annotations

import os

import pytest

from aegis.core.config import LangSmithConfig
from aegis.obs.langsmith_exporter import (
    LangSmithNotConfiguredError,
    enable_langsmith,
)


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch) -> None:
    for key in ("LANGCHAIN_TRACING_V2", "LANGCHAIN_PROJECT", "LANGSMITH_API_KEY"):
        monkeypatch.delenv(key, raising=False)


def test_raises_when_api_key_missing(monkeypatch) -> None:
    cfg = LangSmithConfig(enabled=True, project="aegis-test")
    with pytest.raises(LangSmithNotConfiguredError):
        enable_langsmith(cfg)


def test_sets_env_vars_when_api_key_present(monkeypatch) -> None:
    monkeypatch.setenv("LANGSMITH_API_KEY", "ls_xxx")
    cfg = LangSmithConfig(enabled=True, project="aegis-test")
    enable_langsmith(cfg)
    assert os.environ["LANGCHAIN_TRACING_V2"] == "true"
    assert os.environ["LANGCHAIN_PROJECT"] == "aegis-test"


def test_no_project_falls_back_to_default(monkeypatch) -> None:
    monkeypatch.setenv("LANGSMITH_API_KEY", "ls_xxx")
    cfg = LangSmithConfig(enabled=True, project=None)
    enable_langsmith(cfg)
    assert os.environ["LANGCHAIN_PROJECT"] == "aegis"
