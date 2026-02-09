"""End-to-end tests for the full workflow"""

from fastapi.testclient import TestClient

from nekro_cc_sandbox.main import app


class TestFullWorkflow:
    """End-to-end workflow tests"""

    def test_complete_message_flow_health_only(self):
        """Test the complete flow from health to messaging (health/status only)"""
        with TestClient(app) as client:
            # 1. Check health
            health_response = client.get("/health")
            assert health_response.status_code == 200
            assert health_response.json()["status"] == "healthy"

            # 2. Check status
            status_response = client.get("/api/v1/status")
            assert status_response.status_code == 200

            # Note: Message endpoint requires proper lifespan context with claude_runtime
            # Use integration tests for message testing

    def test_multiple_health_checks(self):
        """Test multiple health checks"""
        with TestClient(app) as client:
            response1 = client.get("/health")
            response2 = client.get("/health")

            assert response1.status_code == 200
            assert response2.status_code == 200


class TestCLIToolsAvailability:
    """Test that required CLI tools are available"""

    def test_claude_cli_available(self):
        """Check if Claude CLI is available"""
        import shutil

        assert shutil.which("claude") is not None, "Claude CLI not found in PATH"

    def test_docker_available(self):
        """Check if Docker is available"""
        import shutil

        assert shutil.which("docker") is not None, "Docker not found in PATH"
