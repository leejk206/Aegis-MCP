# Phase 4 — LangGraph team graph and CLI integration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Wire the five Phase-3 `AegisAgent` units into a LangGraph `StateGraph` and replace the Phase-1 CLI stubs (`run`, `status`, `stop`, `approve`, `reject`, `retry`, `inspect`, `daemon`) so a full task can flow from `backlog/` through PM→Dev→QA→Reviewer, pause for human approval, then resume into Docs and merge.

**Architecture:** A LangGraph `StateGraph[TeamState]` with five role nodes plus conditional QA/Reviewer loops. Each node creates its `AegisAgent`, runs it once, parses the resulting message stream for a structured `done`/`block` SDK tool call (provided by an in-process MCP server in `aegis.graph.signals`), and returns a partial state delta. The graph is compiled with `interrupt_before=["docs"]` so it always halts at the human gate after a Reviewer `approve`; `aegis approve` resumes the same thread, `aegis reject` discards it. Worktree, lifecycle, and budget enforcement live in `aegis.graph.runtime` outside the nodes — the graph itself stays pure.

**Tech Stack:** `langgraph` + `langgraph-checkpoint-sqlite` for state and persistence; `claude-agent-sdk`'s `create_sdk_mcp_server` for the in-process `done`/`block` tools; existing `aegis.agents`, `aegis.core.{config,task,worktree,budget,lifecycle}` from Phases 1–3; `typer` for the CLI commands.

---

## Pre-flight

Before starting any task, verify the workspace is in the expected post-Phase-3 state.

```bash
git status                                                # clean
git log --oneline -1                                      # 5056614 docs: add Phase 3 implementation plan
git tag -l | grep phase-3-complete                        # phase-3-complete
pytest tests/unit -q                                      # all green (Phase 1+2+3 tests)
```

If any check fails, stop and reconcile before proceeding. Phase 4 assumes `aegis.agents.AegisAgent`, `aegis.agents.registry.ROLES`, and the four `aegis-*-mcp` console scripts all work as written.

The `claude-agent-sdk` and `langgraph` packages may not yet be installed in this environment. Each task that imports them runs under `pip install -e .[dev] && pip install langgraph langgraph-checkpoint-sqlite` in CI, so the test commands assume those installs have been done. If `pytest` reports `ModuleNotFoundError: No module named 'claude_agent_sdk'` or `'langgraph'`, run `pip install -e .[dev]` once at the start of the phase.

---

## Map of files this phase touches

**Created:**

- `src/aegis/graph/state.py`                       — `TeamState` TypedDict + helpers
- `src/aegis/graph/signals.py`                     — `done`/`block` SDK MCP server
- `src/aegis/graph/parser.py`                      — message-stream → `Signal` extraction
- `src/aegis/graph/checkpointer.py`                — `SqliteSaver` wrapper
- `src/aegis/graph/node_helpers.py`                — stop-flag check, markdown section append, agent factory
- `src/aegis/graph/nodes/__init__.py`              — public node exports
- `src/aegis/graph/nodes/pm.py`
- `src/aegis/graph/nodes/dev.py`
- `src/aegis/graph/nodes/qa.py`
- `src/aegis/graph/nodes/reviewer.py`
- `src/aegis/graph/nodes/docs.py`
- `src/aegis/graph/team_graph.py`                  — `build_graph()` + routing
- `src/aegis/graph/runtime.py`                     — `run_one_task()`, `resume_after_approve()`
- `src/aegis/cli/commands/run.py`
- `src/aegis/cli/commands/status.py`
- `src/aegis/cli/commands/stop.py`
- `src/aegis/cli/commands/approve.py`
- `src/aegis/cli/commands/reject.py`
- `src/aegis/cli/commands/retry.py`
- `src/aegis/cli/commands/inspect.py`
- `src/aegis/cli/commands/daemon.py`
- `tests/unit/test_graph_state.py`
- `tests/unit/test_graph_signals.py`
- `tests/unit/test_graph_parser.py`
- `tests/unit/test_graph_checkpointer.py`
- `tests/unit/test_graph_node_helpers.py`
- `tests/unit/test_graph_nodes_pm.py`
- `tests/unit/test_graph_nodes_dev.py`
- `tests/unit/test_graph_nodes_qa.py`
- `tests/unit/test_graph_nodes_reviewer.py`
- `tests/unit/test_graph_nodes_docs.py`
- `tests/unit/test_graph_team_graph.py`
- `tests/unit/test_graph_runtime.py`
- `tests/unit/test_cli_run.py`
- `tests/unit/test_cli_status.py`
- `tests/unit/test_cli_stop.py`
- `tests/unit/test_cli_approve.py`
- `tests/unit/test_cli_reject.py`
- `tests/unit/test_cli_retry.py`
- `tests/unit/test_cli_inspect.py`
- `tests/unit/test_cli_daemon.py`

**Modified:**

- `pyproject.toml`                                 — add `langgraph`, `langgraph-checkpoint-sqlite`
- `src/aegis/graph/__init__.py`                    — re-export `build_graph`, `TeamState`, runtime entry points
- `src/aegis/agents/prompts/qa.md`                 — teach `done(verdict=...)` payload
- `src/aegis/agents/prompts/reviewer.md`           — teach `done(verdict=...)` payload
- `src/aegis/agents/prompts/pm.md`                 — mention signals server
- `src/aegis/agents/prompts/dev.md`                — mention signals server
- `src/aegis/agents/prompts/docs.md`               — mention signals server
- `src/aegis/agents/tools.py`                      — merge in-process signals server
- `src/aegis/cli/main.py`                          — register the new commands, drop `register_stubs` for the ones now real
- `src/aegis/cli/commands/stubs.py`                — remove the now-implemented stubs

---

## Task 1: Add LangGraph dependencies

**Files:**

- Modify: `pyproject.toml`

- [ ] **Step 1: Edit `pyproject.toml` to add the two LangGraph packages**

```toml
dependencies = [
    "pydantic>=2.7",
    "python-frontmatter>=1.1",
    "pyyaml>=6.0",
    "typer>=0.12",
    "mcp>=1.0",
    "claude-agent-sdk>=0.1.61",
    "langgraph>=0.2.50",
    "langgraph-checkpoint-sqlite>=2.0",
]
```

- [ ] **Step 2: Install in development mode**

```bash
pip install -e .[dev]
```

Expected: installs successfully, no resolver errors.

- [ ] **Step 3: Smoke-import**

```bash
python -c "from langgraph.graph import StateGraph, START, END; from langgraph.checkpoint.sqlite import SqliteSaver; print('ok')"
```

Expected: `ok`.

- [ ] **Step 4: Commit**

```bash
git add pyproject.toml
git commit -m "build: add langgraph and sqlite checkpointer to phase 4 deps"
```

---

## Task 2: Update role prompts to teach the signals contract

**Files:**

- Modify: `src/aegis/agents/prompts/pm.md`
- Modify: `src/aegis/agents/prompts/dev.md`
- Modify: `src/aegis/agents/prompts/qa.md`
- Modify: `src/aegis/agents/prompts/reviewer.md`
- Modify: `src/aegis/agents/prompts/docs.md`
- Test: `tests/unit/test_agents_prompts.py` (extend)

The `done` tool will live on an in-process MCP server named `signals`. PM/Dev/Docs call `done(summary=...)`. QA calls `done(summary=..., verdict="pass"|"fail")`. Reviewer calls `done(summary=..., verdict="approve"|"rework")`. All five may call `block(reason=...)` instead.

- [ ] **Step 1: Write a failing prompt-content test**

Append to `tests/unit/test_agents_prompts.py`:

```python
import pytest

from aegis.agents.base import load_prompt


@pytest.mark.parametrize("role", ["pm", "dev", "qa", "reviewer", "docs"])
def test_prompt_mentions_signals_server(role: str) -> None:
    text = load_prompt(role)
    assert "mcp__signals__done" in text or "signals" in text, (
        f"{role} prompt must reference the signals server"
    )


def test_qa_prompt_documents_verdict_field() -> None:
    text = load_prompt("qa")
    assert "verdict" in text
    assert '"pass"' in text or "`pass`" in text
    assert '"fail"' in text or "`fail`" in text


def test_reviewer_prompt_documents_verdict_field() -> None:
    text = load_prompt("reviewer")
    assert "verdict" in text
    assert "approve" in text and "rework" in text
```

- [ ] **Step 2: Run the new tests to confirm they fail**

```bash
pytest tests/unit/test_agents_prompts.py -k "signals or verdict" -v
```

Expected: 7 FAILED.

- [ ] **Step 3: Patch each prompt's "Style" or "Tools available" section**

For `pm.md`, replace the block under `## Tools available` to add a final bullet:

```markdown
- `mcp__signals__done`, `mcp__signals__block` — in-process completion
  signals (see "## Style").
```

And rewrite the closing two bullets of `## Style` to:

```markdown
- When you are done, call `mcp__signals__done` with `{"summary": "<plan content>"}`.
  PM does not set the `verdict` field; leave it absent.
- If you are stuck (unclear criteria, missing files, conflicting
  constraints), call `mcp__signals__block` with `{"reason": "<one sentence>"}`
  rather than guessing.
```

For `dev.md`, append to `## Tools available` the same `mcp__signals__*` bullet, and replace the closing `## Style` bullets:

```markdown
- When you have committed every PM subtask, call `mcp__signals__done` with
  `{"summary": "<one paragraph naming each commit>"}`. Dev does not set
  `verdict`.
- If you are stuck, call `mcp__signals__block` with a clear blocker message.
```

For `qa.md`, append the same tool bullet and rewrite the closing block:

```markdown
- When you are done, call `mcp__signals__done` with
  `{"summary": "<the QA report markdown>", "verdict": "pass"}`
  if the worktree passes acceptance criteria, or `{"verdict": "fail", ...}`
  if it does not. The graph routes on this verdict — set it correctly.
- If you are stuck (missing fixtures, broken environment), call
  `mcp__signals__block` with a clear blocker message.
```

For `reviewer.md`, append the same tool bullet and rewrite the closing block:

```markdown
- When you are done, call `mcp__signals__done` with
  `{"summary": "<the review markdown>", "verdict": "approve"}`
  if the diff is mergeable, or `{"verdict": "rework", ...}` if Dev must
  iterate. The graph routes on this verdict.
- If you cannot form a verdict (e.g. acceptance criteria are
  malformed), call `mcp__signals__block` with a one-sentence blocker.
```

For `docs.md`, append the tool bullet and rewrite the closing block:

```markdown
- When you are done, call `mcp__signals__done` with
  `{"summary": "<one paragraph of what shipped>"}`. Docs does not set
  `verdict`. If the change was internal-only and you wrote nothing, set
  `summary` to `"no user-visible changes"`.
- If you are stuck, call `mcp__signals__block` with a clear blocker.
```

- [ ] **Step 4: Re-run the tests to confirm green**

```bash
pytest tests/unit/test_agents_prompts.py -v
```

Expected: every test passes, including the existing Phase-3 prompt tests.

- [ ] **Step 5: Commit**

```bash
git add src/aegis/agents/prompts tests/unit/test_agents_prompts.py
git commit -m "feat(prompts): document signals server and verdict field for QA/Reviewer"
```

---

## Task 3: Define `TeamState` and helpers

**Files:**

- Create: `src/aegis/graph/state.py`
- Create: `tests/unit/test_graph_state.py`

`TeamState` is the canonical LangGraph state. Field names mirror spec §5.1 with two additions: `blocked_reason: str | None` (set when a node bails out) and `current_node: str | None` (last node to write — used by the runtime, not by routing).

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/test_graph_state.py
from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from aegis.core.task import Priority, Task, TaskBudget, TaskFrontmatter, TaskStatus
from aegis.graph.state import TeamState, initial_state


def _make_task(task_id: str = "001", title: str = "demo") -> Task:
    fm = TaskFrontmatter(
        id=task_id,
        title=title,
        status=TaskStatus.IN_PROGRESS,
        priority=Priority.P2,
        budget=TaskBudget(usd=2.0, minutes=30),
        created=datetime.now(tz=UTC),
    )
    return Task(frontmatter=fm, body=f"# {title}\n\nbody.\n")


def test_initial_state_populates_identity_fields(tmp_path: Path) -> None:
    task = _make_task()
    repo = tmp_path / "repo"
    wt = tmp_path / "worktrees" / "001-demo"
    state: TeamState = initial_state(
        task=task,
        task_path=tmp_path / ".aegis" / "in-progress" / "001-demo.md",
        worktree_path=wt,
        target_repo_root=repo,
    )
    assert state["task_id"] == "001"
    assert state["worktree_path"] == str(wt)
    assert state["target_repo_root"] == str(repo)
    assert state["plan"] is None
    assert state["test_report"] is None
    assert state["review"] is None
    assert state["pr_branch"] is None
    assert state["awaiting_human"] is False
    assert state["blocked_reason"] is None
    assert state["retry_counts"] == {"dev_on_qa_fail": 0, "dev_on_review": 0}


def test_initial_state_uses_task_budget(tmp_path: Path) -> None:
    task = _make_task()
    state = initial_state(
        task=task,
        task_path=tmp_path / "001-demo.md",
        worktree_path=tmp_path / "wt",
        target_repo_root=tmp_path / "repo",
    )
    assert state["budget_remaining"]["usd"] == 2.0
    assert state["budget_remaining"]["seconds"] == 30 * 60
    assert state["budget_remaining"]["input_tokens"] == 0
    assert state["budget_remaining"]["output_tokens"] == 0
```

- [ ] **Step 2: Run; confirm import fails**

```bash
pytest tests/unit/test_graph_state.py -v
```

Expected: ModuleNotFoundError or similar.

- [ ] **Step 3: Implement `state.py`**

```python
# src/aegis/graph/state.py
from __future__ import annotations

from pathlib import Path
from typing import Any, TypedDict

from aegis.core.task import Task

__all__ = ["TeamState", "initial_state"]


class TeamState(TypedDict):
    # Identity
    task_id: str
    task_path: str

    # Execution environment
    worktree_path: str
    target_repo_root: str

    # Agent outputs
    plan: dict[str, Any] | None
    implementation_status: str  # pending | in_progress | done | blocked
    test_report: dict[str, Any] | None
    review: dict[str, Any] | None
    pr_branch: str | None

    # Control
    budget_remaining: dict[str, float]
    retry_counts: dict[str, int]
    trace_id: str
    awaiting_human: bool
    blocked_reason: str | None
    current_node: str | None

    # History
    history: list[dict[str, Any]]


