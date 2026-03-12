from functools import lru_cache
from typing import Annotated

from pydantic import field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Settings(BaseSettings):
    project_name: str = "Insurance Annual Report Fact Extraction API"
    environment: str = "development"
    debug: bool = False
    api_v1_prefix: str = "/api/v1"
    database_url: str = "postgresql+psycopg://postgres@localhost:5432/insurance_facts"
    storage_root: str = "data/uploads"
    preview_cache_root: str = "data/previews"
    export_root: str = "data/exports"

    ocr_enabled: bool = True
    ocr_language: str = "chi_sim+eng"
    tesseract_cmd: str | None = None
    tessdata_prefix: str | None = None
    pdf_render_scale: float = 2.0
    ocr_min_text_len: int = 20
    parse_page_retries: int = 1

    celery_broker_url: str = "redis://localhost:6379/0"
    celery_result_backend: str = "redis://localhost:6379/1"
    celery_task_always_eager: bool = True
    celery_task_store_eager_result: bool = True
    celery_task_track_started: bool = True

    cors_origins: Annotated[
        list[str],
        NoDecode,
    ] = [
        "http://localhost:3000",
        "http://localhost:5173",
    ]

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, value: str | list[str]) -> list[str]:
        if isinstance(value, list):
            return value
        if isinstance(value, str):
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        raise ValueError("CORS_ORIGINS must be a comma-separated string or list")


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
