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
