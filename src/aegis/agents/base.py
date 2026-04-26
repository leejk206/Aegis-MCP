"""The public ``AegisAgent`` wrapper and its building blocks.

``load_prompt`` and ``build_options`` are pure and synchronous; they do
not touch the Claude SDK client at all. ``AegisAgent`` composes them
with a ``ClaudeSDKClient`` (injected for testability) and exposes a
single async ``run`` method.
"""

from __future__ import annotations

import importlib.resources
from collections.abc import Callable
from pathlib import Path
from typing import Any  # noqa: F401 — used in Task 6

from claude_agent_sdk import ClaudeAgentOptions, ClaudeSDKClient

from aegis.agents.registry import ROLES, RoleName
from aegis.agents.tools import build_mcp_servers
from aegis.core.config import AegisConfig

ClientFactory = Callable[[ClaudeAgentOptions], ClaudeSDKClient]  # noqa: F401 — used in Task 6

__all__ = [
    "AegisAgent",
    "build_options",
    "ClientFactory",
    "load_prompt",
]


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
