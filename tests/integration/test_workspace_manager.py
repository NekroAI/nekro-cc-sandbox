"""Integration tests for workspace manager"""

import pytest

from nekro_cc_sandbox.workspace.manager import WorkspaceManager


class TestWorkspaceManager:
    """Tests for WorkspaceManager class"""

    @pytest.fixture
    def temp_root(self, tmp_path):
        """Create temporary workspace root"""
        return tmp_path / "workspaces"

    @pytest.fixture
    def manager(self, temp_root):
        """Create workspace manager"""
        return WorkspaceManager(temp_root)

    @pytest.mark.asyncio
    async def test_create_default_workspace(self, manager, temp_root):
        """Test creating the default workspace"""
        workspace = await manager.create_default_workspace("default")

        assert workspace is not None
        assert workspace.id == "default"
        assert workspace.name == "default"
        assert (temp_root / "default").exists()

    @pytest.mark.asyncio
    async def test_get_workspace(self, manager):
        """Test getting an existing workspace"""
        await manager.create_default_workspace("test-ws")
        workspace = await manager.get_workspace("test-ws")

        assert workspace is not None
        assert workspace.id == "test-ws"

    @pytest.mark.asyncio
    async def test_get_nonexistent_workspace(self, manager):
        """Test getting a workspace that doesn't exist"""
        workspace = await manager.get_workspace("nonexistent")

        assert workspace is None

    @pytest.mark.asyncio
    async def test_list_workspaces(self, manager):
        """Test listing all workspaces"""
        await manager.create_default_workspace("ws1")
        await manager.create_default_workspace("ws2")

        workspaces = await manager.list_workspaces()

        assert len(workspaces) == 2

    @pytest.mark.asyncio
    async def test_update_session(self, manager):
        """Test updating workspace session ID"""
        await manager.create_default_workspace("test-ws")
        await manager.update_session("test-ws", "new-session-id")

        workspace = await manager.get_workspace("test-ws")
        assert workspace.session_id == "new-session-id"

    @pytest.mark.asyncio
    async def test_delete_workspace(self, manager):
        """Test deleting a workspace"""
        await manager.create_default_workspace("to-delete")
        result = await manager.delete_workspace("to-delete")

        assert result is True
        workspace = await manager.get_workspace("to-delete")
        assert workspace is None
