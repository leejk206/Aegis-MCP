from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from aegis.graph.parser import Block, Done, NoSignal, Signal, extract_signal


@dataclass
class _ToolUse:
    name: str
    input: dict[str, Any]
    server_name: str | None = None


@dataclass
class _Assistant:
    content: list[Any]


@dataclass
class _UserResult:
    content: list[Any]


def _tool_use(name: str, args: dict[str, Any], server: str = "signals") -> _ToolUse:
    return _ToolUse(name=name, input=args, server_name=server)


def test_extract_done_with_verdict() -> None:
    msgs = [_Assistant(content=[_tool_use("done", {"summary": "ok", "verdict": "pass"})])]
    sig = extract_signal(msgs)
    assert isinstance(sig, Done)
    assert sig.summary == "ok"
    assert sig.verdict == "pass"


def test_extract_block_reason() -> None:
    msgs = [_Assistant(content=[_tool_use("block", {"reason": "fixtures missing"})])]
    sig = extract_signal(msgs)
    assert isinstance(sig, Block)
    assert sig.reason == "fixtures missing"


def test_extract_returns_no_signal_when_absent() -> None:
    msgs = [_Assistant(content=[{"type": "text", "text": "thinking..."}])]
    sig = extract_signal(msgs)
    assert isinstance(sig, NoSignal)


def test_extract_uses_last_signal_when_multiple() -> None:
    msgs = [
        _Assistant(content=[_tool_use("done", {"summary": "first"})]),
        _Assistant(content=[_tool_use("done", {"summary": "second"})]),
    ]
    sig = extract_signal(msgs)
    assert isinstance(sig, Done)
    assert sig.summary == "second"


def test_extract_ignores_unrelated_tool_use() -> None:
    msgs = [
        _Assistant(content=[_tool_use("git_status", {}, server="git")]),
        _Assistant(content=[_tool_use("done", {"summary": "real"}, server="signals")]),
    ]
    sig = extract_signal(msgs)
    assert isinstance(sig, Done)
    assert sig.summary == "real"


def test_extract_handles_dict_messages() -> None:
    msgs = [
        {
            "type": "assistant",
            "content": [
                {
                    "type": "tool_use",
                    "name": "mcp__signals__done",
                    "input": {"summary": "dict-form", "verdict": "approve"},
                }
            ],
        }
    ]
    sig: Signal = extract_signal(msgs)
    assert isinstance(sig, Done)
    assert sig.verdict == "approve"
