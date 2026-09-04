"""initial schema

Revision ID: 0001
Revises:
Create Date: 2026-09-04

"""

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects.postgresql import JSONB, UUID

# revision identifiers, used by Alembic.
revision = "0001"
down_revision = None
branch_labels = None
depends_on = None

# NOTE: confirm the exact Voyage AI model's output dimension at
# https://docs.voyageai.com before Day 2 ingestion — don't carry this
# default forward unverified (spec2.md section 9).
EMBEDDING_DIM = 1024


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto")

    op.create_table(
        "projects",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("name", sa.String, nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("created_by", UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )

    op.create_table(
        "project_members",
        sa.Column(
            "project_id", UUID(as_uuid=True), sa.ForeignKey("projects.id", ondelete="CASCADE"), primary_key=True
        ),
        sa.Column("user_id", UUID(as_uuid=True), primary_key=True),
        sa.Column("role", sa.String, nullable=False, server_default="member"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("role in ('owner', 'member')", name="project_members_role_check"),
    )

    op.create_table(
        "documents",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column(
            "project_id", UUID(as_uuid=True), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("uploaded_by", UUID(as_uuid=True), nullable=False),
        sa.Column("filename", sa.String, nullable=False),
        sa.Column("storage_path", sa.String, nullable=False),
        sa.Column("file_size", sa.BigInteger, nullable=True),
        sa.Column("status", sa.String, nullable=False, server_default="uploaded"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint(
            "status in ('uploaded', 'processing', 'ready', 'failed')", name="documents_status_check"
        ),
    )

    op.create_table(
        "document_chunks",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column(
            "document_id", UUID(as_uuid=True), sa.ForeignKey("documents.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column(
            "project_id", UUID(as_uuid=True), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("page", sa.Integer, nullable=True),
        sa.Column("chunk_index", sa.Integer, nullable=False),
        sa.Column("content", sa.Text, nullable=False),
        sa.Column("embedding", Vector(EMBEDDING_DIM), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("document_chunks_project_id_idx", "document_chunks", ["project_id"])
    op.execute(
        "CREATE INDEX document_chunks_embedding_idx ON document_chunks "
        "USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100)"
    )

    op.create_table(
        "conversations",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column(
            "project_id", UUID(as_uuid=True), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("user_id", UUID(as_uuid=True), nullable=False),
        sa.Column("title", sa.String, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )

    op.create_table(
        "messages",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column(
            "conversation_id",
            UUID(as_uuid=True),
            sa.ForeignKey("conversations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("user_id", UUID(as_uuid=True), nullable=True),
        sa.Column("role", sa.String, nullable=False),
        sa.Column("content", sa.Text, nullable=False),
        sa.Column("metadata", JSONB, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("role in ('user', 'assistant', 'system', 'tool')", name="messages_role_check"),
    )

    op.create_table(
        "email_logs",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column(
            "project_id", UUID(as_uuid=True), sa.ForeignKey("projects.id", ondelete="SET NULL"), nullable=True
        ),
        sa.Column("user_id", UUID(as_uuid=True), nullable=False),
        sa.Column("recipient", sa.String, nullable=True),
        sa.Column("subject", sa.String, nullable=True),
        sa.Column("body", sa.Text, nullable=True),
        sa.Column("status", sa.String, nullable=False, server_default="draft"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint(
            "status in ('draft', 'confirmed', 'sent', 'failed', 'cancelled')", name="email_logs_status_check"
        ),
    )

    # Project-scoped similarity search (spec2.md section 14 / 22).
    op.execute(
        """
        CREATE OR REPLACE FUNCTION match_document_chunks(
            query_embedding vector(1024),
            match_project_id uuid,
            match_count int DEFAULT 5
        )
        RETURNS TABLE (
            id uuid,
            document_id uuid,
            page integer,
            chunk_index integer,
            content text,
            similarity float
        )
        LANGUAGE sql STABLE
        AS $$
            SELECT
                document_chunks.id,
                document_chunks.document_id,
                document_chunks.page,
                document_chunks.chunk_index,
                document_chunks.content,
                1 - (document_chunks.embedding <=> query_embedding) AS similarity
            FROM document_chunks
            WHERE document_chunks.project_id = match_project_id
            ORDER BY document_chunks.embedding <=> query_embedding
            LIMIT match_count;
        $$;
        """
    )


def downgrade() -> None:
    op.execute("DROP FUNCTION IF EXISTS match_document_chunks(vector, uuid, int)")
    op.drop_table("email_logs")
    op.drop_table("messages")
    op.drop_table("conversations")
    op.execute("DROP INDEX IF EXISTS document_chunks_embedding_idx")
    op.drop_table("document_chunks")
    op.drop_table("documents")
    op.drop_table("project_members")
    op.drop_table("projects")
