# Phase 6 — Read-only Web Dashboard Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the `aegis web` CLI stub with a working read-only FastAPI dashboard (kanban, task detail with git-diff preview, JSONL log stream, approve/reject buttons, config view) that runs on `127.0.0.1:8765` and shares the runtime layer with the existing CLI.

**Architecture:** A `create_app(aegis_dir, repo_root)` factory builds a FastAPI instance with an `OriginHostMiddleware` (whitelists `127.0.0.1:<port>` and `localhost:<port>`) and a process-scoped CSRF token (random 32-byte hex; required on all `POST` routes via `X-CSRF-Token` header or hidden form input). Routes read state from the filesystem only — `core.lifecycle.list_tasks()` for the kanban, `core.task.parse_task()` for task detail, the existing JSONL trace files for logs, and `git diff --stat` (subprocess) for the diff preview. `POST /task/<id>/{approve,reject}` calls the existing `aegis.graph.runtime.{resume_after_approve,reject_task}` functions directly. The `aegis web` CLI command starts uvicorn in the foreground (Ctrl+C exits). LangGraph checkpointer access is intentionally avoided to dodge SQLite lock contention with concurrent `aegis run`.

**Tech Stack:** `fastapi`, `uvicorn[standard]`, `jinja2`, `markdown-it-py` (markdown render); HTMX 1.x and Tailwind 3 via CDN script tags (no build step); existing `aegis.core.{config,task,lifecycle}`, `aegis.graph.runtime`, `aegis.cli.commands.init.AEGIS_DIRNAME`, `aegis.cli.commands.logs._format_line`.

---

## Pre-flight

Before starting any task, verify the workspace is in the expected post-Phase-5 state.

```bash
git status                                          # clean working tree
git log --oneline -1                                # 0a1997b docs: observability section in README
git tag -l | grep phase-5-complete                  # phase-5-complete
pytest tests/unit -q --ignore=tests/unit/test_shell_mcp.py
```

If any check fails, stop and reconcile before proceeding. Phase 6 assumes:
- `aegis.cli.commands.init.AEGIS_DIRNAME == ".aegis"`
- `aegis.core.lifecycle.list_tasks(aegis_dir, status)` returns `list[tuple[Task, Path]]`
- `aegis.core.lifecycle.find_task(aegis_dir, task_id)` returns `tuple[Task, Path] | None`
- `aegis.graph.runtime.resume_after_approve(*, task_id, aegis_dir, repo_root, config)` and `aegis.graph.runtime.reject_task(*, task_id, aegis_dir, repo_root, reason)` exist
- `aegis.cli.commands.stubs.register_stubs(app)` registers the placeholder `aegis web`
- `src/aegis/web/__init__.py` exists as a one-line placeholder string

Tests use `pytest` + `fastapi.testclient.TestClient`. The `fastapi`/`uvicorn`/`jinja2`/`markdown-it-py` packages are not yet installed; Task 1 adds them and runs `pip install -e .[dev]`.

---

## Map of files this phase touches

**Created:**

- `src/aegis/web/app.py`                          — `create_app(aegis_dir, repo_root, config)` FastAPI factory + middleware wiring + Jinja2 environment
- `src/aegis/web/middleware.py`                   — `OriginHostMiddleware` (Starlette `BaseHTTPMiddleware`)
- `src/aegis/web/csrf.py`                         — `CSRFManager` (random token, FastAPI dependency for POST verification)
- `src/aegis/web/render.py`                       — `render_markdown(body) -> str` using `markdown-it-py`
- `src/aegis/web/git_diff.py`                     — `diff_stat(repo_root, branch) -> str` and `diff_full(repo_root, branch) -> str` via subprocess
- `src/aegis/web/log_tail.py`                     — `tail_jsonl(path, max_lines=200) -> list[dict]` (parses + reuses `_format_line`)
- `src/aegis/web/routes/__init__.py`              — empty
- `src/aegis/web/routes/kanban.py`                — `GET /`
- `src/aegis/web/routes/task.py`                  — `GET /task/{task_id}`, `GET /task/{task_id}/logs` (HTMX partial)
- `src/aegis/web/routes/actions.py`               — `POST /task/{task_id}/approve`, `POST /task/{task_id}/reject`
- `src/aegis/web/routes/config_view.py`           — `GET /config`
- `src/aegis/web/templates/base.html`             — page shell + HTMX/Tailwind CDN scripts + nav
- `src/aegis/web/templates/kanban.html`           — 4-column board
- `src/aegis/web/templates/task.html`             — task detail view
- `src/aegis/web/templates/_logs.html`            — HTMX partial (no `<html>` shell)
- `src/aegis/web/templates/config.html`           — read-only YAML pre block
- `src/aegis/web/static/.gitkeep`                 — placeholder (Tailwind via CDN; no custom CSS yet)
- `src/aegis/cli/commands/web.py`                 — real `aegis web` command (uvicorn launcher)
- `tests/unit/test_web_app.py`
- `tests/unit/test_web_middleware.py`
- `tests/unit/test_web_csrf.py`
- `tests/unit/test_web_render.py`
- `tests/unit/test_web_git_diff.py`
- `tests/unit/test_web_log_tail.py`
- `tests/unit/test_web_kanban.py`
- `tests/unit/test_web_task.py`
- `tests/unit/test_web_actions.py`
- `tests/unit/test_web_config_view.py`
- `tests/unit/test_cli_web.py`

**Modified:**

- `pyproject.toml`                                — add `fastapi`, `uvicorn[standard]`, `jinja2`, `markdown-it-py` (+ dev: `httpx` for `TestClient`)
- `src/aegis/web/__init__.py`                     — export `create_app` (real one, not the placeholder string)
- `src/aegis/cli/commands/stubs.py`               — drop the `web` stub; keep `register_stubs` callable for any future stubs (currently empty after this drop)
- `src/aegis/cli/main.py`                         — register the real `aegis web`
- `README.md`                                     — add "Web dashboard" section
- `docs/status.json`                              — flip Phase 6 to complete and add `phase-6-complete` tag

---

## Task 1: Add web dependencies

**Files:**
- Modify: `pyproject.toml`

- [ ] **Step 1: Add the FastAPI + Jinja + markdown packages**

Edit the `[project] dependencies` array in `pyproject.toml` so it ends with:

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
    "opentelemetry-api>=1.27",
    "opentelemetry-sdk>=1.27",
    "opentelemetry-exporter-otlp-proto-http>=1.27",
    "langsmith>=0.1.140",
    "langfuse>=2.50",
    "fastapi>=0.110",
    "uvicorn[standard]>=0.27",
    "jinja2>=3.1",
    "markdown-it-py>=3.0",
]
```

And update the `[project.optional-dependencies] dev` array:

```toml
dev = [
    "pytest>=8.0",
    "ruff>=0.6",
    "mypy>=1.10",
    "types-PyYAML>=6.0",
    "httpx>=0.27",
]
```

`httpx` is required by `fastapi.testclient.TestClient`. (FastAPI does not declare it as a runtime dep.)

- [ ] **Step 2: Install in development mode**

Run: `pip install -e .[dev]`
Expected: installs without resolver errors.

- [ ] **Step 3: Smoke-import**

Run:

```bash
python -c "from fastapi import FastAPI; from fastapi.testclient import TestClient; from jinja2 import Environment; from markdown_it import MarkdownIt; print('ok')"
```

Expected: `ok`.

- [ ] **Step 4: Commit**

```bash
git add pyproject.toml
git commit -m "build: add FastAPI + Jinja + markdown-it-py to phase 6 deps"
```

---

## Task 2: Markdown render helper

**Files:**
- Create: `src/aegis/web/render.py`
- Test: `tests/unit/test_web_render.py`

- [ ] **Step 1: Write failing tests**

Create `tests/unit/test_web_render.py`:

```python
from __future__ import annotations

from aegis.web.render import render_markdown


def test_render_basic_markdown() -> None:
    html = render_markdown("# Title\n\nHello **world**.")
    assert "<h1>" in html
    assert "Title" in html
    assert "<strong>world</strong>" in html


def test_render_escapes_raw_html_by_default() -> None:
    html = render_markdown("<script>alert(1)</script>")
    assert "<script>" not in html
    assert "&lt;script&gt;" in html


def test_render_supports_fenced_code() -> None:
    html = render_markdown("```python\nprint('hi')\n```")
    assert "<pre>" in html
    assert "print" in html
```

- [ ] **Step 2: Run tests to confirm they fail**

Run: `pytest tests/unit/test_web_render.py -v`
Expected: 3 FAILED with `ModuleNotFoundError: No module named 'aegis.web.render'`.

- [ ] **Step 3: Implement `render_markdown`**

Create `src/aegis/web/render.py`:

```python
"""Render task body markdown to HTML for the dashboard.

`html=False` keeps raw HTML escaped — task bodies come from the user's
filesystem, but we still want defense in depth against accidental
script injection in commit messages or pasted PR bodies.
"""

