import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, String, Text, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base

EVENT_TYPES = (
    "user_logged_in",
    "project_created",
    "pdf_uploaded",
    "pdf_processing_completed",
    "embedding_generated",
    "rag_search_executed",
    "vision_analysis_completed",
    "meeting_summary_generated",
    "email_draft_generated",
    "user_confirmed_email",
    "email_sent",
)


class ActivityLog(Base):
    __tablename__ = "activity_logs"
    __table_args__ = (
        CheckConstraint(f"event_type in {EVENT_TYPES!r}", name="activity_logs_event_type_check"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    project_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    event_type: Mapped[str] = mapped_column(String, nullable=False)
    detail: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("now()"))
