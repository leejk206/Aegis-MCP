# Aegis Phase 1 — Teardown, Scaffolding, Core Layer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Transform the current Aegis-MCP (a Slack security bot scaffold) into an installable Python package whose CLI (`aegis init`, `aegis task`, `aegis config`) works end-to-end on any git repository, with a fully unit-tested core layer (config schema, markdown task parser, git worktree helpers, budget tracker, lifecycle state machine).

**Architecture:** `src/` layout Python package built with Hatchling. Three layers: `core/` (pure data/helpers, no I/O side effects beyond files), `cli/` (Typer entrypoint + subcommands), and tests under `tests/unit/`. No LangGraph, no Claude Agent SDK, no MCP, no web dashboard, no agent code in Phase 1.

**Tech Stack:** Python 3.11+, Hatchling, Pydantic v2, Typer, python-frontmatter, PyYAML, pytest, ruff, mypy.

**Spec reference:** `docs/superpowers/specs/2026-04-14-aegis-ai-engineering-team-design.md`

---

## Scope

### Phase 1 covers these spec sections

- **§2 Non-goals** — enforced by deleting all in-scope code we've marked delete.
- **§6 `.aegis/` directory spec** — `core.config`, `core.task`, `core.lifecycle` implement the config.yaml schema, markdown task schema, and lifecycle transitions. `cli.commands.init` creates the directory structure.
- **§7 CLI UX reference** — `init`, `task add/list/show/edit`, `config get/set/edit` subcommands are implemented. Commands that need agents or the team graph (`run`, `daemon`, `status`, `inspect`, `approve`, `reject`, `retry`, `stop`, `logs`, `trace`, `web`) are stubbed or deferred to later phases.
- **§8 Python package layout** — the `src/aegis/` tree is created with `core/`, `cli/` populated; other subpackages (`graph/`, `agents/`, `mcp_servers/`, `obs/`, `web/`) are scaffolded as empty packages but not implemented.
- **§11.1 Per-task budget primitive** — `core.budget.BudgetTracker` is implemented standalone so later phases can wire it into the graph.
- **§13.1 Unit tests** — every module in `core/` and every implemented CLI command has unit tests.
- **§15 Migration plan** — steps 1 (teardown), 2 (scaffold), 3 (core layer), and partial 4 (CLI stubs against core) are executed.

### What Phase 1 explicitly does NOT cover

These become Phase 2, 3, ... plans:

- **Phase 2**: MCP servers (`aegis-git-mcp`, `aegis-fs-mcp`, `aegis-shell-mcp`, `aegis-project-index-mcp`).
- **Phase 3**: Agent layer — Claude Agent SDK wrapper, prompt files, per-agent tests.
- **Phase 4**: LangGraph team graph — 5 nodes (PM/Dev/QA/Reviewer/Docs), state machine, checkpointer, node-level integration tests.
- **Phase 5**: Observability — OTel bootstrap, LangSmith exporter, Langfuse exporter, local JSONL mirror, `docker-compose.yml`.
- **Phase 6**: Web dashboard (read-only kanban, approve/reject endpoints).
- **Phase 7**: Golden-trajectory e2e tests with recorded LLM transcripts on a fixture repo.
- **Phase 8**: Dogfooding iteration + final README rewrite.

At the end of Phase 1, running `aegis run` or `aegis daemon start` must print a clear "not implemented yet — Phase 4" error, not silently do nothing.

---

## File map

### Files created by this plan

```
pyproject.toml
Makefile
README.md                                         (replaced, short stub)
.gitignore                                        (modified, see Task 1)
src/aegis/__init__.py
src/aegis/core/__init__.py
src/aegis/core/config.py
src/aegis/core/task.py
src/aegis/core/worktree.py
src/aegis/core/budget.py
src/aegis/core/lifecycle.py
src/aegis/cli/__init__.py
src/aegis/cli/main.py
src/aegis/cli/commands/__init__.py
src/aegis/cli/commands/init.py
src/aegis/cli/commands/task.py
src/aegis/cli/commands/config.py
src/aegis/cli/commands/stubs.py                   (placeholders for run/daemon/etc.)
src/aegis/graph/__init__.py                       (empty scaffold)
src/aegis/agents/__init__.py                      (empty scaffold)
src/aegis/mcp_servers/__init__.py                 (empty scaffold)
src/aegis/obs/__init__.py                         (empty scaffold)
src/aegis/web/__init__.py                         (empty scaffold)
tests/__init__.py
tests/unit/__init__.py
tests/unit/conftest.py
tests/unit/test_config.py
tests/unit/test_task.py
tests/unit/test_worktree.py
tests/unit/test_budget.py
tests/unit/test_lifecycle.py
tests/unit/test_cli_init.py
tests/unit/test_cli_task.py
tests/unit/test_cli_config.py
.github/workflows/ci.yml                          (replaced)
```

### Files deleted by this plan

```
app/                                              (entire tree)
aegis_mock.db
requirements.txt
tests/__init__.py                                 (recreated later)
tests/test_orchestrator.py
```

---

## Task 1: Teardown old Aegis-MCP code

**Files:**
- Delete: `app/` (entire tree)
- Delete: `aegis_mock.db`
- Delete: `requirements.txt`
- Delete: `tests/test_orchestrator.py`
- Delete: `tests/__init__.py`

The current repo is a Slack-based security bot that is incompatible with the new direction. Per the spec's migration table (§8.1), all of `app/` is deleted because `core/config.py` needs rewriting for the new YAML schema, `mac_service.py` and `dp_filter.py` are out of scope, `slack_*` is out of scope, and `orchestrator.py` is reimplemented as a LangGraph graph in Phase 4.

The git history is preserved via a normal deletion commit — we do not rewrite history.

- [ ] **Step 1: Confirm current state**

Run: `cd /home/ljk9121/projects/Aegis-MCP && git status`
Expected: `On branch main`, clean working tree (one commit ahead of origin after Phase 0 spec push).

- [ ] **Step 2: Delete old code with `git rm`**

Run these one at a time, each must succeed:

```bash
git rm -r app/
git rm aegis_mock.db
git rm requirements.txt
git rm tests/test_orchestrator.py
git rm tests/__init__.py
```

Expected: `rm 'app/...'` lines for each deleted file, no errors.

- [ ] **Step 3: Verify nothing else references the old package**

Run: `grep -r "from app" . --include="*.py" 2>/dev/null; grep -r "import app" . --include="*.py" 2>/dev/null`
Expected: empty output (no remaining imports).

- [ ] **Step 4: Commit teardown**

```bash
git commit -m "$(cat <<'EOF'
chore: remove legacy Aegis-MCP Slack/security scaffold

Delete the old FastAPI + Slack Events + SQLite MAC scaffold in app/ to
make room for the Phase 1 Aegis redesign (installable CLI + core layer).

Per the spec migration table, all of app/ is unused in the new design:
slack_*, mac_service, dp_filter are out of scope; orchestrator and
intent_classifier are re-implemented as LangGraph nodes in Phase 4;
models/user and models/task are replaced by git-native markdown tasks.

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>
EOF
)"
```

Expected: commit created, `git status` shows clean tree.

---

## Task 2: Scaffold the new package (pyproject.toml, src layout, empty modules)

**Files:**
- Create: `pyproject.toml`
- Create: `Makefile`
- Create: `README.md` (overwrites existing)
- Create: `src/aegis/__init__.py`
- Create: `src/aegis/core/__init__.py`
- Create: `src/aegis/cli/__init__.py`
- Create: `src/aegis/cli/commands/__init__.py`
- Create: `src/aegis/graph/__init__.py`
- Create: `src/aegis/agents/__init__.py`
- Create: `src/aegis/mcp_servers/__init__.py`
- Create: `src/aegis/obs/__init__.py`
- Create: `src/aegis/web/__init__.py`
- Create: `tests/__init__.py`
- Create: `tests/unit/__init__.py`

- [ ] **Step 1: Write `pyproject.toml`**

```toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "aegis"
version = "0.1.0"
description = "Personal AI engineering team: LangGraph + Claude Agent SDK + MCP for solo developers"
readme = "README.md"
requires-python = ">=3.11"
license = { text = "MIT" }
authors = [{ name = "Aegis contributors" }]
dependencies = [
    "pydantic>=2.7",
    "python-frontmatter>=1.1",
    "pyyaml>=6.0",
    "typer>=0.12",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0",
    "ruff>=0.6",
    "mypy>=1.10",
    "types-PyYAML>=6.0",
]

[project.scripts]
aegis = "aegis.cli.main:app"

[tool.hatch.build.targets.wheel]
packages = ["src/aegis"]

[tool.ruff]
line-length = 100
target-version = "py311"

[tool.ruff.lint]
select = ["E", "F", "I", "B", "UP", "SIM"]

[tool.mypy]
python_version = "3.11"
strict = true
warn_unreachable = true
files = ["src/aegis"]

[[tool.mypy.overrides]]
module = ["frontmatter"]
ignore_missing_imports = true

[tool.pytest.ini_options]
testpaths = ["tests"]
pythonpath = ["src"]
addopts = "-v --strict-markers"
```

- [ ] **Step 2: Write `Makefile`**

```makefile
.PHONY: install test e2e lint typecheck clean

install:
	pip install -e ".[dev]"

test:
	pytest tests/unit

lint:
	ruff check src tests
	ruff format --check src tests

typecheck:
	mypy

clean:
	rm -rf .pytest_cache .mypy_cache .ruff_cache build dist *.egg-info
	find . -type d -name __pycache__ -exec rm -rf {} +
```

- [ ] **Step 3: Write `README.md`** (overwrites the old README)

```markdown
# Aegis

> **Status:** Phase 1 (core scaffolding) — under active redesign.
> Not yet functional as an AI team. See
> `docs/superpowers/specs/2026-04-14-aegis-ai-engineering-team-design.md`
> for the target architecture.

**Aegis** will be a local CLI + dashboard that drops a five-role AI
engineering team (PM / Dev / QA / Reviewer / Docs) onto any git repo.
You write vague task ideas as markdown, go to sleep, and wake up to
PRs the team has built, tested, and reviewed.

## Install (contributors)

```bash
pip install -e ".[dev]"
```

## Run tests

```bash
make test
```

## What works today

- `aegis init` — creates `.aegis/` in a git repo
- `aegis task add/list/show/edit` — author and browse markdown tasks
- `aegis config get/set/edit` — read and edit `.aegis/config.yaml`

## What does NOT work yet

- `aegis run`, `aegis daemon`, `aegis approve`, `aegis web`, and
  everything that touches actual LLM agents. These arrive in Phases
  2–6.
```

