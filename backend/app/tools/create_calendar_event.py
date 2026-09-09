import logging
import uuid

from app.core.config import CALENDAR_MODE
from app.core.database import SessionLocal
from app.services import calendar_service

logger = logging.getLogger(__name__)


def run(
    summary: str,
    start_datetime: str,
    end_datetime: str,
    description: str | None = None,
    attendees: list[str] | None = None,
    user_id: str | None = None,
) -> dict:
    """Mock mode (default) logs and returns success without touching a real
    Calendar. google_calendar mode creates a real event via calendar_service,
    using the calling user's connected Google credential (the same Gmail
    OAuth grant, extended with calendar.events).

    Never called by the Agent's tool loop directly (human-in-the-loop,
    mirroring send_email.py) -- the only caller is
    app.services.calendar_event_service.confirm_and_create, itself only
    reachable via an explicit user "Confirm & Create" action
    (POST .../calendar-events/create).
    """
    if CALENDAR_MODE == "mock":
        # Never log description -- same rule as never logging email body.
        logger.info("[MOCK CALENDAR] summary=%s start=%s end=%s", summary, start_datetime, end_datetime)
        return {
            "status": "created",
            "message": f"[MOCK CALENDAR] 已模擬建立事件：{summary}",
            "google_event_id": None,
        }

    if CALENDAR_MODE == "google_calendar":
        if not user_id:
            return {"status": "failed", "message": "缺少 user_id，無法建立 Google Calendar 事件", "google_event_id": None}

        db = SessionLocal()
        try:
            result = calendar_service.create_event(
                db, uuid.UUID(user_id), summary, start_datetime, end_datetime, description, attendees
            )
        finally:
            db.close()

        logger.info("[CALENDAR] summary=%s status=%s", summary, result.get("status"))
        return result

    return {
        "status": "failed",
        "message": f"CALENDAR_MODE={CALENDAR_MODE} 尚未支援",
        "google_event_id": None,
    }
