"""Ollama (local LLM runtime) integration: status, chat streaming, and embeddings."""

import json
from collections.abc import Iterator

import httpx

from app.ai.providers import (
    ChatTurn,
    ModelNotInstalledError,
    ProviderError,
    ProviderUnavailableError,
)
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


def _raise_for_ollama(response: httpx.Response, model: str) -> None:
    if response.status_code == 404:
        raise ModelNotInstalledError(
            f"The Ollama model “{model}” is not installed. Run: ollama pull {model}"
        )
    if response.status_code >= 400:
        try:
            detail = response.json().get("error", "")
        except ValueError:
            detail = ""
        raise ProviderError(f"Ollama returned HTTP {response.status_code}. {detail}".strip())


class _OllamaBase:
    def __init__(self, settings: Settings, model: str, transport: httpx.BaseTransport | None):
        self.base_url = settings.ollama_base_url.rstrip("/")
        self.model = model
        self._timeout = httpx.Timeout(settings.ollama_generation_timeout_seconds, connect=5.0)
        self._transport = transport

    def _client(self) -> httpx.Client:
        return httpx.Client(timeout=self._timeout, transport=self._transport)


class OllamaChatProvider(_OllamaBase):
    name = "ollama"

    def __init__(self, settings: Settings, transport: httpx.BaseTransport | None = None):
        super().__init__(settings, settings.ollama_chat_model, transport)
        self._num_ctx = settings.ollama_num_ctx

    def stream_chat(self, system: str, turns: list[ChatTurn], *, max_tokens: int) -> Iterator[str]:
        payload = {
            "model": self.model,
            "stream": True,
            "messages": [{"role": "system", "content": system}]
            + [{"role": t.role, "content": t.content} for t in turns],
            # Low temperature: answers should stick to the provided sources.
            "options": {"temperature": 0.1, "num_ctx": self._num_ctx, "num_predict": max_tokens},
        }
        try:
            with (
                self._client() as client,
                client.stream("POST", f"{self.base_url}/api/chat", json=payload) as response,
            ):
                if response.status_code >= 400:
                    response.read()
                    _raise_for_ollama(response, self.model)
                for line in response.iter_lines():
                    if not line.strip():
                        continue
                    event = json.loads(line)
                    if event.get("error"):
                        raise ProviderError(f"Ollama error: {event['error']}")
                    text = event.get("message", {}).get("content", "")
                    if text:
                        yield text
                    if event.get("done"):
                        return
        except httpx.ConnectError as exc:
            raise ProviderUnavailableError(
                "Ollama is not running. Start the Ollama app and try again."
            ) from exc
        except httpx.TimeoutException as exc:
            raise ProviderError(
                "The local model took too long to respond. Try a shorter question, a smaller "
                "model, or raise OLLAMA_GENERATION_TIMEOUT_SECONDS."
            ) from exc


class OllamaEmbeddingProvider(_OllamaBase):
    def __init__(self, settings: Settings, transport: httpx.BaseTransport | None = None):
        super().__init__(settings, settings.ollama_embed_model, transport)

    def _prefix(self, kind: str) -> str:
        # nomic-embed-text is trained with task prefixes; other models don't need them.
        if "nomic-embed" in self.model:
            return "search_document: " if kind == "document" else "search_query: "
        return ""

    def _embed(self, texts: list[str]) -> list[list[float]]:
        try:
            with self._client() as client:
                response = client.post(
                    f"{self.base_url}/api/embed", json={"model": self.model, "input": texts}
                )
        except httpx.ConnectError as exc:
            raise ProviderUnavailableError("Ollama is not running.") from exc
        except httpx.TimeoutException as exc:
            raise ProviderUnavailableError("Ollama timed out while embedding.") from exc
        _raise_for_ollama(response, self.model)
        embeddings = response.json().get("embeddings")
        if not isinstance(embeddings, list) or len(embeddings) != len(texts):
            raise ProviderError("Ollama returned an unexpected embedding response.")
        return embeddings

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        prefix = self._prefix("document")
        return self._embed([prefix + t for t in texts])

    def embed_query(self, text: str) -> list[float]:
        return self._embed([self._prefix("query") + text])[0]