- [ ] **Step 4: Create empty `__init__.py` files**

Create these files, each containing only the comment line shown:

```python
# src/aegis/__init__.py
"""Aegis — personal AI engineering team."""

__version__ = "0.1.0"
```

Then for every other `__init__.py` listed in the file map above (except `src/aegis/__init__.py` just above), write a single-line marker:

```python
# src/aegis/core/__init__.py
"""Core: config, task, worktree, budget, lifecycle."""
```

```python
# src/aegis/cli/__init__.py
"""CLI: Typer entrypoint and subcommands."""
```

```python
# src/aegis/cli/commands/__init__.py
"""CLI command modules, one per top-level `aegis <subcommand>`."""
```

```python
# src/aegis/graph/__init__.py
"""LangGraph team graph. Implemented in Phase 4."""
```

```python
# src/aegis/agents/__init__.py
"""Claude Agent SDK wrapper + role prompts. Implemented in Phase 3."""
```

```python
# src/aegis/mcp_servers/__init__.py
"""First-party MCP servers: git, fs, shell, project-index. Implemented in Phase 2."""
```

```python
# src/aegis/obs/__init__.py
"""OpenTelemetry + LangSmith/Langfuse exporters. Implemented in Phase 5."""
```

```python
# src/aegis/web/__init__.py
"""Read-only FastAPI dashboard. Implemented in Phase 6."""
```

```python
# tests/__init__.py
```

```python
# tests/unit/__init__.py
```

- [ ] **Step 5: Install the package in editable mode**

Run: `pip install -e ".[dev]"`
Expected: `Successfully installed aegis-0.1.0 ...`

If Python 3.11+ is not available, install it first. This plan assumes it is.

- [ ] **Step 6: Smoke-run the (not yet wired) entry point**

Run: `aegis --help`
Expected: `Error: No such command` or similar (since `main.py` is empty). This is expected at this step.

- [ ] **Step 7: Commit scaffolding**

```bash
git add pyproject.toml Makefile README.md src/ tests/
git commit -m "$(cat <<'EOF'
chore: scaffold src/aegis package with pyproject.toml and empty modules

Create the src/ layout, Hatchling build config, pydantic + typer +
pytest deps, Makefile shortcuts, and empty __init__.py files for every
subpackage (core, cli, graph, agents, mcp_servers, obs, web). Replace
the README with a Phase 1 status stub.

The CLI entry point is registered but unimplemented — `aegis --help`
errors out. That wiring happens in Task 8.

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 3: Core — `AegisConfig` pydantic schema (TDD)

**Files:**
- Create: `src/aegis/core/config.py`
- Create: `tests/unit/test_config.py`

This module is the Python representation of `.aegis/config.yaml` described in spec §6.2. It must round-trip cleanly to YAML and provide sensible defaults so `aegis init` can emit a usable config for any project.

- [ ] **Step 1: Write the failing tests**

Create `tests/unit/test_config.py`:

```python
from pathlib import Path

import pytest
import yaml

from aegis.core.config import (
    AegisConfig,
    default_config,
    dump_config,
    load_config,
)


def test_default_config_has_expected_fields() -> None:
    cfg = default_config("my-cream")
    assert cfg.version == 1
    assert cfg.project.name == "my-cream"
    assert cfg.project.root == "."
    assert cfg.llm.provider == "anthropic"
    assert cfg.llm.models["pm"] == "claude-opus-4-6"
    assert cfg.llm.models["dev"] == "claude-sonnet-4-6"
    assert cfg.llm.models["docs"] == "claude-haiku-4-5"
    assert cfg.budget.task.usd == pytest.approx(2.00)
    assert cfg.budget.task.minutes == 30
    assert cfg.budget.parallel.max == 3
    assert cfg.gates.strategy == "merge_only"
    assert cfg.gates.auto_approve_docs is True
    assert len(cfg.mcp.servers) == 4
    assert {s.name for s in cfg.mcp.servers} == {"git", "fs", "shell", "project-index"}


def test_config_roundtrip_yaml(tmp_path: Path) -> None:
    original = default_config("sample")
    path = tmp_path / "config.yaml"
    dump_config(original, path)

    raw = yaml.safe_load(path.read_text())
    assert raw["project"]["name"] == "sample"

    loaded = load_config(path)
    assert loaded == original


def test_config_loads_partial_yaml(tmp_path: Path) -> None:
    path = tmp_path / "config.yaml"
    path.write_text(
        "version: 1\nproject:\n  name: partial\n",
        encoding="utf-8",
    )
    loaded = load_config(path)
    assert loaded.project.name == "partial"
    # Defaults fill in the rest.
    assert loaded.llm.models["pm"] == "claude-opus-4-6"
    assert loaded.budget.task.usd == pytest.approx(2.00)


def test_config_overrides_model_routing(tmp_path: Path) -> None:
    path = tmp_path / "config.yaml"
    path.write_text(
        """
version: 1
project:
  name: override
llm:
  provider: anthropic
  models:
    pm: claude-sonnet-4-6
    dev: claude-haiku-4-5
    qa: claude-haiku-4-5
    reviewer: claude-sonnet-4-6
    docs: claude-haiku-4-5
""",
        encoding="utf-8",
    )
    loaded = load_config(path)
    assert loaded.llm.models["pm"] == "claude-sonnet-4-6"
    assert loaded.llm.models["dev"] == "claude-haiku-4-5"


def test_config_rejects_unknown_gate_strategy(tmp_path: Path) -> None:
    path = tmp_path / "config.yaml"
    path.write_text(
        """
version: 1
project:
  name: bad
gates:
  strategy: none
""",
        encoding="utf-8",
    )
    with pytest.raises(Exception):
        load_config(path)
```

- [ ] **Step 2: Run tests — they must fail**

Run: `pytest tests/unit/test_config.py -v`
Expected: `ImportError: No module named 'aegis.core.config'` (or similar).

- [ ] **Step 3: Write the minimal implementation**

Create `src/aegis/core/config.py`:

```python
from __future__ import annotations

from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field


class ProjectConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    root: str = "."


class LLMConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    provider: Literal["anthropic"] = "anthropic"
    models: dict[str, str] = Field(
        default_factory=lambda: {
            "pm": "claude-opus-4-6",
            "dev": "claude-sonnet-4-6",
            "qa": "claude-sonnet-4-6",
            "reviewer": "claude-opus-4-6",
            "docs": "claude-haiku-4-5",
        }
    )


class TaskBudgetDefaults(BaseModel):
    model_config = ConfigDict(extra="forbid")

    usd: float = 2.00
    minutes: int = 30


class ParallelConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    max: int = 3


class BudgetConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    task: TaskBudgetDefaults = Field(default_factory=TaskBudgetDefaults)
    parallel: ParallelConfig = Field(default_factory=ParallelConfig)


class GatesConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    strategy: Literal["merge_only"] = "merge_only"
    auto_approve_docs: bool = True


class PMAgentConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    max_subtasks: int = 8


class DevAgentConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    retries_on_qa_fail: int = 2


class QAAgentConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    fail_fast: bool = False


class ReviewerAgentConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    retries_on_rework: int = 1
    checklist_path: str | None = None


class DocsAgentConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    paths: list[str] = Field(
        default_factory=lambda: ["README.md", "CHANGELOG.md", "docs/"]
    )


class AgentsConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    pm: PMAgentConfig = Field(default_factory=PMAgentConfig)
    dev: DevAgentConfig = Field(default_factory=DevAgentConfig)
    qa: QAAgentConfig = Field(default_factory=QAAgentConfig)
    reviewer: ReviewerAgentConfig = Field(default_factory=ReviewerAgentConfig)
    docs: DocsAgentConfig = Field(default_factory=DocsAgentConfig)


class LangSmithConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    enabled: bool = False
    project: str | None = None


class LangfuseConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    enabled: bool = True
    url: str = "http://localhost:3000"


class OtelConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    service_name: str = "aegis"


class ObservabilityConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    langsmith: LangSmithConfig = Field(default_factory=LangSmithConfig)
    langfuse: LangfuseConfig = Field(default_factory=LangfuseConfig)
    otel: OtelConfig = Field(default_factory=OtelConfig)


class MCPServerConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    command: str
    env: dict[str, str] = Field(default_factory=dict)


class MCPConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    servers: list[MCPServerConfig] = Field(
        default_factory=lambda: [
            MCPServerConfig(name="git", command="aegis-git-mcp"),
            MCPServerConfig(name="fs", command="aegis-fs-mcp"),
            MCPServerConfig(name="project-index", command="aegis-project-index-mcp"),
            MCPServerConfig(
                name="shell",
                command="aegis-shell-mcp",
                env={"ALLOW_CMDS": "pytest,python,pip,npm,pnpm,node,ruff,mypy"},
            ),
        ]
    )


class AegisConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version: int = 1
    project: ProjectConfig
    llm: LLMConfig = Field(default_factory=LLMConfig)
    budget: BudgetConfig = Field(default_factory=BudgetConfig)
    gates: GatesConfig = Field(default_factory=GatesConfig)
    agents: AgentsConfig = Field(default_factory=AgentsConfig)
    observability: ObservabilityConfig = Field(default_factory=ObservabilityConfig)
    mcp: MCPConfig = Field(default_factory=MCPConfig)


def default_config(project_name: str) -> AegisConfig:
    return AegisConfig(project=ProjectConfig(name=project_name))