from __future__ import annotations

from markdown_it import MarkdownIt

__all__ = ["render_markdown"]

_md = MarkdownIt("commonmark", {"html": False, "linkify": True, "breaks": False})


def render_markdown(body: str) -> str:
    return _md.render(body)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/unit/test_web_render.py -v`
Expected: 3 PASSED.

- [ ] **Step 5: Commit**

```bash
git add src/aegis/web/render.py tests/unit/test_web_render.py
git commit -m "feat(web): markdown render helper"
```

---

## Task 3: JSONL trace tail helper

**Files:**
- Create: `src/aegis/web/log_tail.py`
- Test: `tests/unit/test_web_log_tail.py`

- [ ] **Step 1: Write failing tests**

Create `tests/unit/test_web_log_tail.py`:

```python
from __future__ import annotations

import json
from pathlib import Path

from aegis.web.log_tail import tail_jsonl


def _write(path: Path, *records: dict) -> None:
    with open(path, "a", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(r) + "\n")


def _record(name: str, *, verdict: str | None = None) -> dict:
    return {
        "name": name,
        "trace_id": "0" * 32,
        "span_id": "0" * 16,
        "parent_span_id": None,
        "start_time_ns": 1_000_000_000,
        "end_time_ns": 1_500_000_000,
        "duration_ns": 500_000_000,
        "status": {"code": "OK", "description": None},
        "attributes": {**({"aegis.verdict": verdict} if verdict else {})},
        "events": [],
    }


def test_tail_returns_formatted_lines_in_order(tmp_path: Path) -> None:
    p = tmp_path / "001.jsonl"
    _write(p, _record("pm_node"), _record("dev_node"), _record("qa_node", verdict="pass"))
    out = tail_jsonl(p)
    assert len(out) == 3
    assert "pm_node" in out[0]
    assert "qa_node" in out[2]
    assert "verdict=pass" in out[2]


def test_tail_caps_at_max_lines(tmp_path: Path) -> None:
    p = tmp_path / "002.jsonl"
    _write(p, *(_record(f"n{i}") for i in range(50)))
    out = tail_jsonl(p, max_lines=10)
    assert len(out) == 10
    assert "n40" in out[0]
    assert "n49" in out[-1]


def test_tail_returns_empty_for_missing_file(tmp_path: Path) -> None:
    assert tail_jsonl(tmp_path / "missing.jsonl") == []


def test_tail_skips_malformed_lines(tmp_path: Path) -> None:
    p = tmp_path / "003.jsonl"
    p.write_text("not json\n", encoding="utf-8")
    _write(p, _record("pm_node"))
    out = tail_jsonl(p)
    assert len(out) == 1
    assert "pm_node" in out[0]
```

- [ ] **Step 2: Run tests to confirm they fail**

Run: `pytest tests/unit/test_web_log_tail.py -v`
Expected: 4 FAILED with `ModuleNotFoundError: No module named 'aegis.web.log_tail'`.

- [ ] **Step 3: Implement `tail_jsonl`**

Create `src/aegis/web/log_tail.py`:

```python
"""Read the last N lines of a JSONL trace file as formatted display strings.

Reuses :func:`aegis.cli.commands.logs._format_line` so the dashboard
shows the same per-span line format as `aegis logs`.
"""

from __future__ import annotations

import json
from collections import deque
from pathlib import Path

from aegis.cli.commands.logs import _format_line

__all__ = ["tail_jsonl"]


def tail_jsonl(path: Path, max_lines: int = 200) -> list[str]:
    if not path.exists():
        return []
    lines: deque[str] = deque(maxlen=max_lines)
    with open(path, encoding="utf-8") as f:
        for raw in f:
            raw = raw.strip()
            if not raw:
                continue
            try:
                rec = json.loads(raw)
            except json.JSONDecodeError:
                continue
            lines.append(_format_line(rec))
    return list(lines)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/unit/test_web_log_tail.py -v`
Expected: 4 PASSED.

- [ ] **Step 5: Commit**

```bash
git add src/aegis/web/log_tail.py tests/unit/test_web_log_tail.py
git commit -m "feat(web): JSONL trace tail helper"
```

---

## Task 4: Git diff preview helper

**Files:**
- Create: `src/aegis/web/git_diff.py`
- Test: `tests/unit/test_web_git_diff.py`

- [ ] **Step 1: Write failing tests**

Create `tests/unit/test_web_git_diff.py`:

```python
from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from aegis.web.git_diff import diff_full, diff_stat


