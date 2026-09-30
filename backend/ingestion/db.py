"""Sessions share the application transaction and use isolated pipeline metadata."""

from sqlalchemy.orm import sessionmaker

from models.database import engine


def pipeline_bind(bind):
    if bind.dialect.name == "sqlite":
        return bind.execution_options(schema_translate_map={"ingestion": None})
    return bind


Session = sessionmaker(bind=pipeline_bind(engine), expire_on_commit=False)


def prepare_session(db):
    # Existing request sessions are synchronous and are already in a transaction.
    # SQLite has no schemas; translation is confined to local pipeline operations.
    if db.get_bind().dialect.name == "sqlite":
        db.connection().execution_options(schema_translate_map={"ingestion": None})


def source_lock(db, key):
    """Serialize source/version updates across API and worker processes."""
    if db.get_bind().dialect.name == "postgresql":
        import hashlib

        from sqlalchemy import text

        lock_id = int.from_bytes(hashlib.sha256(key.encode()).digest()[:8], "big", signed=True)
        db.execute(text("SELECT pg_advisory_xact_lock(:key)"), {"key": lock_id})