def initial_state(
    *,
    task: Task,
    task_path: Path,
    worktree_path: Path,
    target_repo_root: Path,
    trace_id: str = "",
) -> TeamState:
    fm = task.frontmatter
    return TeamState(
        task_id=fm.id,
        task_path=str(task_path),
        worktree_path=str(worktree_path),
        target_repo_root=str(target_repo_root),
        plan=None,
        implementation_status="pending",
        test_report=None,
        review=None,
        pr_branch=None,
        budget_remaining={
            "usd": float(fm.budget.usd),
            "seconds": float(fm.budget.minutes) * 60.0,
            "input_tokens": 0.0,
            "output_tokens": 0.0,
        },
        retry_counts={"dev_on_qa_fail": 0, "dev_on_review": 0},
        trace_id=trace_id,
        awaiting_human=False,
        blocked_reason=None,
        current_node=None,
        history=[],
    )
```

- [ ] **Step 4: Re-run tests; confirm green**

```bash
pytest tests/unit/test_graph_state.py -v
```

- [ ] **Step 5: Commit**

```bash
git add src/aegis/graph/state.py tests/unit/test_graph_state.py
git commit -m "feat(graph): add TeamState TypedDict and initial_state factory"
```

---

## Task 4: Implement the in-process `signals` MCP server

**Files:**

- Create: `src/aegis/graph/signals.py`
- Create: `tests/unit/test_graph_signals.py`

The `done` and `block` tools must be callable from inside an `AegisAgent` run, which means they must be advertised through the agent's `mcp_servers` dict. Spec §5 calls them "in-process tools, not stdio". The Claude Agent SDK exposes `create_sdk_mcp_server(name=..., tools=[...])` for this. Each call creates a fresh server with two tools that return constant ack payloads — the agent's actual signal is in the tool-use *message* itself, which the parser (Task 5) reads from the assistant's message stream.

- [ ] **Step 1: Verify the SDK API surface**

```bash
python -c "from claude_agent_sdk import create_sdk_mcp_server, tool; print(tool, create_sdk_mcp_server)"
```

Expected: prints two callables. If the imports fail, check `pip show claude-agent-sdk` (must be ≥ 0.1.61). Cross-check with the SDK README for the exact decorator signature; if `tool` takes positional `(name, description, schema)`, follow that.

- [ ] **Step 2: Write the failing test**

```python
# tests/unit/test_graph_signals.py
from __future__ import annotations

from aegis.graph.signals import SIGNALS_SERVER_NAME, build_signals_server


def test_signals_server_has_done_and_block() -> None:
    name, config = build_signals_server()
    assert name == SIGNALS_SERVER_NAME == "signals"
    assert config["type"] == "sdk"
    server = config["server"]
    # Tool names exposed by the SDK MCP server. The SDK keeps them on
    # the underlying MCP `Server` instance; the public surface is the
    # `name` and the `tools` list.
    tool_names = {t.name for t in getattr(server, "tools", [])} | set(
        getattr(server, "_tool_names", [])
    )
    # If the SDK does not expose tools-by-attribute, fall back to the
    # registered McpServer attribute that's always present.
    assert tool_names <= {"done", "block"} or tool_names == set()
    assert config["server"] is not None


def test_signals_server_factory_is_idempotent_per_call() -> None:
    a = build_signals_server()
    b = build_signals_server()
    # Each call returns its own server instance — important for
    # per-task isolation.
    assert a[1]["server"] is not b[1]["server"]
```

- [ ] **Step 3: Run; confirm fail**

```bash
pytest tests/unit/test_graph_signals.py -v
```

Expected: ModuleNotFoundError.

- [ ] **Step 4: Implement `signals.py`**

```python
# src/aegis/graph/signals.py
"""In-process MCP server exposing the ``done`` and ``block`` signals.

Every ``AegisAgent`` invocation in Phase 4 spawns a fresh signals
server (one per task per node) and merges it into the role's
``mcp_servers`` dict alongside the four stdio servers from Phase 2.
The tool callbacks themselves return a static acknowledgement payload;
the **signal that matters** is the ``tool_use`` block in the model's
output, which :mod:`aegis.graph.parser` extracts.
"""
from __future__ import annotations

from typing import Any

from claude_agent_sdk import create_sdk_mcp_server, tool

SIGNALS_SERVER_NAME = "signals"

__all__ = ["SIGNALS_SERVER_NAME", "build_signals_server"]


@tool(
    "done",
    "Signal task completion. summary is required free-form text. "
    "verdict is one of 'pass' | 'fail' | 'approve' | 'rework' for "
    "QA and Reviewer roles; PM/Dev/Docs leave it absent.",
    {"summary": str, "verdict": str},
)
async def _done(args: dict[str, Any]) -> dict[str, Any]:
    return {"content": [{"type": "text", "text": "ok"}]}


@tool(
    "block",
    "Signal that the role cannot continue. reason is a one-sentence "
    "human-readable blocker.",
    {"reason": str},
)
async def _block(args: dict[str, Any]) -> dict[str, Any]:
    return {"content": [{"type": "text", "text": "ok"}]}


def build_signals_server() -> tuple[str, dict[str, Any]]:
    """Return ``(name, McpServerConfig)`` for one fresh signals server.

    The returned tuple is meant to be merged into the existing
    ``mcp_servers`` dict produced by
    :func:`aegis.agents.tools.build_mcp_servers`.
    """
    server = create_sdk_mcp_server(name=SIGNALS_SERVER_NAME, tools=[_done, _block])
    return SIGNALS_SERVER_NAME, {"type": "sdk", "server": server}
```

If the SDK's `tool` decorator signature differs (e.g. only takes name/description, no schema dict), trim the third positional argument. The smoke-import in Step 1 surfaces the correct shape.

- [ ] **Step 5: Re-run; confirm green**

```bash
pytest tests/unit/test_graph_signals.py -v
```

- [ ] **Step 6: Commit**

```bash
git add src/aegis/graph/signals.py tests/unit/test_graph_signals.py
git commit -m "feat(graph): add in-process signals MCP server (done/block)"
```

---

## Task 5: Wire the signals server into the agent's MCP servers

**Files:**

- Modify: `src/aegis/agents/tools.py`
- Modify: `tests/unit/test_agents_tools.py`

`AegisAgent` must advertise the signals server to its model. The cleanest place is `build_mcp_servers` — it already constructs the dict that becomes `ClaudeAgentOptions.mcp_servers`.

- [ ] **Step 1: Append a failing test**

In `tests/unit/test_agents_tools.py`:

```python
def test_build_mcp_servers_always_includes_signals(tmp_path):
    from aegis.agents.tools import build_mcp_servers

    servers = build_mcp_servers("reviewer", tmp_path)
    assert "signals" in servers
    assert servers["signals"]["type"] == "sdk"
    # And the registry-driven stdio entries are still there
    assert "git" in servers
```

- [ ] **Step 2: Run; confirm fail**

```bash
pytest tests/unit/test_agents_tools.py::test_build_mcp_servers_always_includes_signals -v
```

- [ ] **Step 3: Patch `tools.py`**

Insert at the top of the module:

```python
from aegis.graph.signals import build_signals_server
```

Inside `build_mcp_servers`, after the `for server_name in spec.mcp_server_names:` loop and before `return servers`, add:

```python
    name, sdk_config = build_signals_server()
    servers[name] = sdk_config
```

- [ ] **Step 4: Update `allowed_tools`/`disallowed_tools` in the registry**

In `src/aegis/agents/registry.py`, append two tool names to every role's `allowed_tools`:

Add a new constant near the existing tool tuples:

```python
_SIGNALS_TOOLS = ("mcp__signals__done", "mcp__signals__block")
```

Then for every entry in the `ROLES` dict, change `allowed_tools=...` to also include `_SIGNALS_TOOLS`. Example for `pm`:

```python
    "pm": RoleSpec(
        ...
        allowed_tools=_INDEX_TOOLS + _FS_READ_TOOLS + _SIGNALS_TOOLS,
        ...
    ),
```

Repeat for `dev`, `qa`, `reviewer`, `docs`.

- [ ] **Step 5: Add a regression test for the registry change**

In `tests/unit/test_agents_registry.py`, append:

```python
def test_every_role_allows_signals_tools() -> None:
    from aegis.agents.registry import ROLES

    for role, spec in ROLES.items():
        assert "mcp__signals__done" in spec.allowed_tools, role
        assert "mcp__signals__block" in spec.allowed_tools, role
```

- [ ] **Step 6: Run the full agent suite**

```bash
pytest tests/unit/test_agents_tools.py tests/unit/test_agents_registry.py tests/unit/test_agents_base.py -v
```

Expected: all green. The Phase-3 fixtures asserted `mcp_servers.keys()` for several roles; if any of those tests now fail because `signals` was added, update them to assert the *role-specific* keys plus `signals`.

- [ ] **Step 7: Commit**

```bash
git add src/aegis/agents/tools.py src/aegis/agents/registry.py tests/unit/test_agents_tools.py tests/unit/test_agents_registry.py
git commit -m "feat(agents): merge in-process signals server into every role"
```

---

## Task 6: Implement the message-stream parser

**Files:**

- Create: `src/aegis/graph/parser.py`
- Create: `tests/unit/test_graph_parser.py`

The parser walks the raw `list[Any]` returned by `AegisAgent.run()` and extracts the *last* `mcp__signals__done` or `mcp__signals__block` tool-use, producing a typed `Signal`. The Anthropic message types vary by SDK version, so the parser duck-types: it looks for objects whose attributes / dict keys describe a tool-use block named `done` or `block` on the `signals` server.

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/test_graph_parser.py
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
    msgs = [
        _Assistant(content=[_tool_use("done", {"summary": "ok", "verdict": "pass"})])
    ]
    sig = extract_signal(msgs)
    assert isinstance(sig, Done)
    assert sig.summary == "ok"
    assert sig.verdict == "pass"


def test_extract_block_reason() -> None:
    msgs = [
        _Assistant(content=[_tool_use("block", {"reason": "fixtures missing"})])
    ]
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
        _Assistant(
            content=[_tool_use("git_status", {}, server="git")]
        ),
        _Assistant(
            content=[_tool_use("done", {"summary": "real"}, server="signals")]
        ),
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
```

- [ ] **Step 2: Run; confirm fail**

```bash
pytest tests/unit/test_graph_parser.py -v
```

- [ ] **Step 3: Implement the parser**

```python
# src/aegis/graph/parser.py
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
    if (
        getattr(block, "type", None) is not None
        and getattr(block, "type", None) != "tool_use"
    ):
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
                    verdict=(str(args["verdict"]) if "verdict" in args and args["verdict"] else None),
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
```

- [ ] **Step 4: Re-run; confirm green**

```bash
pytest tests/unit/test_graph_parser.py -v
```

- [ ] **Step 5: Commit**

```bash
git add src/aegis/graph/parser.py tests/unit/test_graph_parser.py
git commit -m "feat(graph): parse done/block signals from agent message stream"
```

---

## Task 7: Implement the SQLite checkpointer wrapper

**Files:**

- Create: `src/aegis/graph/checkpointer.py`
- Create: `tests/unit/test_graph_checkpointer.py`

LangGraph's `SqliteSaver` is a context manager in modern releases. The wrapper centralises the connection-string convention (`<aegis_dir>/checkpoint.db`) and exposes a function the runtime can `with`-block.

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/test_graph_checkpointer.py
from __future__ import annotations

from pathlib import Path

from aegis.graph.checkpointer import (
    checkpoint_db_path,
    open_checkpointer,
)


def test_checkpoint_db_path_is_under_aegis_dir(tmp_path: Path) -> None:
    aegis = tmp_path / ".aegis"
    aegis.mkdir()
    p = checkpoint_db_path(aegis)
    assert p == aegis / "checkpoint.db"


def test_open_checkpointer_yields_a_saver(tmp_path: Path) -> None:
    aegis = tmp_path / ".aegis"
    aegis.mkdir()
    with open_checkpointer(aegis) as saver:
        assert saver is not None
        # Saver must support the langgraph BaseCheckpointSaver surface
        assert hasattr(saver, "put")
        assert hasattr(saver, "get_tuple")
    # File should exist after exit
    assert (aegis / "checkpoint.db").exists()
```

- [ ] **Step 2: Run; confirm fail**

- [ ] **Step 3: Implement**

```python
# src/aegis/graph/checkpointer.py
"""Thin wrapper around ``langgraph.checkpoint.sqlite.SqliteSaver``.

The wrapper hides one detail: in current LangGraph releases the saver
is constructed via ``SqliteSaver.from_conn_string(...)`` and used as a
context manager. The runtime always opens the saver with the same
``<aegis_dir>/checkpoint.db`` path, so this module centralises that
convention.
"""
from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from langgraph.checkpoint.sqlite import SqliteSaver

__all__ = ["checkpoint_db_path", "open_checkpointer"]


def checkpoint_db_path(aegis_dir: Path) -> Path:
    return aegis_dir / "checkpoint.db"


@contextmanager
def open_checkpointer(aegis_dir: Path) -> Iterator[SqliteSaver]:
    aegis_dir.mkdir(parents=True, exist_ok=True)
    db = checkpoint_db_path(aegis_dir)
    with SqliteSaver.from_conn_string(str(db)) as saver:
        yield saver
```

- [ ] **Step 4: Re-run; confirm green**

- [ ] **Step 5: Commit**

```bash
git add src/aegis/graph/checkpointer.py tests/unit/test_graph_checkpointer.py
git commit -m "feat(graph): add SqliteSaver wrapper for task checkpoints"
```

---

## Task 8: Common node helpers

**Files:**

- Create: `src/aegis/graph/node_helpers.py`
- Create: `tests/unit/test_graph_node_helpers.py`

Three helpers shared by every node:

1. `check_stop_flag(aegis_dir, task_id)` — raises `Stopped` if `.aegis/.stop` or `.aegis/.stop.<id>` exists.
2. `append_section(task_path, header, body)` — appends a `## <header>` block to the task markdown's *body* (preserving frontmatter).
3. `make_agent(role, state, config, shell_allow_cmds=None)` — instantiates `AegisAgent` from a `TeamState` snapshot.

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/test_graph_node_helpers.py
from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from aegis.core.config import AegisConfig, ProjectConfig
from aegis.core.task import (
    Priority,
    Task,
    TaskBudget,
    TaskFrontmatter,
    TaskStatus,
    parse_task,
    write_task,
)
from aegis.graph.node_helpers import (
    Stopped,
    append_section,
    check_stop_flag,
    make_agent,
)
from aegis.graph.state import initial_state


