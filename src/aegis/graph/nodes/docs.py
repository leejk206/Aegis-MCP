from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any, Protocol

from aegis.agents import AegisAgent
from aegis.core.config import AegisConfig
from aegis.core.task import parse_task
from aegis.graph.node_helpers import make_agent
from aegis.graph.parser import Block, Done, NoSignal, extract_signal
from aegis.graph.state import TeamState

__all__ = ["docs_node"]


class _AgentLike(Protocol):
    async def run(self, prompt: str) -> list[Any]: ...


AgentFactory = Callable[[TeamState, AegisConfig], _AgentLike]


def _default_factory(state: TeamState, config: AegisConfig) -> AegisAgent:
    return make_agent("docs", state, config)


def _build_prompt(state: TeamState) -> str:
    task = parse_task(Path(state["task_path"]))
    return (
        f"Task {state['task_id']} just merged to main.\n"
        f"Task body:\n\n{task.body}\n\n"
        "Update README.md, CHANGELOG.md, and any docs/ markdown that need "
        "to reflect this change. Commit your edits to main. When done, "
        "call mcp__signals__done with a one-paragraph summary."
    )


async def docs_node(
    state: TeamState,
    *,
    config: AegisConfig,
    agent_factory: AgentFactory = _default_factory,
) -> dict[str, Any]:
    agent = agent_factory(state, config)
    messages = await agent.run(_build_prompt(state))
    sig = extract_signal(messages)

    if isinstance(sig, Done):
        return {
            "current_node": "docs",
            "implementation_status": "done",
            "review": {
                **(state.get("review") or {}),
                "docs_summary": sig.summary,
            },
        }
    if isinstance(sig, Block):
        return {"blocked_reason": sig.reason, "current_node": "docs"}
    assert isinstance(sig, NoSignal)
    return {
        "blocked_reason": "Docs did not signal completion",
        "current_node": "docs",
    }
