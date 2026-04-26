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
from typing import Any

from claude_agent_sdk import ClaudeAgentOptions, ClaudeSDKClient

from aegis.agents.registry import ROLES, RoleName
from aegis.agents.tools import build_mcp_servers
from aegis.core.config import AegisConfig

ClientFactory = Callable[[ClaudeAgentOptions], ClaudeSDKClient]

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
            raise FileNotFoundError(f"worktree {worktree_resolved} does not exist")

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
        messages: list[Any] = []
        async with self._client_factory(options) as client:
            await client.query(task_prompt)
            async for msg in client.receive_response():
                messages.append(msg)
        return messages