@pytest.fixture
def repo_with_branch(git_repo: Path) -> tuple[Path, str]:
    branch = "aegis/001-add-feature"
    subprocess.run(["git", "-C", str(git_repo), "checkout", "-b", branch], check=True)
    (git_repo / "feature.py").write_text("def f():\n    return 1\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(git_repo), "add", "feature.py"], check=True)
    subprocess.run(
        ["git", "-C", str(git_repo), "commit", "-q", "-m", "add feature"], check=True
    )
    subprocess.run(["git", "-C", str(git_repo), "checkout", "main"], check=True)
    return git_repo, branch


def test_diff_stat_shows_added_file(repo_with_branch: tuple[Path, str]) -> None:
    repo, branch = repo_with_branch
    out = diff_stat(repo, branch)
    assert "feature.py" in out
    assert "+" in out  # diffstat line uses '+' to indicate insertions


def test_diff_full_includes_added_lines(repo_with_branch: tuple[Path, str]) -> None:
    repo, branch = repo_with_branch
    out = diff_full(repo, branch)
    assert "+def f():" in out


def test_diff_stat_returns_empty_for_unknown_branch(git_repo: Path) -> None:
    assert diff_stat(git_repo, "aegis/does-not-exist") == ""


def test_diff_full_returns_empty_for_unknown_branch(git_repo: Path) -> None:
    assert diff_full(git_repo, "aegis/does-not-exist") == ""
```

The `git_repo` fixture already exists in `tests/unit/conftest.py`.

- [ ] **Step 2: Run tests to confirm they fail**

Run: `pytest tests/unit/test_web_git_diff.py -v`
Expected: 4 FAILED with `ModuleNotFoundError: No module named 'aegis.web.git_diff'`.

- [ ] **Step 3: Implement `diff_stat` / `diff_full`**

Create `src/aegis/web/git_diff.py`:

```python
"""Read-only `git diff main..<branch>` helpers for the dashboard.

Returns an empty string instead of raising when the branch does not
exist, so the task-detail page can render before a worktree is set up.
The truncation cap on `diff_full` exists so a runaway diff cannot blow
up the rendered HTML.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

__all__ = ["diff_stat", "diff_full"]

_MAIN = "main"
_FULL_DIFF_BYTE_CAP = 256 * 1024  # 256 KB


def _run(repo_root: Path, args: list[str]) -> str:
    try:
        result = subprocess.run(
            ["git", "-C", str(repo_root), *args],
            capture_output=True,
            text=True,
            check=False,
        )
    except FileNotFoundError:
        return ""
    if result.returncode != 0:
        return ""
    return result.stdout


def diff_stat(repo_root: Path, branch: str) -> str:
    return _run(repo_root, ["diff", "--stat", f"{_MAIN}..{branch}"])


def diff_full(repo_root: Path, branch: str) -> str:
    out = _run(repo_root, ["diff", f"{_MAIN}..{branch}"])
    if len(out.encode("utf-8")) > _FULL_DIFF_BYTE_CAP:
        encoded = out.encode("utf-8")[:_FULL_DIFF_BYTE_CAP]
        out = encoded.decode("utf-8", errors="ignore")
        out += "\n... [diff truncated at 256 KB] ...\n"
    return out
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/unit/test_web_git_diff.py -v`
Expected: 4 PASSED.

- [ ] **Step 5: Commit**

```bash
git add src/aegis/web/git_diff.py tests/unit/test_web_git_diff.py
git commit -m "feat(web): git diff preview helpers"
```

---

## Task 5: CSRF manager

**Files:**
- Create: `src/aegis/web/csrf.py`
- Test: `tests/unit/test_web_csrf.py`

- [ ] **Step 1: Write failing tests**

Create `tests/unit/test_web_csrf.py`:

```python
from __future__ import annotations

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from aegis.web.csrf import CSRFManager


def test_token_is_64_hex_chars() -> None:
    mgr = CSRFManager()
    assert len(mgr.token) == 64
    int(mgr.token, 16)  # parses as hex


def test_two_managers_have_different_tokens() -> None:
    a = CSRFManager()
    b = CSRFManager()
    assert a.token != b.token


def test_dependency_rejects_missing_header() -> None:
    mgr = CSRFManager()
    app = FastAPI()

    @app.post("/x")
    def _x(_: None = mgr.depends_verify()) -> dict[str, str]:
        return {"ok": "yes"}

    client = TestClient(app)
    response = client.post("/x")
    assert response.status_code == 403


def test_dependency_rejects_wrong_token() -> None:
    mgr = CSRFManager()
    app = FastAPI()

    @app.post("/x")
    def _x(_: None = mgr.depends_verify()) -> dict[str, str]:
        return {"ok": "yes"}

    client = TestClient(app)
    response = client.post("/x", headers={"X-CSRF-Token": "deadbeef"})
    assert response.status_code == 403


def test_dependency_accepts_correct_token() -> None:
    mgr = CSRFManager()
    app = FastAPI()

    @app.post("/x")
    def _x(_: None = mgr.depends_verify()) -> dict[str, str]:
        return {"ok": "yes"}

    client = TestClient(app)
    response = client.post("/x", headers={"X-CSRF-Token": mgr.token})
    assert response.status_code == 200
    assert response.json() == {"ok": "yes"}


def test_dependency_accepts_form_field_when_no_header() -> None:
    mgr = CSRFManager()
    app = FastAPI()

    @app.post("/x")
    def _x(_: None = mgr.depends_verify()) -> dict[str, str]:
        return {"ok": "yes"}

    client = TestClient(app)
    response = client.post("/x", data={"csrf_token": mgr.token})
    assert response.status_code == 200
```

- [ ] **Step 2: Run tests to confirm they fail**

Run: `pytest tests/unit/test_web_csrf.py -v`
Expected: 6 FAILED with `ModuleNotFoundError: No module named 'aegis.web.csrf'`.

- [ ] **Step 3: Implement `CSRFManager`**

Create `src/aegis/web/csrf.py`:

```python
"""Process-scoped CSRF token: one random 32-byte hex per server boot.

The token is regenerated every time `aegis web` starts, embedded in
templates, and required on every POST. We accept it from either an
`X-CSRF-Token` header (HTMX preferred) or a `csrf_token` form field
(fallback for native form submits). The token is constant-time
compared.
"""

from __future__ import annotations

import secrets
from collections.abc import Callable
from typing import Annotated

from fastapi import Form, Header, HTTPException, status

__all__ = ["CSRFManager"]


class CSRFManager:
    def __init__(self) -> None:
        self.token: str = secrets.token_hex(32)

    def verify(self, header_token: str | None, form_token: str | None) -> None:
        candidate = header_token or form_token
        if candidate is None or not secrets.compare_digest(candidate, self.token):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="invalid or missing CSRF token",
            )

    def depends_verify(self) -> Callable[..., None]:
        token = self.token  # capture by reference

        def _dep(
            x_csrf_token: Annotated[str | None, Header()] = None,
            csrf_token: Annotated[str | None, Form()] = None,
        ) -> None:
            candidate = x_csrf_token or csrf_token
            if candidate is None or not secrets.compare_digest(candidate, token):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="invalid or missing CSRF token",
                )

        return _dep
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/unit/test_web_csrf.py -v`
Expected: 6 PASSED.

- [ ] **Step 5: Commit**

```bash
git add src/aegis/web/csrf.py tests/unit/test_web_csrf.py
git commit -m "feat(web): process-scoped CSRF manager"
```

---

## Task 6: Origin/Host middleware

**Files:**
- Create: `src/aegis/web/middleware.py`
- Test: `tests/unit/test_web_middleware.py`

- [ ] **Step 1: Write failing tests**

Create `tests/unit/test_web_middleware.py`:

```python
from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from aegis.web.middleware import OriginHostMiddleware


def _app(allowed_hosts: set[str]) -> FastAPI:
    app = FastAPI()
    app.add_middleware(OriginHostMiddleware, allowed_hosts=allowed_hosts)

    @app.get("/")
    def _home() -> dict[str, str]:
        return {"ok": "yes"}

    @app.post("/x")
    def _x() -> dict[str, str]:
        return {"ok": "yes"}

    return app


def test_get_with_allowed_host_passes() -> None:
    client = TestClient(_app({"127.0.0.1:8765"}))
    response = client.get("/", headers={"Host": "127.0.0.1:8765"})
    assert response.status_code == 200


def test_get_with_disallowed_host_rejected() -> None:
    client = TestClient(_app({"127.0.0.1:8765"}))
    response = client.get("/", headers={"Host": "evil.com"})
    assert response.status_code == 421


def test_post_without_origin_rejected() -> None:
    client = TestClient(_app({"127.0.0.1:8765"}))
    response = client.post("/x", headers={"Host": "127.0.0.1:8765"})
    assert response.status_code == 403


def test_post_with_allowed_origin_passes() -> None:
    client = TestClient(_app({"127.0.0.1:8765"}))
    response = client.post(
        "/x",
        headers={"Host": "127.0.0.1:8765", "Origin": "http://127.0.0.1:8765"},
    )
    assert response.status_code == 200


def test_post_with_disallowed_origin_rejected() -> None:
    client = TestClient(_app({"127.0.0.1:8765"}))
    response = client.post(
        "/x",
        headers={"Host": "127.0.0.1:8765", "Origin": "http://evil.com"},
    )
    assert response.status_code == 403
```

- [ ] **Step 2: Run tests to confirm they fail**

Run: `pytest tests/unit/test_web_middleware.py -v`
Expected: 5 FAILED with `ModuleNotFoundError: No module named 'aegis.web.middleware'`.

- [ ] **Step 3: Implement `OriginHostMiddleware`**

Create `src/aegis/web/middleware.py`:

```python
"""Reject requests whose Host or Origin headers fall outside a whitelist.

Defense against DNS rebinding (Host check) and cross-site POST CSRF
(Origin check). The whitelist is built from the bound (host, port)
plus the canonical localhost aliases.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from urllib.parse import urlparse

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import PlainTextResponse, Response

__all__ = ["OriginHostMiddleware", "build_allowed_hosts"]

_SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}


def build_allowed_hosts(host: str, port: int) -> set[str]:
    return {
        f"{host}:{port}",
        f"127.0.0.1:{port}",
        f"localhost:{port}",
    }


class OriginHostMiddleware(BaseHTTPMiddleware):
    def __init__(self, app: object, *, allowed_hosts: set[str]) -> None:
        super().__init__(app)  # type: ignore[arg-type]
        self.allowed_hosts = allowed_hosts

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        host = request.headers.get("host", "")
        if host not in self.allowed_hosts:
            return PlainTextResponse("Misdirected Request", status_code=421)
        if request.method not in _SAFE_METHODS:
            origin = request.headers.get("origin", "")
            if not origin:
                return PlainTextResponse("Origin header required", status_code=403)
            parsed = urlparse(origin)
            if parsed.netloc not in self.allowed_hosts:
                return PlainTextResponse("Origin not allowed", status_code=403)
        return await call_next(request)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/unit/test_web_middleware.py -v`
Expected: 5 PASSED.

- [ ] **Step 5: Commit**

```bash
git add src/aegis/web/middleware.py tests/unit/test_web_middleware.py
git commit -m "feat(web): Origin/Host whitelist middleware"
```

---

## Task 7: App factory + base template

**Files:**
- Create: `src/aegis/web/app.py`
- Create: `src/aegis/web/templates/base.html`
- Create: `src/aegis/web/static/.gitkeep`
- Modify: `src/aegis/web/__init__.py`
- Test: `tests/unit/test_web_app.py`

- [ ] **Step 1: Write failing tests**

Create `tests/unit/test_web_app.py`:

```python
from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from aegis.cli.commands.init import run_init
from aegis.core.config import load_config
from aegis.web.app import create_app


@pytest.fixture
def app_client(git_repo: Path) -> TestClient:
    aegis_dir = run_init(git_repo)
    config = load_config(aegis_dir / "config.yaml")
    app = create_app(
        aegis_dir=aegis_dir,
        repo_root=git_repo,
        config=config,
        host="127.0.0.1",
        port=8765,
    )
    return TestClient(app, headers={"Host": "127.0.0.1:8765"})


def test_app_factory_returns_fastapi_instance(git_repo: Path) -> None:
    aegis_dir = run_init(git_repo)
    config = load_config(aegis_dir / "config.yaml")
    app = create_app(
        aegis_dir=aegis_dir, repo_root=git_repo, config=config,
        host="127.0.0.1", port=8765,
    )
    assert app.title == "Aegis"


def test_kanban_route_returns_200(app_client: TestClient) -> None:
    response = app_client.get("/")
    assert response.status_code == 200
    assert "Aegis" in response.text


def test_disallowed_host_rejected(git_repo: Path) -> None:
    aegis_dir = run_init(git_repo)
    config = load_config(aegis_dir / "config.yaml")
    app = create_app(
        aegis_dir=aegis_dir, repo_root=git_repo, config=config,
        host="127.0.0.1", port=8765,
    )
    client = TestClient(app, headers={"Host": "evil.com"})
    response = client.get("/")
    assert response.status_code == 421


