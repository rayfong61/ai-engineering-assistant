import uuid

from fastapi import APIRouter, Depends
from sqlalchemy import and_, or_
from sqlalchemy.orm import Session

from app.core.auth import get_current_user
from app.core.authorization import require_project_member
from app.core.database import get_db
from app.models import ActivityLog
from app.schemas.activity import ActivityLogOut

router = APIRouter(prefix="/api/projects/{project_id}/activity", tags=["activity"])


@router.get("", response_model=list[ActivityLogOut])
def list_activity(
    project_id: str, user: dict = Depends(get_current_user), db: Session = Depends(get_db)
):
    require_project_member(db, project_id, user)
    # project_id IS NULL rows are global events (currently just
    # user_logged_in, which has no project context) -- included here only
    # when they belong to the requesting user, not every member's login.
    return (
        db.query(ActivityLog)
        .filter(
            or_(
                ActivityLog.project_id == project_id,
                and_(ActivityLog.project_id.is_(None), ActivityLog.user_id == uuid.UUID(user["id"])),
            )
        )
        .order_by(ActivityLog.created_at.desc())
        .limit(200)
        .all()
    )
