"""Settings management for API configuration"""

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path


@dataclass
class ProviderConfig:
    """API provider configuration"""

    name: str
    base_url: str = ""
    auth_token: str = ""
    model: str = ""


@dataclass
class Settings:
    """Application settings"""

    # Provider settings
    provider: str = "anthropic"
    providers: dict[str, ProviderConfig] = field(default_factory=dict)

    # Current active provider
    active_provider: str = "anthropic"

    # Timeout settings
    timeout_ms: int = 300000

    def get_active_config(self) -> ProviderConfig | None:
        """Get the active provider configuration"""
        if self.active_provider in self.providers:
            return self.providers[self.active_provider]
        return None

    def get_env_vars(self) -> dict[str, str]:
        """Get environment variables for Claude spawn"""
        config = self.get_active_config()
        if not config:
            return {}

        env = {
            "ANTHROPIC_BASE_URL": config.base_url,
            "ANTHROPIC_AUTH_TOKEN": config.auth_token,
            "ANTHROPIC_MODEL": config.model,
            "API_TIMEOUT_MS": str(self.timeout_ms),
        }
        # Only include non-empty values
        return {k: v for k, v in env.items() if v}

    def to_dict(self) -> dict:
        """Convert to dictionary"""
        data = asdict(self)
        data["providers"] = {k: asdict(v) for k, v in self.providers.items()}
        return data

    @classmethod
    def from_dict(cls, data: dict) -> "Settings":
        """Create from dictionary"""
        providers = {}
        for k, v in data.get("providers", {}).items():
            providers[k] = ProviderConfig(**v)

        return cls(
            provider=data.get("provider", "anthropic"),
            providers=providers,
            active_provider=data.get("active_provider", "anthropic"),
            timeout_ms=data.get("timeout_ms", 300000),
        )

    def save(self, path: Path) -> None:
        """Save settings to file"""
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, indent=2)

    @classmethod
    def load(cls, path: Path) -> "Settings":
        """Load settings from file"""
        if not path.exists():
            return cls()

        with open(path, encoding="utf-8") as f:
            return cls.from_dict(json.load(f))


# Preset configurations
PRESETS: dict[str, dict] = {
    "anthropic": {
        "name": "Anthropic",
        "base_url": "https://api.anthropic.com",
        "model": "sonnet-4-20250514",
    },
    "minimax": {
        "name": "MiniMax",
        "base_url": "https://api.minimaxi.com/anthropic",
        "model": "MiniMax-M2.1",
    },
    "openai-compatible": {
        "name": "OpenAI Compatible",
        "base_url": "https://api.openai.com/v1",
        "model": "gpt-4o",
    },
    "ollama": {
        "name": "Ollama",
        "base_url": "http://localhost:11434/v1",
        "model": "llama3",
    },
    "lm-studio": {
        "name": "LM Studio",
        "base_url": "http://localhost:1234/v1",
        "model": "lmstudio-community/Meta-Llama-3-8B-Instruct-GGUF",
    },
}
