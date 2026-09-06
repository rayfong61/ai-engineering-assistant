import logging
import uuid

from sqlalchemy.orm import Session

from app.models import ActivityLog

logger = logging.getLogger(__name__)


def log_activity(
    db: Session, project_id, user_id, event_type: str, detail: str | None = None
) -> None:
    """Insert-only, best-effort activity record (spec2.md section 29).

    Wrapped in a SAVEPOINT so a logging failure never aborts the caller's
    own transaction -- SessionLocal has no autoflush/autocommit, so one
    aborted statement would otherwise block the whole session until a
    rollback, breaking the real workflow step this call is describing.

    Never pass email subject/body or API keys into `detail` -- recipient
    or filename only.
    """
    try:
        with db.begin_nested():
            db.add(
                ActivityLog(
                    project_id=project_id,
                    user_id=uuid.UUID(str(user_id)),
                    event_type=event_type,
                    detail=detail,
                )
            )
    except Exception:
        logger.exception("log_activity failed for event_type=%s", event_type)
