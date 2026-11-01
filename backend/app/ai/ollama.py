"""Ollama (local LLM runtime) integration."""

import httpx

from app.core.config import Settings
from app.schemas.system import OllamaStatus


def _model_installed(wanted: str, installed: list[str]) -> bool:
    # Ollama reports "name:tag"; a bare name in config means the ":latest" tag.
    candidates = {wanted} if ":" in wanted else {wanted, f"{wanted}:latest"}
    return any(name in candidates for name in installed)


async def get_ollama_status(settings: Settings) -> OllamaStatus:
    base = settings.ollama_base_url.rstrip("/")
    models: list[str] = []
    error: str | None = None
    reachable = False
    try:
        async with httpx.AsyncClient(timeout=settings.ollama_timeout_seconds) as client:
            response = await client.get(f"{base}/api/tags")
            response.raise_for_status()
            payload = response.json()
        models = sorted(m["name"] for m in payload.get("models", []) if "name" in m)
        reachable = True
    except httpx.ConnectError:
        error = "Ollama is not running or not installed."
    except httpx.TimeoutException:
        error = "Could not reach Ollama (timed out). Is it installed and running?"
    except (httpx.HTTPError, ValueError, KeyError) as exc:
        error = f"Unexpected response from Ollama: {type(exc).__name__}"

    return OllamaStatus(
        base_url=base,
        reachable=reachable,
        models=models,
        chat_model=settings.ollama_chat_model,
        embed_model=settings.ollama_embed_model,
        chat_model_available=_model_installed(settings.ollama_chat_model, models),
        embed_model_available=_model_installed(settings.ollama_embed_model, models),
        error=error,
    )
