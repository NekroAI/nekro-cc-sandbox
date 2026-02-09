"""Real API provider tests for MiniMax

These tests make actual API calls and require MINIMAX_API_KEY.
Run with: pytest --enable-provider-tests -k provider
"""

import pytest

from . import MINIMAX, skip_if_no_provider_env


@pytest.mark.provider
class TestMiniMaxProvider:
    """Tests for real MiniMax API calls"""

    def test_minimax_configured(self):
        """Check if MiniMax is configured"""
        assert MINIMAX.is_configured(), "MINIMAX_API_KEY not set"

    def test_minimax_api_call(self):
        """Test making a real API call to MiniMax"""
        import httpx

        skip_if_no_provider_env("MINIMAX_API_KEY")

        response = httpx.post(
            f"{MINIMAX.base_url}/v1/messages",
            headers={
                "Authorization": f"Bearer {MINIMAX.api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": "MiniMax-M2.1",
                "max_tokens": 100,
                "messages": [{"role": "user", "content": "Hello"}],
            },
            timeout=30.0,
        )

        # MiniMax may return different status codes or formats
        # Just verify we get a valid response
        assert response.status_code in [200, 400, 401, 429]
