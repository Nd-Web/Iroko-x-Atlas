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
        choices=[
            "worker", "once", "drain", "scheduled-drain", "stats", "check", "init-local",
            "import-manifest", "import-folder",
        ],
    )
    parser.add_argument("--manifest", help="import-*: JSON list of official documents")
    parser.add_argument("--folder", help="import-folder: files saved from a browser")
    parser.add_argument("--owner", help="import-*: email of the platform admin who owns the documents")
    parser.add_argument("--archive", action="store_true",
                        help="import-manifest: use exact Internet Archive copies when a host blocks downloads")
    parser.add_argument("--max-uploads", type=int, default=0,
                        help="import-*: raise this process's daily workspace upload quota")
    parser.add_argument("--max-queue", type=int, default=0,
                        help="import-*: raise this process's limit on queued workspace documents")
    parser.add_argument("--report", default="import-report.json")
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
        if args.command in {"import-manifest", "import-folder"}:
            _import(parser, args, Session)
        elif args.command in {"drain", "scheduled-drain"}:
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


def _import(parser, args, Session):
    from ingestion import manifest
    from ingestion.db import prepare_session
    from models.database import User

    if not args.manifest or not args.owner:
        parser.error("--manifest and --owner are required")
    if args.command == "import-folder" and not args.folder:
        parser.error("--folder is required")
    manifest.backfill_limits(args.max_uploads, args.max_queue)
    entries = manifest.load_manifest(args.manifest)
    with Session() as db:
        prepare_session(db)
        owner = db.query(User).filter_by(email=args.owner).first()
        if owner is None or owner.role != "superadmin":
            parser.error("--owner must be a platform administrator's email")
        if args.command == "import-folder":
            results = asyncio.run(manifest.import_folder(db, args.folder, entries, owner.id))
        else:
            results = asyncio.run(manifest.import_entries(db, entries, owner.id, archive=args.archive))
    manifest.write_report(results, args.report)
    print(manifest.summarise(results), "->", args.report)


if __name__ == "__main__":
    main()
