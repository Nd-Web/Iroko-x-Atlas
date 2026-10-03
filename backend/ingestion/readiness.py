"""Database-only preflight. Does not send model requests or modify stored evidence."""

from sqlalchemy import select, text

from ingestion.models import PipelineBase


def check_api_schema(db, pipeline_enabled):
    # Audit/workspace hooks are installed by imported API routes even when
    # document processing is disabled. Postgres auth therefore needs this schema.
    if pipeline_enabled or db.get_bind().dialect.name == "postgresql":
        check_schema(db)


def check_schema(db):
    try:
        for table in PipelineBase.metadata.sorted_tables:
            db.execute(select(table).limit(0))
        if db.get_bind().dialect.name == "postgresql":
            revision = db.execute(
                text("SELECT version_num FROM ingestion.alembic_version_ingestion")
            ).scalar_one()
            if revision != "20261003_retire_demo":
                raise RuntimeError("Unexpected ingestion migration version")
    except Exception as exc:
        db.rollback()
        raise RuntimeError(
            "Document schema is not ready. Run: python -m alembic -c ingestion/alembic.ini upgrade head"
        ) from exc