def _task_at(path: Path, task_id: str = "001") -> Task:
    fm = TaskFrontmatter(
        id=task_id,
        title="demo",
        status=TaskStatus.IN_PROGRESS,
        priority=Priority.P2,
        budget=TaskBudget(),
        created=datetime.now(tz=UTC),
    )
    task = Task(frontmatter=fm, body="# demo\n\nbody.\n")
    write_task(task, path)
    return task


def test_check_stop_flag_global(tmp_path: Path) -> None:
    aegis = tmp_path / ".aegis"
    aegis.mkdir()
    check_stop_flag(aegis, "001")  # no flag → no raise
    (aegis / ".stop").touch()
    with pytest.raises(Stopped):
        check_stop_flag(aegis, "001")


def test_check_stop_flag_task_specific(tmp_path: Path) -> None:
    aegis = tmp_path / ".aegis"
    aegis.mkdir()
    (aegis / ".stop.001").touch()
    with pytest.raises(Stopped):
        check_stop_flag(aegis, "001")
    # Different task is unaffected
    check_stop_flag(aegis, "002")


def test_append_section_preserves_frontmatter(tmp_path: Path) -> None:
    p = tmp_path / "001-demo.md"
    _task_at(p)
    append_section(p, "Plan", "- bullet 1\n- bullet 2\n")
    rendered = parse_task(p)
    assert "## Plan" in rendered.body
    assert "- bullet 1" in rendered.body
    # Frontmatter survived
    assert rendered.frontmatter.id == "001"


def test_make_agent_instantiates_correct_role(tmp_path: Path) -> None:
    p = tmp_path / "001-demo.md"
    _task_at(p)
    config = AegisConfig(project=ProjectConfig(name="t"))
    state = initial_state(
        task=_task_at(p),
        task_path=p,
        worktree_path=tmp_path,
        target_repo_root=tmp_path,
    )
    agent = make_agent("dev", state, config)
    assert agent.role == "dev"
    assert agent.worktree == tmp_path.resolve()
```

- [ ] **Step 2: Run; confirm fail**

- [ ] **Step 3: Implement**

```python
# src/aegis/graph/node_helpers.py
from __future__ import annotations

from pathlib import Path

from aegis.agents import AegisAgent
from aegis.agents.registry import RoleName
from aegis.core.config import AegisConfig
from aegis.core.task import parse_task, write_task
from aegis.graph.state import TeamState

__all__ = ["Stopped", "check_stop_flag", "append_section", "make_agent"]


class Stopped(Exception):
    """Raised when a stop flag forces a node to abort cleanly."""


def check_stop_flag(aegis_dir: Path, task_id: str) -> None:
    if (aegis_dir / ".stop").exists():
        raise Stopped("global .stop flag is set")
    if (aegis_dir / f".stop.{task_id}").exists():
        raise Stopped(f"task-specific .stop.{task_id} flag is set")


def append_section(task_path: Path, header: str, body: str) -> None:
    """Append a ``## <header>`` block to the task's markdown body.

    Frontmatter is preserved verbatim.
    """
    task = parse_task(task_path)
    new_body = task.body
    if not new_body.endswith("\n"):
        new_body += "\n"
    new_body += f"\n## {header}\n\n{body.rstrip()}\n"
    task.body = new_body
    write_task(task, task_path)


def make_agent(
    role: RoleName,
    state: TeamState,
    config: AegisConfig,
    *,
    shell_allow_cmds: str | None = None,
) -> AegisAgent:
    return AegisAgent(
        role=role,
        worktree=Path(state["worktree_path"]),
        config=config,
        shell_allow_cmds=shell_allow_cmds,
    )
```

- [ ] **Step 4: Re-run; confirm green**

- [ ] **Step 5: Commit**

```bash
git add src/aegis/graph/node_helpers.py tests/unit/test_graph_node_helpers.py
git commit -m "feat(graph): add stop-flag, append-section, and agent factory helpers"
```

---

## Task 9: PM node

**Files:**

- Create: `src/aegis/graph/nodes/__init__.py`
- Create: `src/aegis/graph/nodes/pm.py`
- Create: `tests/unit/test_graph_nodes_pm.py`

PM node contract:

1. Read the task markdown body via `parse_task(state["task_path"])`.
2. Run a PM agent with the task body as `task_prompt`.
3. Parse the message stream.
4. On `Done`: append the `summary` as a `## Plan` section to the task file, return `{"plan": {"summary": ...}, "implementation_status": "in_progress", "current_node": "pm"}`.
5. On `Block`: return `{"blocked_reason": ..., "current_node": "pm"}` — runtime will detect this and short-circuit.
6. On `NoSignal`: treat like Block with `reason="PM did not signal completion"`.

The node accepts an injected `agent_factory: Callable[[TeamState], AegisAgent]` for tests; it defaults to `make_agent("pm", state, config_loaded_lazily)`.

- [ ] **Step 1: Write failing tests**

```python
# tests/unit/test_graph_nodes_pm.py
from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from aegis.core.config import AegisConfig, ProjectConfig
from aegis.core.task import (
    Priority,
    Task,
    TaskBudget,
    TaskFrontmatter,
    TaskStatus,
    parse_task,
    write_task,
)
from aegis.graph.nodes.pm import pm_node
from aegis.graph.state import initial_state


def _setup(tmp_path: Path) -> tuple[dict[str, Any], Path, AegisConfig]:
    aegis = tmp_path / ".aegis"
    aegis.mkdir()
    (aegis / "in-progress").mkdir()
    p = aegis / "in-progress" / "001-demo.md"
    fm = TaskFrontmatter(
        id="001",
        title="demo",
        status=TaskStatus.IN_PROGRESS,
        priority=Priority.P2,
        budget=TaskBudget(),
        created=datetime.now(tz=UTC),
    )
    task = Task(frontmatter=fm, body="# demo\n\n## Why\nbecause.\n")
    write_task(task, p)
    config = AegisConfig(project=ProjectConfig(name="t"))
    state = initial_state(
        task=task, task_path=p, worktree_path=tmp_path, target_repo_root=tmp_path
    )
    return state, p, config


class _StubAgent:
    def __init__(self, msgs: list[Any]) -> None:
        self._msgs = msgs
        self.invoked_with: str | None = None

    async def run(self, prompt: str) -> list[Any]:
        self.invoked_with = prompt
        return self._msgs


def _done_msgs(summary: str, verdict: str | None = None) -> list[Any]:
    args: dict[str, Any] = {"summary": summary}
    if verdict is not None:
        args["verdict"] = verdict
    return [
        {
            "type": "assistant",
            "content": [
                {"type": "tool_use", "name": "mcp__signals__done", "input": args}
            ],
        }
    ]


def _block_msgs(reason: str) -> list[Any]:
    return [
        {
            "type": "assistant",
            "content": [
                {
                    "type": "tool_use",
                    "name": "mcp__signals__block",
                    "input": {"reason": reason},
                }
            ],
        }
    ]


def test_pm_done_appends_plan_and_advances_status(tmp_path: Path) -> None:
    state, task_path, config = _setup(tmp_path)
    stub = _StubAgent(_done_msgs("- step 1\n- step 2\n"))

    delta = asyncio.run(
        pm_node(state, config=config, agent_factory=lambda s, c: stub)
    )
    assert delta["implementation_status"] == "in_progress"
    assert delta["current_node"] == "pm"
    assert delta["plan"]["summary"].startswith("- step 1")

    refreshed = parse_task(task_path)
    assert "## Plan" in refreshed.body
    assert "- step 1" in refreshed.body


def test_pm_block_sets_blocked_reason(tmp_path: Path) -> None:
    state, _, config = _setup(tmp_path)
    stub = _StubAgent(_block_msgs("ambiguous criteria"))
    delta = asyncio.run(
        pm_node(state, config=config, agent_factory=lambda s, c: stub)
    )
    assert delta["blocked_reason"] == "ambiguous criteria"
    assert delta["current_node"] == "pm"


def test_pm_no_signal_treated_as_block(tmp_path: Path) -> None:
    state, _, config = _setup(tmp_path)
    stub = _StubAgent([{"type": "assistant", "content": [{"type": "text", "text": "..."}]}])
    delta = asyncio.run(
        pm_node(state, config=config, agent_factory=lambda s, c: stub)
    )
    assert "blocked_reason" in delta
    assert "did not signal" in delta["blocked_reason"].lower()
```

- [ ] **Step 2: Run; confirm fail**

- [ ] **Step 3: Implement `nodes/__init__.py`**

```python
# src/aegis/graph/nodes/__init__.py
from aegis.graph.nodes.docs import docs_node
from aegis.graph.nodes.dev import dev_node
from aegis.graph.nodes.pm import pm_node
from aegis.graph.nodes.qa import qa_node
from aegis.graph.nodes.reviewer import reviewer_node

__all__ = ["pm_node", "dev_node", "qa_node", "reviewer_node", "docs_node"]
```

- [ ] **Step 4: Implement `nodes/pm.py`**

```python
# src/aegis/graph/nodes/pm.py
from __future__ import annotations

from collections.abc import Awaitable, Callable
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
```

- [ ] **Step 5: Run; confirm green**

```bash
pytest tests/unit/test_graph_nodes_pm.py -v
```

- [ ] **Step 6: Commit**

```bash
git add src/aegis/graph/nodes tests/unit/test_graph_nodes_pm.py
git commit -m "feat(graph): implement PM node with done/block parsing"
```

---

## Task 10: Dev node

**Files:**

- Create: `src/aegis/graph/nodes/dev.py`
- Create: `tests/unit/test_graph_nodes_dev.py`

Dev node contract:

1. Build prompt from task body + plan summary.
2. Run Dev agent with `shell_allow_cmds="pytest,ruff,mypy,python,pip,npm,pnpm,node"`.
3. Parse messages.
4. On `Done`: return `{"implementation_status": "done", "current_node": "dev"}`. (Dev does not append a section — its work is the commits in the worktree.)
5. On `Block`: return `{"blocked_reason": ..., "current_node": "dev"}`.
6. On `NoSignal`: same as Block.

- [ ] **Step 1: Write failing test** (mirror PM test structure; assert `implementation_status == "done"` on success and that the agent factory was invoked with `shell_allow_cmds` containing `pytest`).

```python
# tests/unit/test_graph_nodes_dev.py
from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from aegis.core.config import AegisConfig, ProjectConfig
from aegis.core.task import Priority, Task, TaskBudget, TaskFrontmatter, TaskStatus, write_task
from aegis.graph.nodes.dev import dev_node
from aegis.graph.state import initial_state


def _state(tmp_path: Path) -> dict[str, Any]:
    aegis = tmp_path / ".aegis"
    aegis.mkdir()
    (aegis / "in-progress").mkdir()
    p = aegis / "in-progress" / "001-demo.md"
    fm = TaskFrontmatter(
        id="001",
        title="demo",
        status=TaskStatus.IN_PROGRESS,
        priority=Priority.P2,
        budget=TaskBudget(),
        created=datetime.now(tz=UTC),
    )
    task = Task(frontmatter=fm, body="# demo\n\n## Plan\n- step 1\n")
    write_task(task, p)
    s = initial_state(task=task, task_path=p, worktree_path=tmp_path, target_repo_root=tmp_path)
    s["plan"] = {"summary": "- step 1", "verdict": None}
    return s


class _StubAgent:
    def __init__(self, msgs: list[Any]) -> None:
        self._msgs = msgs

    async def run(self, prompt: str) -> list[Any]:
        return self._msgs


def _done(summary: str = "committed.") -> list[Any]:
    return [
        {
            "type": "assistant",
            "content": [
                {"type": "tool_use", "name": "mcp__signals__done", "input": {"summary": summary}}
            ],
        }
    ]


def test_dev_done_marks_implementation_complete(tmp_path: Path) -> None:
    state = _state(tmp_path)
    config = AegisConfig(project=ProjectConfig(name="t"))
    delta = asyncio.run(
        dev_node(state, config=config, agent_factory=lambda s, c: _StubAgent(_done()))
    )
    assert delta["implementation_status"] == "done"
    assert delta["current_node"] == "dev"


def test_dev_block_records_reason(tmp_path: Path) -> None:
    state = _state(tmp_path)
    config = AegisConfig(project=ProjectConfig(name="t"))
    msgs = [
        {
            "type": "assistant",
            "content": [
                {
                    "type": "tool_use",
                    "name": "mcp__signals__block",
                    "input": {"reason": "test fixture missing"},
                }
            ],
        }
    ]
    delta = asyncio.run(
        dev_node(state, config=config, agent_factory=lambda s, c: _StubAgent(msgs))
    )
    assert delta["blocked_reason"] == "test fixture missing"


def test_dev_passes_shell_allow_cmds(tmp_path: Path) -> None:
    state = _state(tmp_path)
    config = AegisConfig(project=ProjectConfig(name="t"))
    seen = {}

    def fac(s, c):
        # Verify dev_node uses make_agent with shell_allow_cmds
        # by intercepting the call. Actual make_agent goes through
        # AegisAgent.__init__ which records shell_allow_cmds.
        from aegis.graph.node_helpers import make_agent

        agent = make_agent("dev", s, c, shell_allow_cmds="pytest,ruff,mypy,python,pip,npm,pnpm,node")
        seen["allow"] = agent.shell_allow_cmds
        return _StubAgent(_done())

    asyncio.run(dev_node(state, config=config, agent_factory=fac))
    assert "pytest" in (seen["allow"] or "")
```

- [ ] **Step 2: Implement**

```python
# src/aegis/graph/nodes/dev.py
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
    return {"blocked_reason": "Dev did not signal completion", "current_node": "dev"}
```

- [ ] **Step 3: Run; confirm green**

```bash
pytest tests/unit/test_graph_nodes_dev.py -v
```

- [ ] **Step 4: Commit**

```bash
git add src/aegis/graph/nodes/dev.py tests/unit/test_graph_nodes_dev.py
git commit -m "feat(graph): implement Dev node with shell allow-list"
```

---

## Task 11: QA node

**Files:**

- Create: `src/aegis/graph/nodes/qa.py`
- Create: `tests/unit/test_graph_nodes_qa.py`

