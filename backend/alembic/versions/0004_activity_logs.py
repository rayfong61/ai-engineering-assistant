"""activity logs

Revision ID: 0004
Revises: 0003
Create Date: 2026-09-06

"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None

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


def upgrade() -> None:
    op.create_table(
        "activity_logs",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column(
            "project_id", UUID(as_uuid=True), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=True
        ),
        sa.Column("user_id", UUID(as_uuid=True), nullable=False),
        sa.Column("event_type", sa.String, nullable=False),
        sa.Column("detail", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint(f"event_type in {EVENT_TYPES!r}", name="activity_logs_event_type_check"),
    )
    op.create_index("activity_logs_project_id_idx", "activity_logs", ["project_id"])
    op.create_index("activity_logs_user_id_idx", "activity_logs", ["user_id"])


def downgrade() -> None:
    op.drop_index("activity_logs_user_id_idx", table_name="activity_logs")
    op.drop_index("activity_logs_project_id_idx", table_name="activity_logs")
    op.drop_table("activity_logs")
