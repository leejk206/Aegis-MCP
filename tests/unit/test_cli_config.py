from pathlib import Path

import pytest

from aegis.cli.commands.config import run_config_get, run_config_set
from aegis.cli.commands.init import run_init


@pytest.fixture
def initialized_repo(git_repo: Path) -> Path:
    run_init(git_repo, force=False)
    return git_repo


def test_config_get_returns_default(initialized_repo: Path) -> None:
    assert run_config_get(initialized_repo, "budget.task.usd") == "2.0"
    assert run_config_get(initialized_repo, "gates.strategy") == "merge_only"
    assert run_config_get(initialized_repo, "llm.models.pm") == "claude-opus-4-6"


def test_config_set_persists_value(initialized_repo: Path) -> None:
    run_config_set(initialized_repo, "budget.task.usd", "3.50")
    assert run_config_get(initialized_repo, "budget.task.usd") == "3.5"


def test_config_set_model_routing(initialized_repo: Path) -> None:
    run_config_set(initialized_repo, "llm.models.dev", "claude-haiku-4-5")
    assert run_config_get(initialized_repo, "llm.models.dev") == "claude-haiku-4-5"


def test_config_get_unknown_key_raises(initialized_repo: Path) -> None:
    import typer
    with pytest.raises(typer.BadParameter):
        run_config_get(initialized_repo, "nope.nope")


def test_config_set_rejects_invalid_value(initialized_repo: Path) -> None:
    import typer
    with pytest.raises(typer.BadParameter):
        run_config_set(initialized_repo, "gates.strategy", "anarchy")
