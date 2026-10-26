from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    app_name: str = "RoleLens — AI recruiting workbench"
    api_prefix: str = "/api"
    cors_origins: list[str] = Field(
        default_factory=lambda: ["http://localhost:5173", "http://localhost:8080"]
    )
    mongodb_uri: str = "mongodb://localhost:27017"
    mongodb_db_name: str = "rolelens_demo"
    mongodb_candidates_collection: str = "candidates"
    mongodb_job_orders_collection: str = "job_orders"
    mongodb_email_intakes_collection: str = "email_job_order_intakes"
    mongodb_vector_index: str = "candidate_vector_index"
    atlas_vector_enabled: bool = False
    ai_mode: Literal["demo", "gemini"] = "demo"
    gemini_api_key: str | None = None
    gemini_extraction_model: str = "gemini-3.5-flash-lite"
    gemini_embedding_model: str = "gemini-embedding-2"
    embedding_dimensions: int = Field(default=768, ge=1)
    seed_demo: bool = True
    gmail_enabled: bool = False
    max_file_size_mb: int = 10
    max_preview_chars: int = 12000
    gmail_credentials_path: str = str(BASE_DIR / "storage" / "credentials.json")
    gmail_token_path: str = str(BASE_DIR / "storage" / "token.json")
    gmail_poll_query: str = "is:unread newer_than:1d"
    gmail_max_messages_per_run: int = 10
    gmail_attachment_storage_dir: str = str(BASE_DIR / "storage" / "email_attachments")
    gmail_oauth_redirect_uri: str = "http://localhost:8080/auth/callback"
    frontend_redirect_url: str = "http://localhost:8080"
    model_config = SettingsConfigDict(
        env_file=str(BASE_DIR.parent / ".env"), extra="ignore", case_sensitive=False
    )

    @model_validator(mode="after")
    def validate_ai(self):
        if self.ai_mode == "gemini" and not self.gemini_api_key:
            raise ValueError(
                "AI_MODE=gemini requires GEMINI_API_KEY. Use AI_MODE=demo for the keyless walkthrough."
            )
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
