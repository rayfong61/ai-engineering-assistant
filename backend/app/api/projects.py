import uuid

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.auth import get_current_user
from app.core.authorization import require_project_member, require_project_owner
from app.core.config import STORAGE_BUCKET
from app.core.database import get_db
from app.core.supabase_client import get_supabase
from app.models import Document, Project, ProjectMember, VisionAnalysis
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
        # DB rows are the source of truth for what Storage objects exist --
        # same assumption documents.py's delete_document makes. The cascade
        # below deletes these rows, so their storage_path must be collected
        # first or it's unrecoverable.
        storage_paths = [
            d.storage_path
            for d in db.query(Document).filter(Document.project_id == project_id).all()
            if d.storage_path
        ] + [
            v.storage_path
            for v in db.query(VisionAnalysis).filter(VisionAnalysis.project_id == project_id).all()
            if v.storage_path
        ]
        if storage_paths:
            try:
                get_supabase().storage.from_(STORAGE_BUCKET).remove(storage_paths)
            except Exception:
                pass  # storage cleanup best-effort; DB row is the source of truth

        db.delete(project)  # cascades to project_members/documents/conversations/etc
        db.commit()

    return Response(status_code=204)
