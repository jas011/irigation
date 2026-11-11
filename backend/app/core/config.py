import os
from typing import List
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    PROJECT_NAME: str = "AgriSense AI Irrigation Advisor"
    API_V1_STR: str = "/api"

    JWT_SECRET: str = "supersecretjwtkeyforagrisenseaiadvisor2026!!!"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7

    DATABASE_URL: str = "postgresql://postgres:postgres@localhost:5432/agrisense"

    CORS_ORIGINS: List[str] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ]

    GEE_PROJECT_ID: str | None = None
    GEE_CROP_TRAINING_ASSET: str | None = None
    CROP_TRAINING_CSV_PATH: str | None = None
    BHOONIDHI_USER_ID: str | None = None
    BHOONIDHI_PASSWORD: str | None = None
    OPENAI_API_KEY: str | None = None
    OPENAI_MODEL: str = "gpt-4o-mini"
    OPENAI_CONFIDENCE_THRESHOLD: float = 0.5

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )


settings = Settings()

