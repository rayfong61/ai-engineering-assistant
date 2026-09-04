import uuid

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.auth import get_current_user
from app.core.authorization import require_project_member, require_project_owner
from app.core.database import get_db
from app.models import Project, ProjectMember
from app.schemas.project import ProjectCreate, ProjectOut

router = APIRouter(prefix="/api/projects", tags=["projects"])


@router.get("", response_model=list[ProjectOut])
def list_projects(user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    project_ids = [
        row.project_id
        for row in db.query(ProjectMember.project_id).filter(ProjectMember.user_id == user["id"]).all()
    ]
    if not project_ids:
        return []
    return db.query(Project).filter(Project.id.in_(project_ids)).all()


@router.post("", response_model=ProjectOut)
def create_project(
    payload: ProjectCreate, user: dict = Depends(get_current_user), db: Session = Depends(get_db)
):
    project = Project(
        name=payload.name, description=payload.description, created_by=uuid.UUID(user["id"])
    )
    db.add(project)
    try:
        db.flush()  # assign project.id before creating the membership row

        db.add(ProjectMember(project_id=project.id, user_id=uuid.UUID(user["id"]), role="owner"))
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=409, detail="已經有同名的專案了"
        ) from exc

    db.refresh(project)
    return project


@router.get("/{project_id}", response_model=ProjectOut)
def get_project(
    project_id: str, user: dict = Depends(get_current_user), db: Session = Depends(get_db)
):
    require_project_member(db, project_id, user)

    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


@router.delete("/{project_id}", status_code=204)
def delete_project(
    project_id: str, user: dict = Depends(get_current_user), db: Session = Depends(get_db)
):
    require_project_owner(db, project_id, user)

    project = db.query(Project).filter(Project.id == project_id).first()
    if project:
        db.delete(project)  # cascades to project_members/documents/conversations/etc
        db.commit()

    return Response(status_code=204)
