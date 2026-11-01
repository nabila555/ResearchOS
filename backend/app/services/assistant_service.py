"""Research assistant: retrieval-augmented answers with verified citations.

Trust rules enforced here (not just requested from the model):
* If retrieval finds nothing, the model is not called; the answer says so.
* Citations are parsed from the answer and checked against the passages that
  were actually sent. Unknown numbers are reported as invalid, never linked.
* An answer with no valid citation is flagged as unverified in the UI.
* Cloud providers are used only after the user consented in Settings.
"""

import json
import re
from collections.abc import Callable, Iterator
from dataclasses import asdict
from typing import Any

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.ai.providers import ChatTurn, ProviderError, RefusalError
from app.ai.registry import CHAT_PROVIDER_LABELS, AIServices
from app.ai.vector_index import VectorIndex
from app.core.config import Settings
from app.core.database import utcnow
from app.models.ai import ChatMessage, ChatSession
from app.schemas.assistant import ChatMessageRead, ChatSessionRead
from app.services import settings_service
from app.services.errors import ConflictError, InvalidRequestError, NotFoundError
from app.services.retrieval_service import Passage, Scope, retrieve

INSUFFICIENT_PHRASE = "The provided sources do not contain enough evidence to answer this."
DEFAULT_TITLE = "New chat"

SYSTEM_PROMPT = f"""You are the research assistant inside ResearchOS. You answer questions \
using ONLY the numbered source passages supplied with each question. They come from the \
user's own research library.

Rules:
1. Base every statement on the sources. Do not use outside knowledge. Never invent studies, \
authors, numbers, quotations, or references.
2. Cite the supporting source number in square brackets immediately after each claim, for \
example: "Spindle density predicted recall [2]." Use several numbers when several sources \
support a claim, for example [1][3]. Only cite numbers that appear in the source list.
3. If the sources do not contain enough information to answer, begin your reply with exactly: \
"{INSUFFICIENT_PHRASE}" Then say briefly what is missing. Do not guess.
4. If sources disagree, say so and cite each side.
5. Keep what the sources state separate from any interpretation you add, and label \
interpretation as such.
6. Be concise: short paragraphs or bullet points. Answer in the language of the question."""

CITATION_RE = re.compile(r"\[(\s*\d+(?:\s*(?:[,;]|[-–])\s*\d+)*\s*)\]")
OLLAMA_MAX_TOKENS = 1024
CLOUD_MAX_TOKENS = 16000


class ConsentRequiredError(ConflictError):
    pass


# --- Sessions ----------------------------------------------------------------------


def _session_read(db: Session, session: ChatSession) -> ChatSessionRead:
    count, last = db.execute(
        select(func.count(), func.max(ChatMessage.created_at)).where(
            ChatMessage.session_id == session.id
        )
    ).one()
    return ChatSessionRead(
        id=session.id,
        title=session.title,
        scope=session.scope or {},
        message_count=count,
        last_message_at=last,
        created_at=session.created_at,
        updated_at=session.updated_at,
    )


def list_sessions(db: Session) -> list[ChatSessionRead]:
    sessions = db.scalars(select(ChatSession).order_by(ChatSession.updated_at.desc()))
    return [_session_read(db, s) for s in sessions]


def get_session(db: Session, session_id: int) -> ChatSession:
    session = db.get(ChatSession, session_id)
    if session is None:
        raise NotFoundError(f"Chat {session_id} not found")
    return session


def create_session(db: Session, title: str | None, scope: dict[str, Any] | None) -> ChatSessionRead:
    session = ChatSession(
        title=(title or DEFAULT_TITLE)[:300], scope=Scope.from_dict(scope).to_dict()
    )
    db.add(session)
    db.commit()
    return _session_read(db, session)


def update_session(
    db: Session, session_id: int, title: str | None, scope: dict[str, Any] | None
) -> ChatSessionRead:
    session = get_session(db, session_id)
    if title:
        session.title = title[:300]
    if scope is not None:
        session.scope = Scope.from_dict(scope).to_dict()
    db.commit()
    return _session_read(db, session)


def delete_session(db: Session, session_id: int) -> None:
    db.delete(get_session(db, session_id))
    db.commit()


