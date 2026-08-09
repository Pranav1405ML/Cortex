from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    APP_NAME: str = "Cortex"
    ENV: str = "development"
    DATABASE_URL: str

    # --- JWT settings ---
    JWT_SECRET_KEY: str                # loaded from .env, no default = required
    JWT_ALGORITHM: str = "HS256"       # HMAC-SHA256 (symmetric signing)
    JWT_EXPIRE_MINUTES: int = 60       # token lifetime in minutes

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()