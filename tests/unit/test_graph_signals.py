from __future__ import annotations

from aegis.graph.signals import SIGNALS_SERVER_NAME, build_signals_server


def test_signals_server_returns_name_and_sdk_config() -> None:
    name, config = build_signals_server()
    assert name == SIGNALS_SERVER_NAME == "signals"
    assert config["type"] == "sdk"
    # The Claude Agent SDK exposes the in-process MCP server as a
    # ``McpSdkServerConfig`` dict with keys ``type``, ``name``, and
    # ``instance``. The instance must be non-None so the SDK can
    # actually route ``mcp__signals__done`` calls to our tool.
    instance = config.get("instance")
    assert instance is not None


def test_signals_server_factory_returns_fresh_instance_each_call() -> None:
    a = build_signals_server()
    b = build_signals_server()
    # Each call returns its own server instance — important for
    # per-task isolation.
    assert a[1]["instance"] is not b[1]["instance"]
