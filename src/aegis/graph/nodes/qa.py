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

__all__ = ["qa_node", "QA_SHELL_ALLOW"]

QA_SHELL_ALLOW = "pytest,ruff,mypy,python"


class _AgentLike(Protocol):
    async def run(self, prompt: str) -> list[Any]: ...


AgentFactory = Callable[[TeamState, AegisConfig], _AgentLike]


def _default_factory(state: TeamState, config: AegisConfig) -> AegisAgent:
    return make_agent("qa", state, config, shell_allow_cmds=QA_SHELL_ALLOW)


def _build_prompt(state: TeamState) -> str:
    task = parse_task(Path(state["task_path"]))
    return (
        f"You are testing task {state['task_id']} in worktree "
        f"{state['worktree_path']}.\n"
        f"Task body:\n\n{task.body}\n\n"
        "Run the test suite, write any missing test files, and call "
        "mcp__signals__done with `verdict='pass'` if all acceptance "
        "criteria are met, or `verdict='fail'` if not."
    )


async def qa_node(
    state: TeamState,
    *,
    config: AegisConfig,
    agent_factory: AgentFactory = _default_factory,
) -> dict[str, Any]:
    agent = agent_factory(state, config)
    messages = await agent.run(_build_prompt(state))
    sig = extract_signal(messages)

    if isinstance(sig, Done):
        verdict = sig.verdict if sig.verdict in ("pass", "fail") else "fail"
        body = sig.summary or "(no QA report)"
        if sig.verdict not in ("pass", "fail"):
            body = body + "\n\n_(verdict missing — graph treated as fail)_"
        append_section(Path(state["task_path"]), "QA report", body)
        delta: dict[str, Any] = {
            "test_report": {"verdict": verdict, "summary": sig.summary},
            "current_node": "qa",
        }
        if verdict == "fail":
            delta["implementation_status"] = "in_progress"
        return delta
    if isinstance(sig, Block):
        return {"blocked_reason": sig.reason, "current_node": "qa"}
    assert isinstance(sig, NoSignal)
    return {
        "blocked_reason": "QA did not signal completion",
        "current_node": "qa",
    }
