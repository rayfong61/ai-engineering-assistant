import uuid

import httpx
from sqlalchemy.orm import Session

from app.models import GmailCredential
from app.services.gmail_service import _decrypt, _refresh_access_token

GOOGLE_CALENDAR_EVENTS_URL = "https://www.googleapis.com/calendar/v3/calendars/primary/events"
_HTTP_TIMEOUT = 10


def create_event(
    db: Session,
    user_id: uuid.UUID,
    summary: str,
    start_datetime: str,
    end_datetime: str,
    description: str | None = None,
    attendees: list[str] | None = None,
) -> dict:
    """Never raises -- the only caller (app.tools.create_calendar_event)
    depends on this always returning
    {"status": "created"|"failed", "message": ..., "google_event_id": ...|None}.
    Mirrors gmail_service.send_email's exact contract shape.

    Reuses the same GmailCredential row as gmail_service -- Calendar and
    Gmail share one OAuth grant (see gmail_service.GMAIL_OAUTH_SCOPES), not
    separate credential tables."""
    credential = db.get(GmailCredential, user_id)
    if not credential:
        return {
            "status": "failed",
            "message": "Google 帳號尚未連接，請先於 Settings 頁面完成授權",
            "google_event_id": None,
        }

    try:
        refresh_token = _decrypt(credential.encrypted_refresh_token)
        access_token = _refresh_access_token(refresh_token)

        body = {
            "summary": summary,
            "start": {"dateTime": start_datetime},
            "end": {"dateTime": end_datetime},
        }
        if description:
            body["description"] = description
        if attendees:
            body["attendees"] = [{"email": a} for a in attendees]

        response = httpx.post(
            GOOGLE_CALENDAR_EVENTS_URL,
            headers={"Authorization": f"Bearer {access_token}"},
            # Without sendUpdates, the Calendar API's default is "none" --
            # attendees are added to the event but never actually emailed an
            # invite. "all" is what makes this a real notification, not just
            # a silent calendar entry.
            params={"sendUpdates": "all"},
            json=body,
            timeout=_HTTP_TIMEOUT,
        )
        response.raise_for_status()
        event = response.json()
    except Exception as exc:
        # Covers insufficient-scope 403s from a pre-calendar.events credential
        # the same way as any other Calendar API failure -- no special case,
        # see CLAUDE.md "Standing decisions -> Calendar".
        return {"status": "failed", "message": f"Google Calendar 建立事件失敗：{exc}", "google_event_id": None}

    return {"status": "created", "message": "已建立 Google Calendar 事件", "google_event_id": event.get("id")}
