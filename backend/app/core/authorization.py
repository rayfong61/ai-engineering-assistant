from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models import ProjectMember


def require_project_member(db: Session, project_id: str, user: dict) -> None:
    """Raise 403 unless the current user belongs to this project.

    First-pass authorization per spec2.md section 37: membership-only,
    no owner/member role differentiation yet.
    """
    is_member = (
        db.query(ProjectMember)
        .filter(ProjectMember.project_id == project_id, ProjectMember.user_id == user["id"])
        .first()
    )
    if not is_member:
        raise HTTPException(status_code=403, detail="Not a member of this project")
