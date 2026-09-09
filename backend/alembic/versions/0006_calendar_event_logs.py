"""calendar event logs + activity_logs event_type additions

Revision ID: 0006
Revises: 0005
Create Date: 2026-09-09

"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None

OLD_EVENT_TYPES = (
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
NEW_EVENT_TYPES = OLD_EVENT_TYPES + (
    "calendar_event_draft_generated",
    "user_confirmed_calendar_event",
    "calendar_event_created",
)


def upgrade() -> None:
    op.create_table(
        "calendar_event_logs",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column(
            "project_id", UUID(as_uuid=True), sa.ForeignKey("projects.id", ondelete="SET NULL"), nullable=True
        ),
        sa.Column("user_id", UUID(as_uuid=True), nullable=False),
        sa.Column("summary", sa.String, nullable=True),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("start_datetime", sa.DateTime(timezone=True), nullable=True),
        sa.Column("end_datetime", sa.DateTime(timezone=True), nullable=True),
        sa.Column("attendees", JSONB, nullable=True),
        sa.Column("status", sa.String, nullable=False, server_default="draft"),
        sa.Column("google_event_id", sa.String, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint(
            "status in ('draft', 'confirmed', 'created', 'failed', 'cancelled')",
            name="calendar_event_logs_status_check",
        ),
    )

    op.drop_constraint("activity_logs_event_type_check", "activity_logs", type_="check")
    op.create_check_constraint(
        "activity_logs_event_type_check", "activity_logs", f"event_type in {NEW_EVENT_TYPES!r}"
    )


def downgrade() -> None:
    op.drop_constraint("activity_logs_event_type_check", "activity_logs", type_="check")
    op.create_check_constraint(
        "activity_logs_event_type_check", "activity_logs", f"event_type in {OLD_EVENT_TYPES!r}"
    )
    op.drop_table("calendar_event_logs")
