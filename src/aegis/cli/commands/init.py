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
