"""设置 API：管理提供商配置。"""

import os
from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ..settings import PRESETS, ProviderConfig, Settings
from .schemas import (
    CurrentProviderConfig,
    OkResponse,
    PresetInfo,
    PresetsResponse,
    ProviderInfo,
    ProviderUpdatedResponse,
    SettingsInfoResponse,
)

router = APIRouter(prefix="/settings", tags=["settings"])

SETTINGS_PATH = Path(os.getenv("SETTINGS_PATH", "./data/settings.json"))


def get_settings() -> Settings:
    """加载设置文件。"""
    return Settings.load(SETTINGS_PATH)


def save_settings(settings: Settings) -> None:
    """保存设置文件。"""
    SETTINGS_PATH.parent.mkdir(parents=True, exist_ok=True)
    settings.save(SETTINGS_PATH)


class ProviderUpdate(BaseModel):
    """更新提供商配置请求。"""

    base_url: str
    # 约定：空字符串表示“保持不变”（避免 UI 留空误清空 token）
    auth_token: str = ""
    model: str


class SettingsUpdate(BaseModel):
    """更新全局设置请求。"""

    active_provider: str
    timeout_ms: int = 300000


@router.get("/", response_model=SettingsInfoResponse)
async def get_settings_info() -> SettingsInfoResponse:
    """获取当前设置（敏感字段需脱敏）。"""
    settings = get_settings()
    active = settings.get_active_config()

    providers: dict[str, ProviderInfo] = {}
    for key, preset in PRESETS.items():
        providers[key] = ProviderInfo(
            id=key,
            name=preset["name"],
            base_url=preset["base_url"],
            model=preset["model"],
            configured=key in settings.providers,
            is_active=key == settings.active_provider,
        )

    current_config: CurrentProviderConfig | None = None
    if active:
        current_config = CurrentProviderConfig(
            base_url=active.base_url,
            auth_token="********" if active.auth_token else "",
            model=active.model,
        )
    return SettingsInfoResponse(
        active_provider=settings.active_provider,
        timeout_ms=settings.timeout_ms,
        providers=providers,
        current_config=current_config,
    )


@router.put("/provider/{provider_id}", response_model=ProviderUpdatedResponse)
async def update_provider(provider_id: str, config: ProviderUpdate) -> ProviderUpdatedResponse:
    """更新提供商配置并切换为激活。"""
    if provider_id not in PRESETS:
        raise HTTPException(status_code=400, detail=f"Unknown provider: {provider_id}")

    settings = get_settings()
    existing = settings.providers.get(provider_id)
    auth_token = config.auth_token
    if auth_token == "" and existing is not None:
        auth_token = existing.auth_token
    settings.providers[provider_id] = ProviderConfig(
        name=PRESETS[provider_id]["name"],
        base_url=config.base_url,
        auth_token=auth_token,
        model=config.model,
    )
    settings.active_provider = provider_id
    save_settings(settings)

    return ProviderUpdatedResponse(provider=provider_id)


@router.put("/", response_model=OkResponse)
async def update_settings(update: SettingsUpdate) -> OkResponse:
    """更新全局设置。"""
    settings = get_settings()
    settings.active_provider = update.active_provider
    settings.timeout_ms = update.timeout_ms
    save_settings(settings)

    return OkResponse()


@router.get("/presets", response_model=PresetsResponse)
async def get_presets() -> PresetsResponse:
    """获取可用预设。"""
    return PresetsResponse(presets={k: PresetInfo(**v) for k, v in PRESETS.items()})


@router.delete("/provider/{provider_id}", response_model=OkResponse)
async def delete_provider(provider_id: str) -> OkResponse:
    """删除提供商配置。"""
    if provider_id not in PRESETS:
        raise HTTPException(status_code=400, detail=f"Unknown provider: {provider_id}")

    settings = get_settings()
    if provider_id in settings.providers:
        del settings.providers[provider_id]

    if settings.active_provider == provider_id:
        settings.active_provider = "anthropic"

    save_settings(settings)
    return OkResponse()
