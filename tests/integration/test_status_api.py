"""Integration tests for status and sessions endpoints."""

import asyncio
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from nekro_cc_sandbox.claude.policy import RuntimePolicy
from nekro_cc_sandbox.claude.runtime import ClaudeRuntime
from nekro_cc_sandbox.shell.manager import ShellManager
from nekro_cc_sandbox.workspace.manager import WorkspaceManager


@pytest.fixture
def client_with_runtime(test_app, tmp_path: Path):
    wm = WorkspaceManager(tmp_path / "workspaces")
    asyncio.run(wm.create_default_workspace("default"))
    runtime = ClaudeRuntime(workspace_manager=wm, skip_permissions=True, policy=RuntimePolicy.strict())
    runtime._last_init_tools["default"] = ["Read", "Grep"]

    test_app.state.workspace_manager = wm
    test_app.state.claude_runtime = runtime
    test_app.state.shell_manager = ShellManager()
    client = TestClient(test_app)
    try:
        yield client, wm, runtime
    finally:
        if hasattr(test_app.state, "shell_manager"):
            del test_app.state.shell_manager
        if hasattr(test_app.state, "claude_runtime"):
            del test_app.state.claude_runtime
        if hasattr(test_app.state, "workspace_manager"):
            del test_app.state.workspace_manager


def test_status_includes_policy_and_tools(client_with_runtime):
    client, _wm, _runtime = client_with_runtime

    response = client.get("/api/v1/status")
    assert response.status_code == 200
    payload = response.json()

    assert payload["services"]["claude_runtime"] == "available"
    assert payload["capabilities"]["tools"] == ["Read", "Grep"]
    assert payload["capabilities"]["policy"]["allow_command_execution"] is False
    assert payload["capabilities"]["policy"]["allow_file_modification"] is False


def test_sessions_list_and_detail(client_with_runtime):
    client, wm, _runtime = client_with_runtime

    asyncio.run(wm.update_session("default", "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"))

    resp_list = client.get("/api/v1/sessions")
    assert resp_list.status_code == 200
    sessions = resp_list.json()["sessions"]
    assert sessions == [
        {"workspace_id": "default", "session_id": "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"}
    ]

    resp_detail = client.get("/api/v1/sessions/aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
    assert resp_detail.status_code == 200
    assert resp_detail.json()["workspace_id"] == "default"


def test_workspaces_get_not_found(client_with_runtime):
    client, _wm, _runtime = client_with_runtime
    response = client.get("/api/v1/workspaces/not-exist")
    assert response.status_code == 404
