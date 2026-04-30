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

__all__ = ["dev_node", "DEV_SHELL_ALLOW"]

DEV_SHELL_ALLOW = "pytest,ruff,mypy,python,pip,npm,pnpm,node"


class _AgentLike(Protocol):
    async def run(self, prompt: str) -> list[Any]: ...


AgentFactory = Callable[[TeamState, AegisConfig], _AgentLike]


def _default_factory(state: TeamState, config: AegisConfig) -> AegisAgent:
    return make_agent("dev", state, config, shell_allow_cmds=DEV_SHELL_ALLOW)


def _build_prompt(state: TeamState) -> str:
    task = parse_task(Path(state["task_path"]))
    plan = state.get("plan") or {}
    plan_text = plan.get("summary", "(no plan available)")
    return (
        f"You are implementing task {state['task_id']} in worktree "
        f"{state['worktree_path']}.\n"
        f"Task body:\n\n{task.body}\n\n"
        f"PM plan:\n\n{plan_text}\n\n"
        "Make the necessary commits in the worktree, then call "
        "mcp__signals__done with a one-paragraph summary."
    )


async def dev_node(
    state: TeamState,
    *,
    config: AegisConfig,
    agent_factory: AgentFactory = _default_factory,
) -> dict[str, Any]:
    agent = agent_factory(state, config)
    messages = await agent.run(_build_prompt(state))
    sig = extract_signal(messages)
    if isinstance(sig, Done):
        return {"implementation_status": "done", "current_node": "dev"}
    if isinstance(sig, Block):
        return {"blocked_reason": sig.reason, "current_node": "dev"}
    assert isinstance(sig, NoSignal)
    return {
        "blocked_reason": "Dev did not signal completion",
        "current_node": "dev",
    }
