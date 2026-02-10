"""Integration tests for API endpoints"""

from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient

# Global mock runtime for tests
_mock_session = MagicMock()
_mock_session.session_id = "test-session-123"

_mock_runtime = MagicMock()
_mock_runtime.start = AsyncMock(return_value=_mock_session)


async def _fake_send_message_in_workspace(_workspace_id: str, _content: str):
    yield "test response"


_mock_runtime.send_message_in_workspace = _fake_send_message_in_workspace


@pytest.fixture(autouse=True)
def setup_mock_runtime(test_app):
    """Setup mock runtime for all tests"""
    test_app.state.claude_runtime = _mock_runtime
    yield
    # Cleanup
    if hasattr(test_app.state, "claude_runtime"):
        del test_app.state.claude_runtime


class TestHealthEndpoint:
    """Tests for health check endpoint"""

    @pytest.fixture
    def client(self, test_app):
        """Create test client"""
        return TestClient(test_app)

    def test_health_check(self, client):
        """Test health endpoint returns healthy status"""
        response = client.get("/health")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["version"] == "0.1.0"


class TestStatusEndpoint:
    """Tests for status endpoints"""

    @pytest.fixture
    def client(self, test_app):
        """Create test client"""
        return TestClient(test_app)

    def test_get_status(self, client):
        """Test status endpoint"""
        response = client.get("/api/v1/status")

        assert response.status_code == 200
        data = response.json()
        assert "status" in data
        assert "services" in data

    def test_list_workspaces(self, client):
        """Test list workspaces endpoint"""
        response = client.get("/api/v1/workspaces")

        assert response.status_code == 200
        data = response.json()
        assert "workspaces" in data


class TestMessagesEndpoint:
    """Tests for message endpoints"""

    @pytest.fixture
    def client_with_runtime(self, test_app):
        """Create test client with mocked runtime"""
        client = TestClient(test_app)
        test_app.state.claude_runtime = _mock_runtime
        return client

    def test_send_message_no_runtime(self, test_app):
        """Test sending message when runtime is not available"""
        client = TestClient(test_app)
        # Ensure no runtime is set
        if hasattr(test_app.state, "claude_runtime"):
            del test_app.state.claude_runtime
        response = client.post(
            "/api/v1/message",
            json={
                "role": "user",
                "content": "List files in the workspace",
            },
        )

        # Should return 200 but success=false when runtime not available
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is False
        assert "not available" in data["message"]

    def test_send_message_with_runtime(self, client_with_runtime):
        """Test sending a message to the workspace"""
        response = client_with_runtime.post(
            "/api/v1/message",
            json={
                "role": "user",
                "content": "List files in the workspace",
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert "session_id" in data
        assert "success" in data

    def test_send_message_with_workspace_runtime(self, client_with_runtime):
        """Test sending message to specific workspace"""
        response = client_with_runtime.post(
            "/api/v1/message",
            json={
                "role": "user",
                "content": "Analyze this project",
                "workspace_id": "test-ws",
            },
        )

        assert response.status_code == 200

    def test_invalid_message(self, client_with_runtime):
        """Test that missing content is rejected"""
        response = client_with_runtime.post(
            "/api/v1/message",
            json={"role": "user"},
        )

        assert response.status_code == 422  # Validation error
