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
