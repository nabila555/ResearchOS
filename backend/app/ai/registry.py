"""Builds the AI providers from settings. Tests replace ``app.state.ai`` with fakes."""

from collections.abc import Callable
from dataclasses import dataclass, field

from app.ai.providers import ChatProvider, EmbeddingProvider, ProviderError
from app.core.config import Settings

CHAT_PROVIDER_LABELS = {"ollama": "Local (Ollama)", "anthropic": "Claude API (cloud)"}


@dataclass
class AIServices:
    embedder: EmbeddingProvider
    chat_factories: dict[str, Callable[[], ChatProvider]] = field(default_factory=dict)

    def available_chat_providers(self) -> list[str]:
        return list(self.chat_factories)

    def chat(self, name: str) -> ChatProvider:
        factory = self.chat_factories.get(name)
        if factory is None:
            raise ProviderError(f"The chat provider “{name}” is not configured.")
        return factory()


def build_ai_services(settings: Settings) -> AIServices:
    from app.ai.ollama import OllamaChatProvider, OllamaEmbeddingProvider

    factories: dict[str, Callable[[], ChatProvider]] = {
        "ollama": lambda: OllamaChatProvider(settings)
    }
    if settings.anthropic_api_key is not None:
        from app.ai.anthropic_provider import AnthropicChatProvider

        factories["anthropic"] = lambda: AnthropicChatProvider(settings)
    return AIServices(embedder=OllamaEmbeddingProvider(settings), chat_factories=factories)
