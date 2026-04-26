"""Per-role static configuration for Aegis agents.

Maps each role to its prompt file, its model-key (which resolves through
``AegisConfig.llm.models``), the MCP servers it may reach, and the
per-tool allow/deny lists that pre-approve or block individual MCP
tools on those servers. See spec §4 for the source of truth table.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


RoleName = Literal["pm", "dev", "qa", "reviewer", "docs"]


@dataclass(frozen=True, slots=True)
class RoleSpec:
    """Immutable, pure-data description of one role."""

    role: RoleName
    prompt_filename: str
    model_key: RoleName
    mcp_server_names: tuple[str, ...]
    allowed_tools: tuple[str, ...]
    disallowed_tools: tuple[str, ...]


# Fully-qualified MCP tool names follow the Claude Code convention
# ``mcp__<server_name>__<tool_name>``. Server names here match the
# ``mcp.servers[i].name`` values in AegisConfig (see core/config.py).

_FS_READ_TOOLS = (
    "mcp__fs__fs_read",
    "mcp__fs__fs_list",
    "mcp__fs__fs_glob",
)
_FS_WRITE_TOOLS = (
    "mcp__fs__fs_write",
    "mcp__fs__fs_mkdir",
    "mcp__fs__fs_delete",
    "mcp__fs__fs_move",
)
_GIT_READ_TOOLS = (
    "mcp__git__git_status",
    "mcp__git__git_diff",
    "mcp__git__git_log",
)
_GIT_WRITE_TOOLS = (
    "mcp__git__git_add",
    "mcp__git__git_commit",
    "mcp__git__git_branch_create",
    "mcp__git__git_checkout",
    "mcp__git__git_worktree_add",
    "mcp__git__git_worktree_remove",
    "mcp__git__git_merge",
)
_SHELL_TOOLS = ("mcp__shell__shell_exec",)
_INDEX_TOOLS = (
    "mcp__project-index__search",
    "mcp__project-index__file_tree",
    "mcp__project-index__outline",
)


ROLES: dict[RoleName, RoleSpec] = {
    "pm": RoleSpec(
        role="pm",
        prompt_filename="pm.md",
        model_key="pm",
        mcp_server_names=("project-index", "fs"),
        allowed_tools=_INDEX_TOOLS + _FS_READ_TOOLS,
        disallowed_tools=_FS_WRITE_TOOLS,
    ),
    "dev": RoleSpec(
        role="dev",
        prompt_filename="dev.md",
        model_key="dev",
        mcp_server_names=("git", "fs", "shell"),
        allowed_tools=_GIT_READ_TOOLS + _GIT_WRITE_TOOLS + _FS_READ_TOOLS + _FS_WRITE_TOOLS + _SHELL_TOOLS,
        disallowed_tools=(),
    ),
    "qa": RoleSpec(
        role="qa",
        prompt_filename="qa.md",
        model_key="qa",
        mcp_server_names=("git", "fs", "shell"),
        # QA may run tests (shell), read code (git/fs read), and write
        # test files (fs write). It must NOT commit or push — Dev is the
        # only role that merges its own work into the worktree branch.
        allowed_tools=_GIT_READ_TOOLS + _FS_READ_TOOLS + _FS_WRITE_TOOLS + _SHELL_TOOLS,
        disallowed_tools=_GIT_WRITE_TOOLS,
    ),
    "reviewer": RoleSpec(
        role="reviewer",
        prompt_filename="reviewer.md",
        model_key="reviewer",
        mcp_server_names=("git", "project-index"),
        allowed_tools=_GIT_READ_TOOLS + _INDEX_TOOLS,
        disallowed_tools=_GIT_WRITE_TOOLS,
    ),
    "docs": RoleSpec(
        role="docs",
        prompt_filename="docs.md",
        model_key="docs",
        mcp_server_names=("fs", "git"),
        # Docs writes README/CHANGELOG (fs_write) and commits them (git_add, git_commit).
        # It must NOT create branches, checkout, merge, or touch worktrees.
        allowed_tools=_FS_READ_TOOLS
        + _FS_WRITE_TOOLS
        + _GIT_READ_TOOLS
        + ("mcp__git__git_add", "mcp__git__git_commit"),
        disallowed_tools=(
            "mcp__git__git_branch_create",
            "mcp__git__git_checkout",
            "mcp__git__git_worktree_add",
            "mcp__git__git_worktree_remove",
            "mcp__git__git_merge",
        ),
    ),
}


def get_role_spec(role: RoleName) -> RoleSpec:
    """Return the spec for ``role`` or raise ``KeyError`` if unknown."""
    return ROLES[role]
