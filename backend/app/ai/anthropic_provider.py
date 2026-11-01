"""Optional Claude chat provider (cloud). Only used with an API key AND user consent."""

from collections.abc import Iterator

import anthropic

from app.ai.providers import ChatTurn, ProviderError, ProviderUnavailableError, RefusalError
from app.core.config import Settings

# Server-side refusal fallback: if the model declines, the API retries on Anthropic's
# recommended fallback model for that refusal category within the same request.
FALLBACK_BETA = "server-side-fallback-2026-07-01"


class AnthropicChatProvider:
    name = "anthropic"

    def __init__(self, settings: Settings, client: anthropic.Anthropic | None = None):
        if settings.anthropic_api_key is None and client is None:
            raise ProviderError("No ANTHROPIC_API_KEY is configured.")
        self.model = settings.anthropic_model
        self._client = client or anthropic.Anthropic(
            api_key=settings.anthropic_api_key.get_secret_value()  # type: ignore[union-attr]
        )

    def stream_chat(self, system: str, turns: list[ChatTurn], *, max_tokens: int) -> Iterator[str]:
        try:
            with self._client.beta.messages.stream(
                model=self.model,
                max_tokens=max_tokens,
                system=system,
                messages=[{"role": t.role, "content": t.content} for t in turns],
                output_config={"effort": "medium"},
                betas=[FALLBACK_BETA],
                fallbacks="default",
            ) as stream:
                yield from stream.text_stream
                final = stream.get_final_message()
            if final.stop_reason == "refusal":
                raise RefusalError("Claude declined to answer this question.")
        except anthropic.AuthenticationError as exc:
            raise ProviderError("The Anthropic API key was rejected.") from exc
        except anthropic.PermissionDeniedError as exc:
            raise ProviderError("The Anthropic API key lacks permission for this model.") from exc
        except anthropic.RateLimitError as exc:
            raise ProviderUnavailableError(
                "Anthropic rate limit reached. Try again shortly."
            ) from exc
        except anthropic.APIStatusError as exc:
            raise ProviderError(f"Anthropic API error (HTTP {exc.status_code}).") from exc
        except anthropic.APIConnectionError as exc:
            raise ProviderUnavailableError("Could not reach the Anthropic API.") from exc
