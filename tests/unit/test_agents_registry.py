from __future__ import annotations

import pytest

from aegis.agents.registry import ROLES, RoleSpec, get_role_spec


def test_exactly_five_roles() -> None:
    assert set(ROLES.keys()) == {"pm", "dev", "qa", "reviewer", "docs"}


def test_roles_values_are_role_spec_instances() -> None:
    for spec in ROLES.values():
        assert isinstance(spec, RoleSpec)


def test_each_role_has_a_unique_prompt_filename() -> None:
    filenames = [spec.prompt_filename for spec in ROLES.values()]
    assert len(filenames) == len(set(filenames))
    for filename in filenames:
        assert filename.endswith(".md")


def test_each_role_model_key_equals_role_name() -> None:
    for name, spec in ROLES.items():
        assert spec.model_key == name


def test_pm_mcp_access_matches_spec() -> None:
    spec = ROLES["pm"]
    assert spec.mcp_server_names == ("project-index", "fs")


def test_dev_mcp_access_matches_spec() -> None:
    spec = ROLES["dev"]
    assert spec.mcp_server_names == ("git", "fs", "shell")


def test_qa_mcp_access_matches_dev_plus_shell() -> None:
    spec = ROLES["qa"]
    assert spec.mcp_server_names == ("git", "fs", "shell")


def test_reviewer_mcp_access_is_read_only_servers() -> None:
    spec = ROLES["reviewer"]
    assert spec.mcp_server_names == ("git", "project-index")


def test_docs_mcp_access_matches_spec() -> None:
    spec = ROLES["docs"]
    assert spec.mcp_server_names == ("fs", "git")


def test_reviewer_disallows_every_git_write_tool() -> None:
    spec = ROLES["reviewer"]
    for tool in (
        "mcp__git__git_add",
        "mcp__git__git_commit",
        "mcp__git__git_branch_create",
        "mcp__git__git_checkout",
        "mcp__git__git_worktree_add",
        "mcp__git__git_worktree_remove",
        "mcp__git__git_merge",
    ):
        assert tool in spec.disallowed_tools


def test_reviewer_allows_every_git_read_tool() -> None:
    spec = ROLES["reviewer"]
    for tool in ("mcp__git__git_status", "mcp__git__git_diff", "mcp__git__git_log"):
        assert tool in spec.allowed_tools


def test_pm_disallows_fs_writes() -> None:
    spec = ROLES["pm"]
    for tool in (
        "mcp__fs__fs_write",
        "mcp__fs__fs_mkdir",
        "mcp__fs__fs_delete",
        "mcp__fs__fs_move",
    ):
        assert tool in spec.disallowed_tools


def test_pm_allows_fs_reads() -> None:
    spec = ROLES["pm"]
    for tool in ("mcp__fs__fs_read", "mcp__fs__fs_list", "mcp__fs__fs_glob"):
        assert tool in spec.allowed_tools


def test_dev_allows_shell_exec() -> None:
    spec = ROLES["dev"]
    assert "mcp__shell__shell_exec" in spec.allowed_tools


def test_allowed_and_disallowed_sets_are_disjoint() -> None:
    for name, spec in ROLES.items():
        overlap = set(spec.allowed_tools) & set(spec.disallowed_tools)
        assert not overlap, f"role {name} has {overlap} in both allow and deny lists"


def test_every_allowed_tool_references_an_allowed_server() -> None:
    # ``signals`` is the universal in-process MCP server that every role
    # is granted by ``aegis.agents.tools.build_mcp_servers``. It is NOT
    # listed in each role's ``mcp_server_names`` (which only enumerates
    # stdio Phase-2 servers). Treat it as an implicit member.
    for name, spec in ROLES.items():
        for tool in spec.allowed_tools:
            # tool name shape: mcp__<server>__<tool_name>
            _, server, _ = tool.split("__", 2)
            if server == "signals":
                continue
            assert server in spec.mcp_server_names, (
                f"role {name} allows tool on server {server!r} but that server is not in"
                " mcp_server_names"
            )


def test_role_spec_is_frozen() -> None:
    spec = ROLES["pm"]
    with pytest.raises(AttributeError):  # dataclass frozen → FrozenInstanceError ⊂ AttributeError
        spec.prompt_filename = "other.md"  # type: ignore[misc]


def test_get_role_spec_returns_by_name() -> None:
    assert get_role_spec("pm") is ROLES["pm"]


def test_get_role_spec_rejects_unknown() -> None:
    with pytest.raises(KeyError):
        get_role_spec("architect")  # type: ignore[arg-type]


def test_every_role_allows_signals_tools() -> None:
    for role, spec in ROLES.items():
        assert "mcp__signals__done" in spec.allowed_tools, role
        assert "mcp__signals__block" in spec.allowed_tools, role
