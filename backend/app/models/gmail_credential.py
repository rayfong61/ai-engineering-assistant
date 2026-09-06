import uuid
from datetime import datetime

from sqlalchemy import DateTime, String, Text, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class GmailCredential(Base):
    """One row per Supabase user who has connected a Gmail account for
    sending (spec2.md section 26's independent Gmail-only OAuth flow --
    unrelated to Supabase Auth's Google login). No FK to a local users
    table -- none exists; user_id is a bare UUID, same pattern as
    ProjectMember.user_id."""

    __tablename__ = "gmail_credentials"

    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    gmail_email: Mapped[str | None] = mapped_column(String, nullable=True)
    encrypted_refresh_token: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("now()"))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("now()"))
