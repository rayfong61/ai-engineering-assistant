import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.auth import get_current_user
from app.core.authorization import require_project_member
from app.core.database import get_db
from app.schemas.email import EmailLogOut, EmailPreviewRequest, EmailSendRequest
from app.services import email_service

router = APIRouter(prefix="/api/projects/{project_id}/email", tags=["email"])


@router.post("/preview", response_model=EmailLogOut)
def preview_email(
    project_id: str,
    payload: EmailPreviewRequest,
    user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    require_project_member(db, project_id, user)

    try:
        email_log = email_service.generate_preview(
            db, project_id, uuid.UUID(user["id"]), payload.instruction, payload.conversation_id
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail="Conversation not found") from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail="產生 Email 草稿失敗，請稍後再試") from exc

    return email_log


@router.post("/send", response_model=EmailLogOut)
def send_email(
    project_id: str,
    payload: EmailSendRequest,
    user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    require_project_member(db, project_id, user)

    try:
        return email_service.confirm_and_send(db, project_id, payload.email_log_id, uuid.UUID(user["id"]))
    except LookupError as exc:
        raise HTTPException(status_code=404, detail="Email draft not found") from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail="寄送 Email 失敗，請稍後再試") from exc
