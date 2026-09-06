"""gmail credentials

Revision ID: 0005
Revises: 0004
Create Date: 2026-09-06

"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "gmail_credentials",
        sa.Column("user_id", UUID(as_uuid=True), primary_key=True),
        sa.Column("gmail_email", sa.String, nullable=True),
        sa.Column("encrypted_refresh_token", sa.Text, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("gmail_credentials")