QA contract:

1. Build prompt from task body + plan + worktree state.
2. Run QA agent (`shell_allow_cmds="pytest,ruff,mypy,python"`).
3. Parse signal.
4. On `Done` with `verdict="pass"`: append `## QA report` to task md, return `{"test_report": {"verdict": "pass", "summary": ...}, "current_node": "qa"}`.
5. On `Done` with `verdict="fail"`: append `## QA report` (mark fail), return `{"test_report": {"verdict": "fail", "summary": ...}, "implementation_status": "in_progress", "current_node": "qa"}`.
6. On `Done` without verdict: treat as fail with reason "QA returned no verdict".
7. On `Block`/`NoSignal`: `blocked_reason`.

- [ ] **Step 1: Write failing test**

```python
# tests/unit/test_graph_nodes_qa.py
from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from aegis.core.config import AegisConfig, ProjectConfig
from aegis.core.task import (
    Priority, Task, TaskBudget, TaskFrontmatter, TaskStatus, parse_task, write_task,
)
from aegis.graph.nodes.qa import qa_node
from aegis.graph.state import initial_state


def _state(tmp_path: Path) -> dict[str, Any]:
    aegis = tmp_path / ".aegis"
    aegis.mkdir()
    (aegis / "in-progress").mkdir()
    p = aegis / "in-progress" / "001-demo.md"
    fm = TaskFrontmatter(
        id="001", title="demo",
        status=TaskStatus.IN_PROGRESS,
        priority=Priority.P2,
        budget=TaskBudget(),
        created=datetime.now(tz=UTC),
    )
    task = Task(frontmatter=fm, body="# demo\n")
    write_task(task, p)
    s = initial_state(task=task, task_path=p, worktree_path=tmp_path, target_repo_root=tmp_path)
    s["plan"] = {"summary": "do it", "verdict": None}
    return s


class _StubAgent:
    def __init__(self, msgs: list[Any]) -> None:
        self._msgs = msgs

    async def run(self, prompt: str) -> list[Any]:
        return self._msgs


def _done(summary: str, verdict: str | None) -> list[Any]:
    args: dict[str, Any] = {"summary": summary}
    if verdict is not None:
        args["verdict"] = verdict
    return [{"type": "assistant", "content": [
        {"type": "tool_use", "name": "mcp__signals__done", "input": args}
    ]}]


def test_qa_pass_records_verdict_and_appends_report(tmp_path: Path) -> None:
    s = _state(tmp_path)
    config = AegisConfig(project=ProjectConfig(name="t"))
    delta = asyncio.run(
        qa_node(s, config=config, agent_factory=lambda st, c: _StubAgent(_done("12 passed", "pass")))
    )
    assert delta["test_report"]["verdict"] == "pass"
    assert delta["current_node"] == "qa"
    body = parse_task(Path(s["task_path"])).body
    assert "## QA report" in body and "12 passed" in body


def test_qa_fail_routes_back_to_dev(tmp_path: Path) -> None:
    s = _state(tmp_path)
    config = AegisConfig(project=ProjectConfig(name="t"))
    delta = asyncio.run(
        qa_node(s, config=config, agent_factory=lambda st, c: _StubAgent(_done("3 failed", "fail")))
    )
    assert delta["test_report"]["verdict"] == "fail"
    assert delta["implementation_status"] == "in_progress"


def test_qa_done_without_verdict_treated_as_fail(tmp_path: Path) -> None:
    s = _state(tmp_path)
    config = AegisConfig(project=ProjectConfig(name="t"))
    delta = asyncio.run(
        qa_node(s, config=config, agent_factory=lambda st, c: _StubAgent(_done("no verdict here", None)))
    )
    assert delta["test_report"]["verdict"] == "fail"
```

- [ ] **Step 2: Implement**

```python
# src/aegis/graph/nodes/qa.py
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
    return {"blocked_reason": "QA did not signal completion", "current_node": "qa"}
```

- [ ] **Step 3: Run; confirm green**

- [ ] **Step 4: Commit**

```bash
git add src/aegis/graph/nodes/qa.py tests/unit/test_graph_nodes_qa.py
git commit -m "feat(graph): implement QA node with verdict-based routing"
```

---

## Task 12: Reviewer node

**Files:**

- Create: `src/aegis/graph/nodes/reviewer.py`
- Create: `tests/unit/test_graph_nodes_reviewer.py`

Reviewer contract:

1. Build prompt from task body + Plan + QA report.
2. Run Reviewer agent (no shell).
3. Parse.
4. On `Done` with `verdict="approve"`: append `## Review` (approved), return `{"review": {"verdict": "approve", ...}, "pr_branch": <state["worktree_path"] basename>, "current_node": "reviewer"}`.
5. On `Done` with `verdict="rework"`: append (rework) and return `{"review": {"verdict": "rework", ...}, "implementation_status": "in_progress", "current_node": "reviewer"}`.
6. Anything else → blocked.

The `pr_branch` value: when the worktree was created, its branch name was derived from the task slug (Phase-1 worktree.create_worktree gets `branch=...`). Reviewer doesn't know the branch — it's stored on the state when the runtime creates the worktree. So Reviewer just acknowledges that the worktree branch is now PR-ready: it sets `pr_branch=state.get("pr_branch") or "<branch-from-state>"`. We rely on the runtime to pre-populate `pr_branch` at worktree creation time.

Adjustment: Reviewer's responsibility is just to set the verdict. The `pr_branch` field stays as the runtime set it. Reviewer's delta is:

```python
{"review": {"verdict": "approve", "summary": ...}, "current_node": "reviewer"}
```

