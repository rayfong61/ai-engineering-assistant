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


def require_project_owner(db: Session, project_id: str, user: dict) -> None:
    """Raise 403 unless the current user is this project's owner.

    Deleting a project cascades to its documents/conversations/etc, so
    this is the one place worth using the `role` column early instead of
    treating every member equally (spec2.md section 37's membership-only
    simplification still applies to read/write access on project content).
    """
    membership = (
        db.query(ProjectMember)
        .filter(ProjectMember.project_id == project_id, ProjectMember.user_id == user["id"])
        .first()
    )
    if not membership or membership.role != "owner":
        raise HTTPException(status_code=403, detail="Only the project owner can do this")
