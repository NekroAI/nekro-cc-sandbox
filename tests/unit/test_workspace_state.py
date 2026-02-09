"""Unit tests for workspace state management"""

from datetime import datetime
from pathlib import Path

from nekro_cc_sandbox.workspace.state import WorkspaceState


class TestWorkspaceState:
    """Tests for WorkspaceState class"""

    def test_create_state(self):
        """Test creating a new workspace state"""
        state = WorkspaceState(
            id="test-ws",
            path=Path("/tmp/test"),
            name="test",
        )

        assert state.id == "test-ws"
        assert state.path == Path("/tmp/test")
        assert state.name == "test"
        assert state.session_id is None
        assert isinstance(state.created_at, datetime)

    def test_to_dict(self):
        """Test serialization to dictionary"""
        state = WorkspaceState(
            id="test-ws",
            path=Path("/tmp/test"),
            name="test",
            session_id="sess-123",
        )

        data = state.to_dict()

        assert data["id"] == "test-ws"
        assert data["path"] == "/tmp/test"
        assert data["name"] == "test"
        assert data["session_id"] == "sess-123"
        assert "created_at" in data

    def test_from_dict(self):
        """Test deserialization from dictionary"""
        data = {
            "id": "test-ws",
            "path": "/tmp/test",
            "name": "test",
            "session_id": "sess-456",
            "created_at": "2024-01-01T00:00:00",
            "updated_at": "2024-01-01T00:00:00",
            "metadata": {},
        }

        state = WorkspaceState.from_dict(data)

        assert state.id == "test-ws"
        assert state.path == Path("/tmp/test")
        assert state.session_id == "sess-456"

    def test_save_and_load(self, temp_workspace):
        """Test saving and loading state from file"""
        state = WorkspaceState(
            id="test-ws",
            path=temp_workspace / "ws1",
            name="test-workspace",
        )

        save_path = temp_workspace / "state.json"
        state.save(save_path)

        assert save_path.exists()

        loaded = WorkspaceState.load(save_path)
        assert loaded.id == state.id
        assert loaded.name == state.name
        assert loaded.path == state.path
