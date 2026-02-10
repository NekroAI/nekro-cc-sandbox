"""Integration tests for settings endpoints."""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from nekro_cc_sandbox.api import settings as settings_api
from nekro_cc_sandbox.settings import ProviderConfig, Settings


@pytest.fixture
def client_with_settings(test_app, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    settings_path = tmp_path / "settings.json"
    monkeypatch.setattr(settings_api, "SETTINGS_PATH", settings_path)
    client = TestClient(test_app)
    yield client, settings_path


def test_get_settings_info_defaults(client_with_settings):
    client, _settings_path = client_with_settings
    response = client.get("/api/v1/settings/")
    assert response.status_code == 200
    payload = response.json()
    assert payload["active_provider"] == "anthropic"
    assert "providers" in payload
    assert payload["current_config"] is None


def test_update_provider_preserves_token(client_with_settings):
    client, settings_path = client_with_settings

    settings = Settings()
    settings.providers["anthropic"] = ProviderConfig(
        name="Anthropic",
        base_url="https://api.anthropic.com",
        auth_token="secret-token",
        model="sonnet-4-20250514",
    )
    settings.active_provider = "anthropic"
    settings.save(settings_path)

    response = client.put(
        "/api/v1/settings/provider/anthropic",
        json={
            "base_url": "https://api.anthropic.com",
            "auth_token": "",
            "model": "sonnet-4-20250514",
        },
    )
    assert response.status_code == 200

    loaded = Settings.load(settings_path)
    assert loaded.providers["anthropic"].auth_token == "secret-token"
    assert loaded.active_provider == "anthropic"


def test_delete_provider_resets_active(client_with_settings):
    client, settings_path = client_with_settings

    settings = Settings()
    settings.providers["minimax"] = ProviderConfig(
        name="MiniMax",
        base_url="https://api.minimaxi.com/anthropic",
        auth_token="minimax-token",
        model="MiniMax-M2.1",
    )
    settings.active_provider = "minimax"
    settings.save(settings_path)

    response = client.delete("/api/v1/settings/provider/minimax")
    assert response.status_code == 200

    loaded = Settings.load(settings_path)
    assert "minimax" not in loaded.providers
    assert loaded.active_provider == "anthropic"
