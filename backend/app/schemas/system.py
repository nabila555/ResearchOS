from pydantic import BaseModel


class HealthResponse(BaseModel):
    status: str
    version: str
    database: str


class OllamaStatus(BaseModel):
    base_url: str
    reachable: bool
    models: list[str]
    chat_model: str
    embed_model: str
    chat_model_available: bool
    embed_model_available: bool
    error: str | None = None


class AnthropicStatus(BaseModel):
    # Only reports whether a key is configured; the key itself is never returned
    # and no request is sent to Anthropic just to check status.
    configured: bool
    model: str


class AIStatus(BaseModel):
    active_provider: str
    ollama: OllamaStatus
    anthropic: AnthropicStatus


class StorageStatus(BaseModel):
    data_dir: str
    database_backend: str
    max_upload_mb: int


class SystemStatus(BaseModel):
    app_name: str
    version: str
    environment: str
    storage: StorageStatus
    ai: AIStatus
