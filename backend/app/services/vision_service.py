from app.core.config import STORAGE_BUCKET
from app.core.supabase_client import get_supabase
from app.services import claude_service

# Long enough for a normal viewing session, short enough that a leaked URL
# doesn't stay valid forever -- the bucket itself stays private either way.
SIGNED_URL_EXPIRES_IN = 60 * 60


def analyze_engineering_image(image_bytes: bytes, media_type: str) -> dict:
    return claude_service.analyze_image(image_bytes, media_type)


def _signed_url_for(storage_path: str) -> str | None:
    try:
        result = get_supabase().storage.from_(STORAGE_BUCKET).create_signed_url(
            storage_path, SIGNED_URL_EXPIRES_IN
        )
        return result["signedURL"]
    except Exception:
        return None  # best-effort, matches this module's other broad-except Storage handling
