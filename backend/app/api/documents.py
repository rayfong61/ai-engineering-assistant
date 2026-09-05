import uuid
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, Response, UploadFile
from sqlalchemy.orm import Session

from app.core.auth import get_current_user
from app.core.authorization import require_project_member
from app.core.config import STORAGE_BUCKET
from app.core.database import SessionLocal, get_db
from app.core.supabase_client import get_supabase
from app.models import Document
from app.schemas.document import DocumentOut
from app.services import rag_service

router = APIRouter(prefix="/api/projects/{project_id}/documents", tags=["documents"])

MAX_PDF_SIZE = 100 * 1024 * 1024


def _ensure_bucket() -> None:
    try:
        get_supabase().storage.create_bucket(STORAGE_BUCKET, options={"public": False})
    except Exception:
        pass  # bucket already exists


def _process_document_task(document_id: str, content: bytes) -> None:
    """Runs after the upload response is sent, on its own DB session --
    the request-scoped session from Depends(get_db) is already closed."""
    db = SessionLocal()
    try:
        document = db.query(Document).filter(Document.id == document_id).first()
        if document:
            rag_service.ingest_document(db, document, content)
    finally:
        db.close()


@router.get("", response_model=list[DocumentOut])
def list_documents(
    project_id: str, user: dict = Depends(get_current_user), db: Session = Depends(get_db)
):
    require_project_member(db, project_id, user)
    return (
        db.query(Document)
        .filter(Document.project_id == project_id)
        .order_by(Document.created_at.desc())
        .all()
    )


@router.post("", response_model=DocumentOut)
async def upload_document(
    project_id: str,
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    require_project_member(db, project_id, user)

    filename = Path(file.filename or "").name
    if not filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="只接受 PDF 檔案")

    content = await file.read()
    if len(content) > MAX_PDF_SIZE:
        raise HTTPException(status_code=400, detail="檔案大小超過 100MB 上限")

    document = Document(
        project_id=project_id,
        uploaded_by=uuid.UUID(user["id"]),
        filename=filename,
        storage_path="",
        file_size=len(content),
        status="uploaded",
    )
    db.add(document)
    db.flush()  # assign document.id before building its storage path

    # Storage object keys must be ASCII -- Supabase Storage's cloud backend
    # rejects non-ASCII keys (e.g. Chinese filenames) with "Invalid key".
    # The human-readable name is preserved in document.filename (DB column,
    # used for display/citations); the storage key itself doesn't need it.
    document.storage_path = f"projects/{project_id}/documents/{document.id}/{document.id}.pdf"

    _ensure_bucket()
    try:
        get_supabase().storage.from_(STORAGE_BUCKET).upload(
            document.storage_path, content, {"content-type": "application/pdf"}
        )
    except Exception as exc:
        db.rollback()  # discard the flushed row -- don't leave a stuck ghost document
        raise HTTPException(status_code=502, detail="上傳到儲存空間失敗，請稍後再試") from exc

    db.commit()
    db.refresh(document)

    background_tasks.add_task(_process_document_task, str(document.id), content)

    return document


@router.delete("/{document_id}", status_code=204)
def delete_document(
    project_id: str,
    document_id: str,
    user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    require_project_member(db, project_id, user)

    document = (
        db.query(Document)
        .filter(Document.id == document_id, Document.project_id == project_id)
        .first()
    )
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")

    try:
        get_supabase().storage.from_(STORAGE_BUCKET).remove([document.storage_path])
    except Exception:
        pass  # storage cleanup best-effort; DB row is the source of truth

    db.delete(document)  # cascades to document_chunks
    db.commit()

    return Response(status_code=204)
