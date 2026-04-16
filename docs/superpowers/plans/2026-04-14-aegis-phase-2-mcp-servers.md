# Aegis Phase 2 — First-party MCP Servers Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deliver four stdio-based MCP servers (`aegis-git-mcp`, `aegis-fs-mcp`, `aegis-shell-mcp`, `aegis-project-index-mcp`) as installable console scripts, each path-scoped via a `--scope` argument and defended by the `validate_path_in_scope` helper built in Phase 1, with comprehensive unit tests that do not require spinning up a real MCP client.

**Architecture:** Each server lives in a single module under `src/aegis/mcp_servers/`. Tool implementations are exposed as free functions `tool(scope: Path, ...)` so they are unit-testable in isolation. A thin `build_server(scope: Path) -> FastMCP` wraps those impls with the FastMCP decorator for stdio transport. A tiny `_base.py` module centralizes `--scope` parsing and scope-relative path resolution so all four servers share the same contract. Scope enforcement is always defense-in-depth — the graph runner will ALSO pass scoped paths, but the server refuses anything outside its declared scope regardless.

**Tech Stack:** Python 3.11+, `mcp>=1.0` (Python MCP SDK, FastMCP high-level API), subprocess + ripgrep (`rg`) for project index, pytest for unit tests. No async test machinery is introduced — tool impls are sync and tested as plain functions. Ripgrep is required for `project_index_mcp` and will be installed in CI.

**Spec reference:** `docs/superpowers/specs/2026-04-14-aegis-ai-engineering-team-design.md` (§10 MCP servers, §11.4 Worktree lifecycle, §11.5 Minimal prompt-injection posture)

**Predecessor plan:** `docs/superpowers/plans/2026-04-14-aegis-phase-1-core.md` (tagged `phase-1-complete`)

---

## Scope

### Phase 2 covers these spec sections

- **§10.1 `aegis-git-mcp`** — all 10 tools: `git_status`, `git_diff`, `git_log`, `git_add`, `git_commit`, `git_branch_create`, `git_checkout`, `git_worktree_add`, `git_worktree_remove`, `git_merge`.
- **§10.2 `aegis-fs-mcp`** — all 7 tools: `fs_read`, `fs_list`, `fs_glob`, `fs_write`, `fs_mkdir`, `fs_delete`, `fs_move`.
- **§10.3 `aegis-shell-mcp`** — `shell_exec` with `ALLOW_CMDS` env allow-list and scoped `cwd`.
- **§10.4 `aegis-project-index-mcp`** — `search` (content/symbol/filename), `file_tree`, `outline`.
- **§10.5 Public distribution** — four console scripts registered in `pyproject.toml`.
- **§11.4 Worktree lifecycle** — the worktree tools in `git_mcp` call `aegis.core.worktree.create_worktree` / `remove_worktree` from Phase 1.
- **§11.5 Minimal prompt-injection posture** — `shell_exec` never uses `shell=True`; `command` and `args` are always passed separately; allow-list is enforced server-side.

### What Phase 2 explicitly does NOT cover

- Wiring any MCP server into LangGraph nodes (Phase 4).
- Claude Agent SDK tool binding (Phase 3).
- Any form of credential redaction, audit logging, or prompt-injection filtering beyond the minimum already in the spec (deferred forever — §2 non-goals).
- An MCP integration test that spawns a server and talks to it over real stdio from pytest. We do a manual smoke test in Task 8 instead; adding `pytest-asyncio` + in-process MCP client machinery is out of scope. Correctness is proven by unit tests on the free-function impls.
- Any changes to Phase 1 modules (`core.config`, `core.task`, `core.worktree`, `core.budget`, `core.lifecycle`) — except that `core.worktree` is read-only consumed from `mcp_servers`.

At the end of Phase 2, running `aegis-fs-mcp --scope /tmp` must start a FastMCP stdio server that blocks waiting on stdin. `pip install -e .[dev]` and `pytest` must remain green; the phase adds roughly 40–50 new unit tests.

---

## File map

### Files created by this plan

```
src/aegis/mcp_servers/_base.py
src/aegis/mcp_servers/fs_mcp.py
src/aegis/mcp_servers/shell_mcp.py
src/aegis/mcp_servers/git_mcp.py
src/aegis/mcp_servers/project_index_mcp.py
tests/unit/test_mcp_base.py
tests/unit/test_fs_mcp.py
tests/unit/test_shell_mcp.py
tests/unit/test_git_mcp.py
tests/unit/test_project_index_mcp.py
```

### Files modified by this plan

- `pyproject.toml` — add `mcp>=1.0` to `dependencies`; add four console scripts under `[project.scripts]`.
- `src/aegis/mcp_servers/__init__.py` — update docstring from "Implemented in Phase 2" to just "First-party MCP servers…".
- `.github/workflows/ci.yml` — add `apt-get install -y ripgrep` step so `project_index_mcp` tests can run.

### Files NOT touched

Anything under `src/aegis/core/`, `src/aegis/cli/`, `src/aegis/graph/`, `src/aegis/agents/`, `src/aegis/obs/`, `src/aegis/web/`, or `tests/unit/test_cli_*.py`, `tests/unit/test_config.py`, `tests/unit/test_task.py`, `tests/unit/test_worktree.py`, `tests/unit/test_budget.py`, `tests/unit/test_lifecycle.py`. Phase 1 code is frozen for Phase 2.

---

## Contracts shared by all four servers

Every server follows the same pattern so that reviewers only need to understand the contract once.

### 1. Entrypoint

Every server module exposes:

```python
def main() -> None:
    scope = parse_scope_from_args()   # from _base.py
    server = build_server(scope)
    server.run()
```

`server.run()` is FastMCP's synchronous stdio entrypoint. `main` is registered in `pyproject.toml` as a console script.

### 2. Scope enforcement

- Server receives `--scope <path>` on the command line.
- `_base.parse_scope_from_args` resolves the scope to an absolute path.
- Every tool impl that takes a path argument calls `_base.resolve_in_scope(scope, path)`, which:
  1. treats relative paths as scope-relative,
  2. calls `aegis.core.worktree.validate_path_in_scope` (defense in depth),
  3. returns the resolved absolute path.
- Any path that escapes scope raises `aegis.core.worktree.ScopeViolation`, which FastMCP converts into an error response.

### 3. Tool impl shape

Tool impls are module-level free functions whose **first argument is the scope**. FastMCP registration is done inside `build_server(scope)` by defining closures that forward to the free functions. This dual structure exists for one reason: the free functions are trivially unit-testable without touching FastMCP, and the closure registration is trivially mechanical so it does not need its own tests beyond "`build_server` doesn't raise".

### 4. No async anywhere

All tool impls are synchronous. FastMCP supports sync tools and will handle the event loop for us. This also means pytest tests do not need `pytest-asyncio`.

---

## Task 1: Add `mcp` dep, console scripts, and `_base.py`

**Files:**
- Modify: `pyproject.toml`
- Modify: `src/aegis/mcp_servers/__init__.py`
- Create: `src/aegis/mcp_servers/_base.py`
- Create: `tests/unit/test_mcp_base.py`

- [ ] **Step 1: Write the failing test**

Create `tests/unit/test_mcp_base.py`:

