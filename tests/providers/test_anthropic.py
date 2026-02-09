"""Real API provider tests for Anthropic

These tests make actual API calls and require ANTHROPIC_AUTH_TOKEN.
Run with: pytest --enable-provider-tests -k provider
"""

import pytest

from . import ANTHROPIC, skip_if_no_provider_env


@pytest.mark.provider
class TestAnthropicProvider:
    """Tests for real Anthropic API calls"""

    def test_anthropic_configured(self):
        """Check if Anthropic is configured"""
        assert ANTHROPIC.is_configured(), "ANTHROPIC_AUTH_TOKEN not set"

    def test_anthropic_api_call(self):
        """Test making a real API call to Anthropic"""
        import httpx

        skip_if_no_provider_env("ANTHROPIC_AUTH_TOKEN")

        response = httpx.post(
            f"{ANTHROPIC.base_url}/v1/messages",
            headers={
                "Authorization": f"Bearer {ANTHROPIC.api_key}",
                "Content-Type": "application/json",
                "x-api-version": "2023-06-01",
            },
            json={
                "model": "claude-sonnet-4-20250514",
                "max_tokens": 100,
                "messages": [{"role": "user", "content": "Hello"}],
            },
            timeout=30.0,
        )

        assert response.status_code == 200
        data = response.json()
        assert "content" in data

    @pytest.mark.asyncio
    async def test_anthropic_async_api_call(self):
        """Test making an async API call to Anthropic"""
        import httpx

        skip_if_no_provider_env("ANTHROPIC_AUTH_TOKEN")

        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{ANTHROPIC.base_url}/v1/messages",
                headers={
                    "Authorization": f"Bearer {ANTHROPIC.api_key}",
                    "Content-Type": "application/json",
                    "x-api-version": "2023-06-01",
                },
                json={
                    "model": "claude-sonnet-4-20250514",
                    "max_tokens": 100,
                    "messages": [{"role": "user", "content": "Hello async"}],
                },
                timeout=30.0,
            )

        assert response.status_code == 200
