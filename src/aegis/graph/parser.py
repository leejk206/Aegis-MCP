"""Extract a structured ``Signal`` from a raw agent message stream.

The Claude Agent SDK returns a list whose entries may be SDK message
dataclasses (``AssistantMessage``, ``UserMessage``) or, in tests, plain
dicts with the same shape. The parser is duck-typed so it works with
either.

A "signals" tool-use is one of:

  * tool name ``done`` (or ``mcp__signals__done``) on server ``signals``
  * tool name ``block`` (or ``mcp__signals__block``) on server ``signals``

The **last** matching tool-use wins. If no tool-use is present, returns
``NoSignal()``.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

__all__ = ["Signal", "Done", "Block", "NoSignal", "extract_signal"]


@dataclass(frozen=True, slots=True)
class Done:
    summary: str
    verdict: str | None = None
    raw: dict[str, Any] | None = None


@dataclass(frozen=True, slots=True)
class Block:
    reason: str
    raw: dict[str, Any] | None = None


@dataclass(frozen=True, slots=True)
class NoSignal:
    pass


Signal = Done | Block | NoSignal


def _content_iter(message: Any) -> list[Any]:
    if isinstance(message, dict):
        return list(message.get("content", []) or [])
    content = getattr(message, "content", None)
    if content is None:
        return []
    return list(content)


def _tool_use_fields(block: Any) -> tuple[str, dict[str, Any], str | None] | None:
    """Return (name, input, server_name) if ``block`` is a tool-use.

    ``server_name`` may be ``None`` if not exposed; in that case we
    accept the call as long as the tool name matches one of our
    signals (the model never names a non-MCP tool ``done``/``block``
    in this codebase).
    """
    if isinstance(block, dict):
        kind = block.get("type")
        name = block.get("name")
        if kind != "tool_use" or name is None:
            return None
        args = block.get("input") or {}
        server = block.get("server_name")
        return str(name), dict(args), server if server is None else str(server)

    name = getattr(block, "name", None)
    if name is None:
        return None
    if getattr(block, "type", None) is not None and getattr(block, "type", None) != "tool_use":
        return None
    args = getattr(block, "input", None) or {}
    if not isinstance(args, dict):
        return None
    server = getattr(block, "server_name", None)
    return str(name), dict(args), None if server is None else str(server)


def _is_signals_tool(name: str, server: str | None, expected: str) -> bool:
    if name == expected and (server is None or server == "signals"):
        return True
    if name == f"mcp__signals__{expected}":
        return True
    return False


def extract_signal(messages: list[Any]) -> Signal:
    last_done: Done | None = None
    last_block: Block | None = None
    last_was_done: bool = True  # tracks ordering between done/block
    for msg in messages:
        for block in _content_iter(msg):
            fields = _tool_use_fields(block)
            if fields is None:
                continue
            name, args, server = fields
            if _is_signals_tool(name, server, "done"):
                last_done = Done(
                    summary=str(args.get("summary", "")),
                    verdict=(
                        str(args["verdict"]) if "verdict" in args and args["verdict"] else None
                    ),
                    raw=args,
                )
                last_was_done = True
            elif _is_signals_tool(name, server, "block"):
                last_block = Block(reason=str(args.get("reason", "")), raw=args)
                last_was_done = False
    if last_done is None and last_block is None:
        return NoSignal()
    if last_was_done and last_done is not None:
        return last_done
    if last_block is not None:
        return last_block
    # Fallback: whichever is non-None
    return last_done if last_done is not None else last_block  # type: ignore[return-value]
