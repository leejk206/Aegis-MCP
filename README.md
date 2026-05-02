# Aegis

> **Status:** Phases 1–6 complete (core, MCP servers, agents, LangGraph
> team graph + CLI, observability, web dashboard).
> See `docs/superpowers/specs/2026-04-14-aegis-ai-engineering-team-design.md`
> for the architecture.

**Aegis** is a local CLI + read-only web dashboard that drops a five-role
AI engineering team (PM / Dev / QA / Reviewer / Docs) onto any git repo.
Write vague task ideas as markdown, go to sleep, and wake up to PRs the
team has built, tested, and reviewed.

- One process. One git repo. No SaaS dependencies (LangSmith / Langfuse
  are optional).
- Tasks are markdown files in `.aegis/`. The CLI authors them; agents
  consume them; the web dashboard surfaces them — read-only.
- Each task runs in its own git worktree on a `aegis/<id>-<slug>`
  branch. On approval, fast-forward merge into `main`.

---

## Install

```bash
pip install -e ".[dev]"
```

Requires Python ≥ 3.11 and a working `git` on `PATH`. An Anthropic API
key is required to actually run agents (`ANTHROPIC_API_KEY`); CLI
authoring (`init`, `task add`, etc.) works without one.

---

## Quickstart

```bash
# in any git repo
aegis init                         # create .aegis/
aegis task add "add login page"    # writes .aegis/backlog/001-...md
$EDITOR .aegis/backlog/001-*.md    # flesh out the task body
aegis run                          # drains the backlog one task at a time
                                   # — pauses at the human gate when QA + Reviewer
                                   #   approve, just before Docs

# in another terminal (or browser):
aegis status                       # CLI kanban
aegis web --port 8765              # browser kanban at http://127.0.0.1:8765

# review the work, then:
aegis approve 001                  # merge into main, run Docs, finish task
# or
aegis reject 001 "not what I meant"  # discard the worktree, mark rejected
```

`aegis run` runs in the foreground. For unattended overnight drains use
`aegis daemon start` (PID file at `.aegis/.daemon.pid`).

---

## CLI

| Command | Purpose |
|---|---|
| `aegis init` | Create `.aegis/` (gitignore-aware) in the current git repo |
| `aegis task add\|list\|show\|edit` | Author and browse markdown tasks |
| `aegis config get\|set\|edit` | Read or edit `.aegis/config.yaml` |
| `aegis run` | Run the team graph in the foreground (one task or drain backlog) |
| `aegis status` | Print the kanban view of all tasks |
| `aegis stop` | Kill switch — sets a stop flag the running graph respects |
| `aegis approve <id>` | Resume a task paused at the docs gate (merge + Docs run) |
| `aegis reject <id> [reason]` | Discard a paused task and clean up its worktree |
| `aegis retry <id>` | Retry a failed/blocked task |
| `aegis inspect <id>` | Print a task's full markdown |
| `aegis daemon start\|stop\|status\|restart` | Background backlog drainer |
| `aegis logs <id> [--follow]` | Tail the JSONL trace for a task |
| `aegis trace <id>` | Open the trace in LangSmith / Langfuse if configured |
| `aegis web [--port 8765] [--host 127.0.0.1]` | Start the read-only dashboard (foreground uvicorn) |

---

## Architecture (one screen)

```
┌─ User ────────────────────────────────────────────────────────────────┐
│  CLI: aegis init / task / run / status / approve / web …             │
│  Web: read-only kanban + task view + approve/reject buttons          │
└───────────────────┬───────────────────────────────────────────────────┘
                    ▼
┌─ aegis (Python pkg) ──────────────────────────────────────────────────┐
│  LangGraph TeamState graph                                            │
│  ┌─PM─┐  ┌─Dev─┐  ┌─QA─┐  ┌─Reviewer─┐  [interrupt_before]  ┌─Docs─┐  │
│  │    │→│     │→│    │→│          │ ───────────────────── →│      │  │
│  └────┘  └─────┘  └────┘  └──────────┘                       └──────┘  │
│      ↑       ↑       ↑          ↑                                     │
│      └ each node = Claude Agent SDK loop with MCP tools               │
│                                                                       │
│  MCP servers (path-scoped, read/write capability split):              │
│    aegis-git-mcp   aegis-fs-mcp   aegis-shell-mcp                     │
│    aegis-project-index-mcp   in-process: signals (done / block)       │
│                                                                       │
│  Safety: per-task USD/wallclock cap • aegis stop kill switch          │
│           per-task git worktree • LangGraph SqliteSaver checkpointer  │
└───────────────────────────────────────────────────────────────────────┘
                    ▼
                  .aegis/
                  ├── backlog/  in-progress/  review/  done/  blocked/  rejected/   ← markdown tasks
                  ├── .worktrees/<id-slug>/                                          ← per-task git worktree
                  ├── trace/<id>.jsonl                                               ← OTel JSONL mirror
                  ├── checkpoint.db                                                  ← LangGraph state
                  └── config.yaml                                                    ← project config
```

Five role agents, each backed by a Claude model selectable per role
in `.aegis/config.yaml` (defaults: Opus for PM/Reviewer, Sonnet for
Dev/QA, Haiku for Docs). Tool allowlists per role are enforced by the
graph layer, not by trust in the prompt.

---

## Web dashboard

```bash
aegis web --port 8765 --host 127.0.0.1
```

Routes:

- `/` — kanban: backlog / in-progress / review / blocked
- `/task/<id>` — task body (markdown), metadata sidebar, `git diff` vs
  `main`, live log tail (HTMX, 1 s polling), and Approve / Reject
  buttons when the task is in `review/`
- `/config` — read-only view of `.aegis/config.yaml`

Single-user, binds to localhost by default. POST routes require an
`Origin` header matching the bound host and a CSRF token issued at
server start. No build step — Tailwind 3 and HTMX 1.x are loaded from
CDN. Press Ctrl+C to stop.

Task authoring still happens via CLI or by editing markdown directly
— the dashboard never writes user files.

---

## Observability

Aegis emits OpenTelemetry spans for every role-node invocation. Three
sinks are available:

- **JSONL local mirror** (always on by default). One file per task at
  `.aegis/trace/<task_id>.jsonl`. View with `aegis logs <id> [--follow]`.
- **Langfuse** (self-hosted). Enable `observability.langfuse.enabled`
  in `.aegis/config.yaml`, run `make langfuse` to start the stack on
  `localhost:3000`, then set `LANGFUSE_PUBLIC_KEY` and
  `LANGFUSE_SECRET_KEY` in your environment.
- **LangSmith** (SaaS). Enable `observability.langsmith.enabled` and set
  `LANGSMITH_API_KEY`. LangGraph's built-in callback handler does the rest.

Open a remote trace with `aegis trace <id>` — Aegis prefers LangSmith
when both are configured, and falls back to a hint about `aegis logs`
when neither is.

---

## Development

```bash
make test          # pytest tests/unit
make lint          # ruff check + format check
make typecheck     # mypy
make langfuse      # docker-compose up the self-host Langfuse stack
make langfuse-down # tear it down
```

> Note: `tests/unit/test_shell_mcp.py` requires a `python` binary on
> `PATH` and may fail under WSL where only `python3` is present.
> Run `pytest tests/unit --ignore=tests/unit/test_shell_mcp.py` to skip.

Project layout: `src/aegis/{core, mcp_servers, agents, graph, cli, obs, web}/`.
Tests in `tests/unit/`. Implementation plans live under
`docs/superpowers/plans/` (one per phase). Status is tracked in
`docs/status.json`.
