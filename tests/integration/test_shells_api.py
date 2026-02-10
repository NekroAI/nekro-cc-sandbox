"""Integration tests for shell endpoints."""

import asyncio
import shutil
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from nekro_cc_sandbox.shell.manager import ShellManager
from nekro_cc_sandbox.workspace.manager import WorkspaceManager


@pytest.fixture
def client_with_shells(test_app, tmp_path: Path):
    if shutil.which("bash") is None:
        pytest.skip("bash not available; shell tests skipped")

    wm = WorkspaceManager(tmp_path / "workspaces")
    asyncio.run(wm.create_default_workspace("default"))
    sm = ShellManager()

    test_app.state.workspace_manager = wm
    test_app.state.shell_manager = sm
    client = TestClient(test_app)
    try:
        yield client
    finally:
        if hasattr(test_app.state, "shell_manager"):
            del test_app.state.shell_manager
        if hasattr(test_app.state, "workspace_manager"):
            del test_app.state.workspace_manager


def test_create_list_close_shell(client_with_shells: TestClient):
    response = client_with_shells.post(
        "/api/v1/shells",
        json={"workspace_id": "default", "argv": ["/bin/bash", "-l"], "rows": 24, "cols": 80},
    )
    assert response.status_code == 200
    shell_id = response.json()["id"]

    response = client_with_shells.get("/api/v1/shells")
    assert response.status_code == 200
    shells = response.json()["shells"]
    assert any(s["id"] == shell_id for s in shells)

    response = client_with_shells.delete(f"/api/v1/shells/{shell_id}")
    assert response.status_code == 200
