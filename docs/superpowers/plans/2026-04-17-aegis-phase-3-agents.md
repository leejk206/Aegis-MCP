# Aegis Phase 3 — Claude Agent SDK Agent Layer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deliver a testable, LLM-free-at-test-time agent abstraction for the five Aegis roles (PM / Dev / QA / Reviewer / Docs) by wrapping the Claude Agent SDK, binding each role to the Phase-2 MCP servers with the right scope and per-role allow-lists, and shipping the five role prompts per spec §4.2.

**Architecture:** A single `AegisAgent` class per instantiation binds one role to one worktree. Its body is a thin wrapper over `claude_agent_sdk.ClaudeSDKClient`; all LLM-touching behavior goes through an injected client factory so unit tests can run without the `claude` CLI or a network. A `registry` module declares the five roles and their per-role MCP server / tool allow-lists as pure data. A `tools` module turns that data plus a concrete worktree path into the `ClaudeAgentOptions.mcp_servers` dict that spawns our Phase-2 `aegis-*-mcp` binaries over stdio. A `base` module assembles prompt loading, role resolution, and options construction into the public `AegisAgent` surface.

**Tech Stack:** Python 3.11+, `claude-agent-sdk>=0.1.61` (Python SDK — **not** `anthropic[agent]` as the spec's §8.1 table incorrectly said; we reconcile this in Task 1), the four Phase-2 MCP console scripts (`aegis-git-mcp`, `aegis-fs-mcp`, `aegis-shell-mcp`, `aegis-project-index-mcp`), and pytest. No real LLM calls in unit tests — the `ClaudeSDKClient` is dependency-injected and replaced with a fake in tests. No `pytest-asyncio`: we test the async `run()` method by driving the event loop manually with `asyncio.run`.

**Spec reference:** `docs/superpowers/specs/2026-04-14-aegis-ai-engineering-team-design.md` (§4 Agent roles, §4.1 Why exactly these five, §4.2 Per-agent prompt authoring, §4.3 Model routing rationale, §6.2 config.yaml schema, §10 MCP servers, §11.4 Worktree lifecycle)

**Predecessor plans:**
- `docs/superpowers/plans/2026-04-14-aegis-phase-1-core.md` (tagged `phase-1-complete`)
- `docs/superpowers/plans/2026-04-14-aegis-phase-2-mcp-servers.md` (tagged `phase-2-complete`)

---

## Scope

### Phase 3 covers these spec sections

- **§4 (all subsections)** — the five roles, their inputs/outputs, their MCP tool grants, their default model routing, and the prompt template from §4.2. This phase produces the five runnable-in-isolation agent units.
- **§6.2 `llm.models`** — the Phase-1 `AegisConfig.llm.models` dict is now *consumed* to decide which model string goes into each agent's `ClaudeAgentOptions.model`. Phase 1 only defined the schema; Phase 3 wires it through.
- **§10.1–§10.4 tool allow-lists** — the per-role allowed_tools list (see §4 table) is realized as `allowed_tools=["mcp__<server>__<tool>", ...]` on `ClaudeAgentOptions`. Read-only roles get read-only tools; write roles also get the write tools for their server set.
- **§11.4 Worktree lifecycle (consumer side)** — the agent's `worktree` argument becomes the `--scope` for every MCP server it spawns. The agent does not *create* the worktree (Phase 4 graph setup does that by calling `aegis.core.worktree.create_worktree`); it only *operates inside* one.
- **Handoff instruction from Phase-2 Appendix B** — `tools.py` is the module that "spawns each of the four MCP servers built in Phase 2 (with the correct `--scope`) and registers their tools as Claude Agent SDK tools". We fulfill that exactly, as stdio entries in `ClaudeAgentOptions.mcp_servers`.

### What Phase 3 explicitly does NOT cover

- **No LangGraph wiring.** The graph nodes (PM node, Dev node, ...) that *invoke* `AegisAgent` are Phase 4. Phase 3 stops at "a single role, a single worktree, a single `await agent.run(task_prompt)` returns messages".
- **No `done` / `block` control tools.** §4.2 prompts reference them but they are graph-level signalling tools; Phase 4 will bind them via `claude_agent_sdk.create_sdk_mcp_server`. For Phase 3 the prompts mention the tools — the absence just means the SDK reports the tool call as unresolved, which is fine for the unit-level contract we ship here.
- **No live LLM smoke test.** Unit tests use a `FakeClient`. There is a documented manual smoke test in Task 8 that spins up a real Claude session against `pm.md` + `aegis-fs-mcp`, but it is **opt-in** via an environment variable and is NOT part of CI. CI never calls a real LLM.
- **No per-role shell allow-list config field.** §4 states QA may have a tighter `ALLOW_CMDS` than Dev. We support that by having `build_options` accept an `shell_allow_cmds: str | None` override parameter, but we do NOT extend `AegisConfig` with a per-role field in this phase (would modify Phase-1 code for a Phase-4-only consumer). The graph-node author in Phase 4 decides how to pick the allow-list per role.
- **No budget enforcement hooks.** `ClaudeAgentOptions.hooks` exists, and Phase-1 shipped `BudgetTracker`. Wiring them together is a Phase-4 node responsibility (`hooks={"PreToolUse": [budget_hook]}`), not Phase 3's.
- **No changes to Phase-1 or Phase-2 modules.** Only `src/aegis/agents/__init__.py`'s docstring is edited; every other Phase-1/2 file is frozen.

At the end of Phase 3:
- `pip install -e .[dev]` installs `claude-agent-sdk>=0.1.61`.
- Importing `from aegis.agents import AegisAgent, ROLES, load_prompt, build_options` all succeed.
- Unit test suite adds ~35 new tests under `tests/unit/test_agents_*.py`, all green, zero real LLM calls.
- All Phase-1 and Phase-2 tests remain green.
- The five prompt markdown files exist and are loadable.

---

## File map

### Files created by this plan

```
src/aegis/agents/registry.py
src/aegis/agents/tools.py
src/aegis/agents/base.py
src/aegis/agents/prompts/pm.md
src/aegis/agents/prompts/dev.md
src/aegis/agents/prompts/qa.md
src/aegis/agents/prompts/reviewer.md
src/aegis/agents/prompts/docs.md
tests/unit/test_agents_registry.py
tests/unit/test_agents_tools.py
tests/unit/test_agents_prompts.py
tests/unit/test_agents_base.py
tests/unit/test_agents_per_role.py
```

### Files modified by this plan

- `pyproject.toml` — add `claude-agent-sdk>=0.1.61` to `dependencies`.
- `src/aegis/agents/__init__.py` — replace the placeholder docstring with a real one and export `AegisAgent`, `ROLES`, `RoleName`, `load_prompt`, `build_options`, `build_mcp_servers`.

### Files NOT touched

Everything under `src/aegis/core/`, `src/aegis/cli/`, `src/aegis/mcp_servers/`, `src/aegis/graph/`, `src/aegis/obs/`, `src/aegis/web/`, and every existing test file in `tests/unit/`. Phase-1 and Phase-2 code is frozen for Phase 3.

---

## Contracts shared by the module

Every downstream reader (Phase 4 graph, Phase 5 observability, direct human inspection) depends on these contracts. They are stable as of Phase 3.

### 1. The five role names

`RoleName = Literal["pm", "dev", "qa", "reviewer", "docs"]`. Exactly five, exactly in that order wherever order matters (it rarely does). Any string outside this set is a programming error and raises `KeyError` / `ValueError` immediately — no silent fallback.

### 2. Role registry — one row per role

For each role the registry declares, as pure data:

| Field | Type | Meaning |
|---|---|---|
| `role` | `RoleName` | One of the five. |
| `prompt_filename` | `str` | e.g. `"pm.md"`. Resolved under `src/aegis/agents/prompts/`. |
| `model_key` | `RoleName` | The key into `AegisConfig.llm.models` that supplies the model string. Always equals `role`; the indirection exists only so users can remap at the config layer. |
| `mcp_server_names` | `tuple[str, ...]` | The subset of `{"git", "fs", "shell", "project-index"}` this role may use. Order is stable across test runs. |
| `allowed_tools` | `tuple[str, ...]` | Fully-qualified MCP tool names (e.g. `"mcp__git__git_diff"`) that this role is *pre-approved* to call. |
| `disallowed_tools` | `tuple[str, ...]` | Fully-qualified MCP tool names that this role is *blocked from* calling. For read-only roles this includes every write tool in the servers they can reach. |

The full table is materialized in Task 2's code exactly per spec §4.

### 3. MCP stdio server config shape

Each entry in `ClaudeAgentOptions.mcp_servers` produced by `build_mcp_servers` is a dict of this exact shape (matches `claude_agent_sdk` docs verbatim):

```python
{
    "type": "stdio",
    "command": "aegis-fs-mcp",                 # Phase-2 console script
    "args": ["--scope", "/abs/path/to/worktree"],
    "env": {},                                 # empty unless shell server
}
```

The shell server additionally receives `env={"ALLOW_CMDS": allow_cmds}` when the role has shell access and a non-None `shell_allow_cmds` argument is supplied.

### 4. Prompt loading

`load_prompt(role, override_path=None) -> str` returns the raw UTF-8 markdown file contents as a string. The override path, if supplied, must exist and be a regular file; otherwise `FileNotFoundError` is raised. No templating, no frontmatter parsing — §4.2's prompts are deliberately static markdown so a maintainer editing `pm.md` does not need to understand an interpolation DSL.

### 5. Agent instantiation

```python
AegisAgent(
    role: RoleName,
    worktree: Path,
    config: AegisConfig,
    prompt_override: Path | None = None,
    shell_allow_cmds: str | None = None,
    client_factory: Callable[[ClaudeAgentOptions], ClaudeSDKClient] = ClaudeSDKClient,
)
```

`worktree` MUST be absolute and exist. `config` supplies the model for this role (via `config.llm.models[role]`). `client_factory` is the test seam — production code never passes it; tests pass a fake.

### 6. Single public async entrypoint

```python
async def run(self, task_prompt: str) -> list[Any]
```

Drives the SDK client once with `task_prompt`, collects every message from `receive_response()` into a list, returns it. This is intentionally the thinnest wrapper possible: structured post-processing (turning messages into `TeamState` fields) is Phase-4 graph-node responsibility, not Phase-3's.

### 7. No async fixtures, no async test machinery

Tests call `asyncio.run(agent.run(...))` directly. Fake clients are plain classes with `__aenter__` / `__aexit__` / `query` / `receive_response` defined as `async def`. No `pytest-asyncio`. Keeps the test stack identical to Phase 1 / Phase 2.

---

## Task 1: Add `claude-agent-sdk` dependency and update the package docstring

**Files:**
- Modify: `pyproject.toml`
- Modify: `src/aegis/agents/__init__.py`

- [ ] **Step 1: Inspect the current `pyproject.toml` `dependencies` block**

Run: `grep -n -A 8 "^dependencies" pyproject.toml`
Expected output:

```
13:dependencies = [
14:    "pydantic>=2.7",
15:    "python-frontmatter>=1.1",
16:    "pyyaml>=6.0",
17:    "typer>=0.12",
18:    "mcp>=1.0",
19:]
```

- [ ] **Step 2: Add `claude-agent-sdk` to `dependencies` in `pyproject.toml`**

Replace the block with:

```toml
dependencies = [
    "pydantic>=2.7",
    "python-frontmatter>=1.1",
    "pyyaml>=6.0",
    "typer>=0.12",
    "mcp>=1.0",
    "claude-agent-sdk>=0.1.61",
]
```

Why this package and not `anthropic[agent]`: the spec §8.1 table was authored before the SDK GA and used a placeholder name. The actual Python package is `claude-agent-sdk` (imported as `claude_agent_sdk`), released by Anthropic as a separate distribution. Version `0.1.61` (released 2026-04-16) is the one we design against; any newer patch release should be compatible with the surface we use (`ClaudeAgentOptions`, `ClaudeSDKClient`).

- [ ] **Step 3: Update `src/aegis/agents/__init__.py`**

Current content is a single-line docstring placeholder:

```python
"""Claude Agent SDK wrapper + role prompts. Implemented in Phase 3."""
```

Replace with:

```python
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

from aegis.agents.base import AegisAgent, build_options, load_prompt
from aegis.agents.registry import ROLES, RoleName, RoleSpec
from aegis.agents.tools import build_mcp_servers

__all__ = [
    "AegisAgent",
    "ROLES",
    "RoleName",
    "RoleSpec",
    "build_mcp_servers",
    "build_options",
    "load_prompt",
]
```

Note: these imports will be unresolved until Tasks 2, 4, and 5 create the modules. That is acceptable at this checkpoint because Task 1's commit is specifically a "dependency + docstring" commit; the re-install step below does not execute Python that imports `aegis.agents`, and pytest is not run at this task because the new tests do not exist yet. Tests are run (and expected to pass) after Task 2.

- [ ] **Step 4: Reinstall with the new dep**

Run: `pip install -e .[dev]`
Expected output: ends with `Successfully installed claude-agent-sdk-0.1.61 ...` (transitive deps may also install: `anyio`, `httpx`, etc., many already present from Phase 2).

- [ ] **Step 5: Verify the SDK imports cleanly in a throwaway shell**

Run: `python -c "import claude_agent_sdk; print(claude_agent_sdk.__name__)"`
Expected output: `claude_agent_sdk`

If this fails with `ModuleNotFoundError`, the install step silently skipped — rerun Step 4 and re-read the pip output.

- [ ] **Step 6: Commit**

```bash
git add pyproject.toml src/aegis/agents/__init__.py
git commit -m "feat(agents): add claude-agent-sdk dependency and package surface"
```

---

## Task 2: Role registry

**Files:**
- Create: `src/aegis/agents/registry.py`
- Create: `tests/unit/test_agents_registry.py`

This is pure data: the single source of truth for "which MCP servers is role X allowed to see, and which tools within those servers is role X allowed / blocked from calling". Every other Phase-3 module reads from this registry.

- [ ] **Step 1: Write the failing test**

Create `tests/unit/test_agents_registry.py`:

```python
from __future__ import annotations

import pytest

from aegis.agents.registry import ROLES, RoleSpec, get_role_spec


def test_exactly_five_roles() -> None:
    assert set(ROLES.keys()) == {"pm", "dev", "qa", "reviewer", "docs"}


def test_each_role_has_a_unique_prompt_filename() -> None:
    filenames = [spec.prompt_filename for spec in ROLES.values()]
    assert len(filenames) == len(set(filenames))
    for filename in filenames:
        assert filename.endswith(".md")


def test_each_role_model_key_equals_role_name() -> None:
    for name, spec in ROLES.items():
        assert spec.model_key == name


def test_pm_mcp_access_matches_spec() -> None:
    spec = ROLES["pm"]
    assert spec.mcp_server_names == ("project-index", "fs")


def test_dev_mcp_access_matches_spec() -> None:
    spec = ROLES["dev"]
    assert spec.mcp_server_names == ("git", "fs", "shell")


def test_qa_mcp_access_matches_dev_plus_shell() -> None:
    spec = ROLES["qa"]
    assert spec.mcp_server_names == ("git", "fs", "shell")


def test_reviewer_mcp_access_is_read_only_servers() -> None:
    spec = ROLES["reviewer"]
    assert spec.mcp_server_names == ("git", "project-index")


def test_docs_mcp_access_matches_spec() -> None:
    spec = ROLES["docs"]
    assert spec.mcp_server_names == ("fs", "git")


def test_reviewer_disallows_every_git_write_tool() -> None:
    spec = ROLES["reviewer"]
    for tool in (
        "mcp__git__git_add",
        "mcp__git__git_commit",
        "mcp__git__git_branch_create",
        "mcp__git__git_checkout",
        "mcp__git__git_worktree_add",
        "mcp__git__git_worktree_remove",
        "mcp__git__git_merge",
    ):
        assert tool in spec.disallowed_tools


def test_reviewer_allows_every_git_read_tool() -> None:
    spec = ROLES["reviewer"]
    for tool in ("mcp__git__git_status", "mcp__git__git_diff", "mcp__git__git_log"):
        assert tool in spec.allowed_tools


def test_pm_disallows_fs_writes() -> None:
    spec = ROLES["pm"]
    for tool in ("mcp__fs__fs_write", "mcp__fs__fs_mkdir", "mcp__fs__fs_delete", "mcp__fs__fs_move"):
        assert tool in spec.disallowed_tools


def test_pm_allows_fs_reads() -> None:
    spec = ROLES["pm"]
    for tool in ("mcp__fs__fs_read", "mcp__fs__fs_list", "mcp__fs__fs_glob"):
        assert tool in spec.allowed_tools


def test_dev_allows_shell_exec() -> None:
    spec = ROLES["dev"]
    assert "mcp__shell__shell_exec" in spec.allowed_tools


def test_allowed_and_disallowed_sets_are_disjoint() -> None:
    for name, spec in ROLES.items():
        overlap = set(spec.allowed_tools) & set(spec.disallowed_tools)
        assert not overlap, f"role {name} has {overlap} in both allow and deny lists"


def test_every_allowed_tool_references_an_allowed_server() -> None:
    for name, spec in ROLES.items():
        for tool in spec.allowed_tools:
            # tool name shape: mcp__<server>__<tool_name>
            _, server, _ = tool.split("__", 2)
            assert server in spec.mcp_server_names, (
                f"role {name} allows tool on server {server!r} but that server is not in mcp_server_names"
            )


def test_role_spec_is_frozen() -> None:
    spec = ROLES["pm"]
    with pytest.raises(Exception):  # dataclass frozen → FrozenInstanceError, subclass of AttributeError
        spec.prompt_filename = "other.md"  # type: ignore[misc]


def test_get_role_spec_returns_by_name() -> None:
    assert get_role_spec("pm") is ROLES["pm"]


def test_get_role_spec_rejects_unknown() -> None:
    with pytest.raises(KeyError):
        get_role_spec("architect")  # type: ignore[arg-type]
```

- [ ] **Step 2: Run tests — they must fail**

Run: `pytest tests/unit/test_agents_registry.py -v`
Expected: every test fails with `ModuleNotFoundError: No module named 'aegis.agents.registry'`.

- [ ] **Step 3: Create `src/aegis/agents/registry.py`**

```python
"""Per-role static configuration for Aegis agents.

Maps each role to its prompt file, its model-key (which resolves through
``AegisConfig.llm.models``), the MCP servers it may reach, and the
per-tool allow/deny lists that pre-approve or block individual MCP
tools on those servers. See spec §4 for the source of truth table.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


RoleName = Literal["pm", "dev", "qa", "reviewer", "docs"]


@dataclass(frozen=True, slots=True)
class RoleSpec:
    """Immutable, pure-data description of one role."""

    role: RoleName
    prompt_filename: str
    model_key: RoleName
    mcp_server_names: tuple[str, ...]
    allowed_tools: tuple[str, ...]
    disallowed_tools: tuple[str, ...]


# Fully-qualified MCP tool names follow the Claude Code convention
# ``mcp__<server_name>__<tool_name>``. Server names here match the
# ``mcp.servers[i].name`` values in AegisConfig (see core/config.py).

_FS_READ_TOOLS = (
    "mcp__fs__fs_read",
    "mcp__fs__fs_list",
    "mcp__fs__fs_glob",
)
_FS_WRITE_TOOLS = (
    "mcp__fs__fs_write",
    "mcp__fs__fs_mkdir",
    "mcp__fs__fs_delete",
    "mcp__fs__fs_move",
)
_GIT_READ_TOOLS = (
    "mcp__git__git_status",
    "mcp__git__git_diff",
    "mcp__git__git_log",
)
_GIT_WRITE_TOOLS = (
    "mcp__git__git_add",
    "mcp__git__git_commit",
    "mcp__git__git_branch_create",
    "mcp__git__git_checkout",
    "mcp__git__git_worktree_add",
    "mcp__git__git_worktree_remove",
    "mcp__git__git_merge",
)
_SHELL_TOOLS = ("mcp__shell__shell_exec",)
_INDEX_TOOLS = (
    "mcp__project-index__search",
    "mcp__project-index__file_tree",
    "mcp__project-index__outline",
)


ROLES: dict[RoleName, RoleSpec] = {
    "pm": RoleSpec(
        role="pm",
        prompt_filename="pm.md",
        model_key="pm",
        mcp_server_names=("project-index", "fs"),
        allowed_tools=_INDEX_TOOLS + _FS_READ_TOOLS,
        disallowed_tools=_FS_WRITE_TOOLS,
    ),
    "dev": RoleSpec(
        role="dev",
        prompt_filename="dev.md",
        model_key="dev",
        mcp_server_names=("git", "fs", "shell"),
        allowed_tools=_GIT_READ_TOOLS + _GIT_WRITE_TOOLS + _FS_READ_TOOLS + _FS_WRITE_TOOLS + _SHELL_TOOLS,
        disallowed_tools=(),
    ),
    "qa": RoleSpec(
        role="qa",
        prompt_filename="qa.md",
        model_key="qa",
        mcp_server_names=("git", "fs", "shell"),
        # QA may run tests (shell), read code (git/fs read), and write
        # test files (fs write). It must NOT commit or push — Dev is the
        # only role that merges its own work into the worktree branch.
        allowed_tools=_GIT_READ_TOOLS + _FS_READ_TOOLS + _FS_WRITE_TOOLS + _SHELL_TOOLS,
        disallowed_tools=_GIT_WRITE_TOOLS,
    ),
    "reviewer": RoleSpec(
        role="reviewer",
        prompt_filename="reviewer.md",
        model_key="reviewer",
        mcp_server_names=("git", "project-index"),
        allowed_tools=_GIT_READ_TOOLS + _INDEX_TOOLS,
        disallowed_tools=_GIT_WRITE_TOOLS,
    ),
    "docs": RoleSpec(
        role="docs",
        prompt_filename="docs.md",
        model_key="docs",
        mcp_server_names=("fs", "git"),
        # Docs writes README/CHANGELOG (fs_write) and commits them (git_add, git_commit).
        # It must NOT create branches, checkout, merge, or touch worktrees.
        allowed_tools=_FS_READ_TOOLS
        + _FS_WRITE_TOOLS
        + _GIT_READ_TOOLS
        + ("mcp__git__git_add", "mcp__git__git_commit"),
        disallowed_tools=(
            "mcp__git__git_branch_create",
            "mcp__git__git_checkout",
            "mcp__git__git_worktree_add",
            "mcp__git__git_worktree_remove",
            "mcp__git__git_merge",
        ),
    ),
}


def get_role_spec(role: RoleName) -> RoleSpec:
    """Return the spec for ``role`` or raise ``KeyError`` if unknown."""
    return ROLES[role]
```

- [ ] **Step 4: Run tests — they must pass**

Run: `pytest tests/unit/test_agents_registry.py -v`
Expected: all 17 tests PASSED.

- [ ] **Step 5: Run the full suite to confirm nothing regressed**

Run: `pytest tests/unit -q`
Expected: prior Phase-1/2 tests all pass, plus 17 new registry tests.

- [ ] **Step 6: Commit**

```bash
git add src/aegis/agents/registry.py tests/unit/test_agents_registry.py
git commit -m "feat(agents): declare per-role MCP server and tool allow-lists"
```

---

## Task 3: The five prompt files

**Files:**
- Create: `src/aegis/agents/prompts/pm.md`
- Create: `src/aegis/agents/prompts/dev.md`
- Create: `src/aegis/agents/prompts/qa.md`
- Create: `src/aegis/agents/prompts/reviewer.md`
- Create: `src/aegis/agents/prompts/docs.md`
- Create: `tests/unit/test_agents_prompts.py`

Each prompt follows the §4.2 template. Prompts are static markdown — no interpolation at load time (§4.2 paragraph 2). The **test** here is that the five files exist, are non-empty, and contain every section header from the template. Prompt *quality* is validated by dogfooding in later phases, not by unit tests.

- [ ] **Step 1: Write the failing test**

Create `tests/unit/test_agents_prompts.py`:

```python
from __future__ import annotations

import importlib.resources
from pathlib import Path

import pytest

from aegis.agents.registry import ROLES


REQUIRED_SECTIONS = (
    "## Identity",
    "## Inputs",
    "## Outputs",
    "## Tools available",
    "## Hard rules",
    "## Style",
)


def _prompt_path(filename: str) -> Path:
    # Prompts live under src/aegis/agents/prompts/ in the installed
    # package. Use importlib.resources to locate them the way
    # load_prompt() will in Task 5.
    package = importlib.resources.files("aegis.agents") / "prompts" / filename
    return Path(str(package))


@pytest.mark.parametrize("role_name", sorted(ROLES.keys()))
def test_prompt_file_exists_for_each_role(role_name: str) -> None:
    spec = ROLES[role_name]
    path = _prompt_path(spec.prompt_filename)
    assert path.is_file(), f"missing prompt file {path}"


@pytest.mark.parametrize("role_name", sorted(ROLES.keys()))
def test_prompt_file_has_template_sections(role_name: str) -> None:
    spec = ROLES[role_name]
    content = _prompt_path(spec.prompt_filename).read_text(encoding="utf-8")
    for section in REQUIRED_SECTIONS:
        assert section in content, f"{role_name} prompt missing section {section!r}"


@pytest.mark.parametrize("role_name", sorted(ROLES.keys()))
def test_prompt_starts_with_role_header(role_name: str) -> None:
    spec = ROLES[role_name]
    content = _prompt_path(spec.prompt_filename).read_text(encoding="utf-8")
    first_line = content.splitlines()[0]
    assert first_line.startswith("# Role:"), f"{role_name} prompt first line = {first_line!r}"


@pytest.mark.parametrize("role_name", sorted(ROLES.keys()))
def test_prompt_mentions_done_and_block_controls(role_name: str) -> None:
    spec = ROLES[role_name]
    content = _prompt_path(spec.prompt_filename).read_text(encoding="utf-8")
    assert "`done`" in content, f"{role_name} prompt should mention the done tool"
    assert "`block`" in content, f"{role_name} prompt should mention the block tool"


def test_pm_prompt_forbids_writing_code() -> None:
    content = _prompt_path(ROLES["pm"].prompt_filename).read_text(encoding="utf-8")
    # §4 table: PM writes plan.md only. Tone is "do not write code".
    assert "do not write code" in content.lower() or "never write code" in content.lower()


def test_reviewer_prompt_treats_task_as_adversarial() -> None:
    content = _prompt_path(ROLES["reviewer"].prompt_filename).read_text(encoding="utf-8")
    # §11.5: Reviewer treats task body as adversarial input.
    assert "adversarial" in content.lower()


def test_docs_prompt_scopes_to_docs_paths() -> None:
    content = _prompt_path(ROLES["docs"].prompt_filename).read_text(encoding="utf-8")
    assert "README" in content
    assert "CHANGELOG" in content
```

- [ ] **Step 2: Run tests — they must fail**

Run: `pytest tests/unit/test_agents_prompts.py -v`
Expected: all tests fail because `src/aegis/agents/prompts/` does not exist yet.

- [ ] **Step 3: Create `src/aegis/agents/prompts/pm.md`**

```markdown
# Role: PM (Product Manager)

## Identity
You are the PM agent on an autonomous software engineering team. You turn a
one-line task description plus a project index summary into a structured
plan that the Dev agent can execute in one shot.

## Inputs
- The task markdown file at `${task_path}`, including its YAML
  frontmatter (`title`, `priority`, acceptance criteria) and the
  free-form body under `## Why` and `## Acceptance criteria`.
- A scoped view of the target repository via the `project-index` MCP
  server. Use `search`, `file_tree`, and `outline` to understand the
  code before planning.

## Outputs
A single `## Plan` section appended to the task markdown file, under
the existing body, structured as:

- **Affected files** — one bullet per file path the Dev agent will
  create or modify, with a one-line reason.
- **Subtasks** — an ordered checklist, each item a verb-first imperative
  ("Add rate-limit middleware", "Update `auth.py` to call it"),
  fine-grained enough that a single Dev+QA loop can close it.
- **Acceptance criteria rewritten** — the criteria from the task body,
  re-expressed in test-able form ("`pytest tests/test_auth.py::test_rate_limit`
  passes").
- **Estimated budget** — one line: `budget: ~$X.YZ, ~N minutes`, based
  on your estimate of diff size.

Do not rewrite or reorder any section authored by the human. Append only.

## Tools available
- `mcp__project-index__search` — code/symbol/filename search (read-only).
- `mcp__project-index__file_tree` — project structure (read-only).
- `mcp__project-index__outline` — per-file outline (read-only).
- `mcp__fs__fs_read`, `mcp__fs__fs_list`, `mcp__fs__fs_glob` — read the
  repository contents (read-only).

## Hard rules
- Do not write code. Your only artifact is the plan text.
- Do not call `fs_write`, `fs_mkdir`, `fs_delete`, or `fs_move`. These
  are not granted to you.
- Never touch files outside the worktree passed to this agent.
- Cap your plan at 8 subtasks. If the task cannot fit in 8, break it
  into smaller tasks and call `block` with that recommendation — do
  not invent a 12-step plan and proceed.

## Style
- Concise. Plans are for the Dev agent to execute, not for humans to
  read for enjoyment.
- Cite file paths with backticks.
- When you are done, call the `done` tool with the plan content as the
  structured summary argument.
- If you are stuck (unclear criteria, missing files, conflicting
  constraints), call the `block` tool with a one-sentence blocker
  message rather than guessing.
```

- [ ] **Step 4: Create `src/aegis/agents/prompts/dev.md`**

```markdown
# Role: Dev (Developer)

## Identity
You are the Dev agent on an autonomous software engineering team. You
execute the PM's plan by making code changes in an isolated git worktree,
committing each subtask as you go.

## Inputs
- The task markdown file with its `## Plan` section written by the PM.
- The worktree at `${worktree_path}` — an isolated git branch where your
  commits live. `git status` should be clean when you start.
- Full read+write access to the files in the worktree via `fs` and
  `git` MCP tools.

## Outputs
- One git commit per PM subtask, authored in the worktree.
- Commit messages follow `type(scope): subject` conventional-commit
  format (e.g. `feat(auth): add rate limit middleware`).
- No files outside the worktree are modified.

## Tools available
- `mcp__git__git_status`, `mcp__git__git_diff`, `mcp__git__git_log` —
  inspect the worktree.
- `mcp__git__git_add`, `mcp__git__git_commit` — commit your work.
- `mcp__git__git_branch_create`, `mcp__git__git_checkout` — rarely
  needed; the worktree already has a branch.
- `mcp__fs__fs_read`, `mcp__fs__fs_list`, `mcp__fs__fs_glob`,
  `mcp__fs__fs_write`, `mcp__fs__fs_mkdir`, `mcp__fs__fs_delete`,
  `mcp__fs__fs_move` — modify source files.
- `mcp__shell__shell_exec` — run commands from the allow-list (typically
  `pytest`, `ruff`, `mypy`, `python`, `pip`, `npm`). Commands outside
  the allow-list are refused by the MCP server.

## Hard rules
- Never touch files outside `${worktree_path}`. The MCP servers will
  refuse, but you should also not try.
- Do not `git push`, do not `git merge`, do not change branches.
- Do not skip pre-commit hooks (`--no-verify`) or bypass signing.
- If a test fails after your commit, fix it yourself — do not hand off
  a red worktree to QA.
- If the PM plan is ambiguous or wrong, call `block` with the specific
  issue — do not guess.

## Style
- Small commits over mega-commits. One subtask = one commit.
- Run `ruff` and the test suite before committing, via `shell_exec`.
- When you are done with every subtask, call the `done` tool with a
  structured summary of what you committed.
- If you are stuck, call the `block` tool with a clear blocker message.
```

- [ ] **Step 5: Create `src/aegis/agents/prompts/qa.md`**

```markdown
# Role: QA (Quality Assurance)

## Identity
You are the QA agent on an autonomous software engineering team. You
verify that the Dev agent's work actually satisfies the acceptance
criteria. You write additional tests when coverage is missing and run
the full test suite against the worktree.

## Inputs
- The worktree at `${worktree_path}` — Dev's commits are already here.
- The task markdown file with its `## Plan` and acceptance criteria.
- The existing test suite under `tests/` in the worktree.

## Outputs
- New or updated test files (when Dev's work lacks coverage for an
  acceptance criterion). Commit them with messages like
  `test(scope): add coverage for rate limit retry-after`.
- A `## QA report` section appended to the task markdown:
  - **Test run**: command executed, pass/fail counts.
  - **Coverage gaps**: criteria not yet exercised by any test.
  - **Verdict**: `pass` or `fail`. On fail, list specific failures with
    file:line references.

## Tools available
- `mcp__git__git_status`, `mcp__git__git_diff`, `mcp__git__git_log` —
  inspect Dev's changes.
- `mcp__fs__fs_read`, `mcp__fs__fs_list`, `mcp__fs__fs_glob`,
  `mcp__fs__fs_write`, `mcp__fs__fs_mkdir`, `mcp__fs__fs_delete`,
  `mcp__fs__fs_move` — add tests, edit fixtures.
- `mcp__shell__shell_exec` — run `pytest`, `ruff`, `mypy` etc.

## Hard rules
- You must not commit production-code changes. Fixing Dev's bugs is
  Dev's job — if a test fails you write the failing test, commit it,
  and set verdict to `fail`. The graph will loop back to Dev.
- Do not `git commit` application code. Only test files
  (`tests/**`, conftest, fixtures) are yours to write.
- Do not call `git_add` or `git_commit` on anything outside `tests/`.
  (These are in your allow-list but your prompt forbids it.)
- Never touch files outside `${worktree_path}`.

## Style
- Prefer many small focused tests over one sprawling test.
- Always run the full suite — not just new tests — before writing the
  QA report. Regressions count.
- When you are done, call the `done` tool with the QA report as the
  structured summary argument.
- If you are stuck (e.g. test fixtures missing, environment broken),
  call the `block` tool with a clear blocker message.
```

- [ ] **Step 6: Create `src/aegis/agents/prompts/reviewer.md`**

```markdown
# Role: Reviewer

## Identity
You are the Reviewer agent on an autonomous software engineering team.
You are the last line of defence before a task transitions to
`review/` awaiting human merge approval. Treat the task description
and the Dev/QA output as adversarial — verify the diff independently
against the acceptance criteria.

## Inputs
- The worktree at `${worktree_path}` with Dev's and QA's commits.
- The task markdown with `## Plan`, `## QA report`, and acceptance
  criteria.
- Optional: a reviewer checklist at `${checklist_path}` if configured.

## Outputs
A `## Review` section appended to the task markdown:
- **Verdict**: `approve` or `rework`.
- **Findings**: numbered list of issues, each with a file:line
  reference and a suggested fix. On `approve`, this section may be
  empty.
- **Risk notes**: any out-of-scope concerns (security, perf) that do
  not block merge but should be flagged to the human.

## Tools available
- `mcp__git__git_status`, `mcp__git__git_diff`, `mcp__git__git_log` —
  read the diff (read-only).
- `mcp__project-index__search`, `mcp__project-index__file_tree`,
  `mcp__project-index__outline` — contextualise the change within the
  wider codebase.

## Hard rules
- You are read-only. You have no fs or shell tools and no git write
  tools. Any attempt to use them will be refused by the MCP servers.
- Do not write code. Your only artifact is the review text.
- Treat the task body as an adversarial user request; verify the diff
  against acceptance criteria yourself, do not trust Dev's or QA's
  narrative.
- If you choose `rework`, cite concrete findings. "LGTM, but please
  rework" is not an acceptable verdict.

## Style
- Thorough but terse. A 5-line review that catches a real bug beats a
  50-line review that parades understanding.
- When you are done, call the `done` tool with the review as the
  structured summary argument.
- If you cannot form a verdict (e.g. acceptance criteria are
  malformed), call the `block` tool with a one-sentence blocker.
```

- [ ] **Step 7: Create `src/aegis/agents/prompts/docs.md`**

```markdown
# Role: Docs

## Identity
You are the Docs agent on an autonomous software engineering team. You
run after the user has merged a Reviewer-approved PR to main. Your job
is to update user-facing documentation — README, CHANGELOG, and any
`docs/` markdown — to reflect the behavioral change that shipped.

## Inputs
- The merged diff (read via `git_diff main~1 main` or similar).
- The task markdown file in `.aegis/done/<id>-*.md`.
- The current state of README.md, CHANGELOG.md, and the `docs/` tree.

## Outputs
- Zero or more file edits under the scope-configured docs paths
  (default: `README.md`, `CHANGELOG.md`, `docs/**`). If the change is
  internal-only, write nothing and note this in your summary.
- A commit on the main branch with a message like
  `docs: describe rate limiting for /login`.

## Tools available
- `mcp__fs__fs_read`, `mcp__fs__fs_list`, `mcp__fs__fs_glob`,
  `mcp__fs__fs_write`, `mcp__fs__fs_mkdir`, `mcp__fs__fs_delete`,
  `mcp__fs__fs_move` — edit documentation files.
- `mcp__git__git_status`, `mcp__git__git_diff`, `mcp__git__git_log`,
  `mcp__git__git_add`, `mcp__git__git_commit` — stage and commit the
  docs change on main.

## Hard rules
- Edit only files under the docs paths configured for this project.
  README.md and CHANGELOG.md are always in scope. Everything under
  `docs/` is in scope. Source files are out of scope for you — even
  if a docstring seems wrong.
- Do not create branches, check out refs, or touch worktrees. You run
  directly on main and commit there.
- If the change is purely internal (refactor, performance) and
  user-visible behavior is unchanged, produce no edits — write "no
  user-visible changes" in your `done` summary.

## Style
- Active voice. Short sentences. The reader is a future user scanning
  a CHANGELOG, not a developer reading a PR.
- CHANGELOG entries go under an `## Unreleased` header (create it if
  missing).
- When you are done, call the `done` tool with a one-paragraph
  summary of what you changed.
- If you are stuck, call the `block` tool with a clear blocker.
```

- [ ] **Step 8: Run prompt tests — they must pass**

Run: `pytest tests/unit/test_agents_prompts.py -v`
Expected: all prompt tests PASSED.

If any test fails because a template section is missing, re-read the failing prompt and add the missing `##` header — prompts are literally contracts with the test suite in this phase.

- [ ] **Step 9: Commit**

```bash
git add src/aegis/agents/prompts tests/unit/test_agents_prompts.py
git commit -m "feat(agents): author role prompt files for PM/Dev/QA/Reviewer/Docs"
```

---

## Task 4: MCP server binding (`tools.py`)

**Files:**
- Create: `src/aegis/agents/tools.py`
- Create: `tests/unit/test_agents_tools.py`

This module is the bridge from "role X plus worktree Y" to the exact dict shape `ClaudeAgentOptions.mcp_servers` expects. Phase-2 Appendix B called out this responsibility by name.

- [ ] **Step 1: Write the failing test**

Create `tests/unit/test_agents_tools.py`:

```python
from __future__ import annotations

from pathlib import Path

import pytest

from aegis.agents.tools import SERVER_COMMANDS, build_mcp_servers


def test_server_commands_cover_all_four_phase2_servers() -> None:
    assert set(SERVER_COMMANDS.keys()) == {"git", "fs", "shell", "project-index"}
    assert SERVER_COMMANDS["git"] == "aegis-git-mcp"
    assert SERVER_COMMANDS["fs"] == "aegis-fs-mcp"
    assert SERVER_COMMANDS["shell"] == "aegis-shell-mcp"
    assert SERVER_COMMANDS["project-index"] == "aegis-project-index-mcp"


def test_build_for_pm_returns_project_index_and_fs(tmp_path: Path) -> None:
    servers = build_mcp_servers("pm", tmp_path)
    assert set(servers.keys()) == {"project-index", "fs"}


def test_build_for_dev_returns_git_fs_shell(tmp_path: Path) -> None:
    servers = build_mcp_servers("dev", tmp_path)
    assert set(servers.keys()) == {"git", "fs", "shell"}


def test_build_for_reviewer_returns_git_and_project_index(tmp_path: Path) -> None:
    servers = build_mcp_servers("reviewer", tmp_path)
    assert set(servers.keys()) == {"git", "project-index"}


def test_each_server_entry_has_stdio_shape(tmp_path: Path) -> None:
    servers = build_mcp_servers("dev", tmp_path)
    for name, entry in servers.items():
        assert entry["type"] == "stdio", f"{name} missing type=stdio"
        assert isinstance(entry["command"], str)
        assert isinstance(entry["args"], list)
        assert all(isinstance(a, str) for a in entry["args"])
        assert isinstance(entry["env"], dict)


def test_scope_arg_is_the_worktree(tmp_path: Path) -> None:
    servers = build_mcp_servers("dev", tmp_path)
    for entry in servers.values():
        assert entry["args"] == ["--scope", str(tmp_path)]


def test_scope_is_resolved_to_absolute(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    # A relative path is a programming error but the helper must still
    # resolve it to absolute rather than silently passing garbage.
    servers = build_mcp_servers("dev", Path("."))
    for entry in servers.values():
        arg = Path(entry["args"][1])
        assert arg.is_absolute()


def test_shell_server_gets_allow_cmds_env_when_supplied(tmp_path: Path) -> None:
    servers = build_mcp_servers("dev", tmp_path, shell_allow_cmds="pytest,ruff,mypy")
    assert servers["shell"]["env"] == {"ALLOW_CMDS": "pytest,ruff,mypy"}


def test_non_shell_servers_have_empty_env_even_when_allow_cmds_supplied(tmp_path: Path) -> None:
    servers = build_mcp_servers("dev", tmp_path, shell_allow_cmds="pytest")
    assert servers["git"]["env"] == {}
    assert servers["fs"]["env"] == {}


def test_role_without_shell_ignores_allow_cmds(tmp_path: Path) -> None:
    # PM has no shell server; passing shell_allow_cmds must not cause an error.
    servers = build_mcp_servers("pm", tmp_path, shell_allow_cmds="pytest")
    assert "shell" not in servers


def test_shell_server_without_allow_cmds_has_empty_env(tmp_path: Path) -> None:
    servers = build_mcp_servers("dev", tmp_path, shell_allow_cmds=None)
    assert servers["shell"]["env"] == {}


def test_unknown_role_raises(tmp_path: Path) -> None:
    with pytest.raises(KeyError):
        build_mcp_servers("architect", tmp_path)  # type: ignore[arg-type]


def test_missing_worktree_raises(tmp_path: Path) -> None:
    missing = tmp_path / "does-not-exist"
    with pytest.raises(FileNotFoundError):
        build_mcp_servers("dev", missing)
```

- [ ] **Step 2: Run tests — they must fail**

Run: `pytest tests/unit/test_agents_tools.py -v`
Expected: all tests fail with `ModuleNotFoundError: No module named 'aegis.agents.tools'`.

- [ ] **Step 3: Create `src/aegis/agents/tools.py`**

```python
"""Build the ``ClaudeAgentOptions.mcp_servers`` dict for a given role.

Phase-2's four MCP servers are distributed as console scripts
(``aegis-git-mcp``, ``aegis-fs-mcp``, ``aegis-shell-mcp``,
``aegis-project-index-mcp``). When the Claude Agent SDK spawns them,
it uses the ``stdio`` transport with ``command`` + ``args`` + ``env``.
This module turns a ``(role, worktree_path)`` pair into exactly that
dict, in the exact shape ``claude_agent_sdk.ClaudeAgentOptions``
accepts.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from aegis.agents.registry import ROLES, RoleName


# Phase-2 console-script names, keyed by the short MCP server name used
# in AegisConfig.mcp.servers and in RoleSpec.mcp_server_names.
SERVER_COMMANDS: dict[str, str] = {
    "git": "aegis-git-mcp",
    "fs": "aegis-fs-mcp",
    "shell": "aegis-shell-mcp",
    "project-index": "aegis-project-index-mcp",
}


def build_mcp_servers(
    role: RoleName,
    worktree: Path,
    shell_allow_cmds: str | None = None,
) -> dict[str, dict[str, Any]]:
    """Return ``{server_name: {type,command,args,env}}`` for ``role``.

    ``worktree`` is passed verbatim as ``--scope`` to every server. It
    must exist on disk — the MCP server would crash immediately
    otherwise, and surfacing that as a clean ``FileNotFoundError`` here
    avoids a confusing stdio handshake error later.

    ``shell_allow_cmds`` populates ``ALLOW_CMDS`` only on the shell
    server. If the role has no shell access the parameter is silently
    ignored (this lets the caller always pass it without branching).
    """
    spec = ROLES[role]

    worktree_resolved = worktree.resolve()
    if not worktree_resolved.exists():
        raise FileNotFoundError(
            f"worktree {worktree_resolved} does not exist; create it before spawning agents"
        )

    servers: dict[str, dict[str, Any]] = {}
    scope_args = ["--scope", str(worktree_resolved)]

    for server_name in spec.mcp_server_names:
        command = SERVER_COMMANDS[server_name]
        env: dict[str, str] = {}
        if server_name == "shell" and shell_allow_cmds is not None:
            env = {"ALLOW_CMDS": shell_allow_cmds}
        servers[server_name] = {
            "type": "stdio",
            "command": command,
            "args": scope_args,
            "env": env,
        }

    return servers
```

- [ ] **Step 4: Run tests — they must pass**

Run: `pytest tests/unit/test_agents_tools.py -v`
Expected: all 13 tests PASSED.

- [ ] **Step 5: Run the full suite**

Run: `pytest tests/unit -q`
Expected: every test green.

- [ ] **Step 6: Commit**

```bash
git add src/aegis/agents/tools.py tests/unit/test_agents_tools.py
git commit -m "feat(agents): bind per-role MCP servers to worktree scope"
```

---

## Task 5: Prompt loading and options construction (`base.py`, part 1)

**Files:**
- Create: `src/aegis/agents/base.py` (partial — `load_prompt` + `build_options`; the `AegisAgent` class is added in Task 6)
- Create: `tests/unit/test_agents_base.py`

This task produces the two pure helpers. Both are synchronous and do not touch the Claude SDK client at all; the class wrapper in Task 6 composes them.

- [ ] **Step 1: Write the failing test**

Create `tests/unit/test_agents_base.py`:

```python
from __future__ import annotations

from pathlib import Path

import pytest

from aegis.agents.base import build_options, load_prompt
from aegis.core.config import AegisConfig, ProjectConfig


def _make_config() -> AegisConfig:
    return AegisConfig(project=ProjectConfig(name="test"))


# ------------------ load_prompt ------------------

def test_load_prompt_pm_returns_markdown() -> None:
    text = load_prompt("pm")
    assert text.startswith("# Role: PM")
    assert "## Identity" in text


def test_load_prompt_every_role_returns_nonempty() -> None:
    for role in ("pm", "dev", "qa", "reviewer", "docs"):
        text = load_prompt(role)  # type: ignore[arg-type]
        assert text.strip(), f"{role} prompt is empty"


def test_load_prompt_unknown_role_raises() -> None:
    with pytest.raises(KeyError):
        load_prompt("architect")  # type: ignore[arg-type]


def test_load_prompt_override_path_used_verbatim(tmp_path: Path) -> None:
    override = tmp_path / "override.md"
    override.write_text("# Role: PM\n\nCustom override body.\n", encoding="utf-8")
    text = load_prompt("pm", override_path=override)
    assert "Custom override body." in text
    # The packaged prompt must NOT appear
    assert "project-index" not in text


def test_load_prompt_override_missing_raises(tmp_path: Path) -> None:
    missing = tmp_path / "nope.md"
    with pytest.raises(FileNotFoundError):
        load_prompt("pm", override_path=missing)


# ------------------ build_options ------------------

def test_build_options_model_comes_from_config(tmp_path: Path) -> None:
    config = _make_config()
    options = build_options("pm", tmp_path, config)
    assert options.model == config.llm.models["pm"]


def test_build_options_system_prompt_is_the_role_prompt(tmp_path: Path) -> None:
    config = _make_config()
    options = build_options("dev", tmp_path, config)
    assert options.system_prompt.startswith("# Role: Dev")


def test_build_options_cwd_is_the_worktree(tmp_path: Path) -> None:
    config = _make_config()
    options = build_options("dev", tmp_path, config)
    assert str(options.cwd) == str(tmp_path.resolve())


def test_build_options_mcp_servers_match_role(tmp_path: Path) -> None:
    config = _make_config()
    options = build_options("dev", tmp_path, config)
    assert set(options.mcp_servers.keys()) == {"git", "fs", "shell"}


def test_build_options_allowed_tools_match_role(tmp_path: Path) -> None:
    config = _make_config()
    options = build_options("reviewer", tmp_path, config)
    for tool in ("mcp__git__git_diff", "mcp__project-index__search"):
        assert tool in options.allowed_tools
    for tool in ("mcp__git__git_commit", "mcp__git__git_merge"):
        assert tool in options.disallowed_tools


def test_build_options_prompt_override_takes_precedence(tmp_path: Path) -> None:
    config = _make_config()
    override = tmp_path / "custom-pm.md"
    override.write_text("# Role: PM\n\nCustom override.\n", encoding="utf-8")
    options = build_options("pm", tmp_path, config, prompt_override=override)
    assert "Custom override." in options.system_prompt


def test_build_options_shell_allow_cmds_propagates(tmp_path: Path) -> None:
    config = _make_config()
    options = build_options("dev", tmp_path, config, shell_allow_cmds="pytest,ruff")
    assert options.mcp_servers["shell"]["env"] == {"ALLOW_CMDS": "pytest,ruff"}


def test_build_options_permission_mode_is_accept_edits(tmp_path: Path) -> None:
    # Aegis agents run unattended overnight; the graph-level gates
    # control approval, not per-tool prompts. 'acceptEdits' is the
    # right default here.
    config = _make_config()
    options = build_options("dev", tmp_path, config)
    assert options.permission_mode == "acceptEdits"


def test_build_options_unknown_role_raises(tmp_path: Path) -> None:
    config = _make_config()
    with pytest.raises(KeyError):
        build_options("architect", tmp_path, config)  # type: ignore[arg-type]
```

- [ ] **Step 2: Run tests — they must fail**

Run: `pytest tests/unit/test_agents_base.py -v`
Expected: all tests fail with `ModuleNotFoundError: No module named 'aegis.agents.base'`.

- [ ] **Step 3: Create `src/aegis/agents/base.py`**

```python
"""The public ``AegisAgent`` wrapper and its building blocks.

``load_prompt`` and ``build_options`` are pure and synchronous; they do
not touch the Claude SDK client at all. ``AegisAgent`` composes them
with a ``ClaudeSDKClient`` (injected for testability) and exposes a
single async ``run`` method.
"""

from __future__ import annotations

import importlib.resources
from pathlib import Path
from typing import Any, Callable

from claude_agent_sdk import ClaudeAgentOptions, ClaudeSDKClient

from aegis.agents.registry import ROLES, RoleName
from aegis.agents.tools import build_mcp_servers
from aegis.core.config import AegisConfig


ClientFactory = Callable[[ClaudeAgentOptions], ClaudeSDKClient]


def load_prompt(role: RoleName, override_path: Path | None = None) -> str:
    """Return the markdown system prompt for ``role``.

    If ``override_path`` is supplied it MUST exist; its contents are
    returned verbatim. Otherwise the packaged prompt under
    ``aegis.agents.prompts.<role>.md`` is returned.
    """
    spec = ROLES[role]
    if override_path is not None:
        if not override_path.is_file():
            raise FileNotFoundError(f"prompt override {override_path} does not exist")
        return override_path.read_text(encoding="utf-8")
    resource = importlib.resources.files("aegis.agents") / "prompts" / spec.prompt_filename
    return resource.read_text(encoding="utf-8")


def build_options(
    role: RoleName,
    worktree: Path,
    config: AegisConfig,
    prompt_override: Path | None = None,
    shell_allow_cmds: str | None = None,
) -> ClaudeAgentOptions:
    """Construct ``ClaudeAgentOptions`` for one role on one worktree."""
    spec = ROLES[role]
    worktree_resolved = worktree.resolve()

    model = config.llm.models[spec.model_key]
    system_prompt = load_prompt(role, override_path=prompt_override)
    servers = build_mcp_servers(role, worktree_resolved, shell_allow_cmds=shell_allow_cmds)

    return ClaudeAgentOptions(
        model=model,
        system_prompt=system_prompt,
        cwd=worktree_resolved,
        mcp_servers=servers,
        allowed_tools=list(spec.allowed_tools),
        disallowed_tools=list(spec.disallowed_tools),
        permission_mode="acceptEdits",
    )


class AegisAgent:
    """Placeholder — populated in Task 6."""
```

Note that `AegisAgent` is left as a bare placeholder for this task. Task 6 fills in its body; that split is deliberate so this task's commit is "pure helpers" and the next task's commit is "the class + its async tests".

- [ ] **Step 4: Run tests — they must pass**

Run: `pytest tests/unit/test_agents_base.py -v`
Expected: all 13 tests PASSED.

- [ ] **Step 5: Run the full suite**

Run: `pytest tests/unit -q`
Expected: every test green.

- [ ] **Step 6: Commit**

```bash
git add src/aegis/agents/base.py tests/unit/test_agents_base.py
git commit -m "feat(agents): add load_prompt and build_options helpers"
```

---

## Task 6: The `AegisAgent` class

**Files:**
- Modify: `src/aegis/agents/base.py` (replace the placeholder class)
- Modify: `tests/unit/test_agents_base.py` (append class tests)

This task adds the thin async wrapper. Tests use a `FakeClient` to avoid touching the real Claude SDK.

- [ ] **Step 1: Append failing tests to `tests/unit/test_agents_base.py`**

Add these imports at the top (merge with existing):

```python
import asyncio
from typing import Any

from claude_agent_sdk import ClaudeAgentOptions
from aegis.agents.base import AegisAgent
```

Append these tests at the bottom of the file:

```python
# ------------------ AegisAgent ------------------


class _FakeClient:
    """Stand-in for ``ClaudeSDKClient`` that records calls.

    Mirrors the context-manager + ``query`` + ``receive_response`` surface
    of the real client exactly — see the Claude Agent SDK docs.
    """

    last_instance: "_FakeClient | None" = None

    def __init__(self, options: ClaudeAgentOptions) -> None:
        self.options = options
        self.queries: list[str] = []
        self.responses: list[Any] = [
            {"role": "assistant", "content": "ok"},
            {"role": "tool", "name": "done", "input": {"summary": "done"}},
        ]
        _FakeClient.last_instance = self

    async def __aenter__(self) -> "_FakeClient":
        return self

    async def __aexit__(self, *_: Any) -> None:
        return None

    async def query(self, prompt: str) -> None:
        self.queries.append(prompt)

    async def receive_response(self):  # type: ignore[no-untyped-def]
        for msg in self.responses:
            yield msg


def test_agent_run_passes_task_prompt_to_client(tmp_path: Path) -> None:
    config = _make_config()
    agent = AegisAgent("dev", tmp_path, config, client_factory=_FakeClient)
    messages = asyncio.run(agent.run("do the thing"))
    assert _FakeClient.last_instance is not None
    assert _FakeClient.last_instance.queries == ["do the thing"]
    assert len(messages) == 2


def test_agent_run_returns_every_message(tmp_path: Path) -> None:
    config = _make_config()
    agent = AegisAgent("dev", tmp_path, config, client_factory=_FakeClient)
    messages = asyncio.run(agent.run("hi"))
    assert messages == [
        {"role": "assistant", "content": "ok"},
        {"role": "tool", "name": "done", "input": {"summary": "done"}},
    ]


def test_agent_builds_options_for_its_role(tmp_path: Path) -> None:
    config = _make_config()
    agent = AegisAgent("reviewer", tmp_path, config, client_factory=_FakeClient)
    asyncio.run(agent.run("please review"))
    assert _FakeClient.last_instance is not None
    opts = _FakeClient.last_instance.options
    assert set(opts.mcp_servers.keys()) == {"git", "project-index"}
    assert opts.system_prompt.startswith("# Role: Reviewer")
    assert opts.model == config.llm.models["reviewer"]


def test_agent_propagates_prompt_override(tmp_path: Path) -> None:
    config = _make_config()
    override = tmp_path / "pm-override.md"
    override.write_text("# Role: PM\n\noverride.\n", encoding="utf-8")
    agent = AegisAgent(
        "pm",
        tmp_path,
        config,
        prompt_override=override,
        client_factory=_FakeClient,
    )
    asyncio.run(agent.run("plan it"))
    assert _FakeClient.last_instance is not None
    assert "override." in _FakeClient.last_instance.options.system_prompt


def test_agent_propagates_shell_allow_cmds(tmp_path: Path) -> None:
    config = _make_config()
    agent = AegisAgent(
        "dev",
        tmp_path,
        config,
        shell_allow_cmds="pytest,ruff",
        client_factory=_FakeClient,
    )
    asyncio.run(agent.run("do"))
    assert _FakeClient.last_instance is not None
    shell = _FakeClient.last_instance.options.mcp_servers["shell"]
    assert shell["env"] == {"ALLOW_CMDS": "pytest,ruff"}


def test_agent_requires_worktree_to_exist(tmp_path: Path) -> None:
    config = _make_config()
    missing = tmp_path / "nope"
    with pytest.raises(FileNotFoundError):
        AegisAgent("dev", missing, config, client_factory=_FakeClient)


def test_agent_rejects_unknown_role(tmp_path: Path) -> None:
    config = _make_config()
    with pytest.raises(KeyError):
        AegisAgent("architect", tmp_path, config, client_factory=_FakeClient)  # type: ignore[arg-type]
```

- [ ] **Step 2: Run tests — they must fail**

Run: `pytest tests/unit/test_agents_base.py::test_agent_run_passes_task_prompt_to_client -v`
Expected: fails because the `AegisAgent` placeholder has no constructor parameters or `run` method.

- [ ] **Step 3: Replace the `AegisAgent` placeholder in `src/aegis/agents/base.py`**

Remove the last line (`class AegisAgent: "Placeholder …"`) and append this at the end of `base.py`:

```python
class AegisAgent:
    """One role bound to one worktree, wrapping ``ClaudeSDKClient``.

    The wrapper is intentionally thin: structured post-processing of
    the message stream (extracting ``done`` / ``block`` signals,
    updating LangGraph state, etc.) is a Phase-4 graph-node concern.
    Phase 3 only guarantees "a single role invocation returns its
    messages".
    """

    def __init__(
        self,
        role: RoleName,
        worktree: Path,
        config: AegisConfig,
        prompt_override: Path | None = None,
        shell_allow_cmds: str | None = None,
        client_factory: ClientFactory = ClaudeSDKClient,
    ) -> None:
        if role not in ROLES:
            raise KeyError(f"unknown role {role!r}")
        worktree_resolved = worktree.resolve()
        if not worktree_resolved.exists():
            raise FileNotFoundError(
                f"worktree {worktree_resolved} does not exist"
            )

        self.role: RoleName = role
        self.worktree: Path = worktree_resolved
        self.config: AegisConfig = config
        self.prompt_override: Path | None = prompt_override
        self.shell_allow_cmds: str | None = shell_allow_cmds
        self._client_factory: ClientFactory = client_factory

    def build_options(self) -> ClaudeAgentOptions:
        return build_options(
            self.role,
            self.worktree,
            self.config,
            prompt_override=self.prompt_override,
            shell_allow_cmds=self.shell_allow_cmds,
        )

    async def run(self, task_prompt: str) -> list[Any]:
        """Drive the client once with ``task_prompt`` and collect messages."""
        options = self.build_options()
        async with self._client_factory(options) as client:
            await client.query(task_prompt)
            messages: list[Any] = []
            async for msg in client.receive_response():
                messages.append(msg)
            return messages
```

- [ ] **Step 4: Run tests — they must pass**

Run: `pytest tests/unit/test_agents_base.py -v`
Expected: every test in the file PASSED (the 13 from Task 5 plus the 7 class tests = 20 total).

- [ ] **Step 5: Run the full suite**

Run: `pytest tests/unit -q`
Expected: every test green.

- [ ] **Step 6: Commit**

```bash
git add src/aegis/agents/base.py tests/unit/test_agents_base.py
git commit -m "feat(agents): add AegisAgent async wrapper over ClaudeSDKClient"
```

---

## Task 7: Per-role end-to-end integration asserts

**Files:**
- Create: `tests/unit/test_agents_per_role.py`

This test file is a single parametrized sanity check that, for each of the five roles, the `AegisAgent` built from the default `AegisConfig` produces options that exactly match the spec §4 tool-access table. It is the regression guard against silent drift between the registry, tools.py, and the prompt files.

- [ ] **Step 1: Write the failing test**

Create `tests/unit/test_agents_per_role.py`:

```python
from __future__ import annotations

from pathlib import Path

import pytest

from aegis.agents.base import build_options
from aegis.agents.registry import ROLES
from aegis.core.config import AegisConfig, ProjectConfig


@pytest.fixture
def default_config() -> AegisConfig:
    return AegisConfig(project=ProjectConfig(name="test-project"))


@pytest.mark.parametrize("role_name", sorted(ROLES.keys()))
def test_build_options_is_stable_per_role(
    role_name: str,
    default_config: AegisConfig,
    tmp_path: Path,
) -> None:
    spec = ROLES[role_name]
    options = build_options(role_name, tmp_path, default_config)  # type: ignore[arg-type]

    # Model string comes from config.
    assert options.model == default_config.llm.models[role_name]

    # System prompt is the packaged prompt file for this role.
    assert options.system_prompt.startswith(f"# Role: {role_name.upper() if role_name != 'pm' else 'PM'}") or \
           options.system_prompt.startswith("# Role:")  # case-insensitive fallback

    # MCP servers match the registry.
    assert tuple(options.mcp_servers.keys()) == spec.mcp_server_names

    # Allow/deny lists match the registry.
    assert tuple(options.allowed_tools) == spec.allowed_tools
    assert tuple(options.disallowed_tools) == spec.disallowed_tools

    # cwd is the worktree.
    assert Path(options.cwd) == tmp_path.resolve()


def test_pm_has_no_git_or_shell_access(default_config: AegisConfig, tmp_path: Path) -> None:
    options = build_options("pm", tmp_path, default_config)
    assert "git" not in options.mcp_servers
    assert "shell" not in options.mcp_servers


def test_reviewer_has_no_write_tools(default_config: AegisConfig, tmp_path: Path) -> None:
    options = build_options("reviewer", tmp_path, default_config)
    # Reviewer sees git + project-index. The allow-list must contain no
    # write tools at all — not just fs/shell, but also git writes.
    for tool in options.allowed_tools:
        assert "git_commit" not in tool
        assert "git_add" not in tool
        assert "git_merge" not in tool
        assert "fs_write" not in tool
        assert "shell_exec" not in tool


def test_docs_can_commit_but_not_branch(default_config: AegisConfig, tmp_path: Path) -> None:
    options = build_options("docs", tmp_path, default_config)
    assert "mcp__git__git_commit" in options.allowed_tools
    assert "mcp__git__git_add" in options.allowed_tools
    # Docs must not create or switch branches.
    for forbidden in (
        "mcp__git__git_branch_create",
        "mcp__git__git_checkout",
        "mcp__git__git_merge",
        "mcp__git__git_worktree_add",
        "mcp__git__git_worktree_remove",
    ):
        assert forbidden in options.disallowed_tools


def test_dev_shell_allow_cmds_respects_argument(
    default_config: AegisConfig, tmp_path: Path
) -> None:
    options = build_options("dev", tmp_path, default_config, shell_allow_cmds="pytest,ruff,mypy")
    assert options.mcp_servers["shell"]["env"] == {"ALLOW_CMDS": "pytest,ruff,mypy"}


def test_qa_shell_allow_cmds_respects_argument(
    default_config: AegisConfig, tmp_path: Path
) -> None:
    # Spec §4 note: QA may run a TIGHTER allow-list than Dev.
    options = build_options("qa", tmp_path, default_config, shell_allow_cmds="pytest")
    assert options.mcp_servers["shell"]["env"] == {"ALLOW_CMDS": "pytest"}


def test_models_are_configurable(tmp_path: Path) -> None:
    # A user can remap the PM model in config.yaml; the agent must
    # honour that remapping. ``AegisConfig`` is a non-frozen pydantic
    # v2 model so direct mutation of the ``models`` dict is fine.
    config = AegisConfig(project=ProjectConfig(name="t"))
    config.llm.models["pm"] = "claude-opus-5-0"
    options = build_options("pm", tmp_path, config)
    assert options.model == "claude-opus-5-0"
```

- [ ] **Step 2: Run tests — they must fail or pass**

Run: `pytest tests/unit/test_agents_per_role.py -v`
Expected: PASS. All contracts were already built in Tasks 2–6; this file is a *regression guard*, so if it fails it means one of the prior tasks is broken — go fix there, not here.

If `test_build_options_is_stable_per_role` fails for the prompt-header assertion because a role's prompt starts with a different literal (e.g. `# Role: Dev (Developer)`), the assertion's case-insensitive fallback already handles it — re-read the failure message and adjust only if the prompt file is genuinely wrong.

- [ ] **Step 3: Run the full suite**

Run: `pytest tests/unit -q`
Expected: every test green.

- [ ] **Step 4: Commit**

```bash
git add tests/unit/test_agents_per_role.py
git commit -m "test(agents): lock in per-role build_options contract"
```

---

## Task 8: Manual smoke test + Phase-4 handoff

**Files:**
- Modify: `docs/superpowers/plans/2026-04-17-aegis-phase-3-agents.md` (this file, append an "executed smoke test" note) — OR add an optional Makefile target; see Step 3.

This task produces no code. It verifies end-to-end that (a) the console scripts installed by Phase 2 actually spawn, (b) the SDK accepts our `ClaudeAgentOptions`, and (c) the prompt files are well-formed. If the user chooses to skip the live test (no `ANTHROPIC_API_KEY`, no `claude` CLI), only the static checks are mandatory.

- [ ] **Step 1: Confirm the package surface imports cleanly**

Run:

```bash
python -c "
from aegis.agents import (
    AegisAgent, ROLES, RoleName, RoleSpec,
    build_mcp_servers, build_options, load_prompt,
)
for name, spec in ROLES.items():
    print(name, spec.prompt_filename, len(load_prompt(name)), 'chars')
"
```

Expected output: five lines like `pm pm.md 1623 chars` (exact byte counts will differ — the point is that every role loads without error).

- [ ] **Step 2: Confirm the four Phase-2 console scripts are on PATH**

Run: `which aegis-fs-mcp aegis-git-mcp aegis-shell-mcp aegis-project-index-mcp`
Expected: four paths printed, all inside the virtualenv's `bin/` directory.

If any is missing: re-run `pip install -e .[dev]` — this was Phase-2's Task 1 and should be idempotent.

- [ ] **Step 3: (Optional, skipped in CI) Live smoke test**

If `ANTHROPIC_API_KEY` is set AND `claude` CLI is installed, run the following script from a scratch directory. This is **not** part of the automated suite — it makes a real LLM call with a ~$0.01 cost ceiling:

```bash
mkdir -p /tmp/aegis-smoke && cd /tmp/aegis-smoke
git init -q -b main .
git config user.email smoke@test && git config user.name Smoke
echo "# smoke" > README.md
git add README.md && git commit -q -m "init"

python -c "
import asyncio
from pathlib import Path
from aegis.agents import AegisAgent
from aegis.core.config import AegisConfig, ProjectConfig

config = AegisConfig(project=ProjectConfig(name='smoke'))
agent = AegisAgent('reviewer', Path('.'), config)

async def run():
    msgs = await agent.run('What files exist in this repo? Do not attempt to modify anything.')
    for m in msgs:
        print(m)

asyncio.run(run())
"
```

Expected: the Reviewer agent lists `README.md`, uses read-only tools only, and terminates. Any attempt by the model to call a write tool should be refused because `git_commit` etc. are in `disallowed_tools`.

If the live test fails due to missing `claude` CLI, the error message will say so — this does NOT mean Phase 3 is broken, it means the live-smoke prerequisite is not met on this machine. Skip and continue.

- [ ] **Step 4: Final full-suite check**

Run: `pytest tests/unit -q`
Expected:

```
======================= XX passed in Ys ========================
```

where `XX` is the Phase-1 count + Phase-2 count + roughly 80 new tests (17 registry + 23 prompt + 13 tools + 20 base + 11 per-role ≈ 84 new tests; counts may shift ±5 depending on parametrization).

- [ ] **Step 5: Tag the phase**

```bash
git tag -a phase-3-complete -m "Phase 3: Claude Agent SDK agent layer"
```

Do NOT push the tag yet; the user may want to push after reviewing the final diff. Mention the tag in the final commit message if desired:

```bash
git commit --allow-empty -m "chore: mark phase 3 complete"
```

(An empty commit is not strictly required; the tag alone is enough. Skip this step if no empty commit is wanted.)

---

## Appendix A — Decisions locked in by this plan

1. **Package name is `claude-agent-sdk`, not `anthropic[agent]`.** The spec §8.1 table is retroactively wrong; this plan is authoritative.
2. **Per-role shell allow-list is a function parameter, not a config field.** Phase 4's graph-node author picks the value per role. Extending `AegisConfig` for this is deferred to Phase 4 or later if the ergonomics demand it.
3. **Prompts are static markdown, no templating.** `${task_path}` and `${worktree_path}` appear in prompt bodies as human-readable placeholders for what the task prompt will mention at runtime; they are NOT substituted at load time.
4. **`AegisAgent.run` returns raw messages.** Structured interpretation of `done` / `block` tool calls is a Phase-4 concern, not here.
5. **Test strategy is dependency-injection of the client factory.** No `pytest-asyncio`, no real network, no real `claude` CLI in CI.
6. **Read-only roles (Reviewer) have empty write tool-grants AND explicit disallow-lists.** Defense in depth — if a future SDK version makes `allowed_tools` advisory, the disallow-list still blocks the call.

## Appendix B — Handoff to Phase 4

Phase 4 will:

1. Introduce `langgraph` as a dependency.
2. Create `src/aegis/graph/team_graph.py` with a LangGraph `StateGraph` whose nodes invoke `AegisAgent` per the §5.2 diagram.
3. Create `src/aegis/graph/nodes/{pm,dev,qa,reviewer,docs}.py` — each node:
   - Creates its worktree (or reuses the existing one) via `aegis.core.worktree`.
   - Instantiates `AegisAgent(role, worktree, config)`.
   - Calls `agent.run(task_prompt)`.
   - Interprets `done` / `block` / tool-call messages to update `TeamState`.
   - Enforces budget via `aegis.core.budget.BudgetTracker` (Phase 1).
4. Provide the `done` and `block` SDK in-process tools (`claude_agent_sdk.create_sdk_mcp_server`) and merge them into each role's `mcp_servers` dict before invoking the agent.
5. Implement `aegis run`, `aegis daemon`, `aegis status`, `aegis approve`, `aegis reject`, `aegis retry`, `aegis stop` — replacing the Phase-1 stubs.
6. Preserve every Phase-3 contract: the registry, the role prompts, and the `AegisAgent` public surface are stable.

The five agents built in Phase 3 are the exact units Phase 4's five LangGraph nodes will instantiate. The `shell_allow_cmds` parameter becomes the node's policy lever — Dev gets `pytest,ruff,mypy,python,pip,npm,pnpm,node`; QA gets a tighter `pytest,ruff,mypy,python`; Reviewer/Docs/PM do not spawn the shell server at all.

---

*End of Phase 3 implementation plan.*
