from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

import pytest
from claude_agent_sdk import ClaudeAgentOptions

from aegis.agents.base import AegisAgent, build_options, load_prompt
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


# ------------------ AegisAgent ------------------


class _FakeClient:
    """Stand-in for ``ClaudeSDKClient`` that records calls.

    Mirrors the context-manager + ``query`` + ``receive_response`` surface
    of the real client exactly — see the Claude Agent SDK docs.
    """

    last_instance: _FakeClient | None = None

    def __init__(self, options: ClaudeAgentOptions) -> None:
        self.options = options
        self.queries: list[str] = []
        self.responses: list[Any] = [
            {"role": "assistant", "content": "ok"},
            {"role": "tool", "name": "done", "input": {"summary": "done"}},
        ]
        _FakeClient.last_instance = self

    async def __aenter__(self) -> _FakeClient:
        return self

    async def __aexit__(self, *_: Any) -> None:
        return None

    async def query(self, prompt: str) -> None:
        self.queries.append(prompt)

    async def receive_response(self):  # type: ignore[no-untyped-def]
        for msg in self.responses:
            yield msg


def test_agent_run_passes_task_prompt_to_client(tmp_path: Path) -> None:
    config = _make_config()
    agent = AegisAgent("dev", tmp_path, config, client_factory=_FakeClient)
    messages = asyncio.run(agent.run("do the thing"))
    assert _FakeClient.last_instance is not None
    assert _FakeClient.last_instance.queries == ["do the thing"]
    assert len(messages) == 2


def test_agent_run_returns_every_message(tmp_path: Path) -> None:
    config = _make_config()
    agent = AegisAgent("dev", tmp_path, config, client_factory=_FakeClient)
    messages = asyncio.run(agent.run("hi"))
    assert messages == [
        {"role": "assistant", "content": "ok"},
        {"role": "tool", "name": "done", "input": {"summary": "done"}},
    ]


def test_agent_builds_options_for_its_role(tmp_path: Path) -> None:
    config = _make_config()
    agent = AegisAgent("reviewer", tmp_path, config, client_factory=_FakeClient)
    asyncio.run(agent.run("please review"))
    assert _FakeClient.last_instance is not None
    opts = _FakeClient.last_instance.options
    assert set(opts.mcp_servers.keys()) == {"git", "project-index"}
    assert opts.system_prompt.startswith("# Role: Reviewer")
    assert opts.model == config.llm.models["reviewer"]


def test_agent_propagates_prompt_override(tmp_path: Path) -> None:
    config = _make_config()
    override = tmp_path / "pm-override.md"
    override.write_text("# Role: PM\n\noverride.\n", encoding="utf-8")
    agent = AegisAgent(
        "pm",
        tmp_path,
        config,
        prompt_override=override,
        client_factory=_FakeClient,
    )
    asyncio.run(agent.run("plan it"))
    assert _FakeClient.last_instance is not None
    assert "override." in _FakeClient.last_instance.options.system_prompt


def test_agent_propagates_shell_allow_cmds(tmp_path: Path) -> None:
    config = _make_config()
    agent = AegisAgent(
        "dev",
        tmp_path,
        config,
        shell_allow_cmds="pytest,ruff",
        client_factory=_FakeClient,
    )
    asyncio.run(agent.run("do"))
    assert _FakeClient.last_instance is not None
    shell = _FakeClient.last_instance.options.mcp_servers["shell"]
    assert shell["env"] == {"ALLOW_CMDS": "pytest,ruff"}


def test_agent_requires_worktree_to_exist(tmp_path: Path) -> None:
    config = _make_config()
    missing = tmp_path / "nope"
    with pytest.raises(FileNotFoundError):
        AegisAgent("dev", missing, config, client_factory=_FakeClient)


def test_agent_rejects_unknown_role(tmp_path: Path) -> None:
    config = _make_config()
    with pytest.raises(KeyError):
        AegisAgent("architect", tmp_path, config, client_factory=_FakeClient)  # type: ignore[arg-type]
