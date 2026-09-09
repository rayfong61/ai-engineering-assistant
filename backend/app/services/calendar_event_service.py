import uuid
from datetime import datetime

from sqlalchemy.orm import Session

from app.tools import create_calendar_event as create_calendar_event_tool
from app.models import CalendarEventLog
from app.services.activity_service import log_activity
from app.services.email_service import EMAIL_RE


def _parse_datetime(value: str, field_label: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as exc:
        raise ValueError(
            f"{field_label}格式不正確，需為 ISO-8601 並包含時區（例如 2026-09-16T14:00:00+08:00）：{value}"
        ) from exc
    if parsed.tzinfo is None:
        raise ValueError(
            f"{field_label}缺少時區資訊，需為 ISO-8601 並包含時區（例如 2026-09-16T14:00:00+08:00）：{value}"
        )
    return parsed


def _attendee_detail(attendees: list[str] | None) -> str | None:
    # Log attendee emails (identifiers), never summary/description (event
    # content) -- mirrors email_service logging recipient, never subject/body.
    return ", ".join(attendees) if attendees else None


def save_draft(
    db: Session,
    project_id: str,
    user_id: uuid.UUID,
    summary: str,
    start_datetime: str,
    end_datetime: str,
    description: str | None = None,
    attendees: list[str] | None = None,
) -> CalendarEventLog:
    start_dt = _parse_datetime(start_datetime, "開始時間")
    end_dt = _parse_datetime(end_datetime, "結束時間")
    if end_dt <= start_dt:
        raise ValueError("結束時間必須晚於開始時間")
    for email in attendees or []:
        if not EMAIL_RE.match(email):
            raise ValueError(f"參與者 Email 格式不正確：{email}")

    event_log = CalendarEventLog(
        project_id=project_id,
        user_id=user_id,
        summary=summary,
        description=description,
        start_datetime=start_dt,
        end_datetime=end_dt,
        attendees=attendees or [],
        status="draft",
    )
    db.add(event_log)
    log_activity(db, project_id, user_id, "calendar_event_draft_generated", detail=_attendee_detail(attendees))
    db.commit()
    db.refresh(event_log)
    return event_log


def confirm_and_create(
    db: Session, project_id: str, calendar_event_log_id: uuid.UUID, user_id: uuid.UUID
) -> CalendarEventLog:
    event_log = (
        db.query(CalendarEventLog)
        .filter(CalendarEventLog.id == calendar_event_log_id, CalendarEventLog.project_id == project_id)
        .first()
    )
    if not event_log:
        raise LookupError("Calendar event draft not found")
    if event_log.status != "draft":
        raise ValueError(f"Calendar event is already {event_log.status}")

    event_log.status = "confirmed"
    log_activity(
        db, project_id, user_id, "user_confirmed_calendar_event", detail=_attendee_detail(event_log.attendees)
    )
    db.commit()

    try:
        result = create_calendar_event_tool.run(
            summary=event_log.summary,
            start_datetime=event_log.start_datetime.isoformat(),
            end_datetime=event_log.end_datetime.isoformat(),
            description=event_log.description,
            attendees=event_log.attendees,
            user_id=str(user_id),
        )
    except Exception:
        event_log.status = "failed"
        db.commit()
        raise

    event_log.status = "created" if result.get("status") == "created" else "failed"
    event_log.google_event_id = result.get("google_event_id")
    if event_log.status == "created":
        log_activity(
            db, project_id, user_id, "calendar_event_created", detail=_attendee_detail(event_log.attendees)
        )
    db.commit()
    db.refresh(event_log)
    return event_log
