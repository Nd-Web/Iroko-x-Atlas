"""Explicit migrations own ingestion only; never import application metadata."""

from alembic import context
from sqlalchemy import create_engine, text

from ingestion.migrations.ownership import include_name, include_object
from ingestion.models import PipelineBase


def run():
    from dotenv import load_dotenv

    load_dotenv()
    from models.database import DATABASE_URL

    engine = create_engine(DATABASE_URL)
    if engine.dialect.name != "postgresql":
        raise RuntimeError(
            "Production ingestion migrations require the application's PostgreSQL DATABASE_URL"
        )
    with engine.begin() as connection:
        if connection.dialect.default_schema_name == "ingestion":
            raise RuntimeError("Use a migration connection whose default schema is not ingestion")
        connection.execute(text("CREATE SCHEMA IF NOT EXISTS ingestion"))
        context.configure(
            connection=connection,
            target_metadata=PipelineBase.metadata,
            version_table="alembic_version_ingestion",
            version_table_schema="ingestion",
            include_schemas=True,
            include_object=include_object,
            include_name=include_name,
        )
        with context.begin_transaction():
            context.run_migrations()


run()
