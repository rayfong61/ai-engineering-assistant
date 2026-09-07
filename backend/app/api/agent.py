import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.agent import agent_service
from app.core.auth import get_current_user
from app.core.authorization import require_project_member
from app.core.database import get_db
from app.schemas.agent import AgentRequest, AgentResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/projects/{project_id}/agent", tags=["agent"])


@router.post("", response_model=AgentResponse)
def run_agent(
    project_id: str,
    payload: AgentRequest,
    user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    require_project_member(db, project_id, user)
    try:
        return agent_service.process_request(
            db,
            project_id,
            user,
            payload.conversation_id,
            payload.message,
            image_id=str(payload.image_id) if payload.image_id else None,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("Agent request failed for project %s", project_id)
        raise HTTPException(status_code=502, detail="Agent 執行失敗，請稍後再試") from exc
