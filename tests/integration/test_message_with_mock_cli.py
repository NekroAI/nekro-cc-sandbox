"""Integration tests for message endpoints using mock Claude CLI."""

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from nekro_cc_sandbox.claude.runtime import ClaudeRuntime
from nekro_cc_sandbox.workspace.manager import WorkspaceManager


@pytest.fixture
def client_with_runtime(test_app, tmp_path: Path, mock_claude_cli):
    import asyncio

    wm = WorkspaceManager(tmp_path / "workspaces")
    asyncio.run(wm.create_default_workspace("default"))
    runtime = ClaudeRuntime(workspace_manager=wm, skip_permissions=True)
    test_app.state.workspace_manager = wm
    test_app.state.claude_runtime = runtime
    client = TestClient(test_app)
    try:
        yield client
    finally:
        if hasattr(test_app.state, "claude_runtime"):
            del test_app.state.claude_runtime
        if hasattr(test_app.state, "workspace_manager"):
            del test_app.state.workspace_manager


def test_message_endpoint_success(client_with_runtime: TestClient, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("MOCK_CLAUDE_SCENARIO", "success")
    monkeypatch.setenv("MOCK_CLAUDE_SESSION_ID", "44444444-4444-4444-4444-444444444444")

    response = client_with_runtime.post(
        "/api/v1/message",
        json={"role": "user", "content": "hello", "workspace_id": "default"},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is True
    assert payload["message"] == "Hello world"
    assert payload["session_id"] == "44444444-4444-4444-4444-444444444444"


def test_message_stream_endpoint_success(client_with_runtime: TestClient, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("MOCK_CLAUDE_SCENARIO", "success")

    chunks: list[str] = []
    with client_with_runtime.stream(
        "POST",
        "/api/v1/message/stream",
        json={"role": "user", "content": "hello", "workspace_id": "default"},
    ) as response:
        assert response.status_code == 200
        for line in response.iter_lines():
            if not line:
                continue
            if isinstance(line, bytes):
                line = line.decode("utf-8")
            if not line.startswith("data: "):
                continue
            data = json.loads(line[len("data: ") :])
            if data.get("type") == "chunk":
                chunks.append(data.get("chunk", ""))
            elif data.get("type") == "error":
                pytest.fail(f"stream error: {data}")

    assert "".join(chunks) == "Hello world"


def test_tools_refresh_endpoint(client_with_runtime: TestClient, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("MOCK_CLAUDE_SCENARIO", "probe-tools")

    response = client_with_runtime.post("/api/v1/capabilities/tools/refresh")
    assert response.status_code == 200
    payload = response.json()
    assert payload["source"] == "probe"
    assert payload["tools"] == ["Read", "Write", "Bash"]
