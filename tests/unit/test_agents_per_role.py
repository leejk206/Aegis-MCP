from __future__ import annotations

from pathlib import Path

import pytest

from aegis.agents.base import build_options
from aegis.agents.registry import ROLES
from aegis.core.config import AegisConfig, ProjectConfig


@pytest.fixture
def default_config() -> AegisConfig:
    return AegisConfig(project=ProjectConfig(name="test-project"))


@pytest.mark.parametrize("role_name", sorted(ROLES.keys()))
def test_build_options_is_stable_per_role(
    role_name: str,
    default_config: AegisConfig,
    tmp_path: Path,
) -> None:
    spec = ROLES[role_name]
    options = build_options(role_name, tmp_path, default_config)  # type: ignore[arg-type]

    # Model string comes from config.
    assert options.model == default_config.llm.models[role_name]

    # System prompt is the packaged prompt file for this role.
    role_label = "PM" if role_name == "pm" else role_name.upper()
    assert options.system_prompt.startswith(
        f"# Role: {role_label}"
    ) or options.system_prompt.startswith("# Role:")  # case-insensitive fallback

    # MCP servers match the registry.
    assert tuple(options.mcp_servers.keys()) == spec.mcp_server_names

    # Allow/deny lists match the registry.
    assert tuple(options.allowed_tools) == spec.allowed_tools
    assert tuple(options.disallowed_tools) == spec.disallowed_tools

    # cwd is the worktree.
    assert Path(options.cwd) == tmp_path.resolve()


def test_pm_has_no_git_or_shell_access(default_config: AegisConfig, tmp_path: Path) -> None:
    options = build_options("pm", tmp_path, default_config)
    assert "git" not in options.mcp_servers
    assert "shell" not in options.mcp_servers


def test_reviewer_has_no_write_tools(default_config: AegisConfig, tmp_path: Path) -> None:
    options = build_options("reviewer", tmp_path, default_config)
    # Reviewer sees git + project-index. The allow-list must contain no
    # write tools at all — not just fs/shell, but also git writes.
    for tool in options.allowed_tools:
        assert "git_commit" not in tool
        assert "git_add" not in tool
        assert "git_merge" not in tool
        assert "fs_write" not in tool
        assert "shell_exec" not in tool


def test_docs_can_commit_but_not_branch(default_config: AegisConfig, tmp_path: Path) -> None:
    options = build_options("docs", tmp_path, default_config)
    assert "mcp__git__git_commit" in options.allowed_tools
    assert "mcp__git__git_add" in options.allowed_tools
    # Docs must not create or switch branches.
    for forbidden in (
        "mcp__git__git_branch_create",
        "mcp__git__git_checkout",
        "mcp__git__git_merge",
        "mcp__git__git_worktree_add",
        "mcp__git__git_worktree_remove",
    ):
        assert forbidden in options.disallowed_tools


def test_dev_shell_allow_cmds_respects_argument(
    default_config: AegisConfig, tmp_path: Path
) -> None:
    options = build_options("dev", tmp_path, default_config, shell_allow_cmds="pytest,ruff,mypy")
    assert options.mcp_servers["shell"]["env"] == {"ALLOW_CMDS": "pytest,ruff,mypy"}


def test_qa_shell_allow_cmds_respects_argument(default_config: AegisConfig, tmp_path: Path) -> None:
    # Spec §4 note: QA may run a TIGHTER allow-list than Dev.
    options = build_options("qa", tmp_path, default_config, shell_allow_cmds="pytest")
    assert options.mcp_servers["shell"]["env"] == {"ALLOW_CMDS": "pytest"}


def test_models_are_configurable(tmp_path: Path) -> None:
    # A user can remap the PM model in config.yaml; the agent must
    # honour that remapping. ``AegisConfig`` is a non-frozen pydantic
    # v2 model so direct mutation of the ``models`` dict is fine.
    config = AegisConfig(project=ProjectConfig(name="t"))
    config.llm.models["pm"] = "claude-opus-5-0"
    options = build_options("pm", tmp_path, config)
    assert options.model == "claude-opus-5-0"