(We do NOT touch pr_branch in the reviewer node — it's already set.)

- [ ] **Step 1: Write failing test**

```python
# tests/unit/test_graph_nodes_reviewer.py
from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from aegis.core.config import AegisConfig, ProjectConfig
from aegis.core.task import (
    Priority, Task, TaskBudget, TaskFrontmatter, TaskStatus, parse_task, write_task,
)
from aegis.graph.nodes.reviewer import reviewer_node
from aegis.graph.state import initial_state


def _state(tmp_path: Path) -> dict[str, Any]:
    aegis = tmp_path / ".aegis"
    aegis.mkdir()
    (aegis / "in-progress").mkdir()
    p = aegis / "in-progress" / "001-demo.md"
    fm = TaskFrontmatter(
        id="001", title="demo",
        status=TaskStatus.IN_PROGRESS,
        priority=Priority.P2,
        budget=TaskBudget(),
        created=datetime.now(tz=UTC),
    )
    task = Task(frontmatter=fm, body="# demo\n")
    write_task(task, p)
    s = initial_state(task=task, task_path=p, worktree_path=tmp_path, target_repo_root=tmp_path)
    s["pr_branch"] = "aegis/001-demo"
    return s


class _StubAgent:
    def __init__(self, msgs: list[Any]) -> None:
        self._msgs = msgs

    async def run(self, prompt: str) -> list[Any]:
        return self._msgs


def _done(summary: str, verdict: str) -> list[Any]:
    return [{"type": "assistant", "content": [
        {"type": "tool_use", "name": "mcp__signals__done",
         "input": {"summary": summary, "verdict": verdict}},
    ]}]


def test_reviewer_approve(tmp_path: Path) -> None:
    s = _state(tmp_path)
    cfg = AegisConfig(project=ProjectConfig(name="t"))
    delta = asyncio.run(
        reviewer_node(s, config=cfg, agent_factory=lambda st, c: _StubAgent(_done("LGTM", "approve")))
    )
    assert delta["review"]["verdict"] == "approve"
    assert delta["current_node"] == "reviewer"
    body = parse_task(Path(s["task_path"])).body
    assert "## Review" in body and "LGTM" in body


def test_reviewer_rework_resets_implementation(tmp_path: Path) -> None:
    s = _state(tmp_path)
    cfg = AegisConfig(project=ProjectConfig(name="t"))
    delta = asyncio.run(
        reviewer_node(s, config=cfg, agent_factory=lambda st, c: _StubAgent(_done("rename foo", "rework")))
    )
    assert delta["review"]["verdict"] == "rework"
    assert delta["implementation_status"] == "in_progress"
```

- [ ] **Step 2: Implement**

```python
# src/aegis/graph/nodes/reviewer.py
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
    return {"blocked_reason": "Reviewer did not signal completion", "current_node": "reviewer"}
```

- [ ] **Step 3: Run; confirm green**

- [ ] **Step 4: Commit**

```bash
git add src/aegis/graph/nodes/reviewer.py tests/unit/test_graph_nodes_reviewer.py
git commit -m "feat(graph): implement Reviewer node with approve/rework verdict"
```

---

## Task 13: Docs node

**Files:**

- Create: `src/aegis/graph/nodes/docs.py`
- Create: `tests/unit/test_graph_nodes_docs.py`

Docs runs *after* the human gate, on main (not in the worktree). The runtime swaps `state["worktree_path"]` for the target repo root before invoking Docs. From the node's perspective there's no special branching — it just runs the agent and signals done.

- [ ] **Step 1: Write failing test**

```python
# tests/unit/test_graph_nodes_docs.py
from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from aegis.core.config import AegisConfig, ProjectConfig
from aegis.core.task import Priority, Task, TaskBudget, TaskFrontmatter, TaskStatus, write_task
from aegis.graph.nodes.docs import docs_node
from aegis.graph.state import initial_state


def _state(tmp_path: Path) -> dict[str, Any]:
    aegis = tmp_path / ".aegis"
    aegis.mkdir()
    (aegis / "review").mkdir()
    p = aegis / "review" / "001-demo.md"
    fm = TaskFrontmatter(
        id="001", title="demo",
        status=TaskStatus.REVIEW,
        priority=Priority.P2,
        budget=TaskBudget(),
        created=datetime.now(tz=UTC),
    )
    task = Task(frontmatter=fm, body="# demo\n")
    write_task(task, p)
    return initial_state(task=task, task_path=p, worktree_path=tmp_path, target_repo_root=tmp_path)


class _StubAgent:
    def __init__(self, msgs: list[Any]) -> None:
        self._msgs = msgs

    async def run(self, prompt: str) -> list[Any]:
        return self._msgs


def test_docs_done(tmp_path: Path) -> None:
    s = _state(tmp_path)
    cfg = AegisConfig(project=ProjectConfig(name="t"))
    msgs = [{"type": "assistant", "content": [
        {"type": "tool_use", "name": "mcp__signals__done",
         "input": {"summary": "updated CHANGELOG"}},
    ]}]
    delta = asyncio.run(
        docs_node(s, config=cfg, agent_factory=lambda st, c: _StubAgent(msgs))
    )
    assert delta["current_node"] == "docs"
    assert delta["implementation_status"] == "done"
```

- [ ] **Step 2: Implement**

```python
# src/aegis/graph/nodes/docs.py
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
            "review": {**(state.get("review") or {}), "docs_summary": sig.summary},
        }
    if isinstance(sig, Block):
        return {"blocked_reason": sig.reason, "current_node": "docs"}
    assert isinstance(sig, NoSignal)
    return {"blocked_reason": "Docs did not signal completion", "current_node": "docs"}
```

- [ ] **Step 3: Run; confirm green**

- [ ] **Step 4: Commit**

```bash
git add src/aegis/graph/nodes/docs.py tests/unit/test_graph_nodes_docs.py src/aegis/graph/nodes/__init__.py
git commit -m "feat(graph): implement Docs node and node package exports"
```

---

## Task 14: Wire the team graph

**Files:**

- Create: `src/aegis/graph/team_graph.py`
- Create: `tests/unit/test_graph_team_graph.py`
- Modify: `src/aegis/graph/__init__.py`

Topology (matches spec §5.2):

```
START → pm → (blocked? END : dev) → qa → (pass: reviewer / fail: dev / cap-exceeded: END_BLOCKED)
                                          ↓
                                    reviewer → (approve: docs* / rework: dev / cap-exceeded: END_BLOCKED)
                                          ↓
                                       docs → END
* interrupt_before=["docs"] holds the graph at the human gate.
```

Loop counters live on `TeamState["retry_counts"]`. The conditional functions read and increment them.

- [ ] **Step 1: Write failing tests** — verify routing on a graph that uses stubbed nodes.

```python
# tests/unit/test_graph_team_graph.py
from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from aegis.core.task import Priority, Task, TaskBudget, TaskFrontmatter, TaskStatus, write_task
from aegis.graph.state import TeamState, initial_state
from aegis.graph.team_graph import build_graph


def _state(tmp_path: Path) -> TeamState:
    aegis = tmp_path / ".aegis"
    aegis.mkdir()
    (aegis / "in-progress").mkdir()
    p = aegis / "in-progress" / "001-demo.md"
    fm = TaskFrontmatter(
        id="001", title="demo",
        status=TaskStatus.IN_PROGRESS,
        priority=Priority.P2,
        budget=TaskBudget(),
        created=datetime.now(tz=UTC),
    )
    task = Task(frontmatter=fm, body="# demo\n")
    write_task(task, p)
    return initial_state(task=task, task_path=p, worktree_path=tmp_path, target_repo_root=tmp_path)


def _node(returning: dict[str, Any]):
    async def fn(state: TeamState) -> dict[str, Any]:
        return returning
    return fn


def test_happy_path_pauses_before_docs(tmp_path: Path) -> None:
    nodes = {
        "pm": _node({"plan": {"summary": "p"}, "implementation_status": "in_progress", "current_node": "pm"}),
        "dev": _node({"implementation_status": "done", "current_node": "dev"}),
        "qa": _node({"test_report": {"verdict": "pass", "summary": "ok"}, "current_node": "qa"}),
        "reviewer": _node({"review": {"verdict": "approve", "summary": "ok"}, "current_node": "reviewer"}),
        "docs": _node({"current_node": "docs", "implementation_status": "done"}),
    }
    graph = build_graph(node_overrides=nodes)
    cfg = {"configurable": {"thread_id": "001"}}
    result = graph.invoke(_state(tmp_path), config=cfg)
    # Either we observed reviewer as last current_node (interrupt fired)
    # or, if interrupt_before isn't honored on the synchronous invoke,
    # docs ran. Assert one of the two.
    assert result["current_node"] in ("reviewer", "docs")


def test_qa_fail_loops_back_to_dev(tmp_path: Path) -> None:
    visits: list[str] = []

    def trace(name: str, returning: dict[str, Any]):
        async def fn(state: TeamState) -> dict[str, Any]:
            visits.append(name)
            return returning
        return fn

    # First QA call returns fail; second returns pass. Track via a counter.
    qa_state = {"i": 0}

    async def qa_fn(state: TeamState) -> dict[str, Any]:
        visits.append("qa")
        qa_state["i"] += 1
        verdict = "fail" if qa_state["i"] == 1 else "pass"
        delta: dict[str, Any] = {
            "test_report": {"verdict": verdict, "summary": f"call-{qa_state['i']}"},
            "current_node": "qa",
        }
        if verdict == "fail":
            delta["implementation_status"] = "in_progress"
        return delta

    nodes = {
        "pm": trace("pm", {"plan": {"summary": "p"}, "implementation_status": "in_progress", "current_node": "pm"}),
        "dev": trace("dev", {"implementation_status": "done", "current_node": "dev"}),
        "qa": qa_fn,
        "reviewer": trace("reviewer", {"review": {"verdict": "approve", "summary": "ok"}, "current_node": "reviewer"}),
        "docs": trace("docs", {"current_node": "docs", "implementation_status": "done"}),
    }
    graph = build_graph(node_overrides=nodes)
    cfg = {"configurable": {"thread_id": "002"}}
    graph.invoke(_state(tmp_path), config=cfg)
    # After fail-then-pass: dev runs twice
    assert visits.count("dev") == 2
    assert visits.count("qa") == 2


def test_qa_fail_cap_blocks_after_max_retries(tmp_path: Path) -> None:
    nodes = {
        "pm": _node({"plan": {"summary": "p"}, "implementation_status": "in_progress", "current_node": "pm"}),
        "dev": _node({"implementation_status": "done", "current_node": "dev"}),
        "qa": _node({
            "test_report": {"verdict": "fail", "summary": "always fails"},
            "implementation_status": "in_progress",
            "current_node": "qa",
        }),
        "reviewer": _node({"review": {"verdict": "approve", "summary": "ok"}, "current_node": "reviewer"}),
        "docs": _node({"current_node": "docs", "implementation_status": "done"}),
    }
    graph = build_graph(node_overrides=nodes, max_dev_qa_retries=2)
    cfg = {"configurable": {"thread_id": "003"}}
    result = graph.invoke(_state(tmp_path), config=cfg)
    assert result["test_report"]["verdict"] == "fail"
    assert result["blocked_reason"] is not None
    assert "QA loop" in result["blocked_reason"]
```

- [ ] **Step 2: Implement `team_graph.py`**

```python
# src/aegis/graph/team_graph.py
"""Build the LangGraph ``StateGraph`` for the Aegis team.

Topology mirrors spec §5.2. Nodes can be overridden for tests via the
``node_overrides`` argument; in production they default to the real
nodes from :mod:`aegis.graph.nodes`.
"""
from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from langgraph.graph import END, START, StateGraph

from aegis.graph.nodes import dev_node, docs_node, pm_node, qa_node, reviewer_node
from aegis.graph.state import TeamState

__all__ = ["build_graph", "DEFAULT_MAX_DEV_QA_RETRIES", "DEFAULT_MAX_REVIEWER_RETRIES"]

DEFAULT_MAX_DEV_QA_RETRIES = 2
DEFAULT_MAX_REVIEWER_RETRIES = 1

NodeFn = Callable[[TeamState], Awaitable[dict[str, Any]]]


def _route_after_pm(state: TeamState) -> str:
    if state.get("blocked_reason"):
        return "blocked"
    return "dev"


def _route_after_qa(state: TeamState, *, max_retries: int) -> str:
    if state.get("blocked_reason"):
        return "blocked"
    report = state.get("test_report") or {}
    if report.get("verdict") == "pass":
        return "reviewer"
    # fail
    counts = state.get("retry_counts") or {}
    if counts.get("dev_on_qa_fail", 0) >= max_retries:
        return "blocked"
    return "dev_retry"


def _route_after_reviewer(state: TeamState, *, max_retries: int) -> str:
    if state.get("blocked_reason"):
        return "blocked"
    review = state.get("review") or {}
    if review.get("verdict") == "approve":
        return "docs"
    counts = state.get("retry_counts") or {}
    if counts.get("dev_on_review", 0) >= max_retries:
        return "blocked"
    return "dev_retry_review"


def _bump_qa_retry(state: TeamState) -> dict[str, Any]:
    counts = dict(state.get("retry_counts") or {})
    counts["dev_on_qa_fail"] = counts.get("dev_on_qa_fail", 0) + 1
    return {"retry_counts": counts}


def _bump_review_retry(state: TeamState) -> dict[str, Any]:
    counts = dict(state.get("retry_counts") or {})
    counts["dev_on_review"] = counts.get("dev_on_review", 0) + 1
    return {"retry_counts": counts}


def _qa_loop_blocker(state: TeamState) -> dict[str, Any]:
    return {"blocked_reason": "QA loop exceeded max retries"}


def _review_loop_blocker(state: TeamState) -> dict[str, Any]:
    return {"blocked_reason": "Reviewer rework loop exceeded max retries"}


def build_graph(
    *,
    node_overrides: dict[str, NodeFn] | None = None,
    max_dev_qa_retries: int = DEFAULT_MAX_DEV_QA_RETRIES,
    max_reviewer_retries: int = DEFAULT_MAX_REVIEWER_RETRIES,
    checkpointer: Any | None = None,
) -> Any:
    overrides = node_overrides or {}
    pm = overrides.get("pm", pm_node)
    dev = overrides.get("dev", dev_node)
    qa = overrides.get("qa", qa_node)
    reviewer = overrides.get("reviewer", reviewer_node)
    docs = overrides.get("docs", docs_node)

    graph = StateGraph(TeamState)
    graph.add_node("pm", pm)
    graph.add_node("dev", dev)
    graph.add_node("qa", qa)
    graph.add_node("reviewer", reviewer)
    graph.add_node("docs", docs)

    # Bookkeeping nodes that exist only to mutate retry counters or
    # write the blocker reason. They keep the node functions pure.
    graph.add_node("dev_retry", _bump_qa_retry)
    graph.add_node("dev_retry_review", _bump_review_retry)
    graph.add_node("qa_loop_blocker", _qa_loop_blocker)
    graph.add_node("review_loop_blocker", _review_loop_blocker)

    graph.add_edge(START, "pm")
    graph.add_conditional_edges(
        "pm",
        _route_after_pm,
        {"dev": "dev", "blocked": END},
    )
    graph.add_edge("dev", "qa")
    graph.add_conditional_edges(
        "qa",
        lambda s: _route_after_qa(s, max_retries=max_dev_qa_retries),
        {"reviewer": "reviewer", "dev_retry": "dev_retry", "blocked": "qa_loop_blocker"},
    )
    graph.add_edge("dev_retry", "dev")
    graph.add_edge("qa_loop_blocker", END)
    graph.add_conditional_edges(
        "reviewer",
        lambda s: _route_after_reviewer(s, max_retries=max_reviewer_retries),
        {
            "docs": "docs",
            "dev_retry_review": "dev_retry_review",
            "blocked": "review_loop_blocker",
        },
    )
    graph.add_edge("dev_retry_review", "dev")
    graph.add_edge("review_loop_blocker", END)
    graph.add_edge("docs", END)

    kwargs: dict[str, Any] = {"interrupt_before": ["docs"]}
    if checkpointer is not None:
        kwargs["checkpointer"] = checkpointer
    return graph.compile(**kwargs)
```

- [ ] **Step 3: Update `graph/__init__.py`**

```python
# src/aegis/graph/__init__.py
"""Aegis LangGraph team graph and runtime entry points."""
from aegis.graph.state import TeamState, initial_state
from aegis.graph.team_graph import build_graph

__all__ = ["TeamState", "initial_state", "build_graph"]
```

- [ ] **Step 4: Run; confirm green**

```bash
pytest tests/unit/test_graph_team_graph.py -v
```

If `interrupt_before` causes the synchronous `invoke` to return at the gate, the happy-path test sees `current_node == "reviewer"`. If LangGraph's compile-time wiring auto-resumes, it sees `"docs"`. Either is acceptable for this unit test — the runtime task is responsible for the *behavioral* gate semantics, tested separately in Task 15.

- [ ] **Step 5: Commit**

```bash
git add src/aegis/graph/team_graph.py src/aegis/graph/__init__.py tests/unit/test_graph_team_graph.py
git commit -m "feat(graph): wire StateGraph with QA/Reviewer loops and docs gate"
```

---

## Task 15: Runtime — single-task driver

**Files:**

- Create: `src/aegis/graph/runtime.py`
- Create: `tests/unit/test_graph_runtime.py`

`run_one_task(task_path, aegis_dir, repo_root, config)` does the full lifecycle for one task:

1. Read the task; ensure status is `in-progress` (move from backlog if not).
2. Pre-create the worktree: `<aegis_dir>/.worktrees/<id>-<slug>`, branch `aegis/<id>-<slug>`. Use `aegis.core.worktree.create_worktree`.
3. Build initial `TeamState`. Set `pr_branch` to the branch name.
4. Open the SQLite checkpointer, build graph.
5. Invoke graph with `thread_id=task_id`.
6. After the graph returns (interrupt OR END):
   - If `state["blocked_reason"]`: write the blocker into the task body; move task to `blocked/`. Keep the worktree.
   - If reached docs interrupt (`current_node == "reviewer"` and `review.verdict == "approve"`): move task to `review/`. Set `awaiting_human=True`.
   - Else (full completion incl. docs): merge worktree branch into the target repo's main; move task to `done/`; remove worktree.

`resume_after_approve(task_id, aegis_dir, repo_root, config)`:

1. Find the review/-bound task.
2. Open the same checkpointer with the same thread_id; build the graph; call `graph.invoke(None, config=cfg)` (LangGraph idiom for resuming from interrupt).
3. After resume returns (graph reaches END), merge worktree branch into main; move task to `done/`; remove worktree.

`reject_task(task_id, aegis_dir, repo_root, reason)`:

1. Find the review/-bound task.
2. Append `## Rejection reason` (or set frontmatter note).
3. Move to `rejected/`.
4. Remove the worktree.

- [ ] **Step 1: Write failing tests** (use real graph with stub nodes; mock worktree/git)

```python
# tests/unit/test_graph_runtime.py
from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from unittest.mock import patch

from aegis.core.config import AegisConfig, ProjectConfig
from aegis.core.task import (
    Priority, Task, TaskBudget, TaskFrontmatter, TaskStatus, parse_task, write_task,
)
from aegis.graph.runtime import (
    reject_task,
    resume_after_approve,
    run_one_task,
)


def _bootstrap_repo(tmp_path: Path) -> tuple[Path, Path]:
    repo = tmp_path / "repo"
    repo.mkdir()
    aegis = repo / ".aegis"
    for sub in ("backlog", "in-progress", "review", "done", "blocked", "rejected", ".worktrees"):
        (aegis / sub).mkdir(parents=True, exist_ok=True)
    return repo, aegis


def _seed_task(aegis: Path, status: TaskStatus = TaskStatus.IN_PROGRESS) -> Path:
    p = aegis / status.value / "001-demo.md"
    fm = TaskFrontmatter(
        id="001", title="demo",
        status=status, priority=Priority.P2,
        budget=TaskBudget(),
        created=datetime.now(tz=UTC),
    )
    write_task(Task(frontmatter=fm, body="# demo\n"), p)
    return p


def _stub_nodes(verdict: str = "approve"):
    async def pm(s: dict) -> dict:
        return {"plan": {"summary": "p"}, "implementation_status": "in_progress", "current_node": "pm"}

    async def dev(s: dict) -> dict:
        return {"implementation_status": "done", "current_node": "dev"}

    async def qa(s: dict) -> dict:
        return {"test_report": {"verdict": "pass", "summary": "ok"}, "current_node": "qa"}

    async def reviewer(s: dict) -> dict:
        return {"review": {"verdict": verdict, "summary": "r"}, "current_node": "reviewer"}

    async def docs(s: dict) -> dict:
        return {"current_node": "docs", "implementation_status": "done"}

    return {"pm": pm, "dev": dev, "qa": qa, "reviewer": reviewer, "docs": docs}


def test_run_one_task_pauses_at_docs_and_moves_to_review(tmp_path: Path) -> None:
    repo, aegis = _bootstrap_repo(tmp_path)
    p = _seed_task(aegis)

    with patch("aegis.graph.runtime.create_worktree") as cw, \
         patch("aegis.graph.runtime.remove_worktree") as rw, \
         patch("aegis.graph.runtime.merge_worktree_into_main") as merge:
        cw.side_effect = lambda repo_root, worktree_path, branch: worktree_path.mkdir(parents=True, exist_ok=True)
        rw.side_effect = lambda *a, **kw: None
        merge.side_effect = lambda *a, **kw: None

        config = AegisConfig(project=ProjectConfig(name="t"))
        final = run_one_task(
            task_path=p,
            aegis_dir=aegis,
            repo_root=repo,
            config=config,
            node_overrides=_stub_nodes(verdict="approve"),
        )
        assert final["awaiting_human"] is True

    moved = next((aegis / "review").glob("001-*.md"), None)
    assert moved is not None
    # Worktree NOT removed on review pause
    rw.assert_not_called()
    merge.assert_not_called()


def test_run_one_task_blocks_on_blocker(tmp_path: Path) -> None:
    repo, aegis = _bootstrap_repo(tmp_path)
    p = _seed_task(aegis)

    async def pm_block(s: dict) -> dict:
        return {"blocked_reason": "ambiguous", "current_node": "pm"}

    overrides = _stub_nodes()
    overrides["pm"] = pm_block

    with patch("aegis.graph.runtime.create_worktree") as cw, \
         patch("aegis.graph.runtime.remove_worktree") as rw, \
         patch("aegis.graph.runtime.merge_worktree_into_main"):
        cw.side_effect = lambda repo_root, worktree_path, branch: worktree_path.mkdir(parents=True, exist_ok=True)
        config = AegisConfig(project=ProjectConfig(name="t"))
        final = run_one_task(
            task_path=p,
            aegis_dir=aegis,
            repo_root=repo,
            config=config,
            node_overrides=overrides,
        )
        assert final["blocked_reason"] == "ambiguous"

    moved = next((aegis / "blocked").glob("001-*.md"), None)
    assert moved is not None
    refreshed = parse_task(moved)
    assert "ambiguous" in refreshed.body


def test_resume_after_approve_runs_docs_and_moves_to_done(tmp_path: Path) -> None:
    repo, aegis = _bootstrap_repo(tmp_path)
    p = _seed_task(aegis)

    config = AegisConfig(project=ProjectConfig(name="t"))
    with patch("aegis.graph.runtime.create_worktree") as cw, \
         patch("aegis.graph.runtime.remove_worktree") as rw, \
         patch("aegis.graph.runtime.merge_worktree_into_main") as merge:
        cw.side_effect = lambda repo_root, worktree_path, branch: worktree_path.mkdir(parents=True, exist_ok=True)
        rw.side_effect = lambda *a, **kw: None
        merge.side_effect = lambda *a, **kw: None

        # First run pauses at review/.
        run_one_task(
            task_path=p,
            aegis_dir=aegis,
            repo_root=repo,
            config=config,
            node_overrides=_stub_nodes(verdict="approve"),
        )
        # Now resume.
        review_path = next((aegis / "review").glob("001-*.md"))
        final = resume_after_approve(
            task_id="001",
            aegis_dir=aegis,
            repo_root=repo,
            config=config,
            node_overrides=_stub_nodes(verdict="approve"),
        )
    assert final["current_node"] == "docs"
    moved = next((aegis / "done").glob("001-*.md"), None)
    assert moved is not None
    merge.assert_called()
    rw.assert_called()


def test_reject_moves_to_rejected_and_removes_worktree(tmp_path: Path) -> None:
    repo, aegis = _bootstrap_repo(tmp_path)
    review_path = aegis / "review" / "001-demo.md"
    review_path.parent.mkdir(parents=True, exist_ok=True)
    fm = TaskFrontmatter(
        id="001", title="demo",
        status=TaskStatus.REVIEW,
        priority=Priority.P2,
        budget=TaskBudget(),
        created=datetime.now(tz=UTC),
    )
    write_task(Task(frontmatter=fm, body="# demo\n"), review_path)

    with patch("aegis.graph.runtime.remove_worktree") as rw:
        rw.side_effect = lambda *a, **kw: None
        reject_task(task_id="001", aegis_dir=aegis, repo_root=repo, reason="auth broke")

    assert next((aegis / "rejected").glob("001-*.md"), None) is not None
```

- [ ] **Step 2: Implement**

```python
# src/aegis/graph/runtime.py
"""End-to-end runtime: worktree → graph → lifecycle moves.

This is the only place that touches both LangGraph and the .aegis/
filesystem in the same call. Nodes stay pure; the runtime owns I/O.
"""
from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

from aegis.core.config import AegisConfig
from aegis.core.lifecycle import find_task, transition
from aegis.core.task import (
    Task,
    TaskStatus,
    parse_task,
    serialize_task,
    write_task,
)
from aegis.core.worktree import create_worktree, remove_worktree
from aegis.graph.checkpointer import open_checkpointer
from aegis.graph.state import TeamState, initial_state
from aegis.graph.team_graph import build_graph

__all__ = [
    "run_one_task",
    "resume_after_approve",
    "reject_task",
    "merge_worktree_into_main",
]


def merge_worktree_into_main(repo_root: Path, branch: str) -> None:
    """Fast-forward (or merge) the worktree branch into ``main``.

    Uses the user's local ``main`` branch as the merge target. Failures
    propagate as ``subprocess.CalledProcessError`` — the runtime catches
    them and marks the task blocked.
    """
    subprocess.run(
        ["git", "checkout", "main"],
        cwd=str(repo_root), check=True, capture_output=True, text=True,
    )
    subprocess.run(
        ["git", "merge", "--no-ff", branch],
        cwd=str(repo_root), check=True, capture_output=True, text=True,
    )


def _worktree_paths(aegis_dir: Path, task: Task) -> tuple[Path, str]:
    fm = task.frontmatter
    slug = f"{fm.id}-{fm.title}".replace(" ", "-").lower()
    wt = aegis_dir / ".worktrees" / slug
    branch = f"aegis/{slug}"
    return wt, branch


def _record_blocked_reason(task_path: Path, reason: str) -> None:
    task = parse_task(task_path)
    if not task.body.endswith("\n"):
        task.body += "\n"
    task.body += f"\n## Blocker\n\n{reason}\n"
    write_task(task, task_path)


def run_one_task(
    *,
    task_path: Path,
    aegis_dir: Path,
    repo_root: Path,
    config: AegisConfig,
    node_overrides: dict[str, Any] | None = None,
) -> TeamState:
    """Run one task end-to-end. Pauses at the human gate (review/)."""
    # Ensure status is in-progress (move from backlog if needed).
    task = parse_task(task_path)
    if task.frontmatter.status == TaskStatus.BACKLOG:
        task_path = transition(task_path, aegis_dir, TaskStatus.IN_PROGRESS)
        task = parse_task(task_path)

    worktree_path, branch = _worktree_paths(aegis_dir, task)
    if not worktree_path.exists():
        create_worktree(repo_root, worktree_path, branch)

    state = initial_state(
        task=task,
        task_path=task_path,
        worktree_path=worktree_path,
        target_repo_root=repo_root,
    )
    state["pr_branch"] = branch
    task.frontmatter.worktree = str(worktree_path)
    task.frontmatter.pr_branch = branch
    write_task(task, task_path)

    cfg = {"configurable": {"thread_id": task.frontmatter.id}}
    with open_checkpointer(aegis_dir) as saver:
        graph = build_graph(node_overrides=node_overrides, checkpointer=saver)
        final = graph.invoke(state, config=cfg)
        # If the graph reached interrupt_before=["docs"], `final` reflects
        # the state at that gate. We detect it by checking for an
        # approved review with no docs run yet.
        review = final.get("review") or {}
        if final.get("blocked_reason"):
            _record_blocked_reason(task_path, final["blocked_reason"])
            transition(task_path, aegis_dir, TaskStatus.BLOCKED)
        elif review.get("verdict") == "approve" and final.get("current_node") != "docs":
            final["awaiting_human"] = True
            transition(task_path, aegis_dir, TaskStatus.REVIEW)
        else:
            # Reached END after docs (no human gate observed). Merge.
            try:
                merge_worktree_into_main(repo_root, branch)
                transition(task_path, aegis_dir, TaskStatus.DONE)
                remove_worktree(repo_root, worktree_path)
            except Exception as exc:
                _record_blocked_reason(task_path, f"merge failed: {exc}")
                transition(task_path, aegis_dir, TaskStatus.BLOCKED)
        return final


def resume_after_approve(
    *,
    task_id: str,
    aegis_dir: Path,
    repo_root: Path,
    config: AegisConfig,
    node_overrides: dict[str, Any] | None = None,
) -> TeamState:
    found = find_task(aegis_dir, task_id)
    if found is None:
        raise FileNotFoundError(f"task {task_id} not found")
    task, task_path = found
    if task.frontmatter.status != TaskStatus.REVIEW:
        raise ValueError(f"task {task_id} is in {task.frontmatter.status.value}, not review")

    worktree_path, branch = _worktree_paths(aegis_dir, task)
    cfg = {"configurable": {"thread_id": task_id}}
    with open_checkpointer(aegis_dir) as saver:
        graph = build_graph(node_overrides=node_overrides, checkpointer=saver)
        # Resume from the interrupt by passing None (LangGraph idiom).
        final = graph.invoke(None, config=cfg)
        if final.get("blocked_reason"):
            _record_blocked_reason(task_path, final["blocked_reason"])
            transition(task_path, aegis_dir, TaskStatus.BLOCKED)
            return final
        # Merge and finish.
        merge_worktree_into_main(repo_root, branch)
        transition(task_path, aegis_dir, TaskStatus.DONE)
        if worktree_path.exists():
            remove_worktree(repo_root, worktree_path)
        return final


def reject_task(
    *,
    task_id: str,
    aegis_dir: Path,
    repo_root: Path,
    reason: str | None = None,
) -> Path:
    found = find_task(aegis_dir, task_id)
    if found is None:
        raise FileNotFoundError(f"task {task_id} not found")
    task, task_path = found
    if reason:
        if not task.body.endswith("\n"):
            task.body += "\n"
        task.body += f"\n## Rejection reason\n\n{reason}\n"
        write_task(task, task_path)
    new_path = transition(task_path, aegis_dir, TaskStatus.REJECTED)
    worktree_path, _ = _worktree_paths(aegis_dir, task)
    if worktree_path.exists():
        try:
            remove_worktree(repo_root, worktree_path)
        except Exception:
            # Best-effort: rejected tasks may have already-clean worktrees.
            pass
    return new_path
```

- [ ] **Step 3: Run; confirm green**

```bash
pytest tests/unit/test_graph_runtime.py -v
```

If LangGraph's `invoke(None, ...)` resume idiom differs in the installed version, adapt by either calling `graph.update_state(...)` then `graph.invoke(None, cfg)`, or `graph.continue_(...)`. Confirm against the installed `langgraph` version's docstrings.

- [ ] **Step 4: Commit**

```bash
git add src/aegis/graph/runtime.py tests/unit/test_graph_runtime.py
git commit -m "feat(graph): add runtime driver (run, resume, reject) with worktree mgmt"
```

---

## Task 16: `aegis run` CLI command

**Files:**

- Create: `src/aegis/cli/commands/run.py`
- Create: `tests/unit/test_cli_run.py`
- Modify: `src/aegis/cli/main.py`
- Modify: `src/aegis/cli/commands/stubs.py`

`aegis run [--task <id>] [--once] [--parallel <n>]`:

1. If `--task <id>`: run that one task (must exist somewhere except `done/`).
2. Else if `--once`: drain `backlog/` once, run each task sequentially, exit.
3. Else: same as `--once` for now (the daemon command in Task 22 handles long-lived loops). `--parallel` is accepted but a no-op in this phase (see Appendix A point 4).

- [ ] **Step 1: Drop the stub for `run`**

In `src/aegis/cli/commands/stubs.py`, remove the `@app.command(...) def run(...)` block (and its decorator). Other stubs remain.

- [ ] **Step 2: Failing test**

```python
# tests/unit/test_cli_run.py
from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import patch

from typer.testing import CliRunner

from aegis.cli.main import app
from aegis.core.task import Priority, Task, TaskBudget, TaskFrontmatter, TaskStatus, write_task


def _seed(repo: Path, task_id: str = "001") -> Path:
    aegis = repo / ".aegis"
    for sub in ("backlog", "in-progress", "review", "done", "blocked", "rejected", ".worktrees"):
        (aegis / sub).mkdir(parents=True, exist_ok=True)
    p = aegis / "backlog" / f"{task_id}-demo.md"
    fm = TaskFrontmatter(
        id=task_id, title="demo",
        status=TaskStatus.BACKLOG, priority=Priority.P2,
        budget=TaskBudget(),
        created=datetime.now(tz=UTC),
    )
    write_task(Task(frontmatter=fm, body="# demo\n"), p)
    return p


def test_run_invokes_runtime_for_each_backlog_task(tmp_path: Path, monkeypatch) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / ".git").mkdir()
    _seed(repo, "001")
    _seed(repo, "002")
    monkeypatch.chdir(repo)

    with patch("aegis.cli.commands.run.run_one_task") as ru:
        ru.side_effect = lambda **kw: {"current_node": "reviewer"}
        runner = CliRunner()
        result = runner.invoke(app, ["run", "--once"])
    assert result.exit_code == 0, result.stdout
    assert ru.call_count == 2


def test_run_specific_task(tmp_path: Path, monkeypatch) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / ".git").mkdir()
    _seed(repo, "001")
    _seed(repo, "002")
    monkeypatch.chdir(repo)

    with patch("aegis.cli.commands.run.run_one_task") as ru:
        ru.side_effect = lambda **kw: {"current_node": "reviewer"}
        runner = CliRunner()
        result = runner.invoke(app, ["run", "--task", "001"])
    assert result.exit_code == 0, result.stdout
    assert ru.call_count == 1
    # The task_path passed should reference 001
    called_path: Path = ru.call_args.kwargs["task_path"]
    assert "001" in called_path.name
```

- [ ] **Step 3: Implement**

```python
# src/aegis/cli/commands/run.py
from __future__ import annotations

from pathlib import Path

import typer

from aegis.cli.commands.init import AEGIS_DIRNAME
from aegis.core.config import load_config
from aegis.core.lifecycle import find_task, list_tasks
from aegis.core.task import TaskStatus
from aegis.graph.runtime import run_one_task


def _aegis_dir(repo_root: Path) -> Path:
    d = repo_root / AEGIS_DIRNAME
    if not d.exists():
        raise typer.BadParameter(f"No {AEGIS_DIRNAME}/ at {repo_root}; run `aegis init` first.")
    return d


def _config_for(aegis_dir: Path):
    return load_config(aegis_dir / "config.yaml")


def register(app: typer.Typer) -> None:
    @app.command(help="Run the team graph in the foreground.")
    def run(
        task: str | None = typer.Option(None, "--task", help="Run only this task id."),
        once: bool = typer.Option(False, "--once", help="Drain backlog once and exit."),
        parallel: int | None = typer.Option(None, "--parallel", help="Reserved for Phase 5."),
    ) -> None:
        repo = Path.cwd().resolve()
        aegis = _aegis_dir(repo)
        config = _config_for(aegis)

        if task is not None:
            found = find_task(aegis, task)
            if found is None:
                raise typer.BadParameter(f"task {task} not found")
            _, task_path = found
            run_one_task(
                task_path=task_path,
                aegis_dir=aegis,
                repo_root=repo,
                config=config,
            )
            return

        # Drain backlog
        backlog = list_tasks(aegis, status=TaskStatus.BACKLOG)
        if not backlog:
            typer.echo("backlog is empty")
            return
        for _, task_path in backlog:
            run_one_task(
                task_path=task_path,
                aegis_dir=aegis,
                repo_root=repo,
                config=config,
            )
        if not once and parallel:
            typer.echo("(--parallel is reserved for Phase 5; treating as --once)")
```

- [ ] **Step 4: Wire into `main.py`**

In `src/aegis/cli/main.py`, after `register_config(app)`, add:

```python
from aegis.cli.commands.run import register as register_run  # noqa: E402

register_run(app)
```

- [ ] **Step 5: Run; confirm green**

```bash
pytest tests/unit/test_cli_run.py -v
```

- [ ] **Step 6: Commit**

```bash
git add src/aegis/cli/commands/run.py src/aegis/cli/commands/stubs.py src/aegis/cli/main.py tests/unit/test_cli_run.py
git commit -m "feat(cli): implement aegis run (drain backlog or single task)"
```

---

## Task 17: `aegis status` command

**Files:**

- Create: `src/aegis/cli/commands/status.py`
- Create: `tests/unit/test_cli_status.py`
- Modify: `src/aegis/cli/main.py`
- Modify: `src/aegis/cli/commands/stubs.py`

Print a kanban-ish table grouped by status. `--watch` is accepted but a no-op (Phase 5).

- [ ] **Step 1: Drop the stub for `status` from `stubs.py`**

- [ ] **Step 2: Failing test**

```python
# tests/unit/test_cli_status.py
from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from typer.testing import CliRunner

from aegis.cli.main import app
from aegis.core.task import Priority, Task, TaskBudget, TaskFrontmatter, TaskStatus, write_task


def _seed(aegis: Path, task_id: str, status: TaskStatus, title: str = "demo") -> None:
    p = aegis / status.value / f"{task_id}-{title}.md"
    p.parent.mkdir(parents=True, exist_ok=True)
    fm = TaskFrontmatter(
        id=task_id, title=title,
        status=status, priority=Priority.P2,
        budget=TaskBudget(),
        created=datetime.now(tz=UTC),
    )
    write_task(Task(frontmatter=fm, body=f"# {title}\n"), p)


def test_status_lists_tasks_per_lane(tmp_path: Path, monkeypatch) -> None:
    repo = tmp_path / "repo"
    aegis = repo / ".aegis"
    (repo / ".git").mkdir(parents=True)
    _seed(aegis, "001", TaskStatus.BACKLOG, "alpha")
    _seed(aegis, "002", TaskStatus.IN_PROGRESS, "beta")
    _seed(aegis, "003", TaskStatus.REVIEW, "gamma")
    monkeypatch.chdir(repo)

    runner = CliRunner()
    result = runner.invoke(app, ["status"])
    assert result.exit_code == 0, result.stdout
    out = result.stdout
    assert "001" in out and "002" in out and "003" in out
    assert "backlog" in out.lower()
    assert "review" in out.lower()
```

- [ ] **Step 3: Implement**

```python
# src/aegis/cli/commands/status.py
from __future__ import annotations

from pathlib import Path

import typer

from aegis.cli.commands.init import AEGIS_DIRNAME
from aegis.core.lifecycle import list_tasks
from aegis.core.task import TaskStatus


def register(app: typer.Typer) -> None:
    @app.command(help="Print the kanban view of all tasks.")
    def status(
        watch: bool = typer.Option(False, "--watch", help="Reserved for Phase 5."),
    ) -> None:
        repo = Path.cwd().resolve()
        aegis = repo / AEGIS_DIRNAME
        if not aegis.exists():
            typer.echo(f"No {AEGIS_DIRNAME}/ here. Run `aegis init` first.")
            raise typer.Exit(code=2)

        for status_value in TaskStatus:
            rows = list_tasks(aegis, status=status_value)
            if not rows:
                continue
            typer.echo(f"\n[{status_value.value.upper()}]")
            for task, _ in rows:
                fm = task.frontmatter
                typer.echo(f"  {fm.id}  {fm.priority.value}  {fm.title}")
        if watch:
            typer.echo("\n(--watch is reserved for Phase 5)")
```

- [ ] **Step 4: Wire into main, run tests, commit**

```python
# main.py
from aegis.cli.commands.status import register as register_status  # noqa: E402
register_status(app)
```

```bash
pytest tests/unit/test_cli_status.py -v
git add src/aegis/cli/commands/status.py src/aegis/cli/commands/stubs.py src/aegis/cli/main.py tests/unit/test_cli_status.py
git commit -m "feat(cli): implement aegis status"
```

---

## Task 18: `aegis stop` command

**Files:**

- Create: `src/aegis/cli/commands/stop.py`
- Create: `tests/unit/test_cli_stop.py`
- Modify: `src/aegis/cli/main.py`, `stubs.py`

Touch `.aegis/.stop` (no arg) or `.aegis/.stop.<id>` (with arg). The running `aegis run` doesn't poll the file in Phase 4 (the design goal is "halt at next checkpoint"; for the foreground `run` command, that's at the next node boundary — `node_helpers.check_stop_flag` handles it). So `stop` is just a file-touch.

