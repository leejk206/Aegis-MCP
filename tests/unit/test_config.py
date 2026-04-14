from pathlib import Path

import pytest
import yaml
from pydantic import ValidationError

from aegis.core.config import (
    default_config,
    dump_config,
    load_config,
)


def test_default_config_has_expected_fields() -> None:
    cfg = default_config("my-cream")
    assert cfg.version == 1
    assert cfg.project.name == "my-cream"
    assert cfg.project.root == "."
    assert cfg.llm.provider == "anthropic"
    assert cfg.llm.models["pm"] == "claude-opus-4-6"
    assert cfg.llm.models["dev"] == "claude-sonnet-4-6"
    assert cfg.llm.models["docs"] == "claude-haiku-4-5"
    assert cfg.budget.task.usd == pytest.approx(2.00)
    assert cfg.budget.task.minutes == 30
    assert cfg.budget.parallel.max == 3
    assert cfg.gates.strategy == "merge_only"
    assert cfg.gates.auto_approve_docs is True
    assert len(cfg.mcp.servers) == 4
    assert {s.name for s in cfg.mcp.servers} == {"git", "fs", "shell", "project-index"}


def test_config_roundtrip_yaml(tmp_path: Path) -> None:
    original = default_config("sample")
    path = tmp_path / "config.yaml"
    dump_config(original, path)

    raw = yaml.safe_load(path.read_text())
    assert raw["project"]["name"] == "sample"

    loaded = load_config(path)
    assert loaded == original


def test_config_loads_partial_yaml(tmp_path: Path) -> None:
    path = tmp_path / "config.yaml"
    path.write_text(
        "version: 1\nproject:\n  name: partial\n",
        encoding="utf-8",
    )
    loaded = load_config(path)
    assert loaded.project.name == "partial"
    # Defaults fill in the rest.
    assert loaded.llm.models["pm"] == "claude-opus-4-6"
    assert loaded.budget.task.usd == pytest.approx(2.00)


def test_config_overrides_model_routing(tmp_path: Path) -> None:
    path = tmp_path / "config.yaml"
    path.write_text(
        """
version: 1
project:
  name: override
llm:
  provider: anthropic
  models:
    pm: claude-sonnet-4-6
    dev: claude-haiku-4-5
    qa: claude-haiku-4-5
    reviewer: claude-sonnet-4-6
    docs: claude-haiku-4-5
""",
        encoding="utf-8",
    )
    loaded = load_config(path)
    assert loaded.llm.models["pm"] == "claude-sonnet-4-6"
    assert loaded.llm.models["dev"] == "claude-haiku-4-5"


def test_config_rejects_unknown_gate_strategy(tmp_path: Path) -> None:
    path = tmp_path / "config.yaml"
    path.write_text(
        """
version: 1
project:
  name: bad
gates:
  strategy: none
""",
        encoding="utf-8",
    )
    with pytest.raises(ValidationError):
        load_config(path)
