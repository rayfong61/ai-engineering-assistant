"""project name unique per creator

Revision ID: 0002
Revises: 0001
Create Date: 2026-09-04

"""

from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_unique_constraint(
        "projects_created_by_name_key", "projects", ["created_by", "name"]
    )


def downgrade() -> None:
    op.drop_constraint("projects_created_by_name_key", "projects", type_="unique")
