"""Unit tests for API models"""

import pytest

from nekro_cc_sandbox.api.messages import MessageRequest, MessageResponse


class TestMessageRequest:
    """Tests for MessageRequest model"""

    def test_valid_request(self):
        """Test creating a valid message request"""
        request = MessageRequest(
            role="user",
            content="Hello, agent!",
        )

        assert request.role == "user"
        assert request.content == "Hello, agent!"
        assert request.workspace_id == "default"

    def test_custom_workspace(self):
        """Test request with custom workspace"""
        request = MessageRequest(
            role="assistant",
            content="Response",
            workspace_id="my-workspace",
        )

        assert request.workspace_id == "my-workspace"

    def test_missing_content(self):
        """Test that content is required"""
        import pydantic
        with pytest.raises(pydantic.ValidationError):
            MessageRequest.model_validate({"role": "user"})


class TestMessageResponse:
    """Tests for MessageResponse model"""

    def test_valid_response(self):
        """Test creating a valid message response"""
        response = MessageResponse(
            session_id="sess-123",
            message="Hello!",
            success=True,
        )

        assert response.session_id == "sess-123"
        assert response.message == "Hello!"
        assert response.success is True

    def test_failed_response(self):
        """Test creating a failed response"""
        response = MessageResponse(
            session_id="sess-123",
            message="Error occurred",
            success=False,
        )

        assert response.success is False
