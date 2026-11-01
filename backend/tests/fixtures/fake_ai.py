"""Deterministic stand-ins for AI providers so tests never need Ollama or the network."""

import hashlib
import math
import re
from collections.abc import Callable, Iterator
from dataclasses import dataclass, field
from typing import Any

from app.ai.providers import ChatTurn, ProviderError, ProviderUnavailableError
from app.ai.registry import AIServices

DIM = 256


def _stem(word: str) -> str:
    return re.sub(r"(ing|ed|es|s)$", "", word) if len(word) > 4 else word


def bag_of_words_vector(text: str) -> list[float]:
    """Hashing-trick embedding: texts sharing words get high cosine similarity."""
    vector = [0.0] * DIM
    for word in re.findall(r"[a-z0-9]+", text.lower()):
        if len(word) < 3:
            continue
        bucket = int(hashlib.md5(_stem(word).encode()).hexdigest(), 16) % DIM
        vector[bucket] += 1.0
    norm = math.sqrt(sum(v * v for v in vector)) or 1.0
    return [v / norm for v in vector]


@dataclass
class FakeEmbedder:
    model: str = "fake-embed"
    available: bool = True
    calls: int = 0

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        self.calls += 1
        if not self.available:
            raise ProviderUnavailableError("Fake embedder offline.")
        return [bag_of_words_vector(t) for t in texts]

    def embed_query(self, text: str) -> list[float]:
        if not self.available:
            raise ProviderUnavailableError("Fake embedder offline.")
        return bag_of_words_vector(text)


@dataclass
class FakeChat:
    name: str = "ollama"
    model: str = "fake-chat"
    reply: Callable[[str, list[ChatTurn]], str] = lambda _system, _turns: "Spindles help [1]."
    error: ProviderError | None = None
    calls: list[tuple[str, list[ChatTurn]]] = field(default_factory=list)
    # generate_json: a function (system, prompt, schema) -> dict, and a call log.
    json_reply: Callable[[str, str, dict[str, Any]], dict[str, Any]] | None = None
    json_calls: list[tuple[str, str, dict[str, Any]]] = field(default_factory=list)

    def generate_json(
        self, system: str, prompt: str, schema: dict[str, Any], *, max_tokens: int
    ) -> dict[str, Any]:
        self.json_calls.append((system, prompt, schema))
        if self.error is not None:
            raise self.error
        if self.json_reply is None:
            raise ProviderError("No fake JSON reply configured.")
        return self.json_reply(system, prompt, schema)

    def stream_chat(self, system: str, turns: list[ChatTurn], *, max_tokens: int) -> Iterator[str]:
        self.calls.append((system, turns))
        text = self.reply(system, turns)
        midpoint = len(text) // 2
        yield text[:midpoint]
        if self.error is not None:
            raise self.error
        yield text[midpoint:]


def make_fake_ai(chat: FakeChat | None = None, cloud: FakeChat | None = None) -> AIServices:
    chat = chat or FakeChat()
    factories = {"ollama": lambda: chat}
    if cloud is not None:
        factories["anthropic"] = lambda: cloud
    return AIServices(embedder=FakeEmbedder(), chat_factories=factories)