def test_csrf_token_exposed_to_templates(app_client: TestClient) -> None:
    response = app_client.get("/")
    # token rendered into the page (we'll embed it as a meta tag)
    assert 'name="csrf-token"' in response.text
```

- [ ] **Step 2: Run tests to confirm they fail**

Run: `pytest tests/unit/test_web_app.py -v`
Expected: 4 FAILED with `ModuleNotFoundError: No module named 'aegis.web.app'`.

- [ ] **Step 3: Implement the app factory**

Create `src/aegis/web/app.py`:

```python
"""FastAPI app factory for the Aegis read-only dashboard.

Owns: middleware stack, Jinja2 environment, CSRF manager wiring,
route registration. Holds no global state — each `create_app` call
returns a self-contained app keyed to one `.aegis/` directory.
"""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from aegis.core.config import AegisConfig
from aegis.web.csrf import CSRFManager
from aegis.web.middleware import OriginHostMiddleware, build_allowed_hosts

__all__ = ["create_app"]

_TEMPLATES_DIR = Path(__file__).parent / "templates"
_STATIC_DIR = Path(__file__).parent / "static"


def create_app(
    *,
    aegis_dir: Path,
    repo_root: Path,
    config: AegisConfig,
    host: str = "127.0.0.1",
    port: int = 8765,
) -> FastAPI:
    app = FastAPI(title="Aegis", docs_url=None, redoc_url=None, openapi_url=None)
    app.add_middleware(
        OriginHostMiddleware,
        allowed_hosts=build_allowed_hosts(host, port),
    )

    templates = Jinja2Templates(directory=str(_TEMPLATES_DIR))
    csrf = CSRFManager()

    app.state.aegis_dir = aegis_dir
    app.state.repo_root = repo_root
    app.state.config = config
    app.state.templates = templates
    app.state.csrf = csrf

    if _STATIC_DIR.exists():
        app.mount("/static", StaticFiles(directory=str(_STATIC_DIR)), name="static")

    from aegis.web.routes.kanban import router as kanban_router
    from aegis.web.routes.task import router as task_router
    from aegis.web.routes.actions import router as actions_router
    from aegis.web.routes.config_view import router as config_router

    app.include_router(kanban_router)
    app.include_router(task_router)
    app.include_router(actions_router)
    app.include_router(config_router)

    return app
```

- [ ] **Step 4: Create the base template**

Create `src/aegis/web/templates/base.html`:

```html
<!doctype html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <meta name="csrf-token" content="{{ csrf_token }}">
    <title>{% block title %}Aegis{% endblock %}</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <script src="https://unpkg.com/htmx.org@1.9.12" integrity="sha384-ujb1lZYygJmzgSwoxRggbCHcjc0rB2XoQrxeTUQyRjrOnlCoYta87iKBWq3EsdM2" crossorigin="anonymous"></script>
</head>
<body class="bg-slate-50 text-slate-900 min-h-screen">
    <header class="border-b border-slate-200 bg-white">
        <nav class="max-w-7xl mx-auto px-4 py-3 flex items-center gap-6">
            <a href="/" class="font-semibold">Aegis</a>
            <a href="/" class="text-sm text-slate-600 hover:text-slate-900">Kanban</a>
            <a href="/config" class="text-sm text-slate-600 hover:text-slate-900">Config</a>
        </nav>
    </header>
    <main class="max-w-7xl mx-auto px-4 py-6">
        {% block content %}{% endblock %}
    </main>
    <script>
        document.body.addEventListener('htmx:configRequest', function(evt) {
            const meta = document.querySelector('meta[name="csrf-token"]');
            if (meta) evt.detail.headers['X-CSRF-Token'] = meta.content;
        });
    </script>
</body>
</html>
```

- [ ] **Step 5: Replace the placeholder `__init__.py`**

Replace the entire contents of `src/aegis/web/__init__.py` with:

```python
"""Read-only FastAPI dashboard for Aegis."""

from aegis.web.app import create_app

__all__ = ["create_app"]
```

- [ ] **Step 6: Create the static placeholder**

```bash
mkdir -p src/aegis/web/static
touch src/aegis/web/static/.gitkeep
```

(The kanban template will be added in Task 8 — for now `app.py` references the routes, but the route modules don't exist yet, so the test will only pass after Task 8. Skip Step 7/8 of this task and move to Task 8.)

- [ ] **Step 7: Commit (factory + base template only)**

```bash
git add src/aegis/web/app.py src/aegis/web/__init__.py src/aegis/web/templates/base.html src/aegis/web/static/.gitkeep tests/unit/test_web_app.py
git commit -m "feat(web): app factory, base template, static dir"
```

The tests in `test_web_app.py` will FAIL right now because the route modules don't exist. They become PASSING at the end of Task 8 (kanban) — that's fine, we're committing the scaffold here so individual tasks stay small.

---

## Task 8: Kanban route + template

**Files:**
- Create: `src/aegis/web/routes/__init__.py`
- Create: `src/aegis/web/routes/kanban.py`
- Create: `src/aegis/web/templates/kanban.html`
- Test: `tests/unit/test_web_kanban.py`

- [ ] **Step 1: Write failing tests**

Create `tests/unit/test_web_kanban.py`:

```python
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from aegis.cli.commands.init import run_init
from aegis.core.config import load_config
from aegis.core.task import Task, TaskFrontmatter, TaskStatus, write_task
from aegis.web.app import create_app


def _seed_task(aegis_dir: Path, *, task_id: str, title: str, status: TaskStatus) -> None:
    fm = TaskFrontmatter(
        id=task_id,
        title=title,
        status=status,
        created=datetime.now(timezone.utc),
    )
    task = Task(frontmatter=fm, body="## Goal\n\nDo the thing.\n")
    target = aegis_dir / status.value / f"{task_id}-{title.replace(' ', '-')}.md"
    write_task(task, target)


@pytest.fixture
def client(git_repo: Path) -> TestClient:
    aegis_dir = run_init(git_repo)
    _seed_task(aegis_dir, task_id="001", title="add login", status=TaskStatus.BACKLOG)
    _seed_task(aegis_dir, task_id="002", title="fix bug", status=TaskStatus.IN_PROGRESS)
    _seed_task(aegis_dir, task_id="003", title="ship feature", status=TaskStatus.REVIEW)
    _seed_task(aegis_dir, task_id="004", title="hung task", status=TaskStatus.BLOCKED)
    config = load_config(aegis_dir / "config.yaml")
    app = create_app(
        aegis_dir=aegis_dir, repo_root=git_repo, config=config,
        host="127.0.0.1", port=8765,
    )
    return TestClient(app, headers={"Host": "127.0.0.1:8765"})


def test_kanban_shows_all_four_columns(client: TestClient) -> None:
    response = client.get("/")
    assert response.status_code == 200
    body = response.text
    assert "Backlog" in body
    assert "In progress" in body
    assert "Review" in body
    assert "Blocked" in body


def test_kanban_lists_each_task(client: TestClient) -> None:
    body = client.get("/").text
    assert "add login" in body
    assert "fix bug" in body
    assert "ship feature" in body
    assert "hung task" in body


def test_kanban_card_links_to_detail(client: TestClient) -> None:
    body = client.get("/").text
    assert 'href="/task/001"' in body
    assert 'href="/task/003"' in body


def test_kanban_does_not_show_done_or_rejected(client: TestClient, git_repo: Path) -> None:
    aegis_dir = git_repo / ".aegis"
    _seed_task(aegis_dir, task_id="005", title="done task", status=TaskStatus.DONE)
    _seed_task(aegis_dir, task_id="006", title="rejected task", status=TaskStatus.REJECTED)
    body = client.get("/").text
    assert "done task" not in body
    assert "rejected task" not in body
```

- [ ] **Step 2: Run tests to confirm they fail**

Run: `pytest tests/unit/test_web_kanban.py -v`
Expected: 4 FAILED with `ModuleNotFoundError: No module named 'aegis.web.routes'`.

- [ ] **Step 3: Create the routes package**

Create `src/aegis/web/routes/__init__.py` with a single line:

```python
"""FastAPI routers for the Aegis dashboard."""
```

- [ ] **Step 4: Implement the kanban route**

Create `src/aegis/web/routes/kanban.py`:

```python
"""GET / — 4-column kanban (backlog / in-progress / review / blocked)."""

from __future__ import annotations

from fastapi import APIRouter, Request
from starlette.responses import HTMLResponse

from aegis.core.lifecycle import list_tasks
from aegis.core.task import TaskStatus

router = APIRouter()

_KANBAN_STATUSES: list[tuple[TaskStatus, str]] = [
    (TaskStatus.BACKLOG, "Backlog"),
    (TaskStatus.IN_PROGRESS, "In progress"),
    (TaskStatus.REVIEW, "Review"),
    (TaskStatus.BLOCKED, "Blocked"),
]


