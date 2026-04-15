from typing import Any

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    DATABASE_URL: str
    SECRET_KEY: str
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    GEMINI_API_KEY: str
    GEMINI_MODEL: str = "gemini-3-flash-preview"
    GEMINI_LITE_MODEL: str = "gemini-3.1-flash-lite-preview"
    GEMINI_LIVE_MODEL: str = "gemini-3.1-flash-live-preview"
    GEMINI_BACKUP_MODEL = "gemini-2.5-flash"
    GEMINI_BACKUP_LITE_MODEL = "gemini-2.5-flash-lite"
    GEMINI_BACKUP_LIVE_MODEL = "gemini-2.5-flash-native-audio-preview-12-2025"
    SERPAPI_KEY: str
    TAVILY_API_KEY: str
    OPENWEATHER_API_KEY: str
    GOOGLE_MAPS_API_KEY: str
    LOG_LEVEL: str = "DEBUG"

    # Proxy settings for LLM calls (optional)
    LLM_PROXY_ENABLED: bool = False
    SOCKS5_PROXY_URL: str = "socks5://host.docker.internal:1080"

    # VPN settings (optional, used by some deployment configs)
    ovpn_username: str = ""
    ovpn_password: str = ""
    ovpn_server: str = ""
    ovpn_proto: str = ""

    @model_validator(mode="before")
    @classmethod
    def _parse_env_strings(cls, data: Any) -> Any:
        if isinstance(data, dict):
            for field in ("LLM_PROXY_ENABLED",):
                if field in data:
                    v = data[field]
                    if isinstance(v, str):
                        data[field] = v.lower() in ("true", "1", "yes")
            return data
        return data

    model_config = SettingsConfigDict(env_file=".env")


settings = Settings()  # type: ignore[call-arg]