```python
from __future__ import annotations

from pathlib import Path

import pytest

from aegis.core.worktree import ScopeViolation
from aegis.mcp_servers._base import parse_scope_from_args, resolve_in_scope


def test_parse_scope_returns_absolute_resolved_path(tmp_path: Path) -> None:
    scope = parse_scope_from_args(["--scope", str(tmp_path)])
    assert scope == tmp_path.resolve()
    assert scope.is_absolute()


def test_parse_scope_missing_argument_exits() -> None:
    with pytest.raises(SystemExit):
        parse_scope_from_args([])


def test_parse_scope_unknown_flag_exits(tmp_path: Path) -> None:
    with pytest.raises(SystemExit):
        parse_scope_from_args(["--scope", str(tmp_path), "--nope"])


def test_resolve_in_scope_relative_path(tmp_path: Path) -> None:
    (tmp_path / "a.txt").write_text("hi")
    resolved = resolve_in_scope(tmp_path, "a.txt")
    assert resolved == (tmp_path / "a.txt").resolve()


def test_resolve_in_scope_nested_relative_path(tmp_path: Path) -> None:
    (tmp_path / "sub").mkdir()
    resolved = resolve_in_scope(tmp_path, "sub/x.txt")
    assert resolved == (tmp_path / "sub" / "x.txt").resolve()
    assert not resolved.exists()  # non-existent paths still resolvable


def test_resolve_in_scope_absolute_inside(tmp_path: Path) -> None:
    target = tmp_path / "b.txt"
    target.write_text("ok")
    resolved = resolve_in_scope(tmp_path, str(target))
    assert resolved == target.resolve()


def test_resolve_in_scope_rejects_parent_escape(tmp_path: Path) -> None:
    with pytest.raises(ScopeViolation):
        resolve_in_scope(tmp_path, "../evil.txt")


def test_resolve_in_scope_rejects_absolute_outside(tmp_path: Path) -> None:
    outside = tmp_path.parent / "outside.txt"
    with pytest.raises(ScopeViolation):
        resolve_in_scope(tmp_path, str(outside))
```

- [ ] **Step 2: Run tests — they must fail**

Run: `pytest tests/unit/test_mcp_base.py -v`
Expected: all tests FAIL with `ModuleNotFoundError: No module named 'aegis.mcp_servers._base'`.

- [ ] **Step 3: Add `mcp` to dependencies in `pyproject.toml`**

Edit `pyproject.toml`. The `dependencies` list currently reads:

```toml
dependencies = [
    "pydantic>=2.7",
    "python-frontmatter>=1.1",
    "pyyaml>=6.0",
    "typer>=0.12",
]
```

Replace it with:

```toml
dependencies = [
    "pydantic>=2.7",
    "python-frontmatter>=1.1",
    "pyyaml>=6.0",
    "typer>=0.12",
    "mcp>=1.0",
]
```

- [ ] **Step 4: Register the four MCP console scripts**

In `pyproject.toml`, the `[project.scripts]` section currently reads:

```toml
[project.scripts]
aegis = "aegis.cli.main:app"
```

Replace it with:

```toml
[project.scripts]
aegis = "aegis.cli.main:app"
aegis-git-mcp = "aegis.mcp_servers.git_mcp:main"
aegis-fs-mcp = "aegis.mcp_servers.fs_mcp:main"
aegis-shell-mcp = "aegis.mcp_servers.shell_mcp:main"
aegis-project-index-mcp = "aegis.mcp_servers.project_index_mcp:main"
```

- [ ] **Step 5: Update the `mcp_servers` package docstring**

Edit `src/aegis/mcp_servers/__init__.py`:

```python
"""First-party MCP servers: git, fs, shell, project-index.

Each server exposes tools over stdio transport and is path-scoped via a
``--scope`` command-line argument. See spec §10 for the tool inventory.
"""
```

- [ ] **Step 6: Create `_base.py`**

Write `src/aegis/mcp_servers/_base.py`:

```python
"""Shared helpers for Aegis MCP servers.

Every server module uses ``parse_scope_from_args`` to read ``--scope`` from
argv and ``resolve_in_scope`` to turn a tool's ``path`` argument into a
validated absolute path. Scope enforcement is defense in depth per spec
§10 — the graph runner also scopes paths, but the server never trusts it.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from aegis.core.worktree import validate_path_in_scope


def parse_scope_from_args(argv: list[str] | None = None) -> Path:
    """Parse ``--scope`` from argv and return an absolute, resolved Path."""
    parser = argparse.ArgumentParser(description="Aegis MCP server")
    parser.add_argument(
        "--scope",
        type=Path,
        required=True,
        help="Absolute path the server is allowed to read/write. Any path"
        " outside this directory is refused.",
    )
    args = parser.parse_args(argv)
    scope: Path = args.scope.resolve()
    return scope


def resolve_in_scope(scope: Path, path: str) -> Path:
    """Turn a tool ``path`` argument into a validated absolute Path.

    Relative paths are interpreted as scope-relative. Absolute paths are
    used as-is. In both cases the final resolved path must lie inside
    ``scope`` or ``ScopeViolation`` is raised by ``validate_path_in_scope``.
    Non-existent paths are permitted — this is called before ``fs_write``
    or ``fs_mkdir`` for files that are about to be created.
    """
    p = Path(path)
    if not p.is_absolute():
        p = scope / p
    return validate_path_in_scope(p, scope)
```

- [ ] **Step 7: Reinstall with the new deps**

Run: `pip install -e .[dev]`
Expected: installs `mcp` and its transitive deps (includes `pydantic`, `anyio`, etc., most already present). Ends with `Successfully installed ... mcp-x.y.z`.

- [ ] **Step 8: Run tests — they must pass**

Run: `pytest tests/unit/test_mcp_base.py -v`
Expected: 8 PASSED.

Also run: `pytest tests/unit -v` to confirm Phase 1 tests still pass.
Expected: all Phase 1 tests green.

- [ ] **Step 9: Commit**

```bash
git add pyproject.toml src/aegis/mcp_servers/__init__.py src/aegis/mcp_servers/_base.py tests/unit/test_mcp_base.py
git commit -m "feat(mcp): scaffold mcp_servers base with scope parsing helpers"
```

---

## Task 2: `aegis-fs-mcp` (TDD)

**Files:**
- Create: `src/aegis/mcp_servers/fs_mcp.py`
- Create: `tests/unit/test_fs_mcp.py`

Implements §10.2. The fs server is implemented first because it has no external dependencies and exercises the scope machinery end-to-end.

- [ ] **Step 1: Write the failing tests**

Create `tests/unit/test_fs_mcp.py`:

