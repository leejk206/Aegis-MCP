"""In-process MCP server exposing the ``done`` and ``block`` signals.

Every ``AegisAgent`` invocation in Phase 4 spawns a fresh signals
server (one per task per node) and merges it into the role's
``mcp_servers`` dict alongside the four stdio servers from Phase 2.

The tool callbacks themselves return a static acknowledgement payload;
the **signal that matters** is the ``tool_use`` block in the model's
output, which :mod:`aegis.graph.parser` extracts.

Tool naming, when surfaced through the SDK to the model, follows the
``mcp__<server>__<tool>`` convention — i.e. the model sees
``mcp__signals__done`` and ``mcp__signals__block``.
"""

from __future__ import annotations

from typing import Any

from claude_agent_sdk import create_sdk_mcp_server, tool
from claude_agent_sdk.types import McpSdkServerConfig

SIGNALS_SERVER_NAME = "signals"

__all__ = ["SIGNALS_SERVER_NAME", "build_signals_server"]


@tool(
    "done",
    (
        "Signal task completion. summary is required free-form text. "
        "verdict is one of 'pass' | 'fail' | 'approve' | 'rework' for "
        "QA and Reviewer roles; PM/Dev/Docs leave it absent."
    ),
    {"summary": str, "verdict": str},
)
async def _done(args: dict[str, Any]) -> dict[str, Any]:
    return {"content": [{"type": "text", "text": "ok"}]}


@tool(
    "block",
    (
        "Signal that the role cannot continue. reason is a one-sentence "
        "human-readable blocker."
    ),
    {"reason": str},
)
async def _block(args: dict[str, Any]) -> dict[str, Any]:
    return {"content": [{"type": "text", "text": "ok"}]}


def build_signals_server() -> tuple[str, McpSdkServerConfig]:
    """Return ``(name, McpSdkServerConfig)`` for one fresh signals server.

    The returned tuple is meant to be merged into the existing
    ``mcp_servers`` dict produced by
    :func:`aegis.agents.tools.build_mcp_servers`. The SDK config dict
    has shape ``{"type": "sdk", "name": "signals", "instance": <Server>}``
    — the ``instance`` carries the registered ``done``/``block`` tools.
    """
    config = create_sdk_mcp_server(name=SIGNALS_SERVER_NAME, tools=[_done, _block])
    return SIGNALS_SERVER_NAME, config
