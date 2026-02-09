"""API provider tests package

This package contains tests that use real API providers.
These tests are skipped by default and can be enabled with:
    pytest --enable-provider-tests
"""

import os

import pytest


def skip_if_no_provider_env(key: str) -> None:
    """Skip test if provider environment variable is not set"""
    if not os.environ.get(key):
        pytest.skip(f"Requires {key} environment variable")


class ProviderConfig:
    """Configuration for API provider tests"""

    def __init__(
        self,
        name: str,
        api_key_env: str,
        base_url_env: str | None = None,
        default_url: str = "https://api.anthropic.com",
    ):
        self.name = name
        self.api_key_env = api_key_env
        self.base_url_env = base_url_env
        self.default_url = default_url

    @property
    def api_key(self) -> str | None:
        return os.environ.get(self.api_key_env)

    @property
    def base_url(self) -> str | None:
        if self.base_url_env:
            return os.environ.get(self.base_url_env)
        return self.default_url

    def is_configured(self) -> bool:
        return self.api_key is not None


# Pre-configured providers
ANTHROPIC = ProviderConfig(
    name="Anthropic",
    api_key_env="ANTHROPIC_AUTH_TOKEN",
    base_url_env="ANTHROPIC_BASE_URL",
)

MINIMAX = ProviderConfig(
    name="MiniMax",
    api_key_env="MINIMAX_API_KEY",
    base_url_env="MINIMAX_API_BASE",
    default_url="https://api.minimaxi.com/anthropic",
)

OPENAI = ProviderConfig(
    name="OpenAI",
    api_key_env="OPENAI_API_KEY",
    base_url_env="OPENAI_BASE_URL",
    default_url="https://api.openai.com/v1",
)


@pytest.fixture
def anthropic_config():
    """Anthropic provider configuration"""
    return ANTHROPIC


@pytest.fixture
def minimax_config():
    """MiniMax provider configuration"""
    return MINIMAX


@pytest.fixture
def openai_config():
    """OpenAI provider configuration"""
    return OPENAI