def session_messages(db: Session, session_id: int) -> list[ChatMessageRead]:
    get_session(db, session_id)
    rows = db.scalars(
        select(ChatMessage).where(ChatMessage.session_id == session_id).order_by(ChatMessage.id)
    )
    return [ChatMessageRead.model_validate(m) for m in rows]


# --- Citations ---------------------------------------------------------------------


def parse_citations(answer: str) -> list[int]:
    """All citation numbers in order of first appearance: "[1]", "[2, 3]", "[4–6]"."""
    numbers: list[int] = []
    for match in CITATION_RE.finditer(answer):
        for part in re.split(r"[,;]", match.group(1)):
            bounds = re.split(r"[-–]", part.strip())
            if len(bounds) == 2 and bounds[0].strip().isdigit() and bounds[1].strip().isdigit():
                lo, hi = int(bounds[0]), int(bounds[1])
                values = range(lo, hi + 1) if 0 < hi - lo < 20 else [lo, hi]
            else:
                values = [int(bounds[0])] if bounds[0].strip().isdigit() else []
            for value in values:
                if value not in numbers:
                    numbers.append(value)
    return numbers


def is_insufficient(answer: str) -> bool:
    head = answer.strip().lower()[:300]
    return "do not contain enough evidence" in head or "does not contain enough evidence" in head


def verify_citations(answer: str, passage_count: int) -> tuple[list[int], list[int]]:
    cited = parse_citations(answer)
    valid = [n for n in cited if 1 <= n <= passage_count]
    invalid = [n for n in cited if not 1 <= n <= passage_count]
    return valid, invalid


# --- Prompt ------------------------------------------------------------------------


def _format_passage(p: Passage) -> str:
    bits = []
    if p.authors:
        bits.append(", ".join(p.authors[:3]) + (" et al." if len(p.authors) > 3 else ""))
    if p.year:
        bits.append(str(p.year))
    if p.page_start is not None:
        bits.append(
            f"p. {p.page_start}"
            if p.page_end in (None, p.page_start)
            else f"pp. {p.page_start}-{p.page_end}"
        )
    if p.section:
        bits.append(f"section: {p.section}")
    meta = f" ({'; '.join(bits)})" if bits else ""
    return f"[{p.n}] “{p.title}”{meta}\n{p.text}"


def build_user_prompt(question: str, passages: list[Passage]) -> str:
    sources = "\n\n".join(_format_passage(p) for p in passages)
    return f"Sources:\n\n{sources}\n\nQuestion: {question}"


def _history(db: Session, session_id: int, limit: int) -> list[ChatTurn]:
    if limit <= 0:
        return []
    rows = list(
        db.scalars(
            select(ChatMessage)
            .where(
                ChatMessage.session_id == session_id,
                or_(ChatMessage.status.is_(None), ChatMessage.status != "error"),
            )
            .order_by(ChatMessage.id.desc())
            .limit(limit)
        )
    )
    # Earlier answers cite earlier source lists; strip their [n] markers so the model
    # doesn't confuse them with the numbering of the current sources.
    turns = [
        ChatTurn(m.role, CITATION_RE.sub("", m.content) if m.role == "assistant" else m.content)
        for m in reversed(rows)
        if m.content.strip()
    ]
    # Providers expect the conversation to start with a user turn.
    while turns and turns[0].role != "user":
        turns.pop(0)
    return turns


# --- Ask ---------------------------------------------------------------------------


def _event(kind: str, **data: Any) -> str:
    return json.dumps({"type": kind, **data}, default=str) + "\n"


def prepare_question(
    db: Session, settings: Settings, ai: AIServices, session_id: int, content: str
) -> tuple[ChatSession, str]:
    """Validate before streaming starts, so configuration errors return a normal HTTP error."""
    session = get_session(db, session_id)
    question = content.strip()
    if not question:
        raise InvalidRequestError("The question is empty.")
    return session, resolve_chat_provider(db, settings, ai)