```python
from __future__ import annotations

from pathlib import Path

import pytest

from aegis.core.worktree import ScopeViolation
from aegis.mcp_servers.fs_mcp import (
    build_server,
    fs_delete,
    fs_glob,
    fs_list,
    fs_mkdir,
    fs_move,
    fs_read,
    fs_write,
)


def test_fs_read_returns_text(tmp_path: Path) -> None:
    (tmp_path / "a.txt").write_text("hello", encoding="utf-8")
    assert fs_read(tmp_path, "a.txt") == "hello"


def test_fs_read_absolute_path(tmp_path: Path) -> None:
    target = tmp_path / "b.txt"
    target.write_text("bye", encoding="utf-8")
    assert fs_read(tmp_path, str(target)) == "bye"


def test_fs_read_rejects_outside_scope(tmp_path: Path) -> None:
    with pytest.raises(ScopeViolation):
        fs_read(tmp_path, "../outside.txt")


def test_fs_list_returns_sorted_names(tmp_path: Path) -> None:
    (tmp_path / "b").write_text("")
    (tmp_path / "a").write_text("")
    (tmp_path / "c").mkdir()
    assert fs_list(tmp_path, ".") == ["a", "b", "c"]


def test_fs_list_subdir(tmp_path: Path) -> None:
    sub = tmp_path / "sub"
    sub.mkdir()
    (sub / "x").write_text("")
    assert fs_list(tmp_path, "sub") == ["x"]


def test_fs_list_rejects_outside_scope(tmp_path: Path) -> None:
    with pytest.raises(ScopeViolation):
        fs_list(tmp_path, "/etc")


def test_fs_glob_matches_within_scope(tmp_path: Path) -> None:
    (tmp_path / "a.py").write_text("")
    (tmp_path / "b.py").write_text("")
    (tmp_path / "c.txt").write_text("")
    sub = tmp_path / "sub"
    sub.mkdir()
    (sub / "d.py").write_text("")
    assert fs_glob(tmp_path, "*.py") == ["a.py", "b.py"]
    assert fs_glob(tmp_path, "**/*.py") == ["a.py", "b.py", "sub/d.py"]


def test_fs_glob_returns_empty_for_no_match(tmp_path: Path) -> None:
    assert fs_glob(tmp_path, "*.rs") == []


def test_fs_write_creates_file(tmp_path: Path) -> None:
    fs_write(tmp_path, "a.txt", "content")
    assert (tmp_path / "a.txt").read_text(encoding="utf-8") == "content"


def test_fs_write_creates_parent_dirs(tmp_path: Path) -> None:
    fs_write(tmp_path, "nested/deep/file.txt", "x")
    assert (tmp_path / "nested" / "deep" / "file.txt").read_text(encoding="utf-8") == "x"


def test_fs_write_rejects_outside_scope(tmp_path: Path) -> None:
    with pytest.raises(ScopeViolation):
        fs_write(tmp_path, "../leak.txt", "nope")


def test_fs_mkdir_creates_directory(tmp_path: Path) -> None:
    fs_mkdir(tmp_path, "newdir")
    assert (tmp_path / "newdir").is_dir()


def test_fs_mkdir_is_idempotent(tmp_path: Path) -> None:
    fs_mkdir(tmp_path, "again")
    fs_mkdir(tmp_path, "again")  # no error
    assert (tmp_path / "again").is_dir()


def test_fs_mkdir_creates_parents(tmp_path: Path) -> None:
    fs_mkdir(tmp_path, "a/b/c")
    assert (tmp_path / "a" / "b" / "c").is_dir()


def test_fs_delete_removes_file(tmp_path: Path) -> None:
    (tmp_path / "kill.txt").write_text("")
    fs_delete(tmp_path, "kill.txt")
    assert not (tmp_path / "kill.txt").exists()


def test_fs_delete_removes_directory_tree(tmp_path: Path) -> None:
    sub = tmp_path / "dead"
    sub.mkdir()
    (sub / "leaf").write_text("")
    fs_delete(tmp_path, "dead")
    assert not sub.exists()


def test_fs_delete_rejects_outside_scope(tmp_path: Path) -> None:
    with pytest.raises(ScopeViolation):
        fs_delete(tmp_path, "../../nope")


def test_fs_move_renames_file(tmp_path: Path) -> None:
    (tmp_path / "src.txt").write_text("data")
    fs_move(tmp_path, "src.txt", "dst.txt")
    assert not (tmp_path / "src.txt").exists()
    assert (tmp_path / "dst.txt").read_text(encoding="utf-8") == "data"


def test_fs_move_creates_dst_parent(tmp_path: Path) -> None:
    (tmp_path / "a.txt").write_text("x")
    fs_move(tmp_path, "a.txt", "sub/b.txt")
    assert (tmp_path / "sub" / "b.txt").read_text(encoding="utf-8") == "x"


def test_fs_move_rejects_src_outside_scope(tmp_path: Path) -> None:
    outside = tmp_path.parent / "elsewhere.txt"
    outside.write_text("")
    with pytest.raises(ScopeViolation):
        fs_move(tmp_path, str(outside), "here.txt")
    outside.unlink()


def test_fs_move_rejects_dst_outside_scope(tmp_path: Path) -> None:
    (tmp_path / "a.txt").write_text("")
    with pytest.raises(ScopeViolation):
        fs_move(tmp_path, "a.txt", "../escaped.txt")


def test_build_server_does_not_raise(tmp_path: Path) -> None:
    server = build_server(tmp_path)
    assert server is not None
```

- [ ] **Step 2: Run tests — they must fail**

Run: `pytest tests/unit/test_fs_mcp.py -v`
Expected: all tests FAIL with `ModuleNotFoundError: No module named 'aegis.mcp_servers.fs_mcp'`.

- [ ] **Step 3: Write the implementation**

Create `src/aegis/mcp_servers/fs_mcp.py`:

```python
"""``aegis-fs-mcp`` — filesystem MCP server.

Implements spec §10.2. All seven tools are scope-enforced via
``resolve_in_scope``. Tool impls are exposed as free functions so they
can be unit-tested without a running MCP client; ``build_server`` binds
the scope into FastMCP closures for stdio delivery.
"""

from __future__ import annotations

import shutil
from pathlib import Path

from mcp.server.fastmcp import FastMCP

from aegis.mcp_servers._base import parse_scope_from_args, resolve_in_scope


def fs_read(scope: Path, path: str) -> str:
    """Return the text content of ``path``."""
    resolved = resolve_in_scope(scope, path)
    return resolved.read_text(encoding="utf-8")


def fs_list(scope: Path, path: str) -> list[str]:
    """Return a sorted list of entry names in the directory ``path``."""
    resolved = resolve_in_scope(scope, path)
    return sorted(p.name for p in resolved.iterdir())


def fs_glob(scope: Path, pattern: str) -> list[str]:
    """Return scope-relative paths matching ``pattern`` under scope.

    The glob is always rooted at scope — callers cannot escape via the
    pattern itself because ``Path.glob`` anchors to the path it is called
    on. This is defense in depth on top of ``resolve_in_scope``.
    """
    return sorted(
        str(p.relative_to(scope))
        for p in scope.glob(pattern)
    )


def fs_write(scope: Path, path: str, content: str) -> int:
    """Write ``content`` to ``path``, creating parents as needed."""
    resolved = resolve_in_scope(scope, path)
    resolved.parent.mkdir(parents=True, exist_ok=True)
    return resolved.write_text(content, encoding="utf-8")


def fs_mkdir(scope: Path, path: str) -> None:
    """Create ``path`` as a directory, including parents. Idempotent."""
    resolved = resolve_in_scope(scope, path)
    resolved.mkdir(parents=True, exist_ok=True)


def fs_delete(scope: Path, path: str) -> None:
    """Delete ``path``. Removes a directory tree if ``path`` is a dir."""
    resolved = resolve_in_scope(scope, path)
    if resolved.is_dir():
        shutil.rmtree(resolved)
    else:
        resolved.unlink()


def fs_move(scope: Path, src: str, dst: str) -> None:
    """Move ``src`` to ``dst``. Both must lie within scope."""
    src_resolved = resolve_in_scope(scope, src)
    dst_resolved = resolve_in_scope(scope, dst)
    dst_resolved.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(src_resolved), str(dst_resolved))


def build_server(scope: Path) -> FastMCP:
    """Build a FastMCP server whose tools are bound to ``scope``."""
    server: FastMCP = FastMCP("aegis-fs")

    @server.tool(name="fs_read")
    def _fs_read(path: str) -> str:
        return fs_read(scope, path)

    @server.tool(name="fs_list")
    def _fs_list(path: str) -> list[str]:
        return fs_list(scope, path)

    @server.tool(name="fs_glob")
    def _fs_glob(pattern: str) -> list[str]:
        return fs_glob(scope, pattern)

    @server.tool(name="fs_write")
    def _fs_write(path: str, content: str) -> int:
        return fs_write(scope, path, content)

    @server.tool(name="fs_mkdir")
    def _fs_mkdir(path: str) -> None:
        fs_mkdir(scope, path)

    @server.tool(name="fs_delete")
    def _fs_delete(path: str) -> None:
        fs_delete(scope, path)

    @server.tool(name="fs_move")
    def _fs_move(src: str, dst: str) -> None:
        fs_move(scope, src, dst)

    return server


def main() -> None:
    scope = parse_scope_from_args()
    server = build_server(scope)
    server.run()


if __name__ == "__main__":  # pragma: no cover
    main()
```

- [ ] **Step 4: Run tests — they must pass**

Run: `pytest tests/unit/test_fs_mcp.py -v`
Expected: all ~22 tests PASSED.

- [ ] **Step 5: Run the full suite to confirm no regressions**

Run: `pytest tests/unit -v`
Expected: Phase 1 tests + new `test_mcp_base.py` + `test_fs_mcp.py` all green.

- [ ] **Step 6: Commit**