@router.get("/", response_class=HTMLResponse)
def kanban(request: Request) -> HTMLResponse:
    aegis_dir = request.app.state.aegis_dir
    columns: list[dict[str, object]] = []
    for status, label in _KANBAN_STATUSES:
        rows = list_tasks(aegis_dir, status=status)
        columns.append(
            {
                "status": status.value,
                "label": label,
                "cards": [
                    {
                        "id": task.frontmatter.id,
                        "title": task.frontmatter.title,
                        "priority": task.frontmatter.priority.value,
                    }
                    for task, _ in rows
                ],
            }
        )
    csrf_token = request.app.state.csrf.token
    return request.app.state.templates.TemplateResponse(
        request, "kanban.html", {"columns": columns, "csrf_token": csrf_token}
    )
```

- [ ] **Step 5: Implement the kanban template**

Create `src/aegis/web/templates/kanban.html`:

```html
{% extends "base.html" %}
{% block title %}Aegis — Kanban{% endblock %}
{% block content %}
<div class="grid grid-cols-1 md:grid-cols-4 gap-4">
    {% for col in columns %}
    <section class="bg-white border border-slate-200 rounded-md p-3">
        <header class="flex items-center justify-between mb-3">
            <h2 class="text-sm font-semibold uppercase tracking-wide text-slate-500">{{ col.label }}</h2>
            <span class="text-xs text-slate-400">{{ col.cards|length }}</span>
        </header>
        <ul class="space-y-2">
            {% for card in col.cards %}
            <li>
                <a href="/task/{{ card.id }}" class="block p-3 border border-slate-200 rounded hover:bg-slate-50">
                    <div class="text-xs text-slate-500">{{ card.id }} · {{ card.priority }}</div>
                    <div class="text-sm">{{ card.title }}</div>
                </a>
            </li>
            {% else %}
            <li class="text-xs text-slate-400 italic">empty</li>
            {% endfor %}
        </ul>
    </section>
    {% endfor %}
</div>
{% endblock %}
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `pytest tests/unit/test_web_kanban.py tests/unit/test_web_app.py -v`
Expected: all PASSED (the 4 deferred `test_web_app.py` cases now pass too because the route exists).

- [ ] **Step 7: Commit**

```bash
git add src/aegis/web/routes/__init__.py src/aegis/web/routes/kanban.py src/aegis/web/templates/kanban.html tests/unit/test_web_kanban.py
git commit -m "feat(web): kanban route + template"
```

---

## Task 9: Task detail route + template (markdown + sidebar + diff)

**Files:**
- Create: `src/aegis/web/routes/task.py`
- Create: `src/aegis/web/templates/task.html`
- Test: `tests/unit/test_web_task.py`

- [ ] **Step 1: Write failing tests**

Create `tests/unit/test_web_task.py`:

```python
from __future__ import annotations

import subprocess
from datetime import datetime, timezone
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from aegis.cli.commands.init import run_init
from aegis.core.config import load_config
from aegis.core.task import Task, TaskFrontmatter, TaskStatus, write_task
from aegis.web.app import create_app


def _seed_task(
    aegis_dir: Path,
    *,
    task_id: str,
    title: str,
    status: TaskStatus,
    body: str = "## Goal\n\nDo the thing.\n",
    pr_branch: str | None = None,
    trace_id: str | None = None,
) -> None:
    fm = TaskFrontmatter(
        id=task_id,
        title=title,
        status=status,
        created=datetime.now(timezone.utc),
        pr_branch=pr_branch,
        trace_id=trace_id,
    )
    task = Task(frontmatter=fm, body=body)
    target = aegis_dir / status.value / f"{task_id}-{title.replace(' ', '-')}.md"
    write_task(task, target)


@pytest.fixture
def client(git_repo: Path) -> TestClient:
    aegis_dir = run_init(git_repo)
    _seed_task(
        aegis_dir,
        task_id="001",
        title="add login",
        status=TaskStatus.REVIEW,
        body="## Goal\n\nAdd a **login** page.\n",
        pr_branch="aegis/001-add-login",
        trace_id="aabbccddeeff00112233445566778899",
    )
    config = load_config(aegis_dir / "config.yaml")
    app = create_app(
        aegis_dir=aegis_dir, repo_root=git_repo, config=config,
        host="127.0.0.1", port=8765,
    )
    return TestClient(app, headers={"Host": "127.0.0.1:8765"})


def test_task_detail_renders_markdown(client: TestClient) -> None:
    response = client.get("/task/001")
    assert response.status_code == 200
    assert "<strong>login</strong>" in response.text


def test_task_detail_shows_metadata(client: TestClient) -> None:
    body = client.get("/task/001").text
    assert "review" in body
    assert "aegis/001-add-login" in body
    assert "aabbccddeeff" in body  # trace_id (full or truncated)


def test_task_detail_returns_404_for_unknown_id(client: TestClient) -> None:
    response = client.get("/task/999")
    assert response.status_code == 404


def test_task_detail_shows_diff_when_branch_exists(
    client: TestClient, git_repo: Path
) -> None:
    branch = "aegis/001-add-login"
    subprocess.run(["git", "-C", str(git_repo), "checkout", "-b", branch], check=True)
    (git_repo / "login.py").write_text("def login():\n    return True\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(git_repo), "add", "login.py"], check=True)
    subprocess.run(
        ["git", "-C", str(git_repo), "commit", "-q", "-m", "add login"], check=True
    )
    subprocess.run(["git", "-C", str(git_repo), "checkout", "main"], check=True)
    body = client.get("/task/001").text
    assert "login.py" in body


def test_task_detail_shows_approve_reject_when_review(client: TestClient) -> None:
    body = client.get("/task/001").text
    assert "Approve" in body
    assert "Reject" in body


def test_task_detail_hides_approve_reject_when_not_review(
    git_repo: Path,
) -> None:
    aegis_dir = run_init(git_repo)
    _seed_task(aegis_dir, task_id="002", title="t", status=TaskStatus.BACKLOG)
    config = load_config(aegis_dir / "config.yaml")
    app = create_app(
        aegis_dir=aegis_dir, repo_root=git_repo, config=config,
        host="127.0.0.1", port=8765,
    )
    client = TestClient(app, headers={"Host": "127.0.0.1:8765"})
    body = client.get("/task/002").text
    assert "Approve" not in body
    assert "Reject" not in body


def test_logs_partial_returns_lines(client: TestClient, git_repo: Path) -> None:
    aegis_dir = git_repo / ".aegis"
    trace_path = aegis_dir / "trace" / "001.jsonl"
    import json
    record = {
        "name": "pm_node",
        "trace_id": "0" * 32, "span_id": "0" * 16, "parent_span_id": None,
        "start_time_ns": 1_000_000_000, "end_time_ns": 1_500_000_000,
        "duration_ns": 500_000_000, "status": {"code": "OK", "description": None},
        "attributes": {"aegis.role": "pm"}, "events": [],
    }
    with open(trace_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(record) + "\n")
    response = client.get("/task/001/logs")
    assert response.status_code == 200
    assert "pm_node" in response.text


def test_logs_partial_polls_via_htmx(client: TestClient) -> None:
    # the partial template renders an outer div with hx-get/hx-trigger
    response = client.get("/task/001")
    assert "/task/001/logs" in response.text
    assert "hx-trigger=\"every 1s\"" in response.text or "hx-trigger='every 1s'" in response.text
```

- [ ] **Step 2: Run tests to confirm they fail**

Run: `pytest tests/unit/test_web_task.py -v`
Expected: 8 FAILED with `ModuleNotFoundError: No module named 'aegis.web.routes.task'` (and the existing app tests still pass).

- [ ] **Step 3: Implement the task routes**

Create `src/aegis/web/routes/task.py`:

```python
"""GET /task/{task_id} — task detail with markdown body, sidebar, diff preview.
GET /task/{task_id}/logs — HTMX partial returning the last N JSONL trace lines.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from starlette.responses import HTMLResponse

from aegis.core.lifecycle import find_task
from aegis.core.task import TaskStatus
from aegis.web.git_diff import diff_full, diff_stat
from aegis.web.log_tail import tail_jsonl
from aegis.web.render import render_markdown

router = APIRouter()


@router.get("/task/{task_id}", response_class=HTMLResponse)
def task_detail(task_id: str, request: Request) -> HTMLResponse:
    aegis_dir = request.app.state.aegis_dir
    repo_root = request.app.state.repo_root
    found = find_task(aegis_dir, task_id)
    if found is None:
        raise HTTPException(status_code=404, detail=f"task {task_id} not found")
    task, task_path = found
    fm = task.frontmatter
    diff_summary = diff_stat(repo_root, fm.pr_branch) if fm.pr_branch else ""
    diff_body = diff_full(repo_root, fm.pr_branch) if fm.pr_branch else ""
    return request.app.state.templates.TemplateResponse(
        request,
        "task.html",
        {
            "task_id": task_id,
            "title": fm.title,
            "status": fm.status.value,
            "priority": fm.priority.value,
            "branch": fm.pr_branch,
            "worktree": fm.worktree,
            "trace_id": fm.trace_id,
            "body_html": render_markdown(task.body),
            "diff_summary": diff_summary,
            "diff_body": diff_body,
            "is_review": fm.status == TaskStatus.REVIEW,
            "csrf_token": request.app.state.csrf.token,
        },
    )


@router.get("/task/{task_id}/logs", response_class=HTMLResponse)
def task_logs(task_id: str, request: Request) -> HTMLResponse:
    aegis_dir = request.app.state.aegis_dir
    trace_path = aegis_dir / "trace" / f"{task_id}.jsonl"
    lines = tail_jsonl(trace_path, max_lines=200)
    return request.app.state.templates.TemplateResponse(
        request,
        "_logs.html",
        {"task_id": task_id, "lines": lines},
    )
```

