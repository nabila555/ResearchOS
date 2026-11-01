from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.activity import Activity


def log_activity(
    db: Session,
    *,
    action: str,
    entity_type: str,
    entity_id: int | None,
    summary: str,
) -> Activity:
    """Record an activity. The caller owns the transaction and commits it."""
    activity = Activity(
        action=action, entity_type=entity_type, entity_id=entity_id, summary=summary[:500]
    )
    db.add(activity)
    return activity


def recent_activity(db: Session, limit: int = 10) -> list[Activity]:
    stmt = select(Activity).order_by(Activity.created_at.desc(), Activity.id.desc()).limit(limit)
    return list(db.scalars(stmt))
