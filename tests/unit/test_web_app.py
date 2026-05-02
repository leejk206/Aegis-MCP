from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from aegis.cli.commands.init import run_init
from aegis.core.config import load_config
from aegis.web.app import create_app


@pytest.fixture
def app_client(git_repo: Path) -> TestClient:
    aegis_dir = run_init(git_repo)
    config = load_config(aegis_dir / "config.yaml")
    app = create_app(
        aegis_dir=aegis_dir,
        repo_root=git_repo,
        config=config,
        host="127.0.0.1",
        port=8765,
    )
    return TestClient(app, headers={"Host": "127.0.0.1:8765"})


def test_app_factory_returns_fastapi_instance(git_repo: Path) -> None:
    aegis_dir = run_init(git_repo)
    config = load_config(aegis_dir / "config.yaml")
    app = create_app(
        aegis_dir=aegis_dir, repo_root=git_repo, config=config,
        host="127.0.0.1", port=8765,
    )
    assert app.title == "Aegis"


def test_disallowed_host_rejected(git_repo: Path) -> None:
    aegis_dir = run_init(git_repo)
    config = load_config(aegis_dir / "config.yaml")
    app = create_app(
        aegis_dir=aegis_dir, repo_root=git_repo, config=config,
        host="127.0.0.1", port=8765,
    )
    client = TestClient(app, headers={"Host": "evil.com"})
    response = client.get("/")
    # No route is mounted yet; /=404 if Host passes, but Host is bad → 421
    assert response.status_code == 421


def test_app_state_carries_aegis_dir_and_csrf(app_client: TestClient) -> None:
    # The factory should attach state for routes to read in later tasks.
    app = app_client.app
    assert app.state.aegis_dir is not None
    assert app.state.repo_root is not None
    assert app.state.config is not None
    assert app.state.csrf is not None
    assert hasattr(app.state, "templates")