```bash
git add src/aegis/mcp_servers/fs_mcp.py tests/unit/test_fs_mcp.py
git commit -m "feat(mcp): implement aegis-fs-mcp with scope-enforced fs tools"
```

---

## Task 3: `aegis-shell-mcp` (TDD)

**Files:**
- Create: `src/aegis/mcp_servers/shell_mcp.py`
- Create: `tests/unit/test_shell_mcp.py`

Implements §10.3. `shell_exec` takes a `command`, `args`, and `cwd`, enforces a command allow-list from `ALLOW_CMDS` (comma-separated), and runs the process with `shell=False` so agent-provided strings cannot be interpreted as shell metacharacters (§11.5).

- [ ] **Step 1: Write the failing tests**

Create `tests/unit/test_shell_mcp.py`:

```python
from __future__ import annotations

from pathlib import Path

import pytest

from aegis.core.worktree import ScopeViolation
from aegis.mcp_servers.shell_mcp import (
    DEFAULT_ALLOW_CMDS,
    ShellCommandDenied,
    _load_allow_cmds,
    build_server,
    shell_exec,
)


def test_default_allow_cmds_contains_expected_tools() -> None:
    assert "pytest" in DEFAULT_ALLOW_CMDS
    assert "python" in DEFAULT_ALLOW_CMDS
    assert "ruff" in DEFAULT_ALLOW_CMDS
    assert "mypy" in DEFAULT_ALLOW_CMDS


def test_load_allow_cmds_uses_default_when_env_unset(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("ALLOW_CMDS", raising=False)
    assert _load_allow_cmds() == DEFAULT_ALLOW_CMDS


def test_load_allow_cmds_reads_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ALLOW_CMDS", "pytest,ruff")
    assert _load_allow_cmds() == ["pytest", "ruff"]


def test_load_allow_cmds_strips_whitespace(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ALLOW_CMDS", " pytest , ruff ,, mypy ")
    assert _load_allow_cmds() == ["pytest", "ruff", "mypy"]


def test_shell_exec_runs_allowed_command(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALLOW_CMDS", "python")
    result = shell_exec(
        tmp_path, "python", ["-c", "print('hi')"], ".",
    )
    assert result["exit_code"] == 0
    assert "hi" in result["stdout"]
    assert result["stderr"] == ""


def test_shell_exec_captures_nonzero_exit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALLOW_CMDS", "python")
    result = shell_exec(
        tmp_path, "python", ["-c", "import sys; sys.exit(7)"], ".",
    )
    assert result["exit_code"] == 7


def test_shell_exec_captures_stderr(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALLOW_CMDS", "python")
    result = shell_exec(
        tmp_path, "python",
        ["-c", "import sys; sys.stderr.write('oops')"], ".",
    )
    assert "oops" in result["stderr"]


def test_shell_exec_rejects_disallowed_command(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALLOW_CMDS", "pytest")
    with pytest.raises(ShellCommandDenied):
        shell_exec(tmp_path, "rm", ["-rf", "/"], ".")


def test_shell_exec_rejects_cwd_outside_scope(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALLOW_CMDS", "python")
    with pytest.raises(ScopeViolation):
        shell_exec(tmp_path, "python", ["-c", "pass"], "..")


def test_shell_exec_rejects_missing_cwd(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALLOW_CMDS", "python")
    with pytest.raises(FileNotFoundError):
        shell_exec(tmp_path, "python", ["-c", "pass"], "no_such_dir")


def test_shell_exec_does_not_interpret_shell_metachars(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Args with ; and && are passed to the program verbatim, not to a shell."""
    monkeypatch.setenv("ALLOW_CMDS", "python")
    result = shell_exec(
        tmp_path, "python",
        ["-c", "import sys; print(sys.argv[1])", "foo; rm -rf /"],
        ".",
    )
    assert "foo; rm -rf /" in result["stdout"]
    assert result["exit_code"] == 0
    # Sanity: the process did not attempt to run rm
    assert (tmp_path).exists()


def test_build_server_does_not_raise(tmp_path: Path) -> None:
    server = build_server(tmp_path)
    assert server is not None
```

- [ ] **Step 2: Run tests — they must fail**

Run: `pytest tests/unit/test_shell_mcp.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'aegis.mcp_servers.shell_mcp'`.

- [ ] **Step 3: Write the implementation**

Create `src/aegis/mcp_servers/shell_mcp.py`:

```python
"""``aegis-shell-mcp`` — shell-exec MCP server.

Implements spec §10.3 and §11.5. The server runs only commands that
appear in an allow-list, treats ``command`` and ``args`` as a single
argv vector (no shell interpretation), and validates ``cwd`` lies inside
scope. The allow-list is read from ``ALLOW_CMDS`` env var at call time
so tests can monkeypatch it per-case.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path
from typing import TypedDict

from mcp.server.fastmcp import FastMCP

from aegis.mcp_servers._base import parse_scope_from_args, resolve_in_scope


DEFAULT_ALLOW_CMDS: list[str] = [
    "pytest",
    "python",
    "pip",
    "npm",
    "pnpm",
    "node",
    "ruff",
    "mypy",
    "pre-commit",
]


class ShellResult(TypedDict):
    stdout: str
    stderr: str
    exit_code: int


class ShellCommandDenied(Exception):
    """Raised when a command is not in the allow-list."""


def _load_allow_cmds() -> list[str]:
    env = os.environ.get("ALLOW_CMDS")
    if env is None:
        return DEFAULT_ALLOW_CMDS
    return [c.strip() for c in env.split(",") if c.strip()]


def shell_exec(
    scope: Path, command: str, args: list[str], cwd: str
) -> ShellResult:
    """Run ``command args`` under ``cwd`` (scoped) and capture output."""
    allow = _load_allow_cmds()
    if command not in allow:
        raise ShellCommandDenied(
            f"command {command!r} not in ALLOW_CMDS {allow}"
        )
    cwd_resolved = resolve_in_scope(scope, cwd)
    if not cwd_resolved.is_dir():
        raise FileNotFoundError(
            f"cwd {cwd_resolved} does not exist or is not a directory"
        )
    result = subprocess.run(
        [command, *args],
        cwd=str(cwd_resolved),
        capture_output=True,
        text=True,
        check=False,
    )
    return ShellResult(
        stdout=result.stdout,
        stderr=result.stderr,
        exit_code=result.returncode,
    )


def build_server(scope: Path) -> FastMCP:
    server: FastMCP = FastMCP("aegis-shell")

    @server.tool(name="shell_exec")
    def _shell_exec(command: str, args: list[str], cwd: str) -> ShellResult:
        return shell_exec(scope, command, args, cwd)

    return server


def main() -> None:
    scope = parse_scope_from_args()
    server = build_server(scope)
    server.run()


if __name__ == "__main__":  # pragma: no cover
    main()
```

- [ ] **Step 4: Run tests — they must pass**

Run: `pytest tests/unit/test_shell_mcp.py -v`
Expected: all ~12 tests PASSED. (`test_shell_exec_runs_allowed_command` requires `python` on PATH, which the test runner already has.)

- [ ] **Step 5: Commit**

```bash
git add src/aegis/mcp_servers/shell_mcp.py tests/unit/test_shell_mcp.py
git commit -m "feat(mcp): implement aegis-shell-mcp with allow-list and scoped cwd"
```

---

## Task 4: `aegis-git-mcp` — read tools (TDD)

**Files:**
- Create: `src/aegis/mcp_servers/git_mcp.py` (partial — read tools only)
- Create: `tests/unit/test_git_mcp.py` (read-tool tests)

Implements the first three tools from §10.1: `git_status`, `git_diff`, `git_log`. These are the easy ones — they just invoke the git CLI with `cwd=scope` and stream output back. We split git across three tasks so reviews stay bite-sized.

- [ ] **Step 1: Add a shared git-repo fixture check**

The conftest in `tests/unit/conftest.py` already provides a `git_repo` fixture (created in Phase 1 Task 5). Verify it exists:

Run: `pytest tests/unit/test_worktree.py -v`
Expected: PASS — confirms `git_repo` fixture still works.

If for some reason a `git_repo` fixture does not exist under that name, re-read `tests/unit/conftest.py` to find the actual fixture name used by `test_worktree.py` and adapt the imports in the next step.

- [ ] **Step 2: Write the failing tests for read tools**

Create `tests/unit/test_git_mcp.py`:

```python
from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from aegis.core.worktree import ScopeViolation
from aegis.mcp_servers.git_mcp import (
    build_server,
    git_diff,
    git_log,
    git_status,
)


def _run(args: list[str], cwd: Path) -> None:
    subprocess.run(["git", *args], cwd=str(cwd), check=True, capture_output=True)


def _init_repo_with_commit(repo: Path) -> None:
    _run(["init", "-q", "-b", "main"], repo)
    _run(["config", "user.email", "t@t"], repo)
    _run(["config", "user.name", "t"], repo)
    _run(["config", "commit.gpgsign", "false"], repo)
    (repo / "a.txt").write_text("one\n")
    _run(["add", "a.txt"], repo)
    _run(["commit", "-q", "-m", "first"], repo)


def test_git_status_clean(tmp_path: Path) -> None:
    _init_repo_with_commit(tmp_path)
    assert git_status(tmp_path) == ""


def test_git_status_shows_untracked(tmp_path: Path) -> None:
    _init_repo_with_commit(tmp_path)
    (tmp_path / "new.txt").write_text("x")
    out = git_status(tmp_path)
    assert "new.txt" in out
    assert out.startswith("??")


def test_git_status_shows_modified(tmp_path: Path) -> None:
    _init_repo_with_commit(tmp_path)
    (tmp_path / "a.txt").write_text("two\n")
    out = git_status(tmp_path)
    assert "a.txt" in out
    assert " M" in out or "M " in out


def test_git_diff_shows_changes(tmp_path: Path) -> None:
    _init_repo_with_commit(tmp_path)
    (tmp_path / "a.txt").write_text("changed\n")
    out = git_diff(tmp_path)
    assert "-one" in out
    assert "+changed" in out


def test_git_diff_rev_range(tmp_path: Path) -> None:
    _init_repo_with_commit(tmp_path)
    (tmp_path / "a.txt").write_text("two\n")
    _run(["add", "a.txt"], tmp_path)
    _run(["commit", "-q", "-m", "second"], tmp_path)
    out = git_diff(tmp_path, rev_range="HEAD~1..HEAD")
    assert "-one" in out
    assert "+two" in out


def test_git_log_returns_oneline(tmp_path: Path) -> None:
    _init_repo_with_commit(tmp_path)
    out = git_log(tmp_path)
    assert "first" in out
    assert len(out.splitlines()) == 1


def test_git_log_respects_limit(tmp_path: Path) -> None:
    _init_repo_with_commit(tmp_path)
    for i in range(5):
        (tmp_path / f"f{i}.txt").write_text(str(i))
        _run(["add", f"f{i}.txt"], tmp_path)
        _run(["commit", "-q", "-m", f"c{i}"], tmp_path)
    out = git_log(tmp_path, limit=3)
    assert len(out.splitlines()) == 3


def test_git_status_scoped_path_escape_rejected(tmp_path: Path) -> None:
    _init_repo_with_commit(tmp_path)
    with pytest.raises(ScopeViolation):
        git_status(tmp_path, path="../outside")


def test_build_server_does_not_raise(tmp_path: Path) -> None:
    _init_repo_with_commit(tmp_path)
    server = build_server(tmp_path)
    assert server is not None
```

- [ ] **Step 3: Run tests — they must fail**

Run: `pytest tests/unit/test_git_mcp.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'aegis.mcp_servers.git_mcp'`.

- [ ] **Step 4: Write the partial implementation (read tools only)**

Create `src/aegis/mcp_servers/git_mcp.py`:

```python
"""``aegis-git-mcp`` — git MCP server.

Implements spec §10.1. All tools invoke the ``git`` CLI with
``cwd=scope`` — i.e. the scope directory IS the repo (or worktree) the
tools operate on. Path arguments are interpreted as scope-relative and
validated defensively through ``resolve_in_scope``.

This module is built up across three plan tasks: read tools (status,
diff, log), write tools (add, commit, branch_create, checkout), and
worktree/merge tools (worktree_add, worktree_remove, merge).
"""

from __future__ import annotations

import subprocess
from pathlib import Path

from mcp.server.fastmcp import FastMCP

from aegis.mcp_servers._base import parse_scope_from_args, resolve_in_scope


def _git(scope: Path, args: list[str]) -> str:
    """Run ``git args`` with ``cwd=scope`` and return stdout.

    Uses ``check=True`` so git errors become ``CalledProcessError``; the
    MCP server will surface that as a tool error.
    """
    result = subprocess.run(
        ["git", *args],
        cwd=str(scope),
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout


def git_status(scope: Path, path: str | None = None) -> str:
    args = ["status", "--porcelain"]
    if path is not None:
        resolved = resolve_in_scope(scope, path)
        args.extend(["--", str(resolved)])
    return _git(scope, args)


def git_diff(
    scope: Path,
    path: str | None = None,
    rev_range: str | None = None,
) -> str:
    args = ["diff"]
    if rev_range is not None:
        args.append(rev_range)
    if path is not None:
        resolved = resolve_in_scope(scope, path)
        args.extend(["--", str(resolved)])
    return _git(scope, args)


def git_log(scope: Path, path: str | None = None, limit: int = 20) -> str:
    args = ["log", f"-n{limit}", "--oneline"]
    if path is not None:
        resolved = resolve_in_scope(scope, path)
        args.extend(["--", str(resolved)])
    return _git(scope, args)


def build_server(scope: Path) -> FastMCP:
    """Build a FastMCP server whose tools are bound to ``scope``.

    Only read tools are registered in Task 4; write and worktree tools
    are appended in Tasks 5 and 6.
    """
    server: FastMCP = FastMCP("aegis-git")

    @server.tool(name="git_status")
    def _git_status(path: str | None = None) -> str:
        return git_status(scope, path)

    @server.tool(name="git_diff")
    def _git_diff(
        path: str | None = None, rev_range: str | None = None
    ) -> str:
        return git_diff(scope, path, rev_range)

    @server.tool(name="git_log")
    def _git_log(path: str | None = None, limit: int = 20) -> str:
        return git_log(scope, path, limit)

    return server


def main() -> None:
    scope = parse_scope_from_args()
    server = build_server(scope)
    server.run()


if __name__ == "__main__":  # pragma: no cover
    main()
```

- [ ] **Step 5: Run tests — they must pass**

Run: `pytest tests/unit/test_git_mcp.py -v`
Expected: all 9 tests PASSED.

- [ ] **Step 6: Commit**

```bash
git add src/aegis/mcp_servers/git_mcp.py tests/unit/test_git_mcp.py
git commit -m "feat(mcp): implement aegis-git-mcp read tools (status, diff, log)"
```

---

## Task 5: `aegis-git-mcp` — write tools (TDD)

**Files:**
- Modify: `src/aegis/mcp_servers/git_mcp.py`
- Modify: `tests/unit/test_git_mcp.py`

Adds `git_add`, `git_commit`, `git_branch_create`, `git_checkout` to the existing module.

- [ ] **Step 1: Append failing tests to `test_git_mcp.py`**

Add to the bottom of `tests/unit/test_git_mcp.py`:

```python
from aegis.mcp_servers.git_mcp import (
    git_add,
    git_branch_create,
    git_checkout,
    git_commit,
)


def test_git_add_stages_file(tmp_path: Path) -> None:
    _init_repo_with_commit(tmp_path)
    (tmp_path / "new.txt").write_text("data")
    git_add(tmp_path, ["new.txt"])
    status = git_status(tmp_path)
    assert "A  new.txt" in status


def test_git_add_multiple_files(tmp_path: Path) -> None:
    _init_repo_with_commit(tmp_path)
    (tmp_path / "x.txt").write_text("1")
    (tmp_path / "y.txt").write_text("2")
    git_add(tmp_path, ["x.txt", "y.txt"])
    status = git_status(tmp_path)
    assert "x.txt" in status
    assert "y.txt" in status


def test_git_add_rejects_outside_scope(tmp_path: Path) -> None:
    _init_repo_with_commit(tmp_path)
    with pytest.raises(ScopeViolation):
        git_add(tmp_path, ["../escape.txt"])


def test_git_commit_creates_commit(tmp_path: Path) -> None:
    _init_repo_with_commit(tmp_path)
    (tmp_path / "new.txt").write_text("data")
    _run(["add", "new.txt"], tmp_path)
    git_commit(tmp_path, "add new.txt")
    log = git_log(tmp_path)
    assert "add new.txt" in log


def test_git_branch_create_creates_branch(tmp_path: Path) -> None:
    _init_repo_with_commit(tmp_path)
    git_branch_create(tmp_path, "feature/x")
    result = subprocess.run(
        ["git", "branch", "--list", "feature/x"],
        cwd=str(tmp_path), capture_output=True, text=True, check=True,
    )
    assert "feature/x" in result.stdout


def test_git_checkout_switches_branch(tmp_path: Path) -> None:
    _init_repo_with_commit(tmp_path)
    git_branch_create(tmp_path, "other")
    git_checkout(tmp_path, "other")
    result = subprocess.run(
        ["git", "symbolic-ref", "--short", "HEAD"],
        cwd=str(tmp_path), capture_output=True, text=True, check=True,
    )
    assert result.stdout.strip() == "other"
```

- [ ] **Step 2: Run tests — they must fail**

Run: `pytest tests/unit/test_git_mcp.py -v`
Expected: the 6 new tests FAIL at import time with `ImportError: cannot import name 'git_add' from 'aegis.mcp_servers.git_mcp'`.

- [ ] **Step 3: Add the write tool impls**

Edit `src/aegis/mcp_servers/git_mcp.py`. After the `git_log` function and before `build_server`, add:

```python
def git_add(scope: Path, paths: list[str]) -> None:
    resolved = [str(resolve_in_scope(scope, p)) for p in paths]
    _git(scope, ["add", *resolved])


def git_commit(scope: Path, message: str) -> str:
    return _git(scope, ["commit", "-m", message])


def git_branch_create(scope: Path, name: str) -> None:
    _git(scope, ["branch", name])


def git_checkout(scope: Path, ref: str) -> None:
    _git(scope, ["checkout", ref])
```

Then extend `build_server` by appending these registrations inside it, immediately after the existing `_git_log` registration and before `return server`:

```python
    @server.tool(name="git_add")
    def _git_add(paths: list[str]) -> None:
        git_add(scope, paths)

    @server.tool(name="git_commit")
    def _git_commit(message: str) -> str:
        return git_commit(scope, message)

    @server.tool(name="git_branch_create")
    def _git_branch_create(name: str) -> None:
        git_branch_create(scope, name)

    @server.tool(name="git_checkout")
    def _git_checkout(ref: str) -> None:
        git_checkout(scope, ref)
```

- [ ] **Step 4: Run tests — they must pass**

Run: `pytest tests/unit/test_git_mcp.py -v`
Expected: all 15 tests PASSED (9 from Task 4 + 6 new).

- [ ] **Step 5: Commit**

```bash
git add src/aegis/mcp_servers/git_mcp.py tests/unit/test_git_mcp.py
git commit -m "feat(mcp): add git_mcp write tools (add, commit, branch, checkout)"
```

---

## Task 6: `aegis-git-mcp` — worktree & merge tools (TDD)

**Files:**
- Modify: `src/aegis/mcp_servers/git_mcp.py`
- Modify: `tests/unit/test_git_mcp.py`

Adds the last three tools: `git_worktree_add`, `git_worktree_remove`, `git_merge`. The worktree tools delegate to `aegis.core.worktree.create_worktree` / `remove_worktree` built in Phase 1 — this is the first production caller of those helpers.

Scope note: the graph runner spawns `git_mcp` with `scope=<repo_root>` for the setup/teardown flow (where the new worktree path lives under `<repo_root>/.aegis/.worktrees/...`). So the worktree path passed to `git_worktree_add` is scope-relative and validates cleanly. For agent-runtime spawns, `scope=<worktree_path>` and the worktree tools are not expected to be called — but they still exist and their scope enforcement remains intact.

- [ ] **Step 1: Append failing tests**

Add to the bottom of `tests/unit/test_git_mcp.py`:

```python
from aegis.mcp_servers.git_mcp import (
    git_merge,
    git_worktree_add,
    git_worktree_remove,
)


def test_git_worktree_add_creates_worktree(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    _init_repo_with_commit(repo)
    wt_rel = ".worktrees/feature-1"
    git_worktree_add(repo, wt_rel, "aegis/feature-1")
    wt_path = repo / wt_rel
    assert wt_path.is_dir()
    assert (wt_path / "a.txt").read_text() == "one\n"


def test_git_worktree_remove_cleans_up(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    _init_repo_with_commit(repo)
    wt_rel = ".worktrees/feature-2"
    git_worktree_add(repo, wt_rel, "aegis/feature-2")
    git_worktree_remove(repo, wt_rel)
    assert not (repo / wt_rel).exists()


def test_git_worktree_add_rejects_outside_scope(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    _init_repo_with_commit(repo)
    with pytest.raises(ScopeViolation):
        git_worktree_add(repo, "../evil-wt", "aegis/evil")


def test_git_merge_fast_forward(tmp_path: Path) -> None:
    _init_repo_with_commit(tmp_path)
    _run(["checkout", "-q", "-b", "feature"], tmp_path)
    (tmp_path / "new.txt").write_text("x")
    _run(["add", "new.txt"], tmp_path)
    _run(["commit", "-q", "-m", "feat"], tmp_path)
    _run(["checkout", "-q", "main"], tmp_path)
    out = git_merge(tmp_path, "feature", "main")
    assert "feat" in out or "merge" in out.lower() or "fast-forward" in out.lower()
    assert (tmp_path / "new.txt").exists()
    log = git_log(tmp_path)
    assert "feat" in log


def test_build_server_with_all_tools_does_not_raise(tmp_path: Path) -> None:
    _init_repo_with_commit(tmp_path)
    server = build_server(tmp_path)
    assert server is not None
```

- [ ] **Step 2: Run tests — they must fail**

Run: `pytest tests/unit/test_git_mcp.py -v`
Expected: the 5 new tests FAIL at import time with `ImportError: cannot import name 'git_merge' from 'aegis.mcp_servers.git_mcp'`.

- [ ] **Step 3: Add the worktree & merge impls**

Edit `src/aegis/mcp_servers/git_mcp.py`. Add this import at the top (after the existing imports):

```python
from aegis.core.worktree import create_worktree, remove_worktree
```

Then add these functions below `git_checkout` and before `build_server`:

```python
def git_worktree_add(scope: Path, path: str, branch: str) -> None:
    wt = resolve_in_scope(scope, path)
    create_worktree(scope, wt, branch)


def git_worktree_remove(scope: Path, path: str) -> None:
    wt = resolve_in_scope(scope, path)
    remove_worktree(scope, wt)


def git_merge(scope: Path, branch: str, into: str) -> str:
    _git(scope, ["checkout", into])
    return _git(scope, ["merge", "--no-ff", "--no-edit", branch])
```

Then extend `build_server` by appending these registrations inside it, immediately after the existing `_git_checkout` registration and before `return server`:

```python
    @server.tool(name="git_worktree_add")
    def _git_worktree_add(path: str, branch: str) -> None:
        git_worktree_add(scope, path, branch)

    @server.tool(name="git_worktree_remove")
    def _git_worktree_remove(path: str) -> None:
        git_worktree_remove(scope, path)

    @server.tool(name="git_merge")
    def _git_merge(branch: str, into: str) -> str:
        return git_merge(scope, branch, into)
```

- [ ] **Step 4: Run tests — they must pass**

Run: `pytest tests/unit/test_git_mcp.py -v`
Expected: all 20 tests PASSED.

- [ ] **Step 5: Commit**

```bash
git add src/aegis/mcp_servers/git_mcp.py tests/unit/test_git_mcp.py
git commit -m "feat(mcp): add git_mcp worktree and merge tools"
```

---

## Task 7: `aegis-project-index-mcp` (TDD)

**Files:**
- Create: `src/aegis/mcp_servers/project_index_mcp.py`
- Create: `tests/unit/test_project_index_mcp.py`
- Modify: `.github/workflows/ci.yml`

Implements §10.4. `search` shells out to ripgrep (`rg`) for content and symbol queries, walks the scope for filename queries. `file_tree` walks the tree with a depth limit. `outline` uses ripgrep over a single file to extract `def`/`class`/`function`/`fn`/visibility-qualified lines.

Ripgrep is required for content/symbol search and outline. We add a CI step to install it; locally contributors already have `rg`.

- [ ] **Step 1: Write the failing tests**

Create `tests/unit/test_project_index_mcp.py`:

```python
from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from aegis.core.worktree import ScopeViolation
from aegis.mcp_servers.project_index_mcp import (
    build_server,
    file_tree,
    outline,
    search,
)

requires_rg = pytest.mark.skipif(
    shutil.which("rg") is None, reason="ripgrep not installed"
)


def _seed_project(root: Path) -> None:
    (root / "src").mkdir()
    (root / "src" / "main.py").write_text(
        "def hello():\n    return 'world'\n\nclass Widget:\n    pass\n"
    )
    (root / "src" / "util.py").write_text(
        "def compute(x):\n    return x + 1\n"
    )
    (root / "tests").mkdir()
    (root / "tests" / "test_main.py").write_text(
        "def test_hello():\n    assert True\n"
    )
    (root / "README.md").write_text("# project\n")


@requires_rg
def test_search_content(tmp_path: Path) -> None:
    _seed_project(tmp_path)
    hits = search(tmp_path, "hello")
    assert any("main.py" in h for h in hits)
    assert any("test_main.py" in h for h in hits)


@requires_rg
def test_search_content_no_match(tmp_path: Path) -> None:
    _seed_project(tmp_path)
    assert search(tmp_path, "nonexistent_token_zzz") == []


def test_search_filename(tmp_path: Path) -> None:
    _seed_project(tmp_path)
    hits = search(tmp_path, "util", kind="filename")
    assert any("util.py" in h for h in hits)
    assert not any("main.py" in h for h in hits)


@requires_rg
def test_search_symbol(tmp_path: Path) -> None:
    _seed_project(tmp_path)
    hits = search(tmp_path, "Widget", kind="symbol")
    assert any("class Widget" in h for h in hits)


def test_search_unknown_kind_raises(tmp_path: Path) -> None:
    _seed_project(tmp_path)
    with pytest.raises(ValueError):
        search(tmp_path, "foo", kind="bogus")


def test_file_tree_depth_1(tmp_path: Path) -> None:
    _seed_project(tmp_path)
    tree = file_tree(tmp_path, depth=1)
    # Top-level entries only
    assert any("README.md" in line for line in tree)
    assert any("src" in line for line in tree)
    assert any("tests" in line for line in tree)
    # No nested files at depth 1
    assert not any("main.py" in line for line in tree)


def test_file_tree_depth_2(tmp_path: Path) -> None:
    _seed_project(tmp_path)
    tree = file_tree(tmp_path, depth=2)
    assert any("src/main.py" in line for line in tree)
    assert any("tests/test_main.py" in line for line in tree)


def test_file_tree_rejects_outside_scope(tmp_path: Path) -> None:
    _seed_project(tmp_path)
    with pytest.raises(ScopeViolation):
        file_tree(tmp_path, path="..", depth=1)


@requires_rg
def test_outline_python_file(tmp_path: Path) -> None:
    _seed_project(tmp_path)
    lines = outline(tmp_path, "src/main.py")
    assert any("def hello" in line for line in lines)
    assert any("class Widget" in line for line in lines)


def test_outline_rejects_outside_scope(tmp_path: Path) -> None:
    _seed_project(tmp_path)
    with pytest.raises(ScopeViolation):
        outline(tmp_path, "../outside.py")


def test_build_server_does_not_raise(tmp_path: Path) -> None:
    _seed_project(tmp_path)
    server = build_server(tmp_path)
    assert server is not None
```

- [ ] **Step 2: Run tests — they must fail**

Run: `pytest tests/unit/test_project_index_mcp.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'aegis.mcp_servers.project_index_mcp'`.

- [ ] **Step 3: Write the implementation**

Create `src/aegis/mcp_servers/project_index_mcp.py`:

```python
"""``aegis-project-index-mcp`` — lightweight project-index MCP server.

Implements spec §10.4. Content and symbol search shell out to ripgrep
(`rg`). Filename search walks the scope tree in Python. ``file_tree``
returns a depth-limited listing. ``outline`` grep-extracts definition
lines from a single file. All paths are scope-validated.

This is intentionally a "tiny daemon" — no persistent index, no ctags
dependency, no caching layer. Calls are cheap enough at typical repo
sizes that building an index up-front is not worth the complexity.
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Literal

from mcp.server.fastmcp import FastMCP

from aegis.mcp_servers._base import parse_scope_from_args, resolve_in_scope


SearchKind = Literal["content", "symbol", "filename"]


def _run_rg(args: list[str], cwd: Path) -> list[str]:
    result = subprocess.run(
        ["rg", *args],
        cwd=str(cwd),
        capture_output=True,
        text=True,
        check=False,
    )
    # rg exit 1 = no matches, which is not an error for us
    if result.returncode not in (0, 1):
        raise RuntimeError(
            f"rg failed (exit {result.returncode}): {result.stderr.strip()}"
        )
    return [line for line in result.stdout.splitlines() if line]


def search(
    scope: Path, query: str, kind: SearchKind = "content"
) -> list[str]:
    if kind == "content":
        return _run_rg(
            ["--line-number", "--no-heading", "--fixed-strings", query, "."],
            cwd=scope,
        )
    if kind == "symbol":
        pattern = rf"^\s*(def |class |function |fn |public |private ).*{query}"
        return _run_rg(
            ["--line-number", "--no-heading", pattern, "."],
            cwd=scope,
        )
    if kind == "filename":
        return sorted(
            str(p.relative_to(scope))
            for p in scope.rglob("*")
            if p.is_file() and query in p.name
        )
    raise ValueError(f"unknown kind {kind!r}")


def file_tree(scope: Path, path: str = ".", depth: int = 2) -> list[str]:
    root = resolve_in_scope(scope, path)
    root_depth = len(root.parts)
    out: list[str] = []
    for p in sorted(root.rglob("*")):
        rel_depth = len(p.parts) - root_depth
        if rel_depth > depth:
            continue
        rel = p.relative_to(scope)
        out.append(f"{rel}/" if p.is_dir() else str(rel))
    return out


def outline(scope: Path, path: str) -> list[str]:
    resolved = resolve_in_scope(scope, path)
    pattern = r"^\s*(def |class |function |fn |public |private )"
    return _run_rg(
        ["--line-number", "--no-heading", pattern, str(resolved)],
        cwd=scope,
    )


def build_server(scope: Path) -> FastMCP:
    server: FastMCP = FastMCP("aegis-project-index")

    @server.tool(name="search")
    def _search(query: str, kind: SearchKind = "content") -> list[str]:
        return search(scope, query, kind)

    @server.tool(name="file_tree")
    def _file_tree(path: str = ".", depth: int = 2) -> list[str]:
        return file_tree(scope, path, depth)

    @server.tool(name="outline")
    def _outline(path: str) -> list[str]:
        return outline(scope, path)

    return server


def main() -> None:
    scope = parse_scope_from_args()
    server = build_server(scope)
    server.run()


if __name__ == "__main__":  # pragma: no cover
    main()
```