- [ ] **Step 4: Implement the templates**

Create `src/aegis/web/templates/task.html`:

```html
{% extends "base.html" %}
{% block title %}Aegis — {{ task_id }} {{ title }}{% endblock %}
{% block content %}
<div class="grid grid-cols-1 lg:grid-cols-[1fr_18rem] gap-6">
    <article class="space-y-6">
        <header>
            <div class="text-xs text-slate-500">{{ task_id }} · {{ priority }}</div>
            <h1 class="text-2xl font-semibold">{{ title }}</h1>
        </header>

        <section class="prose prose-slate max-w-none bg-white border border-slate-200 rounded-md p-4">
            {{ body_html|safe }}
        </section>

        {% if diff_summary %}
        <section class="bg-white border border-slate-200 rounded-md p-4">
            <h2 class="text-sm font-semibold mb-2">Diff vs main</h2>
            <pre class="text-xs whitespace-pre-wrap bg-slate-50 p-3 rounded">{{ diff_summary }}</pre>
            <details class="mt-3">
                <summary class="text-xs text-slate-600 cursor-pointer">Full diff</summary>
                <pre class="text-xs whitespace-pre overflow-x-auto bg-slate-50 p-3 rounded mt-2">{{ diff_body }}</pre>
            </details>
        </section>
        {% endif %}

        <section class="bg-white border border-slate-200 rounded-md p-4">
            <h2 class="text-sm font-semibold mb-2">Logs</h2>
            <div hx-get="/task/{{ task_id }}/logs" hx-trigger="every 1s" hx-swap="innerHTML">
                {% include "_logs.html" %}
            </div>
        </section>
    </article>

    <aside class="space-y-3 text-sm">
        <div class="bg-white border border-slate-200 rounded-md p-4 space-y-2">
            <div><span class="text-slate-500">Status</span><div class="font-medium">{{ status }}</div></div>
            {% if branch %}<div><span class="text-slate-500">Branch</span><div class="font-mono text-xs break-all">{{ branch }}</div></div>{% endif %}
            {% if worktree %}<div><span class="text-slate-500">Worktree</span><div class="font-mono text-xs break-all">{{ worktree }}</div></div>{% endif %}
            {% if trace_id %}<div><span class="text-slate-500">Trace</span><div class="font-mono text-xs break-all">{{ trace_id }}</div></div>{% endif %}
        </div>

        {% if is_review %}
        <div class="bg-white border border-slate-200 rounded-md p-4 space-y-2">
            <form hx-post="/task/{{ task_id }}/approve" hx-confirm="Approve and merge this task?" hx-swap="none">
                <button type="submit" class="w-full bg-emerald-600 text-white text-sm py-2 rounded hover:bg-emerald-700">Approve</button>
            </form>
            <form hx-post="/task/{{ task_id }}/reject" hx-confirm="Reject this task?" hx-swap="none">
                <button type="submit" class="w-full bg-rose-600 text-white text-sm py-2 rounded hover:bg-rose-700">Reject</button>
            </form>
        </div>
        {% endif %}
    </aside>
</div>
{% endblock %}
```

Create `src/aegis/web/templates/_logs.html`:

```html
{% if lines %}
<pre class="text-xs whitespace-pre-wrap bg-slate-50 p-3 rounded max-h-96 overflow-y-auto">{% for line in lines %}{{ line }}
{% endfor %}</pre>
{% else %}
<div class="text-xs text-slate-400 italic">no trace yet</div>
{% endif %}
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/unit/test_web_task.py -v`
Expected: 8 PASSED.

- [ ] **Step 6: Commit**

```bash
git add src/aegis/web/routes/task.py src/aegis/web/templates/task.html src/aegis/web/templates/_logs.html tests/unit/test_web_task.py
git commit -m "feat(web): task detail route + HTMX log polling"
```

---

## Task 10: Approve/Reject actions

**Files:**
- Create: `src/aegis/web/routes/actions.py`
- Test: `tests/unit/test_web_actions.py`

- [ ] **Step 1: Write failing tests**

Create `tests/unit/test_web_actions.py`:

```python
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from aegis.cli.commands.init import run_init
from aegis.core.config import load_config
from aegis.core.task import Task, TaskFrontmatter, TaskStatus, write_task
from aegis.web.app import create_app


def _seed_review_task(aegis_dir: Path, *, task_id: str = "001") -> None:
    fm = TaskFrontmatter(
        id=task_id,
        title="t",
        status=TaskStatus.REVIEW,
        created=datetime.now(timezone.utc),
        pr_branch=f"aegis/{task_id}-t",
    )
    task = Task(frontmatter=fm, body="body\n")
    write_task(task, aegis_dir / "review" / f"{task_id}-t.md")


@pytest.fixture
def app_and_client(git_repo: Path) -> tuple[object, TestClient]:
    aegis_dir = run_init(git_repo)
    _seed_review_task(aegis_dir)
    config = load_config(aegis_dir / "config.yaml")
    app = create_app(
        aegis_dir=aegis_dir, repo_root=git_repo, config=config,
        host="127.0.0.1", port=8765,
    )
    client = TestClient(
        app,
        headers={"Host": "127.0.0.1:8765", "Origin": "http://127.0.0.1:8765"},
    )
    return app, client


def test_approve_without_csrf_rejected(app_and_client: tuple[object, TestClient]) -> None:
    _, client = app_and_client
    response = client.post("/task/001/approve")
    assert response.status_code == 403


def test_approve_with_csrf_calls_runtime(app_and_client: tuple[object, TestClient]) -> None:
    app, client = app_and_client
    token = app.state.csrf.token
    with patch("aegis.web.routes.actions.resume_after_approve") as mock:
        response = client.post("/task/001/approve", headers={"X-CSRF-Token": token})
        assert response.status_code == 200
        assert mock.called
        kwargs = mock.call_args.kwargs
        assert kwargs["task_id"] == "001"


def test_reject_with_csrf_calls_runtime(app_and_client: tuple[object, TestClient]) -> None:
    app, client = app_and_client
    token = app.state.csrf.token
    with patch("aegis.web.routes.actions.reject_task") as mock:
        response = client.post(
            "/task/001/reject",
            headers={"X-CSRF-Token": token},
            data={"reason": "not needed"},
        )
        assert response.status_code == 200
        assert mock.called
        kwargs = mock.call_args.kwargs
        assert kwargs["task_id"] == "001"
        assert kwargs["reason"] == "not needed"


def test_reject_without_csrf_rejected(app_and_client: tuple[object, TestClient]) -> None:
    _, client = app_and_client
    response = client.post("/task/001/reject")
    assert response.status_code == 403


def test_approve_without_origin_rejected(git_repo: Path) -> None:
    aegis_dir = run_init(git_repo)
    _seed_review_task(aegis_dir)
    config = load_config(aegis_dir / "config.yaml")
    app = create_app(
        aegis_dir=aegis_dir, repo_root=git_repo, config=config,
        host="127.0.0.1", port=8765,
    )
    client = TestClient(app, headers={"Host": "127.0.0.1:8765"})  # no Origin
    response = client.post(
        "/task/001/approve", headers={"X-CSRF-Token": app.state.csrf.token}
    )
    assert response.status_code == 403
```

- [ ] **Step 2: Run tests to confirm they fail**

Run: `pytest tests/unit/test_web_actions.py -v`
Expected: 5 FAILED with `ModuleNotFoundError: No module named 'aegis.web.routes.actions'`.

- [ ] **Step 3: Implement the actions routes**

Create `src/aegis/web/routes/actions.py`:

```python
"""POST /task/{id}/approve and /reject — call the runtime layer.

Runs the (potentially long) graph resume on a worker thread so the
event loop stays responsive. The Origin/Host whitelist + CSRF token
together gate every POST.
"""

from __future__ import annotations

from typing import Annotated

import anyio
from fastapi import APIRouter, Form, HTTPException, Request
from starlette.responses import JSONResponse

from aegis.core.lifecycle import find_task
from aegis.core.task import TaskStatus
from aegis.graph.runtime import reject_task, resume_after_approve

router = APIRouter()


@router.post("/task/{task_id}/approve")
async def approve(
    task_id: str,
    request: Request,
) -> JSONResponse:
    await _verify_csrf(request)
    aegis_dir = request.app.state.aegis_dir
    repo_root = request.app.state.repo_root
    config = request.app.state.config
    found = find_task(aegis_dir, task_id)
    if found is None:
        raise HTTPException(status_code=404, detail=f"task {task_id} not found")
    task, _ = found
    if task.frontmatter.status != TaskStatus.REVIEW:
        raise HTTPException(
            status_code=409,
            detail=f"task {task_id} is in {task.frontmatter.status.value}, not review",
        )
    await anyio.to_thread.run_sync(
        lambda: resume_after_approve(
            task_id=task_id,
            aegis_dir=aegis_dir,
            repo_root=repo_root,
            config=config,
        )
    )
    return JSONResponse({"approved": task_id})


@router.post("/task/{task_id}/reject")
async def reject(
    task_id: str,
    request: Request,
    reason: Annotated[str | None, Form()] = None,
) -> JSONResponse:
    await _verify_csrf(request)
    aegis_dir = request.app.state.aegis_dir
    repo_root = request.app.state.repo_root
    found = find_task(aegis_dir, task_id)
    if found is None:
        raise HTTPException(status_code=404, detail=f"task {task_id} not found")
    await anyio.to_thread.run_sync(
        lambda: reject_task(
            task_id=task_id,
            aegis_dir=aegis_dir,
            repo_root=repo_root,
            reason=reason,
        )
    )
    return JSONResponse({"rejected": task_id})


async def _verify_csrf(request: Request) -> None:
    header_token = request.headers.get("x-csrf-token")
    form_token: str | None = None
    if not header_token:
        ctype = request.headers.get("content-type", "")
        if ctype.startswith("application/x-www-form-urlencoded") or ctype.startswith("multipart/form-data"):
            form = await request.form()
            value = form.get("csrf_token")
            if isinstance(value, str):
                form_token = value
    request.app.state.csrf.verify(header_token, form_token)
```

(We verify CSRF inline with `_verify_csrf` rather than via `Depends` because the dependency form complicated form-body parsing in tests — the inline form is unambiguous.)

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/unit/test_web_actions.py -v`
Expected: 5 PASSED.

- [ ] **Step 5: Commit**

```bash
git add src/aegis/web/routes/actions.py tests/unit/test_web_actions.py
git commit -m "feat(web): approve/reject actions with CSRF + Origin gates"
```

---

## Task 11: Config view route

**Files:**
- Create: `src/aegis/web/routes/config_view.py`
- Create: `src/aegis/web/templates/config.html`
- Test: `tests/unit/test_web_config_view.py`

- [ ] **Step 1: Write failing tests**

Create `tests/unit/test_web_config_view.py`:

```python
from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from aegis.cli.commands.init import run_init
from aegis.core.config import load_config
from aegis.web.app import create_app


@pytest.fixture
def client(git_repo: Path) -> TestClient:
    aegis_dir = run_init(git_repo)
    config = load_config(aegis_dir / "config.yaml")
    app = create_app(
        aegis_dir=aegis_dir, repo_root=git_repo, config=config,
        host="127.0.0.1", port=8765,
    )
    return TestClient(app, headers={"Host": "127.0.0.1:8765"})


def test_config_view_returns_200(client: TestClient) -> None:
    response = client.get("/config")
    assert response.status_code == 200


def test_config_view_renders_yaml_pre_block(client: TestClient) -> None:
    body = client.get("/config").text
    assert "<pre" in body
    assert "project:" in body
    assert "observability:" in body


def test_config_view_returns_404_when_yaml_missing(git_repo: Path) -> None:
    aegis_dir = run_init(git_repo)
    config = load_config(aegis_dir / "config.yaml")
    (aegis_dir / "config.yaml").unlink()
    app = create_app(
        aegis_dir=aegis_dir, repo_root=git_repo, config=config,
        host="127.0.0.1", port=8765,
    )
    client = TestClient(app, headers={"Host": "127.0.0.1:8765"})
    response = client.get("/config")
    assert response.status_code == 404
```

- [ ] **Step 2: Run tests to confirm they fail**

Run: `pytest tests/unit/test_web_config_view.py -v`
Expected: 3 FAILED with `ModuleNotFoundError: No module named 'aegis.web.routes.config_view'`.

- [ ] **Step 3: Implement the config view route**

Create `src/aegis/web/routes/config_view.py`:

```python
"""GET /config — read-only YAML view of `.aegis/config.yaml`."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from starlette.responses import HTMLResponse

router = APIRouter()


@router.get("/config", response_class=HTMLResponse)
def config_view(request: Request) -> HTMLResponse:
    aegis_dir = request.app.state.aegis_dir
    yaml_path = aegis_dir / "config.yaml"
    if not yaml_path.exists():
        raise HTTPException(status_code=404, detail="config.yaml not found")
    yaml_text = yaml_path.read_text(encoding="utf-8")
    return request.app.state.templates.TemplateResponse(
        request,
        "config.html",
        {
            "yaml_text": yaml_text,
            "csrf_token": request.app.state.csrf.token,
        },
    )
```

- [ ] **Step 4: Implement the template**

Create `src/aegis/web/templates/config.html`:

```html
{% extends "base.html" %}
{% block title %}Aegis — Config{% endblock %}
{% block content %}
<section class="bg-white border border-slate-200 rounded-md p-4">
    <h1 class="text-sm font-semibold mb-3">.aegis/config.yaml</h1>
    <pre class="text-xs whitespace-pre overflow-x-auto bg-slate-50 p-3 rounded">{{ yaml_text }}</pre>
    <p class="text-xs text-slate-500 mt-3">Read-only. Edit on disk and restart <code>aegis web</code>.</p>
</section>
{% endblock %}
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/unit/test_web_config_view.py -v`
Expected: 3 PASSED.

- [ ] **Step 6: Commit**

```bash
git add src/aegis/web/routes/config_view.py src/aegis/web/templates/config.html tests/unit/test_web_config_view.py
git commit -m "feat(web): read-only config view"
```

---

## Task 12: `aegis web` CLI command

**Files:**
- Create: `src/aegis/cli/commands/web.py`
- Modify: `src/aegis/cli/commands/stubs.py`
- Modify: `src/aegis/cli/main.py`
- Test: `tests/unit/test_cli_web.py`

- [ ] **Step 1: Write failing tests**

Create `tests/unit/test_cli_web.py`:

```python
from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from aegis.cli.commands.init import AEGIS_DIRNAME
from aegis.cli.main import app


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


def test_web_errors_when_aegis_dir_missing(
    tmp_path: Path, runner: CliRunner, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(app, ["web"])
    assert result.exit_code != 0


def test_web_invokes_uvicorn_with_app(
    tmp_path: Path, runner: CliRunner, monkeypatch: pytest.MonkeyPatch
) -> None:
    aegis_dir = tmp_path / AEGIS_DIRNAME
    aegis_dir.mkdir()
    (aegis_dir / "config.yaml").write_text(
        "version: 1\nproject:\n  name: test\n", encoding="utf-8"
    )
    monkeypatch.chdir(tmp_path)
    with patch("aegis.cli.commands.web.uvicorn.run") as mock:
        result = runner.invoke(app, ["web", "--port", "8888"])
        assert result.exit_code == 0
        assert mock.called
        call_kwargs = mock.call_args.kwargs
        assert call_kwargs["host"] == "127.0.0.1"
        assert call_kwargs["port"] == 8888


def test_web_help_message_lists_options(runner: CliRunner) -> None:
    result = runner.invoke(app, ["web", "--help"])
    assert result.exit_code == 0
    assert "--port" in result.stdout
    assert "--host" in result.stdout
```

- [ ] **Step 2: Run tests to confirm they fail**

Run: `pytest tests/unit/test_cli_web.py -v`
Expected: tests fail because the command is still the stub (`exit code 2 = not implemented`).

- [ ] **Step 3: Implement the real `aegis web` command**

Create `src/aegis/cli/commands/web.py`:

```python
"""``aegis web`` — start the read-only dashboard (uvicorn, foreground)."""

from __future__ import annotations

from pathlib import Path

import typer
import uvicorn

from aegis.cli.commands.init import AEGIS_DIRNAME
from aegis.core.config import load_config
from aegis.web.app import create_app


def register(app_root: typer.Typer) -> None:
    @app_root.command(help="Start the read-only dashboard.")
    def web(
        port: int = typer.Option(8765, "--port"),
        host: str = typer.Option("127.0.0.1", "--host"),
    ) -> None:
        repo = Path.cwd().resolve()
        aegis = repo / AEGIS_DIRNAME
        if not aegis.exists():
            raise typer.BadParameter(f"No {AEGIS_DIRNAME}/ here. Run `aegis init` first.")
        config = load_config(aegis / "config.yaml")
        fastapi_app = create_app(
            aegis_dir=aegis,
            repo_root=repo,
            config=config,
            host=host,
            port=port,
        )
        typer.echo(f"Aegis dashboard on http://{host}:{port}")
        uvicorn.run(fastapi_app, host=host, port=port, log_level="info")
```

- [ ] **Step 4: Drop the `web` stub**

Replace the entire contents of `src/aegis/cli/commands/stubs.py` with:

```python
"""Reserved for future not-yet-implemented commands.

