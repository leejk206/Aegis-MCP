from __future__ import annotations

from pathlib import Path

import pytest

from aegis.agents.tools import SERVER_COMMANDS, build_mcp_servers


def test_server_commands_cover_all_four_phase2_servers() -> None:
    assert set(SERVER_COMMANDS.keys()) == {"git", "fs", "shell", "project-index"}
    assert SERVER_COMMANDS["git"] == "aegis-git-mcp"
    assert SERVER_COMMANDS["fs"] == "aegis-fs-mcp"
    assert SERVER_COMMANDS["shell"] == "aegis-shell-mcp"
    assert SERVER_COMMANDS["project-index"] == "aegis-project-index-mcp"


def test_build_for_pm_returns_project_index_and_fs(tmp_path: Path) -> None:
    servers = build_mcp_servers("pm", tmp_path)
    assert set(servers.keys()) == {"project-index", "fs"}


def test_build_for_dev_returns_git_fs_shell(tmp_path: Path) -> None:
    servers = build_mcp_servers("dev", tmp_path)
    assert set(servers.keys()) == {"git", "fs", "shell"}


def test_build_for_reviewer_returns_git_and_project_index(tmp_path: Path) -> None:
    servers = build_mcp_servers("reviewer", tmp_path)
    assert set(servers.keys()) == {"git", "project-index"}


def test_build_for_docs_returns_fs_and_git(tmp_path: Path) -> None:
    servers = build_mcp_servers("docs", tmp_path)
    assert set(servers.keys()) == {"fs", "git"}


def test_each_server_entry_has_stdio_shape(tmp_path: Path) -> None:
    servers = build_mcp_servers("dev", tmp_path)
    for name, entry in servers.items():
        assert entry["type"] == "stdio", f"{name} missing type=stdio"
        assert isinstance(entry["command"], str)
        assert isinstance(entry["args"], list)
        assert all(isinstance(a, str) for a in entry["args"])
        assert isinstance(entry["env"], dict)


def test_scope_arg_is_the_worktree(tmp_path: Path) -> None:
    servers = build_mcp_servers("dev", tmp_path)
    for entry in servers.values():
        assert entry["args"] == ["--scope", str(tmp_path)]


def test_scope_is_resolved_to_absolute(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    # A relative path is a programming error but the helper must still
    # resolve it to absolute rather than silently passing garbage.
    servers = build_mcp_servers("dev", Path("."))
    for entry in servers.values():
        arg = Path(entry["args"][1])
        assert arg.is_absolute()


def test_args_lists_are_independent_per_server(tmp_path: Path) -> None:
    # Mutating one server's args must not affect another's.
    servers = build_mcp_servers("dev", tmp_path)
    servers["git"]["args"].append("--injected")
    assert "--injected" not in servers["fs"]["args"]
    assert "--injected" not in servers["shell"]["args"]


def test_shell_server_gets_allow_cmds_env_when_supplied(tmp_path: Path) -> None:
    servers = build_mcp_servers("dev", tmp_path, shell_allow_cmds="pytest,ruff,mypy")
    assert servers["shell"]["env"] == {"ALLOW_CMDS": "pytest,ruff,mypy"}


def test_non_shell_servers_have_empty_env_even_when_allow_cmds_supplied(tmp_path: Path) -> None:
    servers = build_mcp_servers("dev", tmp_path, shell_allow_cmds="pytest")
    assert servers["git"]["env"] == {}
    assert servers["fs"]["env"] == {}


def test_role_without_shell_ignores_allow_cmds(tmp_path: Path) -> None:
    # PM has no shell server; passing shell_allow_cmds must not cause an error.
    servers = build_mcp_servers("pm", tmp_path, shell_allow_cmds="pytest")
    assert "shell" not in servers


def test_shell_server_without_allow_cmds_has_empty_env(tmp_path: Path) -> None:
    servers = build_mcp_servers("dev", tmp_path, shell_allow_cmds=None)
    assert servers["shell"]["env"] == {}


def test_unknown_role_raises(tmp_path: Path) -> None:
    with pytest.raises(KeyError):
        build_mcp_servers("architect", tmp_path)  # type: ignore[arg-type]


def test_missing_worktree_raises(tmp_path: Path) -> None:
    missing = tmp_path / "does-not-exist"
    with pytest.raises(FileNotFoundError):
        build_mcp_servers("dev", missing)
