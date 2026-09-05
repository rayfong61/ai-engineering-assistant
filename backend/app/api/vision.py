import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.core.auth import get_current_user
from app.core.authorization import require_project_member
from app.core.config import STORAGE_BUCKET
from app.core.database import get_db
from app.core.supabase_client import get_supabase
from app.models import VisionAnalysis
from app.schemas.vision import VisionAnalysisOut
from app.services import vision_service

router = APIRouter(prefix="/api/projects/{project_id}/vision", tags=["vision"])

MAX_IMAGE_SIZE = 10 * 1024 * 1024
EXTENSION_MEDIA_TYPES = {"jpg": "image/jpeg", "jpeg": "image/jpeg", "png": "image/png", "webp": "image/webp"}
ALLOWED_MEDIA_TYPES = set(EXTENSION_MEDIA_TYPES.values())
# Long enough for a normal viewing session, short enough that a leaked URL
# doesn't stay valid forever -- the bucket itself stays private either way.
SIGNED_URL_EXPIRES_IN = 60 * 60


def _ensure_bucket() -> None:
    try:
        get_supabase().storage.create_bucket(STORAGE_BUCKET, options={"public": False})
    except Exception:
        pass  # bucket already exists


def _signed_url_for(storage_path: str) -> str | None:
    try:
        result = get_supabase().storage.from_(STORAGE_BUCKET).create_signed_url(
            storage_path, SIGNED_URL_EXPIRES_IN
        )
        return result["signedURL"]
    except Exception:
        return None  # best-effort, matches this file's other broad-except Storage handling


def _signed_urls_for(records: list[VisionAnalysis]) -> dict[str, str]:
    """Batch-resolve storage_path -> signed URL in one Storage API round trip.
    A path whose Storage object no longer exists comes back with an "error"
    entry rather than raising -- filtered out here, so one missing image
    doesn't take down the whole list."""
    if not records:
        return {}
    paths = [r.storage_path for r in records]
    try:
        signed = get_supabase().storage.from_(STORAGE_BUCKET).create_signed_urls(
            paths, SIGNED_URL_EXPIRES_IN
        )
    except Exception:
        return {}
    return {item["path"]: item["signedURL"] for item in signed if not item.get("error")}


def _to_out(record: VisionAnalysis, image_url: str | None) -> VisionAnalysisOut:
    return VisionAnalysisOut.model_validate(record).model_copy(update={"image_url": image_url})


@router.get("", response_model=list[VisionAnalysisOut])
def list_vision_analyses(
    project_id: str, user: dict = Depends(get_current_user), db: Session = Depends(get_db)
):
    require_project_member(db, project_id, user)
    records = (
        db.query(VisionAnalysis)
        .filter(VisionAnalysis.project_id == project_id)
        .order_by(VisionAnalysis.created_at.desc())
        .all()
    )
    url_by_path = _signed_urls_for(records)
    return [_to_out(r, url_by_path.get(r.storage_path)) for r in records]


@router.post("", response_model=VisionAnalysisOut)
async def analyze_image(
    project_id: str,
    file: UploadFile = File(...),
    user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    require_project_member(db, project_id, user)

    filename = Path(file.filename or "").name
    ext = filename.lower().rsplit(".", 1)[-1] if "." in filename else ""
    media_type = file.content_type if file.content_type in ALLOWED_MEDIA_TYPES else EXTENSION_MEDIA_TYPES.get(ext)
    if media_type is None:
        raise HTTPException(status_code=400, detail="只接受 JPG/PNG/WEBP 圖片")

    content = await file.read()
    if len(content) > MAX_IMAGE_SIZE:
        raise HTTPException(status_code=400, detail="圖片大小超過 10MB 上限")

    record = VisionAnalysis(
        project_id=project_id,
        uploaded_by=uuid.UUID(user["id"]),
        filename=filename,
        storage_path="",
        file_size=len(content),
        analysis="",
        observations=[],
        limitations=[],
    )
    db.add(record)
    db.flush()  # assign record.id before building its storage path

    # Storage object keys must be ASCII (same constraint as documents.py) --
    # use the record id, not the human-readable filename, which is preserved
    # separately in record.filename for display.
    storage_ext = ext if ext in EXTENSION_MEDIA_TYPES else "jpg"
    record.storage_path = f"projects/{project_id}/images/{record.id}/{record.id}.{storage_ext}"

    _ensure_bucket()
    try:
        get_supabase().storage.from_(STORAGE_BUCKET).upload(
            record.storage_path, content, {"content-type": media_type}
        )
    except Exception as exc:
        db.rollback()
        raise HTTPException(status_code=502, detail="上傳到儲存空間失敗，請稍後再試") from exc

    try:
        result = vision_service.analyze_engineering_image(content, media_type)
    except Exception as exc:
        db.rollback()
        raise HTTPException(status_code=502, detail="圖片分析失敗，請稍後再試") from exc

    record.analysis = result["analysis"]
    record.observations = result["observations"]
    record.limitations = result["limitations"]
    db.commit()
    db.refresh(record)

    return _to_out(record, _signed_url_for(record.storage_path))