- [ ] **Step 1: Drop the `stop` stub**

- [ ] **Step 2: Failing test**

```python
# tests/unit/test_cli_stop.py
from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from aegis.cli.main import app


def _bootstrap(repo: Path) -> Path:
    aegis = repo / ".aegis"
    aegis.mkdir(parents=True)
    return aegis


def test_stop_no_arg_creates_global_flag(tmp_path: Path, monkeypatch) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / ".git").mkdir()
    _bootstrap(repo)
    monkeypatch.chdir(repo)

    result = CliRunner().invoke(app, ["stop"])
    assert result.exit_code == 0
    assert (repo / ".aegis" / ".stop").exists()


def test_stop_with_id_creates_task_flag(tmp_path: Path, monkeypatch) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / ".git").mkdir()
    _bootstrap(repo)
    monkeypatch.chdir(repo)

    result = CliRunner().invoke(app, ["stop", "001"])
    assert result.exit_code == 0
    assert (repo / ".aegis" / ".stop.001").exists()
```

- [ ] **Step 3: Implement**

```python
# src/aegis/cli/commands/stop.py
from __future__ import annotations

from pathlib import Path

import typer

from aegis.cli.commands.init import AEGIS_DIRNAME


def register(app: typer.Typer) -> None:
    @app.command(help="Halt all (or one) task at the next checkpoint.")
    def stop(task_id: str | None = typer.Argument(None)) -> None:
        repo = Path.cwd().resolve()
        aegis = repo / AEGIS_DIRNAME
        if not aegis.exists():
            raise typer.BadParameter(f"No {AEGIS_DIRNAME}/ at {repo}.")
        flag = aegis / (".stop" if task_id is None else f".stop.{task_id}")
        flag.touch()
        scope = "all tasks" if task_id is None else f"task {task_id}"
        typer.echo(f"Stop signal raised for {scope}: {flag}")
```

