"""User-changeable AI settings persisted in the database."""

from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.core.config import Settings
from app.models.ai import AppSetting

CHAT_PROVIDER_KEY = "chat_provider"
CLOUD_CONSENT_KEY = "cloud_consent"


@dataclass
class AISettings:
    chat_provider: str
    # Explicit consent to send question text and retrieved passages to a cloud provider.
    cloud_consent: bool


def _get(db: Session, key: str, default: object) -> object:
    row = db.get(AppSetting, key)
    return default if row is None else row.value


def _set(db: Session, key: str, value: object) -> None:
    row = db.get(AppSetting, key)
    if row is None:
        db.add(AppSetting(key=key, value=value))
    else:
        row.value = value


def get_ai_settings(db: Session, settings: Settings) -> AISettings:
    return AISettings(
        chat_provider=str(_get(db, CHAT_PROVIDER_KEY, settings.ai_provider)),
        cloud_consent=bool(_get(db, CLOUD_CONSENT_KEY, False)),
    )


def update_ai_settings(
    db: Session, *, chat_provider: str | None = None, cloud_consent: bool | None = None
) -> None:
    if chat_provider is not None:
        _set(db, CHAT_PROVIDER_KEY, chat_provider)
    if cloud_consent is not None:
        _set(db, CLOUD_CONSENT_KEY, cloud_consent)
    db.commit()
