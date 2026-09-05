import logging

from app.core.config import EMAIL_MODE

logger = logging.getLogger(__name__)


def run(to: str, subject: str, body: str) -> dict:
    """Day 4: actually "sends" in mock mode -- logs and returns success
    without touching a real mail provider. Real Gmail sending is out of
    scope for now; EMAIL_MODE values other than "mock" fail cleanly rather
    than pretending to send.

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

    return {
        "status": "failed",
        "message": f"EMAIL_MODE={EMAIL_MODE} 尚未支援（Gmail OAuth 尚未串接）",
    }
