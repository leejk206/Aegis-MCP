from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from aegis.cli.commands.init import run_init
from aegis.core.config import load_config
from aegis.web.app import create_app


@pytest.fixture
def client(git_repo: Path) -> TestClient:
    aegis_dir = run_init(git_repo)
    config = load_config(aegis_dir / "config.yaml")
    app = create_app(
        aegis_dir=aegis_dir, repo_root=git_repo, config=config,
        host="127.0.0.1", port=8765,
    )
    return TestClient(app, headers={"Host": "127.0.0.1:8765"})


def test_config_view_returns_200(client: TestClient) -> None:
    response = client.get("/config")
    assert response.status_code == 200


def test_config_view_renders_yaml_pre_block(client: TestClient) -> None:
    body = client.get("/config").text
    assert "<pre" in body
    assert "project:" in body
    assert "observability:" in body


def test_config_view_returns_404_when_yaml_missing(git_repo: Path) -> None:
    aegis_dir = run_init(git_repo)
    config = load_config(aegis_dir / "config.yaml")
    (aegis_dir / "config.yaml").unlink()
    app = create_app(
        aegis_dir=aegis_dir, repo_root=git_repo, config=config,
        host="127.0.0.1", port=8765,
    )
    client = TestClient(app, headers={"Host": "127.0.0.1:8765"})
    response = client.get("/config")
    assert response.status_code == 404
