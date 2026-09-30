"""Initial durable document pipeline, ingestion schema only."""

import sqlalchemy as sa
from alembic import op

revision = "20260930_pipeline"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    # Frozen initial definition: future model edits must require a new revision.
    op.create_table(
        "regulatory_documents",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("source_key", sa.String(), nullable=False),
        sa.Column("sha256", sa.String(64), nullable=False),
        sa.Column("previous_id", sa.String()),
        sa.Column("is_current", sa.Boolean(), nullable=False),
        sa.Column("provenance", sa.JSON(), nullable=False),
        sa.Column("extraction", sa.JSON(), nullable=False),
        sa.Column("issues", sa.JSON(), nullable=False),
        sa.Column("review_status", sa.String(), nullable=False),
        sa.Column("reviewed_by", sa.String()),
        sa.Column("reviewed_at", sa.DateTime()),
        sa.Column("review_note", sa.Text()),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("source_key", "sha256"),
        schema="ingestion",
    )
    op.create_index(
        "ix_ingestion_regulatory_documents_source_key",
        "regulatory_documents",
        ["source_key"],
        schema="ingestion",
    )
    op.create_table(
        "regulatory_document_pages",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("document_id", sa.String(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("page_number", sa.Integer()),
        sa.Column("locator", sa.String()),
        sa.Column("method", sa.String(), nullable=False),
        sa.Column("raw_text", sa.Text(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("quality", sa.JSON(), nullable=False),
        sa.UniqueConstraint("document_id", "position"),
        schema="ingestion",
    )
    op.create_index(
        "ix_ingestion_regulatory_document_pages_document_id",
        "regulatory_document_pages",
        ["document_id"],
        schema="ingestion",
    )
    op.create_table(
        "regulatory_chunks",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("document_id", sa.String(), nullable=False),
        sa.Column("chunk_index", sa.Integer(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("provenance", sa.JSON(), nullable=False),
        schema="ingestion",
    )
    op.create_index(
        "ix_ingestion_regulatory_chunks_document_id",
        "regulatory_chunks",
        ["document_id"],
        schema="ingestion",
    )
    op.create_table(
        "ingestion_jobs",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("kind", sa.String(), nullable=False),
        sa.Column("target_id", sa.String(), nullable=False),
        sa.Column("state", sa.String(), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("available_at", sa.DateTime(), nullable=False),
        sa.Column("lease_until", sa.DateTime()),
        sa.Column("lease_token", sa.String()),
        sa.Column("error", sa.Text()),
        sa.Column("updated_at", sa.DateTime()),
        schema="ingestion",
    )
    op.create_index(
        "ix_ingestion_ingestion_jobs_state", "ingestion_jobs", ["state"], schema="ingestion"
    )
    op.create_index(
        "ix_ingestion_ingestion_jobs_target_id", "ingestion_jobs", ["target_id"], schema="ingestion"
    )
    op.create_table(
        "ingestion_sources",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("regulator", sa.String(), nullable=False),
        sa.Column("url", sa.String(), nullable=False, unique=True),
        sa.Column("parser", sa.String(), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("interval_hours", sa.Integer(), nullable=False),
        sa.Column("max_documents", sa.Integer(), nullable=False),
        sa.Column("owner_id", sa.String(), nullable=False),
        sa.Column("last_run", sa.DateTime()),
        sa.Column("result", sa.JSON(), nullable=False),
        schema="ingestion",
    )
    op.create_table(
        "ingestion_ocr_budget",
        sa.Column("day", sa.String(), primary_key=True),
        sa.Column("pages", sa.Integer(), nullable=False),
        schema="ingestion",
    )
    op.create_table(
        "ingestion_crawl_runs",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("source_id", sa.String(), nullable=False),
        sa.Column("started_at", sa.DateTime(), nullable=False),
        sa.Column("finished_at", sa.DateTime()),
        sa.Column("result", sa.JSON(), nullable=False),
        schema="ingestion",
    )
    op.create_index(
        "ix_ingestion_ingestion_crawl_runs_source_id",
        "ingestion_crawl_runs",
        ["source_id"],
        schema="ingestion",
    )


def downgrade():
    raise RuntimeError("Preserved document history is not automatically deleted by downgrade")
