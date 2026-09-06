from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.auth import get_current_user
from app.core.database import get_db
from app.services.activity_service import log_activity

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.get("/me")
def get_me(user: dict = Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    log_activity(db, None, user["id"], "user_logged_in")
    db.commit()
    return user
