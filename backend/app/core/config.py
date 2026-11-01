"""Application configuration loaded from environment variables and `.env` files.

All paths default to locations inside the project so ResearchOS runs fully
locally with zero configuration. Secrets (API keys) are only ever read from the
environment and are never logged or returned by the API.
"""

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parents[2]
PROJECT_ROOT = BACKEND_DIR.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(PROJECT_ROOT / ".env", BACKEND_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "ResearchOS"
    environment: Literal["development", "production", "test"] = "development"
    log_level: str = "INFO"

    # Storage -----------------------------------------------------------------
    data_dir: Path = PROJECT_ROOT / "data"
    database_url: str | None = Field(
        default=None,
        description="SQLAlchemy URL. Defaults to SQLite inside DATA_DIR/database.",
    )
    max_upload_mb: int = Field(default=50, ge=1, le=1024)

    # HTTP --------------------------------------------------------------------
    cors_origins: list[str] = ["http://localhost:3000", "http://127.0.0.1:3000"]

    # AI ----------------------------------------------------------------------
    ai_provider: Literal["ollama", "anthropic"] = "ollama"
    ollama_base_url: str = "http://127.0.0.1:11434"
    ollama_chat_model: str = "llama3.1:8b"
    ollama_embed_model: str = "nomic-embed-text"
    # Short timeout for status checks; generation can take minutes on a CPU.
    ollama_timeout_seconds: float = 2.0
    ollama_generation_timeout_seconds: float = 600.0
    ollama_num_ctx: int = Field(default=8192, ge=2048)
    anthropic_api_key: SecretStr | None = None
    anthropic_model: str = "claude-opus-5-5"

    # Retrieval & indexing -----------------------------------------------------
    retrieval_top_k: int = Field(default=8, ge=1, le=30)
    retrieval_max_chars: int = Field(default=9000, ge=1000)
    # Vector matches below this cosine similarity are ignored as unrelated.
    retrieval_min_similarity: float = Field(default=0.45, ge=0.0, le=1.0)
    embed_batch_size: int = Field(default=16, ge=1, le=256)
    chat_history_messages: int = Field(default=6, ge=0, le=40)
    # Characters of paper text sent per extraction step (fits an 8k-token context).
    analysis_excerpt_chars: int = Field(default=7000, ge=1500)
    run_background_worker: bool = True

    @field_validator("data_dir", mode="after")
    @classmethod
    def _resolve_data_dir(cls, value: Path) -> Path:
        # Relative paths are interpreted relative to the project root, not the CWD,
        # so the backend behaves the same no matter where it is launched from.
        return value if value.is_absolute() else (PROJECT_ROOT / value).resolve()

    @field_validator("anthropic_api_key", mode="before")
    @classmethod
    def _blank_key_is_none(cls, value: object) -> object:
        return None if isinstance(value, str) and not value.strip() else value

    @property
    def documents_dir(self) -> Path:
        return self.data_dir / "documents"

    @property
    def embeddings_dir(self) -> Path:
        return self.data_dir / "embeddings"

    @property
    def database_dir(self) -> Path:
        return self.data_dir / "database"

    @property
    def resolved_database_url(self) -> str:
        if self.database_url:
            return self.database_url
        return f"sqlite:///{(self.database_dir / 'researchos.db').as_posix()}"

    def ensure_directories(self) -> None:
        for directory in (self.documents_dir, self.embeddings_dir, self.database_dir):
            directory.mkdir(parents=True, exist_ok=True)


@lru_cache
def get_settings() -> Settings:
    return Settings()
