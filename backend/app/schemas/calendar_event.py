import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class CalendarEventCreateRequest(BaseModel):
    calendar_event_log_id: uuid.UUID


class CalendarEventLogOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    summary: str | None
    description: str | None
    start_datetime: datetime | None
    end_datetime: datetime | None
    attendees: list[str] | None
    status: str
    google_event_id: str | None
    created_at: datetime
