"""vision analyses

Revision ID: 0003
Revises: 0002
Create Date: 2026-09-05

"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "vision_analyses",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column(
            "project_id", UUID(as_uuid=True), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("uploaded_by", UUID(as_uuid=True), nullable=False),
        sa.Column("filename", sa.String, nullable=False),
        sa.Column("storage_path", sa.String, nullable=False),
        sa.Column("file_size", sa.BigInteger, nullable=True),
        sa.Column("analysis", sa.Text, nullable=False),
        sa.Column("observations", JSONB, nullable=False),
        sa.Column("limitations", JSONB, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("vision_analyses_project_id_idx", "vision_analyses", ["project_id"])


def downgrade() -> None:
    op.drop_index("vision_analyses_project_id_idx", table_name="vision_analyses")
    op.drop_table("vision_analyses")
