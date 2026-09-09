import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.auth import get_current_user
from app.core.authorization import require_project_member
from app.core.database import get_db
from app.schemas.calendar_event import CalendarEventCreateRequest, CalendarEventLogOut
from app.services import calendar_event_service

router = APIRouter(prefix="/api/projects/{project_id}/calendar-events", tags=["calendar-events"])


@router.post("/create", response_model=CalendarEventLogOut)
def create_calendar_event_route(
    project_id: str,
    payload: CalendarEventCreateRequest,
    user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    require_project_member(db, project_id, user)

    try:
        return calendar_event_service.confirm_and_create(
            db, project_id, payload.calendar_event_log_id, uuid.UUID(user["id"])
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail="Calendar event draft not found") from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail="建立 Google Calendar 事件失敗，請稍後再試") from exc
