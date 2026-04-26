from __future__ import annotations

from pathlib import Path

import pytest

from aegis.agents.base import build_options, load_prompt
from aegis.core.config import AegisConfig, ProjectConfig


def _make_config() -> AegisConfig:
    return AegisConfig(project=ProjectConfig(name="test"))


# ------------------ load_prompt ------------------

def test_load_prompt_pm_returns_markdown() -> None:
    text = load_prompt("pm")
    assert text.startswith("# Role: PM")
    assert "## Identity" in text


def test_load_prompt_every_role_returns_nonempty() -> None:
    for role in ("pm", "dev", "qa", "reviewer", "docs"):
        text = load_prompt(role)  # type: ignore[arg-type]
        assert text.strip(), f"{role} prompt is empty"


def test_load_prompt_unknown_role_raises() -> None:
    with pytest.raises(KeyError):
        load_prompt("architect")  # type: ignore[arg-type]


def test_load_prompt_override_path_used_verbatim(tmp_path: Path) -> None:
    override = tmp_path / "override.md"
    override.write_text("# Role: PM\n\nCustom override body.\n", encoding="utf-8")
    text = load_prompt("pm", override_path=override)
    assert "Custom override body." in text
    # The packaged prompt must NOT appear
    assert "project-index" not in text


def test_load_prompt_override_missing_raises(tmp_path: Path) -> None:
    missing = tmp_path / "nope.md"
    with pytest.raises(FileNotFoundError):
        load_prompt("pm", override_path=missing)


# ------------------ build_options ------------------

def test_build_options_model_comes_from_config(tmp_path: Path) -> None:
    config = _make_config()
    options = build_options("pm", tmp_path, config)
    assert options.model == config.llm.models["pm"]


def test_build_options_system_prompt_is_the_role_prompt(tmp_path: Path) -> None:
    config = _make_config()
    options = build_options("dev", tmp_path, config)
    assert options.system_prompt.startswith("# Role: Dev")


def test_build_options_cwd_is_the_worktree(tmp_path: Path) -> None:
    config = _make_config()
    options = build_options("dev", tmp_path, config)
    assert str(options.cwd) == str(tmp_path.resolve())


def test_build_options_mcp_servers_match_role(tmp_path: Path) -> None:
    config = _make_config()
    options = build_options("dev", tmp_path, config)
    assert set(options.mcp_servers.keys()) == {"git", "fs", "shell"}


def test_build_options_allowed_tools_match_role(tmp_path: Path) -> None:
    config = _make_config()
    options = build_options("reviewer", tmp_path, config)
    for tool in ("mcp__git__git_diff", "mcp__project-index__search"):
        assert tool in options.allowed_tools
    for tool in ("mcp__git__git_commit", "mcp__git__git_merge"):
        assert tool in options.disallowed_tools


def test_build_options_prompt_override_takes_precedence(tmp_path: Path) -> None:
    config = _make_config()
    override = tmp_path / "custom-pm.md"
    override.write_text("# Role: PM\n\nCustom override.\n", encoding="utf-8")
    options = build_options("pm", tmp_path, config, prompt_override=override)
    assert "Custom override." in options.system_prompt


def test_build_options_shell_allow_cmds_propagates(tmp_path: Path) -> None:
    config = _make_config()
    options = build_options("dev", tmp_path, config, shell_allow_cmds="pytest,ruff")
    assert options.mcp_servers["shell"]["env"] == {"ALLOW_CMDS": "pytest,ruff"}


def test_build_options_permission_mode_is_accept_edits(tmp_path: Path) -> None:
    # Aegis agents run unattended overnight; the graph-level gates
    # control approval, not per-tool prompts. 'acceptEdits' is the
    # right default here.
    config = _make_config()
    options = build_options("dev", tmp_path, config)
    assert options.permission_mode == "acceptEdits"


def test_build_options_unknown_role_raises(tmp_path: Path) -> None:
    config = _make_config()
    with pytest.raises(KeyError):
        build_options("architect", tmp_path, config)  # type: ignore[arg-type]
