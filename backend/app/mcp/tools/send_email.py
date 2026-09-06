import logging
import uuid

from app.core.config import EMAIL_MODE
from app.core.database import SessionLocal
from app.services import gmail_service

logger = logging.getLogger(__name__)


def run(to: str, subject: str, body: str, user_id: str | None = None) -> dict:
    """Mock mode (default) logs and returns success without touching a real
    mail provider. Gmail mode sends for real via gmail_service, using the
    calling user's connected Gmail credential (spec2.md section 26's
    independent Gmail-only OAuth flow).

    Never called by the Agent's tool loop directly (human-in-the-loop,
    spec2.md section 24) -- the only caller is
    app.services.email_service.confirm_and_send, itself only reachable via
    an explicit user "Confirm & Send" action (POST /email/send).
    """
    if EMAIL_MODE == "mock":
        # Never log the body -- CLAUDE.md security rule against logging
        # full email contents.
        logger.info("[MOCK EMAIL] to=%s subject=%s", to, subject)
        return {"status": "sent", "message": f"[MOCK EMAIL] 已模擬寄送給 {to}"}

    if EMAIL_MODE == "gmail":
        if not user_id:
            return {"status": "failed", "message": "缺少 user_id，無法寄送 Gmail"}

        db = SessionLocal()
        try:
            result = gmail_service.send_email(db, uuid.UUID(user_id), to, subject, body)
        finally:
            db.close()

        logger.info("[GMAIL] to=%s subject=%s status=%s", to, subject, result.get("status"))
        return result

    return {
        "status": "failed",
        "message": f"EMAIL_MODE={EMAIL_MODE} 尚未支援",
    }