Currently empty — Phase 6 promoted the ``web`` stub to a real command.
"""

from __future__ import annotations

import typer

__all__ = ["register_stubs"]


def register_stubs(app: typer.Typer) -> None:  # noqa: ARG001
    """No-op: kept for forward compatibility with main.py wiring."""
```

- [ ] **Step 5: Wire the real command in `main.py`**

Edit `src/aegis/cli/main.py`. Locate the import block after `register_stubs` and add the `web` import alongside the others, and add `register_web(app)` to the call list.

Apply this diff to `src/aegis/cli/main.py`:

```python
# add to the noqa: E402 import block
from aegis.cli.commands.web import register as register_web  # noqa: E402
```

```python
# add at the bottom (after register_daemon)
register_web(app)
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `pytest tests/unit/test_cli_web.py -v`
Expected: 3 PASSED.

Also re-run the full suite to confirm nothing else broke:

Run: `pytest tests/unit -q --ignore=tests/unit/test_shell_mcp.py`
Expected: all green; new tests added in Tasks 2–11 plus the existing Phase-1–5 tests all pass.

- [ ] **Step 7: Commit**

```bash
git add src/aegis/cli/commands/web.py src/aegis/cli/commands/stubs.py src/aegis/cli/main.py tests/unit/test_cli_web.py
git commit -m "feat(cli): implement aegis web (uvicorn launcher)"
```

---

## Task 13: Manual smoke test

**Files:** none modified.

- [ ] **Step 1: Initialize a scratch project**

```bash
cd /tmp && rm -rf aegis-web-smoke && mkdir aegis-web-smoke && cd aegis-web-smoke
git init -q -b main
git config user.email test@example.com && git config user.name Test
echo '# scratch' > README.md && git add README.md && git commit -q -m initial
aegis init
```

- [ ] **Step 2: Seed one task in each visible status**

```bash
aegis task add "add login"
aegis task add "fix typo"
# Move 002 to in-progress, 001 stays in backlog
mv .aegis/backlog/002-fix-typo.md .aegis/in-progress/
sed -i 's/status: backlog/status: in-progress/' .aegis/in-progress/002-fix-typo.md
```

- [ ] **Step 3: Start the dashboard**

```bash
aegis web --port 8765
```

Expected stdout: `Aegis dashboard on http://127.0.0.1:8765` followed by uvicorn log lines.

- [ ] **Step 4: Browser smoke test**

Open `http://127.0.0.1:8765` in a browser. Verify:
- Kanban shows two columns with a card each
- Click into `001-add-login` → renders body, sidebar shows status/priority
- "Logs" section shows `no trace yet`
- `/config` shows the YAML

Stop the server with Ctrl+C. Expected: the process exits cleanly (no traceback).

- [ ] **Step 5: Clean up the scratch dir**

```bash
cd / && rm -rf /tmp/aegis-web-smoke
```

No commit for this task — it's a manual verification step.

---

## Task 14: Update README and status.json

**Files:**
- Modify: `README.md`
- Modify: `docs/status.json`

- [ ] **Step 1: Add the Web dashboard section to README**

Locate the Observability section in `README.md` and add the following section directly after it (or in the most natural location based on the README's existing structure — keep prior sections intact):

```markdown
## Web dashboard

Start a read-only browser dashboard alongside the CLI:

    aegis web --port 8765 --host 127.0.0.1

Routes:

- `/` — kanban: backlog / in-progress / review / blocked
- `/task/<id>` — task body (markdown), metadata sidebar, git diff vs `main`,
  live log tail (HTMX, 1 s polling), and Approve / Reject buttons when the
  task is in `review/`
- `/config` — read-only view of `.aegis/config.yaml`

The dashboard is single-user and binds to localhost by default. POST routes
require an Origin header matching the bound host and a CSRF token issued at
server start. Press Ctrl+C to stop.

Task authoring still happens in the CLI (`aegis task add`) or by editing
markdown directly — the dashboard never writes user files.
```

- [ ] **Step 2: Update `docs/status.json`**

Edit `docs/status.json`:

1. In `snapshot.tags`, append `"phase-6-complete"`.
2. In `phases`, find the entry with `id: 6`. Replace its body with:

```json
{
  "id": 6,
  "name": "Web dashboard (read-only)",
  "status": "complete",
  "tag": "phase-6-complete",
  "plan": "docs/superpowers/plans/2026-05-02-aegis-phase-6-web-dashboard.md",
  "deliverables": [
    "web/app.py — FastAPI factory + middleware/CSRF/Jinja2 wiring",
    "web/middleware.py — OriginHostMiddleware (Host whitelist + Origin check on POST)",
    "web/csrf.py — process-scoped CSRF token + dependency",
    "web/render.py — markdown-it-py renderer (html disabled)",
    "web/log_tail.py — JSONL trace tail using cli.commands.logs._format_line",
    "web/git_diff.py — diff_stat / diff_full subprocess wrappers",
    "web/routes/{kanban,task,actions,config_view}.py",
    "web/templates/{base,kanban,task,_logs,config}.html (HTMX 1.x + Tailwind 3 via CDN)",
    "cli/commands/web.py — uvicorn launcher (replaces the stub)"
  ]
}
```

3. In `package_layout.modules.web`, change `status` from `placeholder_empty` to `implemented` and update `files` to:

```json
{
  "path": "src/aegis/web",
  "files": [
    "__init__.py",
    "app.py",
    "middleware.py",
    "csrf.py",
    "render.py",
    "log_tail.py",
    "git_diff.py",
    "routes/__init__.py",
    "routes/kanban.py",
    "routes/task.py",
    "routes/actions.py",
    "routes/config_view.py",
    "templates/base.html",
    "templates/kanban.html",
    "templates/task.html",
    "templates/_logs.html",
    "templates/config.html"
  ],
  "status": "implemented"
}
```

4. In `cli_commands.implemented`, append:

```json
{ "name": "web", "help": "Start the read-only dashboard (foreground uvicorn)" }
```

5. Remove the entry from `cli_commands.stubbed_for_future_phases` for `web` (the array becomes empty — keep it as `[]`).

6. In `dependencies.runtime`, append:

```
"fastapi>=0.110",
"uvicorn[standard]>=0.27",
"jinja2>=3.1",
"markdown-it-py>=3.0"
```

7. In `dependencies.dev`, append `"httpx>=0.27"`.

8. Update `next_phase` to:

```json
{
  "phase": null,
  "scope": "All originally-planned phases complete. Open questions in `open_questions_deferred` remain candidates for follow-up phases.",
  "after_that": null
}
```

9. Update `snapshot.head_commit` and `snapshot.head_subject` after the final commit in Step 4 below — leave them as-is in this step; we'll refresh them after the commit.

- [ ] **Step 3: Run the full test suite**

Run: `pytest tests/unit -q --ignore=tests/unit/test_shell_mcp.py`
Expected: all green.

Run: `ruff check src tests`
Expected: clean.

Run: `mypy src/aegis`
Expected: clean (or matches the pre-Phase-6 baseline — we're not introducing new mypy violations).

- [ ] **Step 4: Commit**

```bash
git add README.md docs/status.json
git commit -m "docs(status): mark phase 6 complete + Web dashboard section"
```

- [ ] **Step 5: Tag the phase**

```bash
git tag phase-6-complete
git log --oneline -5
git tag -l | grep phase-6-complete
```

Expected: the new tag is listed and the latest commit is the status.json update.

---

## Out of scope (explicitly deferred)

- WebSocket / SSE — HTMX 1 s polling is sufficient for a single-user local tool; revisit if real-time becomes painful.
- Multi-project dashboard — one `aegis web` process serves one `.aegis/` directory. Multi-project work belongs in the same follow-up that addresses the multi-project daemon (already in `open_questions_deferred`).
- Authentication — single-user localhost. If exposed beyond loopback, reconsider before unblocking that path.
- Theme toggle / dark mode.
- Rich approve/reject UX (comments, partial approval). The current MVP mirrors the CLI: one-click approve, optional reason on reject.
- Cost-per-task display — depends on the same SDK-usage threading deferred from Phase 5.
- Task editing in the UI — explicit non-goal in spec Section 9.2.
