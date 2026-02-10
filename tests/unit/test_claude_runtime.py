"""Unit tests for ClaudeRuntime with mock Claude CLI."""

from pathlib import Path

import pytest

from nekro_cc_sandbox.claude.runtime import ClaudeRuntime
from nekro_cc_sandbox.errors import ClaudeCliError, ErrorCode
from nekro_cc_sandbox.workspace.manager import WorkspaceManager


async def _collect_async(gen):
    chunks: list[str] = []
    async for chunk in gen:
        chunks.append(chunk)
    return chunks


@pytest.mark.asyncio
async def test_send_message_success_updates_session(tmp_path: Path, mock_claude_cli, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("MOCK_CLAUDE_SCENARIO", "success")
    monkeypatch.setenv("MOCK_CLAUDE_SESSION_ID", "22222222-2222-2222-2222-222222222222")

    wm = WorkspaceManager(tmp_path / "workspaces")
    runtime = ClaudeRuntime(workspace_manager=wm, skip_permissions=True)

    chunks = await _collect_async(runtime.send_message_in_workspace("default", "hello"))
    assert "".join(chunks) == "Hello world"

    ws = await wm.get_workspace("default")
    assert ws is not None
    assert ws.session_id == "22222222-2222-2222-2222-222222222222"
    assert runtime.get_last_tools("default") == ["Read", "Write", "Bash"]


@pytest.mark.asyncio
async def test_send_message_resume_retry_on_missing(tmp_path: Path, mock_claude_cli, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("MOCK_CLAUDE_SCENARIO", "resume-miss-once")
    monkeypatch.setenv("MOCK_CLAUDE_SESSION_ID", "33333333-3333-3333-3333-333333333333")

    wm = WorkspaceManager(tmp_path / "workspaces")
    await wm.create_default_workspace("default")
    await wm.update_session("default", "00000000-0000-0000-0000-000000000001")

    runtime = ClaudeRuntime(workspace_manager=wm, skip_permissions=True)
    chunks = await _collect_async(runtime.send_message_in_workspace("default", "hello"))

    assert "".join(chunks) == "Hello world"
    ws = await wm.get_workspace("default")
    assert ws is not None
    assert ws.session_id == "33333333-3333-3333-3333-333333333333"


@pytest.mark.asyncio
async def test_send_message_error_result_raises(tmp_path: Path, mock_claude_cli, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("MOCK_CLAUDE_SCENARIO", "error-result")

    wm = WorkspaceManager(tmp_path / "workspaces")
    runtime = ClaudeRuntime(workspace_manager=wm, skip_permissions=True)

    with pytest.raises(ClaudeCliError) as exc:
        await _collect_async(runtime.send_message_in_workspace("default", "hello"))

    assert exc.value.code == ErrorCode.CLAUDE_CLI_ERROR_RESULT


@pytest.mark.asyncio
async def test_send_message_no_parseable_output(tmp_path: Path, mock_claude_cli, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("MOCK_CLAUDE_SCENARIO", "no-output")

    wm = WorkspaceManager(tmp_path / "workspaces")
    runtime = ClaudeRuntime(workspace_manager=wm, skip_permissions=True)

    with pytest.raises(ClaudeCliError) as exc:
        await _collect_async(runtime.send_message_in_workspace("default", "hello"))

    assert exc.value.code == ErrorCode.CLAUDE_CLI_NO_PARSEABLE_OUTPUT


@pytest.mark.asyncio
async def test_probe_tools_success(tmp_path: Path, mock_claude_cli, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("MOCK_CLAUDE_SCENARIO", "probe-tools")

    wm = WorkspaceManager(tmp_path / "workspaces")
    await wm.create_default_workspace("default")
    runtime = ClaudeRuntime(workspace_manager=wm, skip_permissions=True)

    tools = await runtime.probe_tools(workspace_id="default")
    assert tools == ["Read", "Write", "Bash"]
