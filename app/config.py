from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    # Database
    database_url: str

    # Anthropic
    anthropic_api_key: str
    anthropic_model: str = "claude-sonnet-4-6"

    # LangFuse
    langfuse_public_key: str
    langfuse_secret_key: str
    langfuse_base_url: str = "https://cloud.langfuse.com"

    # Embedding
    embedding_model: str = "all-MiniLM-L6-v2"
    embedding_dim: int = 384

    # App
    log_level: str = "INFO"
    top_k_default: int = 5


@lru_cache
def get_settings() -> Settings:
    return Settings()