def resolve_chat_provider(db: Session, settings: Settings, ai: AIServices) -> str:
    """The provider to use for generation, after checking it is configured and allowed."""
    ai_settings = settings_service.get_ai_settings(db, settings)
    provider_name = ai_settings.chat_provider
    if provider_name not in ai.available_chat_providers():
        raise InvalidRequestError(
            f"The selected AI provider ({CHAT_PROVIDER_LABELS.get(provider_name, provider_name)}) "
            "is not configured. Choose another one in Settings."
        )
    if provider_name != "ollama" and not ai_settings.cloud_consent:
        raise ConsentRequiredError(
            "Using a cloud AI provider sends your question and matching passages from your "
            "documents to that service. Enable this explicitly in Settings first."
        )
    return provider_name


def answer_stream(
    session_factory: Callable[[], Session],
    settings: Settings,
    ai: AIServices,
    index: VectorIndex,
    session_id: int,
    question: str,
    provider_name: str,
    scope_override: dict[str, Any] | None,
) -> Iterator[str]:
    """Yield NDJSON events: user_message, sources, delta*, done | error."""
    with session_factory() as db:
        session = get_session(db, session_id)
        if scope_override is not None:
            session.scope = Scope.from_dict(scope_override).to_dict()
        scope = Scope.from_dict(session.scope)
        history = _history(db, session_id, settings.chat_history_messages)

        user_message = ChatMessage(session_id=session_id, role="user", content=question)
        db.add(user_message)
        if session.title == DEFAULT_TITLE:
            session.title = question[:80] + ("…" if len(question) > 80 else "")
        session.updated_at = utcnow()
        db.commit()
        yield _event(
            "user_message", message=ChatMessageRead.model_validate(user_message).model_dump()
        )

        result = retrieve(db, ai, index, settings, question, scope)
        sources = [asdict(p) for p in result.passages]
        notes = list(result.notes)
        yield _event("sources", sources=sources, semantic=result.semantic, notes=notes)

        assistant = ChatMessage(session_id=session_id, role="assistant", sources=sources)
        if not result.passages:
            assistant.content = (
                f"{INSUFFICIENT_PHRASE} No passages in "
                f"{'the selected documents' if scope.to_dict() else 'your library'} "
                "matched the question."
            )
            assistant.status = "insufficient_evidence"
            assistant.notes = notes
            yield _event("delta", text=assistant.content)
        else:
            provider = ai.chat(provider_name)
            assistant.provider, assistant.model = provider.name, provider.model
            if provider.name != "ollama":
                notes.append(
                    f"Your question and {len(result.passages)} passages were sent to "
                    f"{CHAT_PROVIDER_LABELS.get(provider.name, provider.name)} with your consent."
                )
            parts: list[str] = []
            try:
                turns = history + [ChatTurn("user", build_user_prompt(question, result.passages))]
                max_tokens = OLLAMA_MAX_TOKENS if provider.name == "ollama" else CLOUD_MAX_TOKENS
                for fragment in provider.stream_chat(SYSTEM_PROMPT, turns, max_tokens=max_tokens):
                    parts.append(fragment)
                    yield _event("delta", text=fragment)
                answer = "".join(parts).strip()
                valid, invalid = verify_citations(answer, len(result.passages))
                assistant.content = answer
                assistant.cited, assistant.invalid_citations = valid, invalid
                assistant.grounded = bool(valid)
                if is_insufficient(answer):
                    assistant.status = "insufficient_evidence"
                else:
                    assistant.status = "complete"
                    if not valid:
                        notes.append(
                            "This answer cites none of the provided sources. "
                            "Treat it as unverified."
                        )
                if invalid:
                    notes.append(
                        "The answer refers to source numbers that were not provided: "
                        + ", ".join(f"[{n}]" for n in invalid)
                    )
            except RefusalError as exc:
                assistant.content = str(exc)
                assistant.status = "refused"
            except ProviderError as exc:
                assistant.content = "".join(parts).strip()
                assistant.status = "error"
                notes.append(str(exc))
            assistant.notes = notes

        db.add(assistant)
        session.updated_at = utcnow()
        db.commit()
        message = ChatMessageRead.model_validate(assistant).model_dump()
        if assistant.status == "error":
            yield _event("error", message=notes[-1], chat_message=message)
        else:
            yield _event("done", message=message)
