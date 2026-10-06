from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "sqlite:///./dev.db"
    jwt_secret: str = ""
    access_token_minutes: int = 15
    refresh_token_days: int = 7
    frontend_origin: str = "http://localhost:5173"
    cookie_secure: bool = True
    enable_demo: bool = False  # demo accounts can only sign in when this is true (ENABLE_DEMO=true)

    ai_provider: str = ""  # anthropic | openai | gemini | "" (disabled)
    ai_api_key: str = ""
    ocr_provider: str = ""
    ocr_api_key: str = ""

    def require_secret(self) -> str:
        if len(self.jwt_secret) < 32:
            raise RuntimeError("JWT_SECRET must be set to a random string of at least 32 characters")
        return self.jwt_secret


@lru_cache
def get_settings() -> Settings:
    return Settings()
