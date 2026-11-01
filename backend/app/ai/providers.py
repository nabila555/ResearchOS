"""Provider abstraction for chat generation and embeddings.

Chat providers stream plain text. Embedding providers turn text into vectors.
Embeddings always come from a local provider (Ollama), even when Claude is used
for chat, so document text is only sent to a cloud service for the passages of a
question the user asked, and only after they consented in Settings.
"""

from collections.abc import Iterator
from dataclasses import dataclass
from typing import Protocol


class ProviderError(Exception):
    """A provider failure with a message that is safe to show to the user."""


class ProviderUnavailableError(ProviderError):
    """The provider cannot be reached right now (e.g. Ollama not running). Retry later."""


class ModelNotInstalledError(ProviderUnavailableError):
    """The configured local model has not been downloaded yet."""


class RefusalError(ProviderError):
    """The model declined to answer (safety classifiers)."""


@dataclass(frozen=True)
class ChatTurn:
    role: str  # "user" | "assistant"
    content: str


class ChatProvider(Protocol):
    name: str
    model: str

    def stream_chat(self, system: str, turns: list[ChatTurn], *, max_tokens: int) -> Iterator[str]:
        """Yield text fragments of the reply. Raises ProviderError subclasses."""
        ...


class EmbeddingProvider(Protocol):
    model: str

    def embed_documents(self, texts: list[str]) -> list[list[float]]: ...

    def embed_query(self, text: str) -> list[float]: ...
