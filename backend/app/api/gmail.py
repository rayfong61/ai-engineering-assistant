import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.core.auth import get_current_user
from app.core.config import FRONTEND_URL
from app.core.database import get_db
from app.services import gmail_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/gmail", tags=["gmail"])


@router.get("/authorize-url")
def authorize_url(user: dict = Depends(get_current_user)) -> dict:
    try:
        return {"url": gmail_service.build_authorize_url(user["id"])}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/callback")
def callback(
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
    db: Session = Depends(get_db),
) -> RedirectResponse:
    # No get_current_user here -- Google's redirect carries no bearer
    # token; identity is recovered from the signed `state` param inside
    # handle_callback (spec2.md section 8's "identity from the JWT" rule
    # doesn't apply to this one unauthenticated hop by necessity).
    if error or not code or not state:
        return RedirectResponse(f"{FRONTEND_URL}/settings?gmail=error")

    try:
        gmail_service.handle_callback(db, code, state)
    except Exception:
        logger.exception("Gmail OAuth callback failed")
        return RedirectResponse(f"{FRONTEND_URL}/settings?gmail=error")

    return RedirectResponse(f"{FRONTEND_URL}/settings?gmail=connected")


@router.get("/status")
def status(user: dict = Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    return gmail_service.get_status(db, uuid.UUID(user["id"]))


@router.post("/disconnect")
def disconnect(user: dict = Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    gmail_service.disconnect(db, uuid.UUID(user["id"]))
    return {"connected": False, "gmail_email": None}
