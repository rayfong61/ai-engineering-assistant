from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.agent import agent_service
from app.core.auth import get_current_user
from app.core.authorization import require_project_member
from app.core.database import get_db
from app.schemas.agent import AgentRequest, AgentResponse

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
        return agent_service.process_request(db, project_id, user, payload.conversation_id, payload.message)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