- [ ] **Step 4: Install ripgrep locally if missing**

Run: `which rg || echo "NOT FOUND"`

If `NOT FOUND`, install ripgrep. On Ubuntu/Debian: `sudo apt-get install -y ripgrep`. On WSL: same. On macOS: `brew install ripgrep`. Re-run `which rg` to confirm.

- [ ] **Step 5: Run tests — they must pass**

Run: `pytest tests/unit/test_project_index_mcp.py -v`
Expected: all ~11 tests PASSED (filename/unknown-kind tests pass even without rg; content/symbol/outline are skipped if `rg` missing).

- [ ] **Step 6: Update CI to install ripgrep**

In `.github/workflows/ci.yml`, after the `Set up Python ${{ matrix.python-version }}` step and before the `Install dependencies` step, insert:

```yaml
      - name: Install ripgrep
        run: sudo apt-get update && sudo apt-get install -y ripgrep
```

The surrounding context should look like:

```yaml
      - name: Set up Python ${{ matrix.python-version }}
        uses: actions/setup-python@v5
        with:
          python-version: ${{ matrix.python-version }}

      - name: Install ripgrep
        run: sudo apt-get update && sudo apt-get install -y ripgrep

      - name: Install dependencies
        run: |
          python -m pip install --upgrade pip
          pip install -e ".[dev]"
```

- [ ] **Step 7: Run the full suite**

Run: `pytest tests/unit -v`
Expected: all Phase 1 + Phase 2 tests green. Approximately ~60–70 total.

- [ ] **Step 8: Commit**

```bash
git add src/aegis/mcp_servers/project_index_mcp.py tests/unit/test_project_index_mcp.py .github/workflows/ci.yml
git commit -m "feat(mcp): implement aegis-project-index-mcp with rg backend"
```

---

## Task 8: Phase 2 full-suite validation and completion tag

**Files:**
- No code changes. Only validation, manual smoke, and the completion tag.

- [ ] **Step 1: Run the full test suite**

Run: `pytest tests/unit -v`
Expected: all tests green.

- [ ] **Step 2: Run the linters**

Run: `ruff check src tests`
Expected: "All checks passed!"

Run: `ruff format --check src tests`
Expected: "X files already formatted". If not, run `ruff format src tests` and commit the reformat as a separate follow-up commit: `style: ruff format phase 2 mcp_servers`.

Run: `mypy`
Expected: "Success: no issues found in N source files".

If mypy complains about `mcp.server.fastmcp` being untyped, add to `pyproject.toml` under `[[tool.mypy.overrides]]`:

```toml
[[tool.mypy.overrides]]
module = ["mcp", "mcp.*"]
ignore_missing_imports = true
```

Then re-run mypy.

- [ ] **Step 3: Manual smoke test — each console script launches**

For each server, run the following and confirm the process starts without crashing. FastMCP servers block on stdin; send EOF after one second to exit cleanly.

```bash
timeout 1 aegis-fs-mcp --scope /tmp </dev/null; echo "exit=$?"
timeout 1 aegis-shell-mcp --scope /tmp </dev/null; echo "exit=$?"
timeout 1 aegis-git-mcp --scope "$(pwd)" </dev/null; echo "exit=$?"
timeout 1 aegis-project-index-mcp --scope "$(pwd)" </dev/null; echo "exit=$?"
```

Expected: each prints `exit=124` (timeout hit) or `exit=0` (clean EOF). Either is fine — what we're checking is that the console script exists and starts the server. A non-zero exit other than 124 indicates the server crashed; investigate.

Also verify `--scope` is required:

```bash
aegis-fs-mcp 2>&1 | head -3
```

Expected: "the following arguments are required: --scope".

- [ ] **Step 4: Manual smoke test — import every module cleanly**

Run:

```bash
python -c "from aegis.mcp_servers import fs_mcp, shell_mcp, git_mcp, project_index_mcp; print('ok')"
```

Expected: `ok`.

- [ ] **Step 5: Verify the git log tells a clean story**

Run: `git log --oneline phase-1-complete..HEAD`
Expected: roughly these commits (order may differ if tasks were reordered):

```
feat(mcp): scaffold mcp_servers base with scope parsing helpers
feat(mcp): implement aegis-fs-mcp with scope-enforced fs tools
feat(mcp): implement aegis-shell-mcp with allow-list and scoped cwd
feat(mcp): implement aegis-git-mcp read tools (status, diff, log)
feat(mcp): add git_mcp write tools (add, commit, branch, checkout)
feat(mcp): add git_mcp worktree and merge tools
feat(mcp): implement aegis-project-index-mcp with rg backend
```

If any commit is missing or the messages are unclear, ask the user whether to squash or amend before tagging.

- [ ] **Step 6: Push and tag**

```bash
git push origin main
git tag phase-2-complete
git push origin phase-2-complete
```

- [ ] **Step 7: Write a short handoff to Phase 3**

The Phase 1 plan has "Appendix B — Handoff to Phase 2" at its end. Do the same for Phase 2 by appending this section to `docs/superpowers/plans/2026-04-14-aegis-phase-2-mcp-servers.md` (the file you are reading). See Appendix B below — it's already written and needs no further edits. Just confirm it is present and commit any fix if needed.

---

## Appendix A — Review checklist for this plan

Used during subagent-driven review between tasks.

**Spec coverage:**
- §10.1 `aegis-git-mcp` — all 10 tools: Task 4 (3), Task 5 (4), Task 6 (3). ✓
- §10.2 `aegis-fs-mcp` — all 7 tools: Task 2. ✓
- §10.3 `aegis-shell-mcp` — shell_exec with allow-list and scoped cwd: Task 3. ✓
- §10.4 `aegis-project-index-mcp` — search/file_tree/outline: Task 7. ✓
- §10.5 Public distribution — four console scripts in pyproject.toml: Task 1. ✓
- §11.4 Worktree lifecycle — git_worktree_add/remove delegating to core.worktree: Task 6. ✓
- §11.5 Prompt-injection posture — shell_exec without shell=True, command/args split, allow-list enforced server-side: Task 3. ✓

**Non-negotiables:**
- Every tool path argument flows through `resolve_in_scope` (defense in depth).
- `shell_exec` never uses `shell=True`.
- No ctags dependency added; outline uses ripgrep.
- No async test machinery added.
- Phase 1 modules are not modified.
- Git log stays clean — one feature commit per task.

---

## Appendix B — Handoff to Phase 3

Phase 3 will:

1. Introduce `anthropic[agent]` (Claude Agent SDK) as a dependency.
2. Create `src/aegis/agents/base.py` — a thin wrapper around the Claude Agent SDK that binds a prompt file, a model ID, and an MCP client config (which MCP servers the agent may call, with which tool allow-list).
3. Create `src/aegis/agents/tools.py` — the glue that spawns each of the four MCP servers built in Phase 2 (with the correct `--scope`) and registers their tools as Claude Agent SDK tools.
4. Author five prompts under `src/aegis/agents/prompts/{pm,dev,qa,reviewer,docs}.md` per spec §4.2.
5. Add per-agent unit tests with a mocked Claude Agent SDK (no real LLM calls) asserting prompt loading, tool binding, and per-role allow-lists.
6. No changes to Phase 1 or Phase 2 modules are expected.

The four MCP server `main()` entrypoints built in this plan will be the exact commands Phase 3's `agents/tools.py` spawns via `StdioServerParameters`. The `ALLOW_CMDS` env var on `aegis-shell-mcp` will be set by agent config (tighter for QA than for Dev, etc.).

---

*End of Phase 2 implementation plan.*
