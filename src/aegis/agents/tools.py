"""Build the ``ClaudeAgentOptions.mcp_servers`` dict for a given role.

Phase-2's four MCP servers are distributed as console scripts
(``aegis-git-mcp``, ``aegis-fs-mcp``, ``aegis-shell-mcp``,
``aegis-project-index-mcp``). When the Claude Agent SDK spawns them,
it uses the ``stdio`` transport with ``command`` + ``args`` + ``env``.
This module turns a ``(role, worktree_path)`` pair into exactly that
dict, in the exact shape ``claude_agent_sdk.ClaudeAgentOptions``
accepts.
"""

from __future__ import annotations

from pathlib import Path

from claude_agent_sdk.types import McpServerConfig

from aegis.agents.registry import ROLES, RoleName

# Phase-2 console-script names, keyed by the short MCP server name used
# in AegisConfig.mcp.servers and in RoleSpec.mcp_server_names.
SERVER_COMMANDS: dict[str, str] = {
    "git": "aegis-git-mcp",
    "fs": "aegis-fs-mcp",
    "shell": "aegis-shell-mcp",
    "project-index": "aegis-project-index-mcp",
}


def build_mcp_servers(
    role: RoleName,
    worktree: Path,
    shell_allow_cmds: str | None = None,
) -> dict[str, McpServerConfig]:
    """Return ``{server_name: {type,command,args,env}}`` for ``role``.

    ``worktree`` is passed verbatim as ``--scope`` to every server. It
    must exist on disk — the MCP server would crash immediately
    otherwise, and surfacing that as a clean ``FileNotFoundError`` here
    avoids a confusing stdio handshake error later.

    ``shell_allow_cmds`` populates ``ALLOW_CMDS`` only on the shell
    server. If the role has no shell access the parameter is silently
    ignored (this lets the caller always pass it without branching).
    """
    spec = ROLES[role]

    worktree_resolved = worktree.resolve()
    if not worktree_resolved.exists():
        raise FileNotFoundError(
            f"worktree {worktree_resolved} does not exist; create it before spawning agents"
        )

    servers: dict[str, McpServerConfig] = {}
    scope_args = ["--scope", str(worktree_resolved)]

    for server_name in spec.mcp_server_names:
        command = SERVER_COMMANDS[server_name]
        env: dict[str, str] = {}
        if server_name == "shell" and shell_allow_cmds is not None:
            env = {"ALLOW_CMDS": shell_allow_cmds}
        servers[server_name] = {
            "type": "stdio",
            "command": command,
            "args": list(scope_args),
            "env": env,
        }

    return servers
