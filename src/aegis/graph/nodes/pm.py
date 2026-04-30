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

__all__ = ["pm_node"]


class _AgentLike(Protocol):
    async def run(self, prompt: str) -> list[Any]: ...


AgentFactory = Callable[[TeamState, AegisConfig], _AgentLike]


def _default_factory(state: TeamState, config: AegisConfig) -> AegisAgent:
    return make_agent("pm", state, config)


def _build_prompt(state: TeamState) -> str:
    task = parse_task(Path(state["task_path"]))
    return (
        f"You are planning task {state['task_id']}.\n"
        f"Task markdown body:\n\n{task.body}\n\n"
        "Use the project-index and fs MCP tools to study the codebase, "
        "then call mcp__signals__done with a structured plan in the "
        "summary argument."
    )


async def pm_node(
    state: TeamState,
    *,
    config: AegisConfig,
    agent_factory: AgentFactory = _default_factory,
) -> dict[str, Any]:
    agent = agent_factory(state, config)
    prompt = _build_prompt(state)
    messages = await agent.run(prompt)
    sig = extract_signal(messages)

    if isinstance(sig, Done):
        append_section(Path(state["task_path"]), "Plan", sig.summary)
        return {
            "plan": {"summary": sig.summary, "verdict": sig.verdict},
            "implementation_status": "in_progress",
            "current_node": "pm",
        }
    if isinstance(sig, Block):
        return {
            "blocked_reason": sig.reason,
            "current_node": "pm",
        }
    assert isinstance(sig, NoSignal)
    return {
        "blocked_reason": "PM did not signal completion",
        "current_node": "pm",
    }
