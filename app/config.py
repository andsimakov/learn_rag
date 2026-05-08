from functools import lru_cache

from pydantic import SecretStr, computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Database
    postgres_user: str
    postgres_password: SecretStr
    postgres_db: str
    postgres_host: str = "localhost"
    postgres_port: int = 5432

    @computed_field
    @property
    def database_url(self) -> str:
        return f"postgresql://{self.postgres_user}:{self.postgres_password.get_secret_value()}@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"

    # Anthropic
    anthropic_api_key: SecretStr
    anthropic_model: str = "claude-sonnet-4-6"

    # LangFuse
    langfuse_public_key: str
    langfuse_secret_key: SecretStr
    langfuse_base_url: str = "https://cloud.langfuse.com"

    # Embedding
    embedding_model: str = "all-MiniLM-L6-v2"
    embedding_dim: int = 384

    # App
    log_level: str = "INFO"
    top_k_default: int = 8
    max_tokens: int = 1024
    judge_max_tokens: int = 256
    allowed_origins: list[str] = ["http://localhost:3000", "http://localhost:3001"]


@lru_cache
def get_settings() -> Settings:
    return Settings()