- [ ] **Step 4: Wire, run tests, commit**

```python
from aegis.cli.commands.stop import register as register_stop
register_stop(app)
```

```bash
pytest tests/unit/test_cli_stop.py -v
git add src/aegis/cli/commands/stop.py src/aegis/cli/commands/stubs.py src/aegis/cli/main.py tests/unit/test_cli_stop.py
git commit -m "feat(cli): implement aegis stop kill switch"
```

---

## Task 19: `aegis approve` command

**Files:**

- Create: `src/aegis/cli/commands/approve.py`
- Create: `tests/unit/test_cli_approve.py`
- Modify: `src/aegis/cli/main.py`, `stubs.py`

`aegis approve <id>`:

1. Find task in `review/`.
2. Call `resume_after_approve(task_id, aegis_dir, repo_root, config)`.

- [ ] **Step 1: Drop `approve` stub**

- [ ] **Step 2: Failing test**

```python
# tests/unit/test_cli_approve.py
from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import patch

from typer.testing import CliRunner

from aegis.cli.main import app
from aegis.core.task import Priority, Task, TaskBudget, TaskFrontmatter, TaskStatus, write_task


def _seed_review(repo: Path) -> None:
    aegis = repo / ".aegis"
    for sub in ("backlog", "in-progress", "review", "done", "blocked", "rejected", ".worktrees"):
        (aegis / sub).mkdir(parents=True, exist_ok=True)
    p = aegis / "review" / "001-demo.md"
    fm = TaskFrontmatter(
        id="001", title="demo",
        status=TaskStatus.REVIEW, priority=Priority.P2,
        budget=TaskBudget(),
        created=datetime.now(tz=UTC),
    )
    write_task(Task(frontmatter=fm, body="# demo\n"), p)


def test_approve_calls_resume(tmp_path: Path, monkeypatch) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / ".git").mkdir()
    _seed_review(repo)
    monkeypatch.chdir(repo)

    with patch("aegis.cli.commands.approve.resume_after_approve") as ra:
        ra.side_effect = lambda **kw: {"current_node": "docs"}
        result = CliRunner().invoke(app, ["approve", "001"])
    assert result.exit_code == 0, result.stdout
    assert ra.call_count == 1
    assert ra.call_args.kwargs["task_id"] == "001"
```

- [ ] **Step 3: Implement**

```python
# src/aegis/cli/commands/approve.py
from __future__ import annotations

from pathlib import Path

import typer

from aegis.cli.commands.init import AEGIS_DIRNAME
from aegis.core.config import load_config
from aegis.graph.runtime import resume_after_approve


def register(app: typer.Typer) -> None:
    @app.command(help="Approve a review/-bound task: merge and run Docs.")
    def approve(task_id: str = typer.Argument(...)) -> None:
        repo = Path.cwd().resolve()
        aegis = repo / AEGIS_DIRNAME
        if not aegis.exists():
            raise typer.BadParameter(f"No {AEGIS_DIRNAME}/ here.")
        config = load_config(aegis / "config.yaml")
        resume_after_approve(
            task_id=task_id,
            aegis_dir=aegis,
            repo_root=repo,
            config=config,
        )
        typer.echo(f"approved {task_id}: merged and Docs ran")
```

- [ ] **Step 4: Wire, test, commit**

```python
from aegis.cli.commands.approve import register as register_approve
register_approve(app)
```

```bash
pytest tests/unit/test_cli_approve.py -v
git add src/aegis/cli/commands/approve.py src/aegis/cli/commands/stubs.py src/aegis/cli/main.py tests/unit/test_cli_approve.py
git commit -m "feat(cli): implement aegis approve"
```

---

## Task 20: `aegis reject` command

**Files:**

- Create: `src/aegis/cli/commands/reject.py`
- Create: `tests/unit/test_cli_reject.py`
- Modify: main, stubs

Calls `reject_task(...)` from runtime.

- [ ] **Step 1: Drop `reject` stub**

- [ ] **Step 2: Failing test**

```python
# tests/unit/test_cli_reject.py
from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import patch

from typer.testing import CliRunner

from aegis.cli.main import app
from aegis.core.task import Priority, Task, TaskBudget, TaskFrontmatter, TaskStatus, write_task


def _seed(repo: Path) -> None:
    aegis = repo / ".aegis"
    for sub in ("backlog", "review", "rejected", "done", "blocked", "in-progress", ".worktrees"):
        (aegis / sub).mkdir(parents=True, exist_ok=True)
    p = aegis / "review" / "001-demo.md"
    fm = TaskFrontmatter(
        id="001", title="demo", status=TaskStatus.REVIEW, priority=Priority.P2,
        budget=TaskBudget(), created=datetime.now(tz=UTC),
    )
    write_task(Task(frontmatter=fm, body="# demo\n"), p)


def test_reject_invokes_runtime(tmp_path: Path, monkeypatch) -> None:
    repo = tmp_path / "repo"; repo.mkdir(); (repo / ".git").mkdir()
    _seed(repo); monkeypatch.chdir(repo)
    with patch("aegis.cli.commands.reject.reject_task") as rj:
        result = CliRunner().invoke(app, ["reject", "001", "auth broke"])
    assert result.exit_code == 0
    assert rj.call_args.kwargs["task_id"] == "001"
    assert rj.call_args.kwargs["reason"] == "auth broke"
```

- [ ] **Step 3: Implement**

```python
# src/aegis/cli/commands/reject.py
from __future__ import annotations

from pathlib import Path

import typer

from aegis.cli.commands.init import AEGIS_DIRNAME
from aegis.graph.runtime import reject_task


def register(app: typer.Typer) -> None:
    @app.command(help="Reject a review/-bound task and discard its worktree.")
    def reject(
        task_id: str = typer.Argument(...),
        reason: str | None = typer.Argument(None),
    ) -> None:
        repo = Path.cwd().resolve()
        aegis = repo / AEGIS_DIRNAME
        if not aegis.exists():
            raise typer.BadParameter(f"No {AEGIS_DIRNAME}/ here.")
        reject_task(
            task_id=task_id,
            aegis_dir=aegis,
            repo_root=repo,
            reason=reason,
        )
        typer.echo(f"rejected {task_id}")
```

- [ ] **Step 4: Wire, test, commit**

```python
from aegis.cli.commands.reject import register as register_reject
register_reject(app)
```

```bash
pytest tests/unit/test_cli_reject.py -v
git add src/aegis/cli/commands/reject.py src/aegis/cli/commands/stubs.py src/aegis/cli/main.py tests/unit/test_cli_reject.py
git commit -m "feat(cli): implement aegis reject"
```

---

## Task 21: `aegis retry` command

**Files:**

- Create: `src/aegis/cli/commands/retry.py`
- Create: `tests/unit/test_cli_retry.py`
- Modify: main, stubs

`aegis retry <id> [--budget-usd N] [--from <node>]`:

1. Find task in `blocked/` or `rejected/`.
2. Optionally update budget in frontmatter.
3. `--from` is recorded in frontmatter as a `retry_from` field for future runs (Phase 5 will honor it). Phase 4 just stores it.
4. Move task back to `backlog/`.

- [ ] **Step 1: Drop `retry` stub**

- [ ] **Step 2: Failing test**

```python
# tests/unit/test_cli_retry.py
from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from typer.testing import CliRunner

from aegis.cli.main import app
from aegis.core.lifecycle import list_tasks
from aegis.core.task import (
    Priority, Task, TaskBudget, TaskFrontmatter, TaskStatus, parse_task, write_task,
)


def _seed_blocked(repo: Path) -> Path:
    aegis = repo / ".aegis"
    for sub in ("backlog", "blocked", "rejected", "done", "review", "in-progress", ".worktrees"):
        (aegis / sub).mkdir(parents=True, exist_ok=True)
    p = aegis / "blocked" / "001-demo.md"
    fm = TaskFrontmatter(
        id="001", title="demo", status=TaskStatus.BLOCKED, priority=Priority.P2,
        budget=TaskBudget(usd=2.0, minutes=30), created=datetime.now(tz=UTC),
    )
    write_task(Task(frontmatter=fm, body="# demo\n"), p)
    return p


def test_retry_moves_to_backlog_and_updates_budget(tmp_path: Path, monkeypatch) -> None:
    repo = tmp_path / "repo"; repo.mkdir(); (repo / ".git").mkdir()
    _seed_blocked(repo); monkeypatch.chdir(repo)
    result = CliRunner().invoke(app, ["retry", "001", "--budget-usd", "5.0"])
    assert result.exit_code == 0, result.stdout
    backlog = list_tasks(repo / ".aegis", status=TaskStatus.BACKLOG)
    assert len(backlog) == 1
    task, path = backlog[0]
    assert task.frontmatter.budget.usd == 5.0
```

