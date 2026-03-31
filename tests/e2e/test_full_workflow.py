"""End-to-end tests for the full workflow"""

import pytest
from fastapi.testclient import TestClient
from nekro_cc_sandbox.main import app

_E2E_INTERNAL_TOKEN = "e2e-internal-api-token"


class TestFullWorkflow:
    """End-to-end workflow tests"""

    def test_complete_message_flow_health_only(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test the complete flow from health to messaging (health/status only)"""
        monkeypatch.setenv("INTERNAL_API_TOKEN", _E2E_INTERNAL_TOKEN)
        with TestClient(app) as client:
            # 1. Check health
            health_response = client.get("/health")
            assert health_response.status_code == 200
            assert health_response.json()["status"] == "healthy"

            # 2. Check status (requires NA→sandbox internal Bearer token when configured)
            status_response = client.get(
                "/api/v1/status",
                headers={"Authorization": f"Bearer {_E2E_INTERNAL_TOKEN}"},
            )
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
        import os
        import shutil

        import pytest

        if os.getenv("REQUIRE_CLAUDE_CLI") != "1":
            pytest.skip("Claude CLI not required in this environment (set REQUIRE_CLAUDE_CLI=1 to enforce).")

        assert shutil.which("claude") is not None, "Claude CLI not found in PATH"

    def test_docker_available(self):
        """Check if Docker is available"""
        import shutil

        assert shutil.which("docker") is not None, "Docker not found in PATH"
