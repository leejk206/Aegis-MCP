from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any, Protocol

from aegis.agents import AegisAgent
from aegis.core.config import AegisConfig
from aegis.core.task import parse_task
from aegis.graph.node_helpers import append_section, make_agent
from aegis.graph.parser import Block, Done, NoSignal, extract_signal
from aegis.graph.state import TeamState

__all__ = ["reviewer_node"]


class _AgentLike(Protocol):
    async def run(self, prompt: str) -> list[Any]: ...


AgentFactory = Callable[[TeamState, AegisConfig], _AgentLike]


def _default_factory(state: TeamState, config: AegisConfig) -> AegisAgent:
    return make_agent("reviewer", state, config)


def _build_prompt(state: TeamState) -> str:
    task = parse_task(Path(state["task_path"]))
    return (
        f"You are reviewing task {state['task_id']}.\n"
        f"Task body (with Plan and QA report appended):\n\n{task.body}\n\n"
        "Inspect the diff via git_diff and call mcp__signals__done with "
        "`verdict='approve'` (mergeable) or `verdict='rework'` (Dev must iterate)."
    )


async def reviewer_node(
    state: TeamState,
    *,
    config: AegisConfig,
    agent_factory: AgentFactory = _default_factory,
) -> dict[str, Any]:
    agent = agent_factory(state, config)
    messages = await agent.run(_build_prompt(state))
    sig = extract_signal(messages)

    if isinstance(sig, Done):
        verdict = sig.verdict if sig.verdict in ("approve", "rework") else "rework"
        body = sig.summary or "(empty review)"
        if sig.verdict not in ("approve", "rework"):
            body = body + "\n\n_(verdict missing — graph treated as rework)_"
        append_section(Path(state["task_path"]), "Review", body)
        delta: dict[str, Any] = {
            "review": {"verdict": verdict, "summary": sig.summary},
            "current_node": "reviewer",
        }
        if verdict == "rework":
            delta["implementation_status"] = "in_progress"
        return delta
    if isinstance(sig, Block):
        return {"blocked_reason": sig.reason, "current_node": "reviewer"}
    assert isinstance(sig, NoSignal)
    return {
        "blocked_reason": "Reviewer did not signal completion",
        "current_node": "reviewer",
    }