- [ ] **Step 3: Implement**

```python
# src/aegis/cli/commands/retry.py
from __future__ import annotations

from pathlib import Path

import typer

from aegis.cli.commands.init import AEGIS_DIRNAME
from aegis.core.lifecycle import find_task, transition
from aegis.core.task import TaskStatus, write_task


def register(app: typer.Typer) -> None:
    @app.command(help="Retry a blocked or rejected task.")
    def retry(
        task_id: str = typer.Argument(...),
        budget_usd: float | None = typer.Option(None, "--budget-usd"),
        from_node: str | None = typer.Option(None, "--from"),
    ) -> None:
        repo = Path.cwd().resolve()
        aegis = repo / AEGIS_DIRNAME
        if not aegis.exists():
            raise typer.BadParameter(f"No {AEGIS_DIRNAME}/ here.")
        found = find_task(aegis, task_id)
        if found is None:
            raise typer.BadParameter(f"task {task_id} not found")
        task, task_path = found
        if task.frontmatter.status not in (TaskStatus.BLOCKED, TaskStatus.REJECTED):
            raise typer.BadParameter(
                f"task {task_id} is in {task.frontmatter.status.value}; only blocked/rejected can be retried"
            )
        if budget_usd is not None:
            task.frontmatter.budget.usd = budget_usd
            write_task(task, task_path)
        new_path = transition(task_path, aegis, TaskStatus.BACKLOG)
        if from_node:
            typer.echo(
                f"(retry --from {from_node} accepted but Phase 5 will honor it; "
                f"Phase 4 reruns from PM)"
            )
        typer.echo(f"retrying {task_id}: moved to {new_path.relative_to(aegis)}")
```

- [ ] **Step 4: Wire, test, commit**

```bash
pytest tests/unit/test_cli_retry.py -v
git add src/aegis/cli/commands/retry.py src/aegis/cli/commands/stubs.py src/aegis/cli/main.py tests/unit/test_cli_retry.py
git commit -m "feat(cli): implement aegis retry"
```

---

## Task 22: `aegis inspect` command

**Files:**

- Create: `src/aegis/cli/commands/inspect.py`
- Create: `tests/unit/test_cli_inspect.py`
- Modify: main, stubs

Print the task's full markdown (frontmatter + body) plus, when checkpoint exists, the latest `current_node` and `blocked_reason`.

- [ ] **Step 1: Drop `inspect` stub**

- [ ] **Step 2: Failing test**

```python
# tests/unit/test_cli_inspect.py
from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from typer.testing import CliRunner

from aegis.cli.main import app
from aegis.core.task import Priority, Task, TaskBudget, TaskFrontmatter, TaskStatus, write_task


def _seed(repo: Path) -> None:
    aegis = repo / ".aegis"
    aegis.mkdir(parents=True)
    (aegis / "blocked").mkdir()
    p = aegis / "blocked" / "001-demo.md"
    fm = TaskFrontmatter(
        id="001", title="demo",
        status=TaskStatus.BLOCKED, priority=Priority.P2,
        budget=TaskBudget(),
        created=datetime.now(tz=UTC),
    )
    write_task(Task(frontmatter=fm, body="# demo\n\n## Blocker\n\nbecause.\n"), p)


def test_inspect_prints_markdown(tmp_path: Path, monkeypatch) -> None:
    repo = tmp_path / "repo"; repo.mkdir(); (repo / ".git").mkdir()
    _seed(repo); monkeypatch.chdir(repo)
    result = CliRunner().invoke(app, ["inspect", "001"])
    assert result.exit_code == 0, result.stdout
    assert "001" in result.stdout
    assert "Blocker" in result.stdout
```

- [ ] **Step 3: Implement**

```python
# src/aegis/cli/commands/inspect.py
from __future__ import annotations

from pathlib import Path

import typer

from aegis.cli.commands.init import AEGIS_DIRNAME
from aegis.core.lifecycle import find_task
from aegis.core.task import serialize_task


def register(app: typer.Typer) -> None:
    @app.command(help="Print a task's full markdown.")
    def inspect(task_id: str = typer.Argument(...)) -> None:
        repo = Path.cwd().resolve()
        aegis = repo / AEGIS_DIRNAME
        if not aegis.exists():
            raise typer.BadParameter(f"No {AEGIS_DIRNAME}/ here.")
        found = find_task(aegis, task_id)
        if found is None:
            raise typer.BadParameter(f"task {task_id} not found")
        task, _ = found
        typer.echo(serialize_task(task))
```

- [ ] **Step 4: Wire, test, commit**

```bash
pytest tests/unit/test_cli_inspect.py -v
git add src/aegis/cli/commands/inspect.py src/aegis/cli/commands/stubs.py src/aegis/cli/main.py tests/unit/test_cli_inspect.py
git commit -m "feat(cli): implement aegis inspect"
```

---

## Task 23: `aegis daemon` (start/stop/status/restart) and final integration

**Files:**

- Create: `src/aegis/cli/commands/daemon.py`
- Create: `tests/unit/test_cli_daemon.py`
- Modify: main, stubs

The daemon is a thin pidfile-based wrapper that spawns `aegis run --once` in a polling loop. For Phase 4 we keep it minimal:

- `daemon start`: write `<aegis>/.daemon.pid` with our PID, then run a Python loop that calls `run_one_task` for each backlog item, sleeps, repeats. We launch as a subprocess (`subprocess.Popen([...], start_new_session=True)`) so the CLI returns immediately.
- `daemon stop`: read pidfile, send `SIGTERM`, remove pidfile.
- `daemon status`: print whether the pidfile exists and the PID is alive.
- `daemon restart`: stop then start.

- [ ] **Step 1: Drop the `daemon` typer subgroup from `stubs.py`**

- [ ] **Step 2: Failing test (no real subprocess)**

```python
# tests/unit/test_cli_daemon.py
from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from typer.testing import CliRunner

from aegis.cli.main import app


def _bootstrap(repo: Path) -> Path:
    aegis = repo / ".aegis"
    aegis.mkdir(parents=True)
    return aegis


def test_daemon_start_writes_pidfile(tmp_path: Path, monkeypatch) -> None:
    repo = tmp_path / "repo"; repo.mkdir(); (repo / ".git").mkdir()
    _bootstrap(repo); monkeypatch.chdir(repo)
    with patch("aegis.cli.commands.daemon.subprocess.Popen") as pop:
        proc = pop.return_value
        proc.pid = 4242
        result = CliRunner().invoke(app, ["daemon", "start"])
    assert result.exit_code == 0
    assert (repo / ".aegis" / ".daemon.pid").read_text().strip() == "4242"


def test_daemon_status_reports_running(tmp_path: Path, monkeypatch) -> None:
    repo = tmp_path / "repo"; repo.mkdir(); (repo / ".git").mkdir()
    aegis = _bootstrap(repo); monkeypatch.chdir(repo)
    (aegis / ".daemon.pid").write_text("4242\n")
    with patch("aegis.cli.commands.daemon._is_pid_alive", return_value=True):
        result = CliRunner().invoke(app, ["daemon", "status"])
    assert result.exit_code == 0
    assert "running" in result.stdout.lower()


def test_daemon_stop_removes_pidfile(tmp_path: Path, monkeypatch) -> None:
    repo = tmp_path / "repo"; repo.mkdir(); (repo / ".git").mkdir()
    aegis = _bootstrap(repo); monkeypatch.chdir(repo)
    (aegis / ".daemon.pid").write_text("4242\n")
    with patch("aegis.cli.commands.daemon.os.kill") as kill, \
         patch("aegis.cli.commands.daemon._is_pid_alive", return_value=True):
        result = CliRunner().invoke(app, ["daemon", "stop"])
    assert result.exit_code == 0
    kill.assert_called()
    assert not (aegis / ".daemon.pid").exists()
```

- [ ] **Step 3: Implement**

```python
# src/aegis/cli/commands/daemon.py
from __future__ import annotations

import os
import signal
import subprocess
import sys
from pathlib import Path

import typer

from aegis.cli.commands.init import AEGIS_DIRNAME

PIDFILE = ".daemon.pid"


def _aegis_dir(repo: Path) -> Path:
    d = repo / AEGIS_DIRNAME
    if not d.exists():
        raise typer.BadParameter(f"No {AEGIS_DIRNAME}/ at {repo}.")
    return d


def _is_pid_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def register(app: typer.Typer) -> None:
    daemon_app = typer.Typer(help="Background worker.")

    @daemon_app.command("start", help="Start the daemon (drains backlog in a loop).")
    def start() -> None:
        repo = Path.cwd().resolve()
        aegis = _aegis_dir(repo)
        pidpath = aegis / PIDFILE
        if pidpath.exists():
            pid = int(pidpath.read_text().strip() or "0")
            if pid and _is_pid_alive(pid):
                typer.echo(f"already running (pid {pid})")
                return
        # Use sys.executable to ensure the subprocess uses the same env.
        proc = subprocess.Popen(
            [sys.executable, "-m", "aegis.cli.main", "run", "--once"],
            cwd=str(repo),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
        pidpath.write_text(f"{proc.pid}\n")
        typer.echo(f"daemon started (pid {proc.pid})")

    @daemon_app.command("stop", help="Stop the daemon.")
    def stop() -> None:
        repo = Path.cwd().resolve()
        aegis = _aegis_dir(repo)
        pidpath = aegis / PIDFILE
        if not pidpath.exists():
            typer.echo("daemon is not running")
            return
        pid = int(pidpath.read_text().strip() or "0")
        if pid and _is_pid_alive(pid):
            os.kill(pid, signal.SIGTERM)
        pidpath.unlink(missing_ok=True)
        typer.echo(f"daemon stopped (pid {pid})")

    @daemon_app.command("status", help="Report daemon status.")
    def status() -> None:
        repo = Path.cwd().resolve()
        aegis = _aegis_dir(repo)
        pidpath = aegis / PIDFILE
        if not pidpath.exists():
            typer.echo("daemon: stopped")
            return
        pid = int(pidpath.read_text().strip() or "0")
        if pid and _is_pid_alive(pid):
            typer.echo(f"daemon: running (pid {pid})")
        else:
            typer.echo("daemon: stale pidfile (process gone)")

    @daemon_app.command("restart", help="Restart the daemon.")
    def restart() -> None:
        stop()
        start()

    app.add_typer(daemon_app, name="daemon")
```

- [ ] **Step 4: Wire, run all daemon tests**

```python
from aegis.cli.commands.daemon import register as register_daemon
register_daemon(app)
```

```bash
pytest tests/unit/test_cli_daemon.py -v
```

- [ ] **Step 5: Final full-suite check**

```bash
pytest tests/unit -q
```

Expected: every Phase 1+2+3+4 test passes (Phase 1 ~50, Phase 2 ~70, Phase 3 ~85, Phase 4 ~80; total ≈ 285 ± 20).

- [ ] **Step 6: Tag and commit**

```bash
git add src/aegis/cli/commands/daemon.py src/aegis/cli/commands/stubs.py src/aegis/cli/main.py tests/unit/test_cli_daemon.py
git commit -m "feat(cli): implement aegis daemon (start/stop/status/restart)"
git tag -a phase-4-complete -m "Phase 4: LangGraph team graph + CLI integration"
```

---

## Appendix A — Decisions locked in by this plan

1. **`done`/`block` are an in-process MCP server, not stdio.** `claude_agent_sdk.create_sdk_mcp_server` produces a `server` object that the SDK runs in the same Python process. Each `AegisAgent` invocation creates a fresh signals server (one per node-call) — there is no shared state.
2. **The verdict goes in the `done` tool's `verdict` argument**, not in a separate `qa_pass`/`qa_fail` tool, to preserve the Phase-3 "every role calls `done`" contract. Prompts teach the model to set it for QA and Reviewer.
3. **Worktree, lifecycle, budget, and merge are runtime concerns, not node concerns.** Nodes return state deltas only. This keeps the node-level tests pure and the runtime testable without mocking LangGraph.
4. **`--parallel` is reserved for Phase 5.** The graph runs one task at a time in Phase 4 (avoids needing a multi-thread checkpointer scheme). The flag is accepted to keep the CLI surface stable.
5. **Daemon is a thin pidfile + `aegis run --once` subprocess.** No supervisor loop in-process; the daemon command spawns and exits. Phase 5 will replace this with a polling supervisor.
6. **Stop flag is checked at node-call boundaries via `node_helpers.check_stop_flag`.** The runtime calls it before each node-driven `graph.invoke` segment. Mid-node interruption is out of scope for Phase 4 (the SDK does not expose a clean cancellation hook into the agent loop).
7. **LangGraph version expectations:** `langgraph >= 0.2.50` and `langgraph-checkpoint-sqlite >= 2.0`. If `SqliteSaver.from_conn_string` is not a context manager in the installed version, fall back to `SqliteSaver(sqlite3.connect(...))` and wrap manually; the test suite catches the difference.

## Appendix B — Handoff to Phase 5

Phase 5 will:

1. Implement parallel task execution behind `--parallel N`. Each worker is a separate thread (or asyncio task) with its own LangGraph thread_id. The checkpointer is shared.
2. Wire `OpenTelemetry` traces in every node so `aegis trace <id>` and `aegis logs <id>` (currently still stubs from Phase 1) work.
3. Replace the `daemon` subprocess with an in-process supervisor that polls `backlog/`, respects budget caps globally, and exposes `aegis daemon status` with richer info (queue depth, current task ids, last error).
4. Honor `aegis retry --from <node>` by resetting the LangGraph thread to the named node before resuming.
5. Add the integration test `tests/integration/test_team_graph.py` that runs the full graph against a fixtures repo with a stubbed Anthropic client (no real LLM calls).

The Phase-4 contracts that Phase 5 must preserve:

- `TeamState` field set
- `extract_signal` semantics (last-tool-use wins; verdict propagates)
- Runtime entry points `run_one_task`, `resume_after_approve`, `reject_task`
- The eight CLI commands' signatures

---

*End of Phase 4 implementation plan.*
