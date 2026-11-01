from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg://doxket:doxket@db:5432/doxket"
    redis_url: str = "redis://redis:6379/0"
    data_dir: Path = Path("/data")
    max_upload_mb: int = 25
    inline_jobs: bool = False
    job_timeout: int = 900
    ocr_lang: str = "eng"
    cors_origins: str = "http://localhost:5173,http://localhost:8080"

    llm_base_url: str = "https://api.openai.com/v1"
    llm_api_key: str = ""
    llm_model: str = ""
    llm_timeout: float = 90.0
    agent_max_steps: int = 24
    agent_max_images: int = 14
    llm_price_input_per_m: float = 2.0
    llm_price_cached_per_m: float = 0.1
    llm_price_output_per_m: float = 10.0


@lru_cache
def get_settings() -> Settings:
    return Settings()
