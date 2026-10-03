import argparse
import asyncio
import logging
import os

from dotenv import load_dotenv


def main():
    load_dotenv()
    parser = argparse.ArgumentParser(description="Iroko document pipeline")
    parser.add_argument(
        "command",
        choices=["worker", "once", "drain", "scheduled-drain", "stats", "check", "init-local"],
    )
    parser.add_argument(
        "--max-seconds", type=int, default=int(os.getenv("INGESTION_BATCH_MAX_SECONDS", "5400"))
    )
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO)
    from ingestion.db import Session, pipeline_bind
    from ingestion.models import Job, PipelineBase
    from models.database import engine

    if args.command == "init-local":
        if engine.dialect.name != "sqlite":
            parser.error("init-local is SQLite-only; use ingestion/alembic.ini for Postgres")
        PipelineBase.metadata.create_all(pipeline_bind(engine))
    elif args.command == "check":
        from ingestion.readiness import check_schema

        with Session() as db:
            check_schema(db)
        print("Document schema ready")
    elif args.command == "stats":
        from sqlalchemy import func

        with Session() as db:
            for state, count in db.query(Job.state, func.count()).group_by(Job.state):
                print(f"{state}: {count}")
    else:
        from ingestion.queue import enabled

        if not enabled():
            parser.error("Set DOCUMENT_PIPELINE_ENABLED=true after the ingestion migration")
        from ingestion.readiness import check_schema

        with Session() as db:
            check_schema(db)
        if args.command in {"drain", "scheduled-drain"}:
            from ingestion.batch import BatchIncomplete, drain

            try:
                asyncio.run(
                    drain(
                        max_seconds=args.max_seconds, allow_idle=args.command == "scheduled-drain"
                    )
                )
            except BatchIncomplete as exc:
                logging.error("Manual ingestion batch failed: %s", exc)
                raise SystemExit(1) from exc
        else:
            from ingestion.worker import run, run_once

            asyncio.run(run() if args.command == "worker" else run_once())


if __name__ == "__main__":
    main()
