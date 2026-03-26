from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    DATABASE_URL: str
    SECRET_KEY: str
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    GEMINI_API_KEY: str
    GEMINI_MODEL: str = "gemini-3.0-flash-preview"
    GEMINI_LITE_MODEL: str = "gemini-3.1-flash-lite-preview"
    GEMINI_TTS_MODEL: str = "gemini-2.5-flash-preview-tts"
    SERPAPI_KEY: str
    TAVILY_API_KEY: str
    OPENWEATHER_API_KEY: str
    GOOGLE_MAPS_API_KEY: str
    LOG_LEVEL: str = "DEBUG"

    model_config = SettingsConfigDict(env_file=".env")


settings = Settings()  # type: ignore[call-arg]
