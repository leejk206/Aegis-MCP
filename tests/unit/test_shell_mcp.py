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


def test_shell_exec_runs_allowed_command(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ALLOW_CMDS", "python")
    result = shell_exec(
        tmp_path,
        "python",
        ["-c", "print('hi')"],
        ".",
    )
    assert result["exit_code"] == 0
    assert "hi" in result["stdout"]
    assert result["stderr"] == ""


def test_shell_exec_captures_nonzero_exit(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ALLOW_CMDS", "python")
    result = shell_exec(
        tmp_path,
        "python",
        ["-c", "import sys; sys.exit(7)"],
        ".",
    )
    assert result["exit_code"] == 7


def test_shell_exec_captures_stderr(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ALLOW_CMDS", "python")
    result = shell_exec(
        tmp_path,
        "python",
        ["-c", "import sys; sys.stderr.write('oops')"],
        ".",
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


def test_shell_exec_rejects_missing_cwd(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ALLOW_CMDS", "python")
    with pytest.raises(FileNotFoundError):
        shell_exec(tmp_path, "python", ["-c", "pass"], "no_such_dir")


def test_shell_exec_does_not_interpret_shell_metachars(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Args with ; and && are passed to the program verbatim, not to a shell."""
    monkeypatch.setenv("ALLOW_CMDS", "python")
    result = shell_exec(
        tmp_path,
        "python",
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