def load_config(path: Path) -> AegisConfig:
    with open(path, encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    return AegisConfig.model_validate(data)


def dump_config(config: AegisConfig, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    data = config.model_dump(mode="python")
    with open(path, "w", encoding="utf-8") as f:
        yaml.safe_dump(data, f, sort_keys=False, default_flow_style=False)
```

- [ ] **Step 4: Run tests — they must pass**

Run: `pytest tests/unit/test_config.py -v`
Expected: all 5 tests pass.

- [ ] **Step 5: Commit**

```bash
git add src/aegis/core/config.py tests/unit/test_config.py
git commit -m "$(cat <<'EOF'
feat(core): add AegisConfig pydantic schema with YAML roundtrip

Implements the .aegis/config.yaml schema from spec §6.2 as Pydantic v2
models with defaults. default_config() emits a ready-to-dogfood config;
load_config/dump_config round-trip via PyYAML.

Covers: version, project, llm routing (pm/dev/qa/reviewer/docs),
budget, gates, agents, observability (langsmith+langfuse+otel), mcp
servers list.

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 4: Core — Markdown task parser (TDD)

**Files:**
- Create: `src/aegis/core/task.py`
- Create: `tests/unit/test_task.py`

This module owns the on-disk representation of a task as described in spec §6.3: a markdown file with YAML frontmatter for machine-readable state and a body for human prose + appended sections (plan, QA report, review).

- [ ] **Step 1: Write the failing tests**

Create `tests/unit/test_task.py`:

```python
from datetime import datetime, timezone
from pathlib import Path

import pytest

from aegis.core.task import (
    Priority,
    Task,
    TaskBudget,
    TaskFrontmatter,
    TaskStatus,
    next_task_id,
    parse_task,
    serialize_task,
    slugify,
    task_filename,
    write_task,
)


@pytest.fixture
def sample_task() -> Task:
    return Task(
        frontmatter=TaskFrontmatter(
            id="001",
            title="Add rate limiting to login API",
            status=TaskStatus.BACKLOG,
            priority=Priority.P1,
            budget=TaskBudget(usd=2.00, minutes=30),
            created=datetime(2026, 4, 14, 23, 10, 0, tzinfo=timezone.utc),
            tags=["api", "security"],
        ),
        body=(
            "# Add rate limiting to login API\n\n"
            "Login endpoint currently accepts unlimited attempts. "
            "Add per-IP rate limiting.\n"
        ),
    )


def test_slugify_basic() -> None:
    assert slugify("Add rate limiting to login API") == "add-rate-limiting-to-login-api"


def test_slugify_strips_punctuation() -> None:
    assert slugify("Fix bug #42: broken!") == "fix-bug-42-broken"


def test_slugify_empty_fallback() -> None:
    assert slugify("!!!") == "task"
    assert slugify("") == "task"


def test_task_filename_format() -> None:
    assert task_filename("001", "Add rate limiting") == "001-add-rate-limiting.md"


def test_serialize_and_parse_roundtrip(tmp_path: Path, sample_task: Task) -> None:
    path = tmp_path / "001-add-rate-limiting.md"
    write_task(sample_task, path)

    loaded = parse_task(path)
    assert loaded.frontmatter.id == "001"
    assert loaded.frontmatter.title == sample_task.frontmatter.title
    assert loaded.frontmatter.status == TaskStatus.BACKLOG
    assert loaded.frontmatter.priority == Priority.P1
    assert loaded.frontmatter.budget.usd == pytest.approx(2.00)
    assert loaded.frontmatter.tags == ["api", "security"]
    assert "Login endpoint" in loaded.body


def test_serialize_preserves_appended_sections(tmp_path: Path, sample_task: Task) -> None:
    path = tmp_path / "001-task.md"
    sample_task.body += "\n\n## Plan\n1. Add dependency\n2. Wire limiter\n"
    write_task(sample_task, path)
    loaded = parse_task(path)
    assert "## Plan" in loaded.body
    assert "Wire limiter" in loaded.body


def test_next_task_id_empty_dir(tmp_path: Path) -> None:
    assert next_task_id(tmp_path) == "001"


def test_next_task_id_finds_max_across_directories(tmp_path: Path) -> None:
    for sub in ["backlog", "in-progress", "done"]:
        (tmp_path / sub).mkdir()
    (tmp_path / "backlog" / "005-new.md").write_text("---\nid: '005'\ntitle: x\ncreated: 2026-04-14T00:00:00+00:00\n---\n")
    (tmp_path / "in-progress" / "012-active.md").write_text("---\nid: '012'\ntitle: x\ncreated: 2026-04-14T00:00:00+00:00\n---\n")
    (tmp_path / "done" / "009-finished.md").write_text("---\nid: '009'\ntitle: x\ncreated: 2026-04-14T00:00:00+00:00\n---\n")
    assert next_task_id(tmp_path) == "013"
```

- [ ] **Step 2: Run tests — they must fail**

Run: `pytest tests/unit/test_task.py -v`
Expected: `ImportError: No module named 'aegis.core.task'`.

- [ ] **Step 3: Write the implementation**

Create `src/aegis/core/task.py`:

```python
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from pathlib import Path

import frontmatter
from pydantic import BaseModel, ConfigDict, Field


class TaskStatus(str, Enum):
    BACKLOG = "backlog"
    IN_PROGRESS = "in-progress"
    REVIEW = "review"
    DONE = "done"
    BLOCKED = "blocked"
    REJECTED = "rejected"


class Priority(str, Enum):
    P0 = "P0"
    P1 = "P1"
    P2 = "P2"
    P3 = "P3"


class TaskBudget(BaseModel):
    model_config = ConfigDict(extra="forbid")

    usd: float = 2.00
    minutes: int = 30


class TaskFrontmatter(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    title: str
    status: TaskStatus = TaskStatus.BACKLOG
    priority: Priority = Priority.P2
    budget: TaskBudget = Field(default_factory=TaskBudget)
    created: datetime
    started: datetime | None = None
    completed: datetime | None = None
    worktree: str | None = None
    trace_id: str | None = None
    pr_branch: str | None = None
    dependencies: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)


@dataclass
class Task:
    frontmatter: TaskFrontmatter
    body: str


_SLUG_STRIP = re.compile(r"[^a-z0-9-]+")
_SLUG_RUNS = re.compile(r"-+")


def slugify(title: str) -> str:
    s = title.lower().strip()
    s = re.sub(r"\s+", "-", s)
    s = _SLUG_STRIP.sub("", s)
    s = _SLUG_RUNS.sub("-", s).strip("-")
    return s or "task"


def task_filename(task_id: str, title: str) -> str:
    return f"{task_id}-{slugify(title)}.md"


def parse_task(path: Path) -> Task:
    post = frontmatter.load(str(path))
    fm = TaskFrontmatter.model_validate(dict(post.metadata))
    return Task(frontmatter=fm, body=post.content)


def serialize_task(task: Task) -> str:
    metadata = task.frontmatter.model_dump(mode="json", exclude_none=False)
    post = frontmatter.Post(content=task.body, **metadata)
    return frontmatter.dumps(post)


def write_task(task: Task, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(serialize_task(task), encoding="utf-8")


_STATUS_SUBDIRS = (
    "backlog",
    "in-progress",
    "review",
    "done",
    "blocked",
    "rejected",
)


def next_task_id(aegis_dir: Path) -> str:
    max_id = 0
    pattern = re.compile(r"^(\d+)-")
    for sub in _STATUS_SUBDIRS:
        d = aegis_dir / sub
        if not d.exists():
            continue
        for f in d.glob("*.md"):
            m = pattern.match(f.name)
            if m:
                max_id = max(max_id, int(m.group(1)))
    return f"{max_id + 1:03d}"
```

- [ ] **Step 4: Run tests — they must pass**

Run: `pytest tests/unit/test_task.py -v`
Expected: all 8 tests pass.

- [ ] **Step 5: Commit**

```bash
git add src/aegis/core/task.py tests/unit/test_task.py
git commit -m "$(cat <<'EOF'
feat(core): add markdown task parser with YAML frontmatter

Implements the task schema from spec §6.3: TaskStatus enum, Priority
enum, TaskBudget, TaskFrontmatter (id, title, status, priority, budget,
created, started, completed, worktree, trace_id, pr_branch, deps, tags),
and helpers slugify / task_filename / parse_task / serialize_task /
write_task / next_task_id.

next_task_id scans all six status subdirectories and returns the next
zero-padded 3-digit id.

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 5: Core — Git worktree helpers (TDD)

**Files:**
- Create: `src/aegis/core/worktree.py`
- Create: `tests/unit/conftest.py` (shared git-repo fixture)
- Create: `tests/unit/test_worktree.py`

Per spec §11.4, Aegis creates one git worktree per task and agents work in isolation inside it. This module is the thin wrapper around `git worktree` commands plus a path-scope validator used later by MCP servers for defense-in-depth.

- [ ] **Step 1: Write the shared conftest with a real git repo fixture**

Create `tests/unit/conftest.py`:

```python
from __future__ import annotations

import subprocess
from pathlib import Path

import pytest


@pytest.fixture
def git_repo(tmp_path: Path) -> Path:
    """A fresh git repo with one initial commit."""
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-q", "-b", "main", str(repo)], check=True)
    subprocess.run(
        ["git", "-C", str(repo), "config", "user.email", "test@example.com"],
        check=True,
    )
    subprocess.run(
        ["git", "-C", str(repo), "config", "user.name", "Test"],
        check=True,
    )
    (repo / "README.md").write_text("# test\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(repo), "add", "README.md"], check=True)
    subprocess.run(
        ["git", "-C", str(repo), "commit", "-q", "-m", "initial"],
        check=True,
    )
    return repo
```

- [ ] **Step 2: Write the failing tests**

Create `tests/unit/test_worktree.py`:

```python
from pathlib import Path

import pytest

from aegis.core.worktree import (
    ScopeViolation,
    WorktreeError,
    create_worktree,
    list_worktrees,
    remove_worktree,
    validate_path_in_scope,
)


def test_create_and_list_worktree(tmp_path: Path, git_repo: Path) -> None:
    wt_path = tmp_path / "wt-001"
    create_worktree(git_repo, wt_path, branch="aegis/001-test")
    assert wt_path.exists()
    assert (wt_path / "README.md").exists()

    worktrees = list_worktrees(git_repo)
    paths = [w.get("worktree", "") for w in worktrees]
    assert any(str(wt_path.resolve()) == p for p in paths)


def test_remove_worktree(tmp_path: Path, git_repo: Path) -> None:
    wt_path = tmp_path / "wt-002"
    create_worktree(git_repo, wt_path, branch="aegis/002-test")
    assert wt_path.exists()

    remove_worktree(git_repo, wt_path)
    assert not wt_path.exists()


def test_create_worktree_fails_on_nonrepo(tmp_path: Path) -> None:
    with pytest.raises(WorktreeError):
        create_worktree(tmp_path, tmp_path / "wt", branch="b")


def test_validate_path_in_scope_accepts_inside(tmp_path: Path) -> None:
    scope = tmp_path / "scope"
    scope.mkdir()
    (scope / "a").mkdir()
    result = validate_path_in_scope(scope / "a", scope)
    assert result == (scope / "a").resolve()


def test_validate_path_in_scope_rejects_outside(tmp_path: Path) -> None:
    scope = tmp_path / "scope"
    scope.mkdir()
    other = tmp_path / "other"
    other.mkdir()
    with pytest.raises(ScopeViolation):
        validate_path_in_scope(other, scope)


def test_validate_path_in_scope_rejects_parent(tmp_path: Path) -> None:
    scope = tmp_path / "scope" / "inner"
    scope.mkdir(parents=True)
    with pytest.raises(ScopeViolation):
        validate_path_in_scope(scope.parent, scope)
```

- [ ] **Step 3: Run tests — they must fail**

Run: `pytest tests/unit/test_worktree.py -v`
Expected: ImportError for `aegis.core.worktree`.

- [ ] **Step 4: Write the implementation**

Create `src/aegis/core/worktree.py`:

```python
from __future__ import annotations

import subprocess
from pathlib import Path


class WorktreeError(Exception):
    """Raised when a git worktree operation fails."""


class ScopeViolation(WorktreeError):
    """Raised when a path escapes its declared scope."""


def _run_git(args: list[str], cwd: Path) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=str(cwd),
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise WorktreeError(
            f"git {' '.join(args)} failed (exit {result.returncode}): "
            f"{result.stderr.strip() or result.stdout.strip()}"
        )
    return result.stdout


def create_worktree(repo_root: Path, worktree_path: Path, branch: str) -> None:
    wt = worktree_path.resolve()
    wt.parent.mkdir(parents=True, exist_ok=True)
    _run_git(["worktree", "add", "-b", branch, str(wt)], cwd=repo_root)


def remove_worktree(repo_root: Path, worktree_path: Path) -> None:
    wt = worktree_path.resolve()
    _run_git(["worktree", "remove", "--force", str(wt)], cwd=repo_root)


def list_worktrees(repo_root: Path) -> list[dict[str, str]]:
    out = _run_git(["worktree", "list", "--porcelain"], cwd=repo_root)
    worktrees: list[dict[str, str]] = []
    current: dict[str, str] = {}
    for line in out.splitlines():
        if not line:
            if current:
                worktrees.append(current)
                current = {}
            continue
        if " " in line:
            key, _, value = line.partition(" ")
            current[key] = value
        else:
            current[line] = ""
    if current:
        worktrees.append(current)
    return worktrees


def validate_path_in_scope(path: Path, scope: Path) -> Path:
    resolved = path.resolve()
    scope_resolved = scope.resolve()
    try:
        resolved.relative_to(scope_resolved)
    except ValueError as exc:
        raise ScopeViolation(
            f"{resolved} is outside scope {scope_resolved}"
        ) from exc
    return resolved
```

- [ ] **Step 5: Run tests — they must pass**

Run: `pytest tests/unit/test_worktree.py -v`
Expected: all 6 tests pass.

- [ ] **Step 6: Commit**

```bash
git add src/aegis/core/worktree.py tests/unit/conftest.py tests/unit/test_worktree.py
git commit -m "$(cat <<'EOF'
feat(core): add git worktree helpers with scope validation

Wraps git worktree add/remove/list and adds validate_path_in_scope for
defense-in-depth path sandboxing (used later by MCP servers per spec
§11.4).

Shared fixture tests/unit/conftest.py spins up a throwaway git repo per
test via tmp_path.

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 6: Core — Budget tracker (TDD)

**Files:**
- Create: `src/aegis/core/budget.py`
- Create: `tests/unit/test_budget.py`

Per spec §11.1, every task has a USD cap and a wallclock cap. The `BudgetTracker` is the primitive the LangGraph nodes in Phase 4 will call after each LLM response to decide whether to continue or halt.

- [ ] **Step 1: Write the failing tests**

Create `tests/unit/test_budget.py`:

```python
import pytest

from aegis.core.budget import (
    Budget,
    BudgetExhausted,
    BudgetTracker,
    MODEL_PRICES,
)


def test_record_llm_call_accumulates_cost() -> None:
    tracker = BudgetTracker(Budget(usd_cap=10.0, seconds_cap=600))
    tracker.record_llm_call("claude-sonnet-4-6", input_tokens=1_000_000, output_tokens=0)
    assert tracker.state.usd_spent == pytest.approx(MODEL_PRICES["claude-sonnet-4-6"]["input"])

    tracker.record_llm_call("claude-sonnet-4-6", input_tokens=0, output_tokens=1_000_000)
    expected = (
        MODEL_PRICES["claude-sonnet-4-6"]["input"]
        + MODEL_PRICES["claude-sonnet-4-6"]["output"]
    )
    assert tracker.state.usd_spent == pytest.approx(expected)
    assert tracker.state.input_tokens == 1_000_000
    assert tracker.state.output_tokens == 1_000_000


def test_record_llm_call_unknown_model_raises() -> None:
    tracker = BudgetTracker(Budget(usd_cap=1.0, seconds_cap=60))
    with pytest.raises(ValueError):
        tracker.record_llm_call("gpt-9", input_tokens=100, output_tokens=100)


def test_exhausted_on_usd_cap() -> None:
    tracker = BudgetTracker(Budget(usd_cap=0.50, seconds_cap=600))
    tracker.record_llm_call("claude-opus-4-6", input_tokens=100_000, output_tokens=0)
    exhausted, reason = tracker.exhausted()
    assert exhausted
    assert reason is not None
    assert "USD" in reason


def test_exhausted_on_wallclock(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_time = [1000.0]

    def fake_monotonic() -> float:
        return fake_time[0]

    monkeypatch.setattr("aegis.core.budget.monotonic", fake_monotonic)
    tracker = BudgetTracker(Budget(usd_cap=10.0, seconds_cap=60))
    # After __post_init__, tracker._start == 1000.0 via the patched clock.
    assert tracker._start == 1000.0

    fake_time[0] = 1030.0  # +30s elapsed
    exhausted, reason = tracker.exhausted()
    assert exhausted is False

    fake_time[0] = 1061.0  # +61s elapsed, over cap
    exhausted, reason = tracker.exhausted()
    assert exhausted
    assert reason is not None
    assert "Wallclock" in reason


def test_remaining_values() -> None:
    tracker = BudgetTracker(Budget(usd_cap=5.0, seconds_cap=600))
    tracker.record_llm_call("claude-haiku-4-5", input_tokens=1_000_000, output_tokens=0)
    remaining = tracker.remaining()
    assert remaining["usd"] < 5.0
    assert remaining["seconds"] > 0


def test_raise_if_exhausted() -> None:
    tracker = BudgetTracker(Budget(usd_cap=0.001, seconds_cap=600))
    tracker.record_llm_call("claude-opus-4-6", input_tokens=1_000, output_tokens=0)
    with pytest.raises(BudgetExhausted):
        tracker.raise_if_exhausted()
```

- [ ] **Step 2: Run tests — they must fail**

Run: `pytest tests/unit/test_budget.py -v`
Expected: ImportError for `aegis.core.budget`.

- [ ] **Step 3: Write the implementation**

Create `src/aegis/core/budget.py`:

```python
from __future__ import annotations

from dataclasses import dataclass, field
from time import monotonic

# Prices as of 2026 (USD per million tokens). Update manually when
# Anthropic adjusts pricing. Keys match .aegis/config.yaml llm.models
# values.
MODEL_PRICES: dict[str, dict[str, float]] = {
    "claude-opus-4-6":   {"input": 15.00, "output": 75.00},
    "claude-sonnet-4-6": {"input":  3.00, "output": 15.00},
    "claude-haiku-4-5":  {"input":  1.00, "output":  5.00},
}


@dataclass
class Budget:
    usd_cap: float
    seconds_cap: float


@dataclass
class BudgetState:
    usd_spent: float = 0.0
    seconds_elapsed: float = 0.0
    input_tokens: int = 0
    output_tokens: int = 0


class BudgetExhausted(Exception):
    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


@dataclass
class BudgetTracker:
    budget: Budget
    state: BudgetState = field(default_factory=BudgetState)
    _start: float = 0.0

    def __post_init__(self) -> None:
        # Look up monotonic at runtime from the module so monkeypatching
        # in tests takes effect. Don't use field(default_factory=monotonic) —
        # that captures a direct reference at class-eval time and cannot be
        # mocked.
        if self._start == 0.0:
            self._start = monotonic()

    def record_llm_call(
        self,
        model: str,
        input_tokens: int,
        output_tokens: int,
    ) -> None:
        price = MODEL_PRICES.get(model)
        if price is None:
            raise ValueError(f"Unknown model for pricing: {model}")
        cost = (input_tokens / 1_000_000) * price["input"]
        cost += (output_tokens / 1_000_000) * price["output"]
        self.state.usd_spent += cost
        self.state.input_tokens += input_tokens
        self.state.output_tokens += output_tokens

    def _tick(self) -> None:
        self.state.seconds_elapsed = monotonic() - self._start

    def exhausted(self) -> tuple[bool, str | None]:
        self._tick()
        if self.state.usd_spent >= self.budget.usd_cap:
            return True, (
                f"USD cap ${self.budget.usd_cap:.2f} exceeded "
                f"(spent ${self.state.usd_spent:.4f})"
            )
        if self.state.seconds_elapsed >= self.budget.seconds_cap:
            return True, (
                f"Wallclock cap {self.budget.seconds_cap:.0f}s exceeded "
                f"(elapsed {self.state.seconds_elapsed:.0f}s)"
            )
        return False, None

    def remaining(self) -> dict[str, float]:
        self._tick()
        return {
            "usd": max(0.0, self.budget.usd_cap - self.state.usd_spent),
            "seconds": max(0.0, self.budget.seconds_cap - self.state.seconds_elapsed),
        }

    def raise_if_exhausted(self) -> None:
        is_exhausted, reason = self.exhausted()
        if is_exhausted:
            assert reason is not None
            raise BudgetExhausted(reason)
```

- [ ] **Step 4: Run tests — they must pass**

Run: `pytest tests/unit/test_budget.py -v`
Expected: all 6 tests pass.

- [ ] **Step 5: Commit**

```bash
git add src/aegis/core/budget.py tests/unit/test_budget.py
git commit -m "$(cat <<'EOF'
feat(core): add BudgetTracker with USD and wallclock caps

Implements spec §11.1 per-task budget enforcement: tracks USD spent
via a hardcoded price table keyed on model name (claude-opus-4-6,
claude-sonnet-4-6, claude-haiku-4-5), tracks wallclock via
time.monotonic, and exposes exhausted()/raise_if_exhausted() for the
graph nodes in Phase 4 to call after every LLM response.

Price table is manually curated (no external pricing API per spec §16).

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 7: Core — Lifecycle file-move state machine (TDD)

**Files:**
- Create: `src/aegis/core/lifecycle.py`
- Create: `tests/unit/test_lifecycle.py`

Per spec §6.4, a task's status is represented by which subdirectory of `.aegis/` its markdown file lives in. A transition is one file move plus a frontmatter status update. This module is the only place those transitions happen.

- [ ] **Step 1: Write the failing tests**

Create `tests/unit/test_lifecycle.py`:

```python
from datetime import datetime, timezone
from pathlib import Path

import pytest

from aegis.core.lifecycle import (
    STATUS_DIRS,
    find_task,
    list_tasks,
    transition,
)
from aegis.core.task import (
    Priority,
    Task,
    TaskBudget,
    TaskFrontmatter,
    TaskStatus,
    write_task,
)


@pytest.fixture
def aegis_dir(tmp_path: Path) -> Path:
    d = tmp_path / ".aegis"
    for sub in STATUS_DIRS.values():
        (d / sub).mkdir(parents=True)
    return d


def _make_task(task_id: str, title: str, status: TaskStatus) -> Task:
    return Task(
        frontmatter=TaskFrontmatter(
            id=task_id,
            title=title,
            status=status,
            priority=Priority.P2,
            budget=TaskBudget(),
            created=datetime(2026, 4, 14, tzinfo=timezone.utc),
        ),
        body=f"# {title}\n",
    )


def test_transition_moves_file_and_updates_status(aegis_dir: Path) -> None:
    task = _make_task("001", "First", TaskStatus.BACKLOG)
    src = aegis_dir / "backlog" / "001-first.md"
    write_task(task, src)

    new_path = transition(src, aegis_dir, TaskStatus.IN_PROGRESS)

    assert not src.exists()
    assert new_path.exists()
    assert new_path.parent.name == "in-progress"

    from aegis.core.task import parse_task
    loaded = parse_task(new_path)
    assert loaded.frontmatter.status == TaskStatus.IN_PROGRESS


def test_transition_creates_target_dir_if_missing(tmp_path: Path) -> None:
    aegis = tmp_path / ".aegis"
    (aegis / "backlog").mkdir(parents=True)
    task = _make_task("001", "x", TaskStatus.BACKLOG)
    src = aegis / "backlog" / "001-x.md"
    write_task(task, src)

    new_path = transition(src, aegis, TaskStatus.BLOCKED)
    assert new_path.parent.name == "blocked"
    assert new_path.exists()


def test_list_tasks_all_statuses(aegis_dir: Path) -> None:
    write_task(_make_task("001", "a", TaskStatus.BACKLOG), aegis_dir / "backlog" / "001-a.md")
    write_task(_make_task("002", "b", TaskStatus.IN_PROGRESS), aegis_dir / "in-progress" / "002-b.md")
    write_task(_make_task("003", "c", TaskStatus.DONE), aegis_dir / "done" / "003-c.md")

    results = list_tasks(aegis_dir)
    ids = [t.frontmatter.id for t, _ in results]
    assert set(ids) == {"001", "002", "003"}


def test_list_tasks_filtered_by_status(aegis_dir: Path) -> None:
    write_task(_make_task("001", "a", TaskStatus.BACKLOG), aegis_dir / "backlog" / "001-a.md")
    write_task(_make_task("002", "b", TaskStatus.IN_PROGRESS), aegis_dir / "in-progress" / "002-b.md")

    backlog = list_tasks(aegis_dir, status=TaskStatus.BACKLOG)
    assert len(backlog) == 1
    assert backlog[0][0].frontmatter.id == "001"


def test_find_task_by_id(aegis_dir: Path) -> None:
    write_task(_make_task("042", "answer", TaskStatus.REVIEW), aegis_dir / "review" / "042-answer.md")
    found = find_task(aegis_dir, "042")
    assert found is not None
    task, path = found
    assert task.frontmatter.title == "answer"
    assert "review" in str(path)


def test_find_task_missing(aegis_dir: Path) -> None:
    assert find_task(aegis_dir, "999") is None
```

- [ ] **Step 2: Run tests — they must fail**

Run: `pytest tests/unit/test_lifecycle.py -v`
Expected: ImportError for `aegis.core.lifecycle`.

- [ ] **Step 3: Write the implementation**

Create `src/aegis/core/lifecycle.py`:

```python
from __future__ import annotations

from pathlib import Path

from aegis.core.task import (
    Task,
    TaskStatus,
    parse_task,
    write_task,
)


STATUS_DIRS: dict[TaskStatus, str] = {
    TaskStatus.BACKLOG: "backlog",
    TaskStatus.IN_PROGRESS: "in-progress",
    TaskStatus.REVIEW: "review",
    TaskStatus.DONE: "done",
    TaskStatus.BLOCKED: "blocked",
    TaskStatus.REJECTED: "rejected",
}


class LifecycleError(Exception):
    """Raised on invalid lifecycle operations."""


def transition(
    task_path: Path,
    aegis_dir: Path,
    to_status: TaskStatus,
) -> Path:
    """Update the task's status and move its file to the matching subdir.

    Returns the new path.
    """
    if not task_path.exists():
        raise LifecycleError(f"task not found: {task_path}")
    task = parse_task(task_path)
    task.frontmatter.status = to_status
    target_dir = aegis_dir / STATUS_DIRS[to_status]
    target_dir.mkdir(parents=True, exist_ok=True)
    # Write with the updated status back to the source first, then move,
    # so the final file on disk reflects the new status atomically.
    write_task(task, task_path)
    new_path = target_dir / task_path.name
    task_path.rename(new_path)
    return new_path


def list_tasks(
    aegis_dir: Path,
    status: TaskStatus | None = None,
) -> list[tuple[Task, Path]]:
    """Return all tasks (optionally filtered by status), sorted by id."""
    result: list[tuple[Task, Path]] = []
    statuses: list[TaskStatus] = (
        [status] if status is not None else list(TaskStatus)
    )
    for s in statuses:
        d = aegis_dir / STATUS_DIRS[s]
        if not d.exists():
            continue
        for f in sorted(d.glob("*.md")):
            result.append((parse_task(f), f))
    return result


def find_task(aegis_dir: Path, task_id: str) -> tuple[Task, Path] | None:
    for s in TaskStatus:
        d = aegis_dir / STATUS_DIRS[s]
        if not d.exists():
            continue
        for f in d.glob(f"{task_id}-*.md"):
            return parse_task(f), f
    return None
```

- [ ] **Step 4: Run tests — they must pass**

Run: `pytest tests/unit/test_lifecycle.py -v`
Expected: all 6 tests pass.

- [ ] **Step 5: Commit**

```bash
git add src/aegis/core/lifecycle.py tests/unit/test_lifecycle.py
git commit -m "$(cat <<'EOF'
feat(core): add lifecycle state machine for task file moves

Implements spec §6.4: STATUS_DIRS mapping, transition() to atomically
update frontmatter status and move the markdown file to the matching
subdirectory, list_tasks() with optional status filter, and
find_task() lookup by id across all statuses.

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 8: CLI — Typer entrypoint and stub commands

**Files:**
- Create: `src/aegis/cli/main.py`
- Create: `src/aegis/cli/commands/stubs.py`
- Create: `tests/unit/test_cli_main.py`

This task wires the `aegis` console script to a Typer app and registers placeholder commands for everything not yet implemented (`run`, `daemon`, `approve`, etc.) so that running any of them prints a helpful "not yet implemented — see Phase N" message instead of a crash.

- [ ] **Step 1: Write the failing test**

Create `tests/unit/test_cli_main.py`:

```python
from typer.testing import CliRunner

from aegis.cli.main import app

runner = CliRunner()


def test_cli_shows_version() -> None:
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert "0.1.0" in result.output


def test_cli_help_lists_subcommands() -> None:
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    for name in ["run", "daemon", "approve", "web"]:
        assert name in result.output


def test_cli_stub_run_reports_not_implemented() -> None:
    result = runner.invoke(app, ["run"])
    assert result.exit_code != 0
    assert "Phase 4" in result.output
```

- [ ] **Step 2: Run tests — they must fail**

Run: `pytest tests/unit/test_cli_main.py -v`
Expected: ImportError for `aegis.cli.main`.

- [ ] **Step 3: Write the stubs module**

Create `src/aegis/cli/commands/stubs.py`:

```python
from __future__ import annotations

import typer


def _not_implemented(command: str, phase: str) -> None:
    typer.echo(
        f"`aegis {command}` is not implemented yet. See Phase {phase} "
        f"in docs/superpowers/specs/2026-04-14-aegis-ai-engineering-team-design.md",
        err=True,
    )
    raise typer.Exit(code=2)


def register_stubs(app: typer.Typer) -> None:
    @app.command(help="Run the team graph in the foreground. (Phase 4)")
    def run(
        parallel: int = typer.Option(None, "--parallel"),
        once: bool = typer.Option(False, "--once"),
        task: str | None = typer.Option(None, "--task"),
    ) -> None:
        _not_implemented("run", "4")

    daemon_app = typer.Typer(help="Background worker mode. (Phase 4)")

    @daemon_app.command("start")
    def daemon_start() -> None:
        _not_implemented("daemon start", "4")

    @daemon_app.command("stop")
    def daemon_stop() -> None:
        _not_implemented("daemon stop", "4")

    @daemon_app.command("status")
    def daemon_status() -> None:
        _not_implemented("daemon status", "4")

    @daemon_app.command("restart")
    def daemon_restart() -> None:
        _not_implemented("daemon restart", "4")

    app.add_typer(daemon_app, name="daemon")

    @app.command(help="Show current kanban state. (Phase 4)")
    def status(watch: bool = typer.Option(False, "--watch")) -> None:
        _not_implemented("status", "4")

    @app.command(help="Inspect a task's full trajectory. (Phase 4)")
    def inspect(task_id: str) -> None:
        _not_implemented("inspect", "4")

    @app.command(help="Tail a task's log. (Phase 5)")
    def logs(task_id: str, follow: bool = typer.Option(False, "--follow")) -> None:
        _not_implemented("logs", "5")

    @app.command(help="Open a task trace in the browser. (Phase 5)")
    def trace(task_id: str) -> None:
        _not_implemented("trace", "5")

    @app.command(help="Approve and merge a completed task. (Phase 4)")
    def approve(task_id: str) -> None:
        _not_implemented("approve", "4")

    @app.command(help="Reject a completed task. (Phase 4)")
    def reject(task_id: str, reason: str | None = typer.Argument(None)) -> None:
        _not_implemented("reject", "4")

    @app.command(help="Retry a blocked or rejected task. (Phase 4)")
    def retry(
        task_id: str,
        budget_usd: float | None = typer.Option(None, "--budget-usd"),
        from_node: str | None = typer.Option(None, "--from"),
    ) -> None:
        _not_implemented("retry", "4")

    @app.command(help="Kill switch. (Phase 4)")
    def stop(task_id: str | None = typer.Argument(None)) -> None:
        _not_implemented("stop", "4")

    @app.command(help="Start the read-only dashboard. (Phase 6)")
    def web(
        port: int = typer.Option(8765, "--port"),
        host: str = typer.Option("127.0.0.1", "--host"),
    ) -> None:
        _not_implemented("web", "6")
```

- [ ] **Step 4: Write the main entrypoint**

Create `src/aegis/cli/main.py`:

```python
from __future__ import annotations

import typer

from aegis import __version__
from aegis.cli.commands.stubs import register_stubs


app = typer.Typer(
    name="aegis",
    help="Aegis — personal AI engineering team CLI.",
    no_args_is_help=True,
)


def _version_callback(value: bool) -> None:
    if value:
        typer.echo(f"aegis {__version__}")
        raise typer.Exit()


@app.callback()
def _root(
    version: bool = typer.Option(
        False,
        "--version",
        callback=_version_callback,
        is_eager=True,
        help="Show version and exit.",
    ),
) -> None:
    """Aegis CLI root."""


register_stubs(app)


# Real commands from Tasks 9-11 will be registered below in later tasks.
```

- [ ] **Step 5: Run tests — they must pass**

Run: `pytest tests/unit/test_cli_main.py -v`
Expected: 3 tests pass.

- [ ] **Step 6: Verify the CLI works end-to-end**

Run: `aegis --version`
Expected: `aegis 0.1.0`

Run: `aegis --help`
Expected: help output listing `daemon`, `run`, `status`, `approve`, etc.

Run: `aegis run`
Expected: non-zero exit, stderr message `aegis run is not implemented yet. See Phase 4 ...`

- [ ] **Step 7: Commit**

```bash
git add src/aegis/cli/main.py src/aegis/cli/commands/stubs.py tests/unit/test_cli_main.py
git commit -m "$(cat <<'EOF'
feat(cli): wire Typer entrypoint with --version and Phase 4+ stubs

Adds the aegis console script entrypoint (src/aegis/cli/main.py) with
--version support and registers every not-yet-implemented command
(run/daemon/status/inspect/logs/trace/approve/reject/retry/stop/web) as
a stub that reports the Phase where it will be implemented. This lets
users discover the full CLI surface even during Phase 1.

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 9: CLI — `aegis init` (TDD)

**Files:**
- Create: `src/aegis/cli/commands/init.py`
- Modify: `src/aegis/cli/main.py` (register the command)
- Create: `tests/unit/test_cli_init.py`

This is the first real command. It refuses to run outside a git repo, creates the `.aegis/` tree, writes a default `config.yaml`, and appends Aegis-specific entries to `.gitignore`.

- [ ] **Step 1: Write the failing tests**

Create `tests/unit/test_cli_init.py`:

```python
from pathlib import Path

import pytest
import typer

from aegis.cli.commands.init import run_init
from aegis.core.config import load_config


def test_init_creates_directory_structure(git_repo: Path) -> None:
    aegis_dir = run_init(git_repo, force=False)

    assert aegis_dir == (git_repo / ".aegis").resolve()
    assert (aegis_dir / "backlog").is_dir()
    assert (aegis_dir / "in-progress").is_dir()
    assert (aegis_dir / "review").is_dir()
    assert (aegis_dir / "done").is_dir()
    assert (aegis_dir / "blocked").is_dir()
    assert (aegis_dir / "rejected").is_dir()
    assert (aegis_dir / ".worktrees").is_dir()
    assert (aegis_dir / "trace").is_dir()
    assert (aegis_dir / "config.yaml").is_file()

    cfg = load_config(aegis_dir / "config.yaml")
    assert cfg.project.name == git_repo.name


def test_init_refuses_non_git_dir(tmp_path: Path) -> None:
    with pytest.raises(typer.BadParameter):
        run_init(tmp_path, force=False)


def test_init_refuses_existing_without_force(git_repo: Path) -> None:
    run_init(git_repo, force=False)
    with pytest.raises(typer.BadParameter):
        run_init(git_repo, force=False)


def test_init_with_force_overwrites(git_repo: Path) -> None:
    run_init(git_repo, force=False)
    run_init(git_repo, force=True)  # must not raise
    assert (git_repo / ".aegis" / "config.yaml").is_file()


def test_init_appends_gitignore_entries(git_repo: Path) -> None:
    run_init(git_repo, force=False)
    gitignore = (git_repo / ".gitignore").read_text(encoding="utf-8")
    assert ".aegis/.worktrees/" in gitignore
    assert ".aegis/trace/" in gitignore
    assert ".aegis/checkpoint.db" in gitignore
```

- [ ] **Step 2: Run tests — they must fail**

Run: `pytest tests/unit/test_cli_init.py -v`
Expected: ImportError for `aegis.cli.commands.init`.

- [ ] **Step 3: Write the implementation**

Create `src/aegis/cli/commands/init.py`:

```python
from __future__ import annotations

from pathlib import Path

import typer

from aegis.core.config import default_config, dump_config

AEGIS_DIRNAME = ".aegis"
STATUS_SUBDIRS = (
    "backlog",
    "in-progress",
    "review",
    "done",
    "blocked",
    "rejected",
)
_GITIGNORE_ENTRIES = (
    ".aegis/.worktrees/",
    ".aegis/trace/",
    ".aegis/checkpoint.db",
    ".aegis/.daemon.pid",
    ".aegis/.stop",
    ".aegis/.stop.*",
)


def _ensure_gitignore(target: Path) -> None:
    gi = target / ".gitignore"
    existing = gi.read_text(encoding="utf-8") if gi.exists() else ""
    missing = [e for e in _GITIGNORE_ENTRIES if e not in existing]
    if not missing:
        return
    prefix = "" if existing.endswith("\n") or not existing else "\n"
    block = prefix + "\n# Aegis\n" + "\n".join(missing) + "\n"
    gi.write_text(existing + block, encoding="utf-8")


def run_init(target: Path, force: bool = False) -> Path:
    target = target.resolve()
    if not (target / ".git").exists():
        raise typer.BadParameter(f"{target} is not a git repository")
    aegis_dir = target / AEGIS_DIRNAME
    if aegis_dir.exists() and not force:
        raise typer.BadParameter(
            f"{aegis_dir} already exists. Use --force to overwrite."
        )
    for sub in STATUS_SUBDIRS:
        (aegis_dir / sub).mkdir(parents=True, exist_ok=True)
    (aegis_dir / ".worktrees").mkdir(exist_ok=True)
    (aegis_dir / "trace").mkdir(exist_ok=True)
    cfg = default_config(project_name=target.name)
    dump_config(cfg, aegis_dir / "config.yaml")
    _ensure_gitignore(target)
    return aegis_dir


def register(app: typer.Typer) -> None:
    @app.command(help="Initialize .aegis/ in the current git repository.")
    def init(
        force: bool = typer.Option(False, "--force", help="Overwrite existing .aegis/"),
    ) -> None:
        aegis_dir = run_init(Path.cwd(), force=force)
        typer.echo(f"Initialized Aegis at {aegis_dir}")
```

- [ ] **Step 4: Register in `main.py`**

Modify `src/aegis/cli/main.py`. Find:

```python
register_stubs(app)


# Real commands from Tasks 9-11 will be registered below in later tasks.
```

Replace with:

```python
register_stubs(app)

from aegis.cli.commands.init import register as register_init  # noqa: E402
register_init(app)

# Real commands from Tasks 10-11 will be registered below in later tasks.
```

- [ ] **Step 5: Run tests — they must pass**

Run: `pytest tests/unit/test_cli_init.py -v`
Expected: all 5 tests pass.

- [ ] **Step 6: End-to-end smoke**

```bash
mkdir /tmp/aegis-smoke && cd /tmp/aegis-smoke && git init -q && cd - && aegis init --help
```
Expected: help text for `aegis init`.

Then:
```bash
(cd /tmp/aegis-smoke && aegis init)
ls /tmp/aegis-smoke/.aegis
cat /tmp/aegis-smoke/.aegis/config.yaml
cat /tmp/aegis-smoke/.gitignore
rm -rf /tmp/aegis-smoke
```
Expected: `.aegis/` populated, config.yaml with model routing visible, `.gitignore` has Aegis block.

- [ ] **Step 7: Commit**

```bash
git add src/aegis/cli/commands/init.py src/aegis/cli/main.py tests/unit/test_cli_init.py
git commit -m "$(cat <<'EOF'
feat(cli): implement aegis init

Refuses to run outside a git repo, creates .aegis/{backlog,in-progress,
review,done,blocked,rejected,.worktrees,trace}/, writes a default
config.yaml (from core.config.default_config), and appends Aegis
entries to the target repo's .gitignore.

--force overwrites an existing .aegis/.

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 10: CLI — `aegis task add|list|show|edit` (TDD)

**Files:**
- Create: `src/aegis/cli/commands/task.py`
- Modify: `src/aegis/cli/main.py` (register)
- Create: `tests/unit/test_cli_task.py`

Four subcommands for authoring and browsing markdown tasks.

- [ ] **Step 1: Write the failing tests**

Create `tests/unit/test_cli_task.py`:

```python
from pathlib import Path

import pytest

from aegis.cli.commands.init import run_init
from aegis.cli.commands.task import (
    run_task_add,
    run_task_list,
    run_task_show,
)
from aegis.core.task import TaskStatus


@pytest.fixture
def initialized_repo(git_repo: Path) -> Path:
    run_init(git_repo, force=False)
    return git_repo


def test_task_add_creates_backlog_file(initialized_repo: Path) -> None:
    path = run_task_add(
        initialized_repo,
        title="Add rate limiting",
        priority="P1",
        budget_usd=2.0,
        budget_minutes=30,
    )
    assert path.parent.name == "backlog"
    assert path.name.startswith("001-")
    assert path.name.endswith(".md")

    from aegis.core.task import parse_task
    task = parse_task(path)
    assert task.frontmatter.id == "001"
    assert task.frontmatter.title == "Add rate limiting"
    assert task.frontmatter.priority.value == "P1"
    assert task.frontmatter.status == TaskStatus.BACKLOG


def test_task_add_assigns_incrementing_ids(initialized_repo: Path) -> None:
    p1 = run_task_add(initialized_repo, title="one", priority="P2", budget_usd=2.0, budget_minutes=30)
    p2 = run_task_add(initialized_repo, title="two", priority="P2", budget_usd=2.0, budget_minutes=30)
    assert p1.name.startswith("001-")
    assert p2.name.startswith("002-")


def test_task_list_returns_all_tasks(initialized_repo: Path) -> None:
    run_task_add(initialized_repo, title="a", priority="P2", budget_usd=2.0, budget_minutes=30)
    run_task_add(initialized_repo, title="b", priority="P2", budget_usd=2.0, budget_minutes=30)
    rows = run_task_list(initialized_repo, status=None)
    assert len(rows) == 2
    assert {r["id"] for r in rows} == {"001", "002"}


def test_task_list_filtered_by_status(initialized_repo: Path) -> None:
    run_task_add(initialized_repo, title="x", priority="P2", budget_usd=2.0, budget_minutes=30)
    rows = run_task_list(initialized_repo, status="done")
    assert rows == []
    rows = run_task_list(initialized_repo, status="backlog")
    assert len(rows) == 1


def test_task_show_returns_content(initialized_repo: Path) -> None:
    run_task_add(initialized_repo, title="answer everything", priority="P0", budget_usd=3.0, budget_minutes=45)
    rendered = run_task_show(initialized_repo, task_id="001")
    assert "answer everything" in rendered
    assert "P0" in rendered
```

- [ ] **Step 2: Run tests — they must fail**

Run: `pytest tests/unit/test_cli_task.py -v`
Expected: ImportError for `aegis.cli.commands.task`.

- [ ] **Step 3: Write the implementation**

Create `src/aegis/cli/commands/task.py`:

```python
from __future__ import annotations

import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import typer

from aegis.cli.commands.init import AEGIS_DIRNAME
from aegis.core.lifecycle import find_task, list_tasks
from aegis.core.task import (
    Priority,
    Task,
    TaskBudget,
    TaskFrontmatter,
    TaskStatus,
    next_task_id,
    serialize_task,
    task_filename,
    write_task,
)


def _aegis_dir_for(target: Path) -> Path:
    d = target / AEGIS_DIRNAME
    if not d.exists():
        raise typer.BadParameter(
            f"No .aegis/ directory at {target}. Run `aegis init` first."
        )
    return d


def run_task_add(
    target: Path,
    *,
    title: str,
    priority: str,
    budget_usd: float,
    budget_minutes: int,
) -> Path:
    aegis_dir = _aegis_dir_for(target)
    task_id = next_task_id(aegis_dir)
    fm = TaskFrontmatter(
        id=task_id,
        title=title,
        status=TaskStatus.BACKLOG,
        priority=Priority(priority),
        budget=TaskBudget(usd=budget_usd, minutes=budget_minutes),
        created=datetime.now(tz=timezone.utc),
    )
    body = f"# {title}\n\n<!-- describe the task here -->\n"
    task = Task(frontmatter=fm, body=body)
    path = aegis_dir / "backlog" / task_filename(task_id, title)
    write_task(task, path)
    return path


def run_task_list(
    target: Path,
    *,
    status: str | None,
) -> list[dict[str, Any]]:
    aegis_dir = _aegis_dir_for(target)
    status_enum = TaskStatus(status) if status else None
    rows: list[dict[str, Any]] = []
    for task, path in list_tasks(aegis_dir, status=status_enum):
        rows.append(
            {
                "id": task.frontmatter.id,
                "title": task.frontmatter.title,
                "status": task.frontmatter.status.value,
                "priority": task.frontmatter.priority.value,
                "path": str(path),
            }
        )
    return rows


def run_task_show(target: Path, *, task_id: str) -> str:
    aegis_dir = _aegis_dir_for(target)
    found = find_task(aegis_dir, task_id)
    if found is None:
        raise typer.BadParameter(f"task {task_id} not found")
    task, _ = found
    return serialize_task(task)


def run_task_edit(target: Path, *, task_id: str) -> None:
    aegis_dir = _aegis_dir_for(target)
    found = find_task(aegis_dir, task_id)
    if found is None:
        raise typer.BadParameter(f"task {task_id} not found")
    _, path = found
    editor = os.environ.get("EDITOR", "vi")
    subprocess.run([editor, str(path)], check=False)


def register(app: typer.Typer) -> None:
    task_app = typer.Typer(help="Task management: add, list, show, edit.")

    @task_app.command("add", help="Create a new task in backlog/.")
    def add(
        title: str = typer.Argument(..., help="Task title"),
        priority: str = typer.Option("P2", "--priority", help="P0|P1|P2|P3"),
        budget_usd: float = typer.Option(2.0, "--budget-usd"),
        budget_min: int = typer.Option(30, "--budget-min"),
    ) -> None:
        path = run_task_add(
            Path.cwd(),
            title=title,
            priority=priority,
            budget_usd=budget_usd,
            budget_minutes=budget_min,
        )
        typer.echo(f"Created {path}")

    @task_app.command("list", help="List tasks (optionally filtered by status).")
    def list_cmd(
        status: str | None = typer.Option(None, "--status"),
    ) -> None:
        rows = run_task_list(Path.cwd(), status=status)
        if not rows:
            typer.echo("(no tasks)")
            return
        for r in rows:
            typer.echo(f"{r['id']}  [{r['status']:11}]  {r['priority']}  {r['title']}")

    @task_app.command("show", help="Print a task's full markdown.")
    def show(task_id: str = typer.Argument(...)) -> None:
        rendered = run_task_show(Path.cwd(), task_id=task_id)
        typer.echo(rendered)

    @task_app.command("edit", help="Open a task in $EDITOR.")
    def edit(task_id: str = typer.Argument(...)) -> None:
        run_task_edit(Path.cwd(), task_id=task_id)

    app.add_typer(task_app, name="task")
```

- [ ] **Step 4: Register in `main.py`**

Modify `src/aegis/cli/main.py`. Find:

```python
from aegis.cli.commands.init import register as register_init  # noqa: E402
register_init(app)

# Real commands from Tasks 10-11 will be registered below in later tasks.
```

Replace with:

```python
from aegis.cli.commands.init import register as register_init  # noqa: E402
from aegis.cli.commands.task import register as register_task  # noqa: E402

register_init(app)
register_task(app)

# Real command from Task 11 will be registered below.
```

- [ ] **Step 5: Run tests — they must pass**

Run: `pytest tests/unit/test_cli_task.py -v`
Expected: 5 tests pass.

- [ ] **Step 6: Commit**

```bash
git add src/aegis/cli/commands/task.py src/aegis/cli/main.py tests/unit/test_cli_task.py
git commit -m "$(cat <<'EOF'
feat(cli): implement aegis task add|list|show|edit

Four subcommands for authoring markdown tasks (spec §6.3):
- add creates .aegis/backlog/<id>-<slug>.md with frontmatter seeded
  from CLI flags (priority, budget-usd, budget-min)
- list prints a compact table filtered by --status
- show prints a task's full serialized markdown
- edit opens the task in $EDITOR

All commands resolve the target project from cwd and refuse to run if
.aegis/ is missing.

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 11: CLI — `aegis config get|set|edit` (TDD)

**Files:**
- Create: `src/aegis/cli/commands/config.py`
- Modify: `src/aegis/cli/main.py` (register)
- Create: `tests/unit/test_cli_config.py`

Flat dotted-path config access, e.g. `aegis config set budget.task.usd 3.00`.

- [ ] **Step 1: Write the failing tests**

Create `tests/unit/test_cli_config.py`:

```python
from pathlib import Path

import pytest

from aegis.cli.commands.config import run_config_get, run_config_set
from aegis.cli.commands.init import run_init


@pytest.fixture
def initialized_repo(git_repo: Path) -> Path:
    run_init(git_repo, force=False)
    return git_repo


def test_config_get_returns_default(initialized_repo: Path) -> None:
    assert run_config_get(initialized_repo, "budget.task.usd") == "2.0"
    assert run_config_get(initialized_repo, "gates.strategy") == "merge_only"
    assert run_config_get(initialized_repo, "llm.models.pm") == "claude-opus-4-6"


def test_config_set_persists_value(initialized_repo: Path) -> None:
    run_config_set(initialized_repo, "budget.task.usd", "3.50")
    assert run_config_get(initialized_repo, "budget.task.usd") == "3.5"


def test_config_set_model_routing(initialized_repo: Path) -> None:
    run_config_set(initialized_repo, "llm.models.dev", "claude-haiku-4-5")
    assert run_config_get(initialized_repo, "llm.models.dev") == "claude-haiku-4-5"


def test_config_get_unknown_key_raises(initialized_repo: Path) -> None:
    import typer
    with pytest.raises(typer.BadParameter):
        run_config_get(initialized_repo, "nope.nope")


def test_config_set_rejects_invalid_value(initialized_repo: Path) -> None:
    import typer
    with pytest.raises(typer.BadParameter):
        run_config_set(initialized_repo, "gates.strategy", "anarchy")
```

- [ ] **Step 2: Run tests — they must fail**

Run: `pytest tests/unit/test_cli_config.py -v`
Expected: ImportError for `aegis.cli.commands.config`.

- [ ] **Step 3: Write the implementation**

Create `src/aegis/cli/commands/config.py`:

```python
from __future__ import annotations

import os
import subprocess
from pathlib import Path
from typing import Any

import typer
import yaml
from pydantic import ValidationError

from aegis.cli.commands.init import AEGIS_DIRNAME
from aegis.core.config import AegisConfig, dump_config, load_config


def _config_path(target: Path) -> Path:
    p = target / AEGIS_DIRNAME / "config.yaml"
    if not p.exists():
        raise typer.BadParameter(
            f"{p} not found. Run `aegis init` first."
        )
    return p


def _walk(data: Any, parts: list[str]) -> Any:
    cur = data
    for i, part in enumerate(parts):
        if isinstance(cur, dict) and part in cur:
            cur = cur[part]
        else:
            joined = ".".join(parts[: i + 1])
            raise typer.BadParameter(f"Unknown config key: {joined}")
    return cur


def _set_in(data: Any, parts: list[str], value: Any) -> None:
    cur = data
    for part in parts[:-1]:
        if not isinstance(cur, dict) or part not in cur:
            raise typer.BadParameter(f"Unknown config key segment: {part}")
        cur = cur[part]
    if not isinstance(cur, dict) or parts[-1] not in cur:
        raise typer.BadParameter(f"Unknown config key: {'.'.join(parts)}")
    cur[parts[-1]] = value


def _coerce(raw: str) -> Any:
    # Let YAML do the coercion (handles int/float/bool/null/str).
    return yaml.safe_load(raw)


def run_config_get(target: Path, key: str) -> str:
    cfg_path = _config_path(target)
    cfg = load_config(cfg_path)
    data = cfg.model_dump(mode="python")
    value = _walk(data, key.split("."))
    if isinstance(value, (dict, list)):
        return yaml.safe_dump(value, default_flow_style=False).strip()
    return str(value)


def run_config_set(target: Path, key: str, value: str) -> None:
    cfg_path = _config_path(target)
    cfg = load_config(cfg_path)
    data = cfg.model_dump(mode="python")
    _set_in(data, key.split("."), _coerce(value))
    try:
        new_cfg = AegisConfig.model_validate(data)
    except ValidationError as exc:
        raise typer.BadParameter(f"Invalid value for {key}: {exc}") from exc
    dump_config(new_cfg, cfg_path)


def run_config_edit(target: Path) -> None:
    cfg_path = _config_path(target)
    editor = os.environ.get("EDITOR", "vi")
    subprocess.run([editor, str(cfg_path)], check=False)


def register(app: typer.Typer) -> None:
    config_app = typer.Typer(help="Read and edit .aegis/config.yaml.")

    @config_app.command("get", help="Print a config value by dotted key.")
    def get(key: str = typer.Argument(...)) -> None:
        typer.echo(run_config_get(Path.cwd(), key))

    @config_app.command("set", help="Set a config value by dotted key.")
    def set_cmd(
        key: str = typer.Argument(...),
        value: str = typer.Argument(...),
    ) -> None:
        run_config_set(Path.cwd(), key, value)

    @config_app.command("edit", help="Open config.yaml in $EDITOR.")
    def edit_cmd() -> None:
        run_config_edit(Path.cwd())

    app.add_typer(config_app, name="config")
```

- [ ] **Step 4: Register in `main.py`**

Modify `src/aegis/cli/main.py`. Find:

```python
from aegis.cli.commands.init import register as register_init  # noqa: E402
from aegis.cli.commands.task import register as register_task  # noqa: E402

register_init(app)
register_task(app)

# Real command from Task 11 will be registered below.
```

Replace with:

```python
from aegis.cli.commands.init import register as register_init  # noqa: E402
from aegis.cli.commands.task import register as register_task  # noqa: E402
from aegis.cli.commands.config import register as register_config  # noqa: E402

register_init(app)
register_task(app)
register_config(app)
```

- [ ] **Step 5: Run tests — they must pass**

Run: `pytest tests/unit/test_cli_config.py -v`
Expected: 5 tests pass.

- [ ] **Step 6: Commit**

```bash
git add src/aegis/cli/commands/config.py src/aegis/cli/main.py tests/unit/test_cli_config.py
git commit -m "$(cat <<'EOF'
feat(cli): implement aegis config get|set|edit

Dotted-path config access against .aegis/config.yaml. Values are
parsed via yaml.safe_load so int/float/bool types work naturally, and
every set triggers full AegisConfig re-validation to reject invalid
values (e.g. bogus gate strategies).

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 12: Replace CI workflow

**Files:**
- Modify: `.github/workflows/ci.yml`

The existing CI is wired for the old `app/` layout and runs on Python 3.10/3.11. Phase 1 uses `src/aegis/` and requires 3.11+.

- [ ] **Step 1: Read the existing file**

Run: `cat .github/workflows/ci.yml`
Note the current matrix and install steps (they reference the deleted `requirements.txt`).

- [ ] **Step 2: Replace with new workflow**

Overwrite `.github/workflows/ci.yml`:

```yaml
name: CI

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  test:
    runs-on: ubuntu-latest
    strategy:
      fail-fast: false
      matrix:
        python-version: ["3.11", "3.12"]
    steps:
      - uses: actions/checkout@v4

      - name: Set up Python ${{ matrix.python-version }}
        uses: actions/setup-python@v5
        with:
          python-version: ${{ matrix.python-version }}

      - name: Install dependencies
        run: |
          python -m pip install --upgrade pip
          pip install -e ".[dev]"

      - name: Ruff lint
        run: ruff check src tests

      - name: Ruff format check
        run: ruff format --check src tests

      - name: Mypy
        run: mypy

      - name: Unit tests
        run: pytest tests/unit
```

- [ ] **Step 3: Sanity-check locally**

Run: `make lint`
Expected: ruff passes. If it fails, fix flagged lines inline until green. Commit the ruff fixes as part of this task.

Run: `make typecheck`
Expected: mypy passes under strict mode. If it fails, add the needed annotations (do not relax strict mode).

Run: `make test`
Expected: all unit tests green.

- [ ] **Step 4: Commit**

```bash
git add .github/workflows/ci.yml
git commit -m "$(cat <<'EOF'
ci: rewrite workflow for src/aegis layout and Python 3.11/3.12

Drops the legacy app/-layout CI. New pipeline: checkout, setup Python
(matrix 3.11/3.12), pip install -e ".[dev]", ruff check, ruff format
check, mypy strict, pytest tests/unit. No LLM calls on CI.

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 13: Full-suite validation and Phase 1 completion commit

**Files:**
- (none modified — this task is pure verification + a marker commit)

- [ ] **Step 1: Run the full test suite**

Run: `make test`
Expected: every test green. If anything fails, fix inline before proceeding — do NOT mark Phase 1 complete with red tests.

- [ ] **Step 2: Run the linters**

Run: `make lint && make typecheck`
Expected: both pass. Fix any issues inline.

- [ ] **Step 3: Manual smoke test**

```bash
mkdir /tmp/aegis-e2e && cd /tmp/aegis-e2e && git init -q
aegis --version
aegis init
aegis task add "Write README" --priority P1 --budget-usd 1.50 --budget-min 20
aegis task add "Add tests" --priority P2
aegis task list
aegis task show 001
aegis config get llm.models.pm
aegis config set budget.task.usd 2.5
aegis config get budget.task.usd
aegis run
cd - && rm -rf /tmp/aegis-e2e
```

Expected sequence:
- `aegis --version` prints `aegis 0.1.0`
- `aegis init` prints `Initialized Aegis at /tmp/aegis-e2e/.aegis`
- Two task add lines
- `aegis task list` shows 2 rows
- `aegis task show 001` prints the full markdown with P1 and budget
- `aegis config get llm.models.pm` prints `claude-opus-4-6`
- `aegis config set` silently succeeds, `get` returns `2.5`
- `aegis run` exits non-zero with `Phase 4` in stderr

- [ ] **Step 4: Verify the git log tells a clean story**

Run: `git log --oneline main..HEAD` or `git log --oneline -15`
Expected: a sequence of commits like:
```
feat(cli): implement aegis config get|set|edit
feat(cli): implement aegis task add|list|show|edit
feat(cli): implement aegis init
feat(cli): wire Typer entrypoint with --version and Phase 4+ stubs
feat(core): add lifecycle state machine for task file moves
feat(core): add BudgetTracker with USD and wallclock caps
feat(core): add git worktree helpers with scope validation
feat(core): add markdown task parser with YAML frontmatter
feat(core): add AegisConfig pydantic schema with YAML roundtrip
chore: scaffold src/aegis package with pyproject.toml and empty modules
chore: remove legacy Aegis-MCP Slack/security scaffold
ci: rewrite workflow for src/aegis layout and Python 3.11/3.12
docs: add design spec for Aegis AI Engineering Team redesign
```
(Order will differ depending on exact commit sequence; the CI commit will be near the end.)

- [ ] **Step 5: Push**

Run: `git push origin main`
Expected: clean push.

Do not force-push. If the remote has diverged (someone else pushed), pull/rebase and re-run Steps 1–3 before pushing.

- [ ] **Step 6: Tag Phase 1**

```bash
git tag -a phase-1-complete -m "Phase 1: teardown + scaffolding + core layer + CLI skeleton"
git push origin phase-1-complete
```

Expected: tag pushed. This is the bookmark for "Aegis is installable and has a working CLI, but no agents yet".

---

## Appendix A — Quick reference: what works after Phase 1

```bash
# Install
pip install -e ".[dev]"

# Initialize in any git repo
cd ~/projects/some-repo
aegis init

# Author tasks
aegis task add "Add auth endpoint" --priority P1 --budget-usd 2.5 --budget-min 30
vim .aegis/backlog/002-something.md   # direct authoring also works

# Browse
aegis task list
aegis task list --status backlog
aegis task show 001
aegis task edit 001

# Configure
aegis config get budget.task.usd
aegis config set budget.task.usd 3.00
aegis config edit

# Phase 1 does NOT provide these yet — they will stub out cleanly:
aegis run          # → error: Phase 4
aegis daemon start # → error: Phase 4
aegis approve 001  # → error: Phase 4
aegis web          # → error: Phase 6
```

## Appendix B — Handoff to Phase 2

Phase 2 will:
1. Add `mcp` as a dependency in `pyproject.toml`.
2. Implement `aegis-git-mcp`, `aegis-fs-mcp`, `aegis-shell-mcp`, `aegis-project-index-mcp` under `src/aegis/mcp_servers/` using the `mcp` SDK.
3. Add per-server console scripts to `pyproject.toml`.
4. Add `tests/unit/test_git_mcp.py`, etc. — testing MCP tools with in-process stdio transport.
5. No changes to Phase 1 modules are expected.

The `worktree.validate_path_in_scope` helper built in Task 5 will be the defensive check every MCP server uses before any file-system operation. The `BudgetTracker` built in Task 6 is not yet called by any production code — that wiring happens in Phase 4 when LangGraph nodes exist.

---

*End of Phase 1 implementation plan.*
