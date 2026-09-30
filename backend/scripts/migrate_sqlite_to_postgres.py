"""One-time, fail-closed migration of the legacy application database.

Run from backend/ with MIGRATION_TARGET_DATABASE_URL set to the external
PostgreSQL URL. The target must have no public tables. This intentionally does
not run the separate ingestion Alembic migration.
"""

from __future__ import annotations

import argparse
import sqlite3
from pathlib import Path
from urllib.parse import urlsplit

from sqlalchemy import MetaData, Table, create_engine, inspect, select, text


def _application_metadata():
    from models.database import Base
    import models.pilot_request  # noqa: F401
    import models.network_models  # noqa: F401
    import models.audit_trail  # noqa: F401
    from services.regulatory_memory import RegulatoryMemoryEntry  # noqa: F401
    import models.signal_node  # noqa: F401
    import models.workflow  # noqa: F401

    return Base.metadata


def _source_checks(path: Path) -> tuple[list[str], dict[str, int]]:
    if not path.is_file():
        raise RuntimeError(f"Source SQLite file does not exist: {path}")
    connection = sqlite3.connect(f"file:{path.as_posix()}?mode=ro", uri=True)
    try:
        integrity = connection.execute("PRAGMA integrity_check").fetchone()[0]
        if integrity != "ok":
            raise RuntimeError(f"Source integrity check failed: {integrity}")
        violations = connection.execute("PRAGMA foreign_key_check").fetchall()
        if violations:
            raise RuntimeError(f"Source has {len(violations)} foreign-key violations")
        names = sorted(
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table' "
                "AND name NOT LIKE 'sqlite_%'"
            )
        )
        counts = {
            name: connection.execute(
                f'SELECT COUNT(*) FROM "{name.replace(chr(34), chr(34) * 2)}"'
            ).fetchone()[0]
            for name in names
        }
        return names, counts
    finally:
        connection.close()


def _target_url() -> str:
    import os

    url = os.environ.get("MIGRATION_TARGET_DATABASE_URL", "")
    if not url:
        raise RuntimeError("Set MIGRATION_TARGET_DATABASE_URL in the process environment")
    parsed = urlsplit(url)
    if parsed.scheme not in {"postgresql", "postgresql+psycopg2"}:
        raise RuntimeError("Target must be PostgreSQL")
    if not parsed.hostname:
        raise RuntimeError("Target hostname is missing")
    return url


def migrate(path: Path, *, dry_run: bool) -> None:
    names, source_counts = _source_checks(path)
    app_metadata = _application_metadata()
    unknown = sorted(set(names) - set(app_metadata.tables))
    if unknown:
        raise RuntimeError(f"Source has tables outside application metadata: {unknown}")

    source = create_engine(f"sqlite:///{path.as_posix()}")
    target = create_engine(_target_url(), connect_args={"connect_timeout": 15})
    try:
        with target.connect() as connection:
            existing = inspect(connection).get_table_names(schema="public")
            if existing:
                raise RuntimeError(
                    "Target public schema is not empty; refusing to merge or overwrite: "
                    + ", ".join(sorted(existing))
                )
        print(f"Source: {len(names)} tables, {sum(source_counts.values())} rows")
        for name in names:
            print(f"  {name}: {source_counts[name]}")
        if dry_run:
            print("Dry run passed; target is empty. No data was written.")
            return

        # PostgreSQL DDL and inserts share one transaction. A failed transfer
        # therefore leaves the target public schema empty for a safe retry.
        with source.connect() as source_conn, target.begin() as target_conn:
            app_metadata.create_all(bind=target_conn)
            # These columns are added by the legacy app's init_db(), not by its
            # model metadata. Preserve them if present in the SQLite source.
            legacy_columns = (
                ("documents", "source_connector_id", "VARCHAR REFERENCES connectors(id)"),
                ("documents", "source_item_id", "VARCHAR"),
                ("connectors", "last_sync_at", "TIMESTAMP"),
                ("pilot_requests", "calendar_event_id", "VARCHAR(255)"),
                ("pilot_requests", "calendar_event_link", "TEXT"),
            )
            for table_name, column_name, column_type in legacy_columns:
                columns = {c["name"] for c in inspect(target_conn).get_columns(table_name)}
                if column_name not in columns:
                    target_conn.execute(
                        text(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_type}")
                    )

            target_metadata = MetaData()
            copied: dict[str, int] = {}
            for model_table in app_metadata.sorted_tables:
                name = model_table.name
                if name not in source_counts:
                    continue
                source_table = Table(name, MetaData(), autoload_with=source_conn)
                target_table = Table(name, target_metadata, autoload_with=target_conn)
                target_columns = set(target_table.columns.keys())
                missing = set(source_table.columns.keys()) - target_columns
                if missing:
                    raise RuntimeError(f"{name}: missing target columns {sorted(missing)}")
                rows = source_conn.execute(select(source_table)).mappings()
                copied[name] = 0
                batch: list[dict] = []
                for row in rows:
                    batch.append(dict(row))
                    if len(batch) == 250:
                        target_conn.execute(target_table.insert(), batch)
                        copied[name] += len(batch)
                        batch.clear()
                if batch:
                    target_conn.execute(target_table.insert(), batch)
                    copied[name] += len(batch)
                actual = target_conn.execute(
                    select(text("count(*)")).select_from(target_table)
                ).scalar_one()
                if actual != source_counts[name] or copied[name] != actual:
                    raise RuntimeError(f"{name}: row count verification failed")
            missing_tables = set(names) - set(copied)
            if missing_tables:
                raise RuntimeError(f"Tables were not copied: {sorted(missing_tables)}")
            print(f"Verified {len(copied)} tables and {sum(copied.values())} rows; committing.")
        print("Application migration committed successfully.")
    finally:
        source.dispose()
        target.dispose()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path, help="Path to a backed-up SQLite file")
    parser.add_argument("--execute", action="store_true", help="Commit to an empty target")
    args = parser.parse_args()
    migrate(args.source.resolve(), dry_run=not args.execute)
