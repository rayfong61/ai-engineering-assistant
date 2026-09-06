import re
import uuid

from sqlalchemy.orm import Session

from app.mcp import client as mcp_client
from app.models import Conversation, EmailLog, Message
from app.services import claude_service
from app.services.activity_service import log_activity

# Minimal format check (spec2.md section 32 security minimum) -- not
# exhaustive RFC 5322 validation, just enough to catch an obviously
# malformed address before it's persisted as a draft.
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def save_draft(
    db: Session, project_id: str, user_id: uuid.UUID, recipient: str, subject: str, body: str
) -> EmailLog:
    if not EMAIL_RE.match(recipient):
        raise ValueError(f"收件人 Email 格式不正確：{recipient}")

    email_log = EmailLog(
        project_id=project_id,
        user_id=user_id,
        recipient=recipient,
        subject=subject,
        body=body,
        status="draft",
    )
    db.add(email_log)
    log_activity(db, project_id, user_id, "email_draft_generated", detail=recipient)
    db.commit()
    db.refresh(email_log)
    return email_log


def _conversation_context(db: Session, project_id: str, conversation_id: uuid.UUID) -> str:
    conversation = (
        db.query(Conversation)
        .filter(Conversation.id == conversation_id, Conversation.project_id == project_id)
        .first()
    )
    if not conversation:
        raise LookupError("Conversation not found")

    messages = (
        db.query(Message)
        .filter(Message.conversation_id == conversation.id, Message.role.in_(["user", "assistant"]))
        .order_by(Message.created_at)
        .all()
    )
    return "\n\n".join(f"{m.role}: {m.content}" for m in messages)


def generate_preview(
    db: Session,
    project_id: str,
    user_id: uuid.UUID,
    instruction: str,
    conversation_id: uuid.UUID | None,
) -> EmailLog:
    context = _conversation_context(db, project_id, conversation_id) if conversation_id else None
    draft = claude_service.generate_email_draft(instruction, context)
    return save_draft(db, project_id, user_id, draft["to"], draft["subject"], draft["body"])


def confirm_and_send(db: Session, project_id: str, email_log_id: uuid.UUID, user_id: uuid.UUID) -> EmailLog:
    email_log = (
        db.query(EmailLog)
        .filter(EmailLog.id == email_log_id, EmailLog.project_id == project_id)
        .first()
    )
    if not email_log:
        raise LookupError("Email draft not found")
    if email_log.status != "draft":
        raise ValueError(f"Email is already {email_log.status}")

    email_log.status = "confirmed"
    log_activity(db, project_id, user_id, "user_confirmed_email", detail=email_log.recipient)
    db.commit()

    try:
        result = mcp_client.call_tool(
            "send_email",
            {"to": email_log.recipient, "subject": email_log.subject, "body": email_log.body},
        )
    except Exception:
        email_log.status = "failed"
        db.commit()
        raise

    email_log.status = "sent" if result.get("status") == "sent" else "failed"
    if email_log.status == "sent":
        log_activity(db, project_id, user_id, "email_sent", detail=email_log.recipient)
    db.commit()
    db.refresh(email_log)
    return email_log
