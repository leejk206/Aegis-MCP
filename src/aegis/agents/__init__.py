"""Role-based agent units built on the Claude Agent SDK.

Each Aegis role (PM, Dev, QA, Reviewer, Docs) is instantiated as an
``AegisAgent`` bound to one task's worktree. Per-role MCP tool access
is declared in :mod:`aegis.agents.registry` and realised by
:func:`aegis.agents.tools.build_mcp_servers`, which spawns the four
Phase-2 ``aegis-*-mcp`` console scripts over stdio with the worktree as
``--scope``. The ``AegisAgent`` wrapper itself is thin: its only public
async method, ``run``, drives ``claude_agent_sdk.ClaudeSDKClient`` once
and returns the full list of messages.
"""

try:
    from aegis.agents.base import AegisAgent, build_options, load_prompt
except ImportError:
    pass  # base.py created in Task 4

from aegis.agents.registry import ROLES, RoleName, RoleSpec

try:
    from aegis.agents.tools import build_mcp_servers
except ImportError:
    pass  # tools.py created in Task 5

__all__ = [
    "AegisAgent",
    "ROLES",
    "RoleName",
    "RoleSpec",
    "build_mcp_servers",
    "build_options",
    "load_prompt",
]
