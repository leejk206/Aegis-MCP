from __future__ import annotations

import importlib.resources
from pathlib import Path

import pytest

from aegis.agents.base import load_prompt
from aegis.agents.registry import ROLES

REQUIRED_SECTIONS = (
    "## Identity",
    "## Inputs",
    "## Outputs",
    "## Tools available",
    "## Hard rules",
    "## Style",
)


def _prompt_path(filename: str) -> Path:
    # Prompts live under src/aegis/agents/prompts/ in the installed
    # package. Use importlib.resources to locate them the way
    # load_prompt() will in Task 5.
    package = importlib.resources.files("aegis.agents") / "prompts" / filename
    return Path(str(package))


@pytest.mark.parametrize("role_name", sorted(ROLES.keys()))
def test_prompt_file_exists_for_each_role(role_name: str) -> None:
    spec = ROLES[role_name]
    path = _prompt_path(spec.prompt_filename)
    assert path.is_file(), f"missing prompt file {path}"


@pytest.mark.parametrize("role_name", sorted(ROLES.keys()))
def test_prompt_file_has_template_sections(role_name: str) -> None:
    spec = ROLES[role_name]
    content = _prompt_path(spec.prompt_filename).read_text(encoding="utf-8")
    for section in REQUIRED_SECTIONS:
        assert section in content, f"{role_name} prompt missing section {section!r}"


@pytest.mark.parametrize("role_name", sorted(ROLES.keys()))
def test_prompt_starts_with_role_header(role_name: str) -> None:
    spec = ROLES[role_name]
    content = _prompt_path(spec.prompt_filename).read_text(encoding="utf-8")
    first_line = content.splitlines()[0]
    assert first_line.startswith("# Role:"), f"{role_name} prompt first line = {first_line!r}"


@pytest.mark.parametrize("role_name", sorted(ROLES.keys()))
def test_prompt_mentions_done_and_block_controls(role_name: str) -> None:
    spec = ROLES[role_name]
    content = _prompt_path(spec.prompt_filename).read_text(encoding="utf-8")
    assert "`done`" in content, f"{role_name} prompt should mention the done tool"
    assert "`block`" in content, f"{role_name} prompt should mention the block tool"


def test_pm_prompt_forbids_writing_code() -> None:
    content = _prompt_path(ROLES["pm"].prompt_filename).read_text(encoding="utf-8")
    # §4 table: PM writes plan.md only. Tone is "do not write code".
    assert "do not write code" in content.lower() or "never write code" in content.lower()


def test_reviewer_prompt_treats_task_as_adversarial() -> None:
    content = _prompt_path(ROLES["reviewer"].prompt_filename).read_text(encoding="utf-8")
    # §11.5: Reviewer treats task body as adversarial input.
    assert "adversarial" in content.lower()


def test_docs_prompt_scopes_to_docs_paths() -> None:
    content = _prompt_path(ROLES["docs"].prompt_filename).read_text(encoding="utf-8")
    assert "README" in content
    assert "CHANGELOG" in content


@pytest.mark.parametrize("role", ["pm", "dev", "qa", "reviewer", "docs"])
def test_prompt_mentions_signals_server(role: str) -> None:
    text = load_prompt(role)
    assert "mcp__signals__done" in text or "signals" in text, (
        f"{role} prompt must reference the signals server"
    )


def test_qa_prompt_documents_verdict_field() -> None:
    text = load_prompt("qa")
    assert "verdict" in text
    assert '"pass"' in text or "`pass`" in text
    assert '"fail"' in text or "`fail`" in text


def test_reviewer_prompt_documents_verdict_field() -> None:
    text = load_prompt("reviewer")
    assert "verdict" in text
    assert "approve" in text and "rework" in text
