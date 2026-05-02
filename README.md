# Aegis

> **Status:** Phases 1–6 complete (core, MCP servers, agents, LangGraph
> team graph + CLI, observability, web dashboard). See
> `docs/superpowers/specs/2026-04-14-aegis-ai-engineering-team-design.md`
> for the architecture.

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
- `aegis run`, `aegis status`, `aegis stop`, `aegis approve`,
  `aegis reject`, `aegis retry`, `aegis inspect`, `aegis daemon` —
  drive the LangGraph team graph end-to-end
- `aegis logs <id> [--follow]`, `aegis trace <id>` — local + remote
  observability
- `aegis web` — read-only browser dashboard

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
  `LANGSMITH_API_KEY`. LangGraph's built-in callback handler handles the
  rest.

Open a remote trace with `aegis trace <id>` — Aegis prefers LangSmith
when both are configured, and falls back to a hint about `aegis logs`
when neither is.

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
