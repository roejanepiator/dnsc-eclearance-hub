"""Typed settings loaded from .env (or real environment variables) via pydantic-settings."""
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    # .env is found relative to the project root, not the current directory.
    model_config = SettingsConfigDict(env_file=ROOT / ".env", extra="ignore")

    registrar_api_key: str
    registrar_base_url: str = "http://127.0.0.1:8001/api/v1"
    hmac_signing_key: str
    app_secret_key: str
    starter_hmac_key: str


settings = Settings()  # fails at startup with a clear error if a key is missing
