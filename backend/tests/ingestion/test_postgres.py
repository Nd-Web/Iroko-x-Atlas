"""Disposable local Postgres cluster; never connects to a configured app database."""

import asyncio
import os
import socket
import subprocess
import sys
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import sessionmaker

from ingestion.models import Job
from ingestion.queue import claim, enqueue
from models.database import Base, Document, User

pytestmark = pytest.mark.integration


@pytest.fixture(scope="module")
def postgres(tmp_path_factory):
    binaries = Path(os.environ.get("INGESTION_TEST_PG_BIN", "C:/Program Files/PostgreSQL/18/bin"))
    if not (binaries / "initdb.exe").exists():
        pytest.skip("Disposable Postgres binaries not available; no existing database is used")
    root = tmp_path_factory.mktemp("iroko-isolated-postgres")
    data = root / "cluster"
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    subprocess.run(
        [
            str(binaries / "initdb.exe"),
            "-D",
            str(data),
            "-U",
            "iroko_test",
            "-A",
            "trust",
            "--encoding=UTF8",
            "--no-locale",
        ],
        check=True,
        capture_output=True,
        creationflags=flags,
    )
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        port = listener.getsockname()[1]
    subprocess.run(
        [
            str(binaries / "pg_ctl.exe"),
            "-D",
            str(data),
            "-l",
            str(root / "server.log"),
            "-o",
            f"-p {port} -h 127.0.0.1 -F",
            "-w",
            "start",
        ],
        check=True,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        timeout=60,
        creationflags=flags,
    )
    url = f"postgresql://iroko_test@127.0.0.1:{port}/postgres"
    engine = create_engine(url)
    try:
        with engine.begin() as conn:
            conn.execute(text("CREATE SCHEMA unrelated"))
            conn.execute(text("CREATE TABLE unrelated.keep_me (value text)"))
            conn.execute(text("INSERT INTO unrelated.keep_me VALUES ('untouched')"))
        env = {**os.environ, "DATABASE_URL": url}
        Base.metadata.create_all(engine)
        with sessionmaker(bind=engine)() as db:
            db.add(User(id="legacy", email="legacy@example.invalid", hashed_password="unused"))
            db.flush()
            db.add(
                Document(
                    id="legacy-doc",
                    filename="policy.txt",
                    file_type="txt",
                    title="Retained policy",
                    uploaded_by_id="legacy",
                )
            )
            db.add(
                Document(
                    id="unowned-doc", filename="orphan.txt", file_type="txt", title="Quarantine me"
                )
            )
            db.add(Document(id="doc_001", filename="demo.txt", file_type="txt", title="Legacy sample", uploaded_by_id="legacy", status="indexed"))
            db.commit()
        result = subprocess.run(
            [sys.executable, "-m", "alembic", "-c", "ingestion/alembic.ini", "upgrade", "head"],
            cwd=Path(__file__).parents[2],
            env=env,
            capture_output=True,
            text=True,
            timeout=60,
            creationflags=flags,
        )
        assert result.returncode == 0, result.stderr
        Base.metadata.create_all(engine)  # Only inside the isolated test cluster.
        yield engine
    finally:
        engine.dispose()
        subprocess.run(
            [str(binaries / "pg_ctl.exe"), "-D", str(data), "-m", "fast", "-w", "stop"],
            check=True,
            capture_output=True,
            creationflags=flags,
        )


def test_migration_owns_only_ingestion(postgres):
    tables = inspect(postgres).get_table_names(schema="ingestion")
    assert "alembic_version_ingestion" in tables
    assert "regulatory_documents" in tables
    with postgres.connect() as conn:
        assert conn.execute(text("SELECT value FROM unrelated.keep_me")).scalar_one() == "untouched"


def test_demo_retirement_preserves_recovery_record(postgres):
    from ingestion.readiness import check_schema
    with postgres.connect() as conn:
        original = conn.execute(text("SELECT original_record FROM ingestion.retired_demo_documents WHERE id='doc_001'")).scalar_one()
        assert original["title"] == "Legacy sample"
        assert original["status"] == "indexed"
        assert conn.execute(text("SELECT status FROM public.documents WHERE id='doc_001'")).scalar_one() == "archived"
        assert conn.execute(text("SELECT count(*) FROM ingestion.document_access WHERE document_id='doc_001'")).scalar_one() == 0
    with sessionmaker(bind=postgres)() as db:
        check_schema(db)


def test_migration_backfills_private_ownership_without_changing_documents(postgres):
    with postgres.connect() as conn:
        records = dict(
            conn.execute(
                text("SELECT document_id, workspace_id FROM ingestion.document_access")
            ).all()
        )
        assert records["legacy-doc"] == "user:legacy"
        assert records["unowned-doc"] == "quarantine:unowned"
        assert (
            conn.execute(
                text("SELECT count(*) FROM ingestion.document_access WHERE shared_regulatory")
            ).scalar_one()
            == 0
        )
        assert (
            conn.execute(
                text("SELECT title FROM public.documents WHERE id='legacy-doc'")
            ).scalar_one()
            == "Retained policy"
        )


def test_concurrent_upload_budget_cannot_be_overspent(postgres, monkeypatch):
    from ingestion.limits import reserve_upload
    from ingestion.validation import UploadLimitError

    monkeypatch.setenv("WORKSPACE_DAILY_UPLOAD_LIMIT", "1")

    def reserve(_):
        with sessionmaker(bind=postgres)() as db:
            try:
                reserve_upload(db, "quota-race-test", 10)
                db.commit()
                return True
            except UploadLimitError:
                db.rollback()
                return False

    with ThreadPoolExecutor(max_workers=4) as pool:
        assert sum(pool.map(reserve, range(4))) == 1


def test_concurrent_workers_do_not_claim_same_job(postgres):
    sessions = sessionmaker(bind=postgres)
    with sessions() as db:
        for i in range(8):
            enqueue(db, "document", f"test-{i}")
        db.commit()

    def acquire(_):
        with sessions() as db:
            return claim(db)

    with ThreadPoolExecutor(max_workers=4) as pool:
        claimed = list(pool.map(acquire, range(8)))
    assert all(claimed)
    assert len({item[0] for item in claimed}) == 8
    with sessions() as db:
        assert db.query(Job).filter_by(state="running").count() == 8


async def test_simultaneous_uploads_do_not_block_api_event_loop(postgres, tmp_path, monkeypatch):
    from ingestion.pipeline import accept

    path = tmp_path / "concurrent.txt"
    path.write_text(
        "Each institution must maintain complete compliance records.\n" * 10, encoding="utf-8"
    )
    saving = threading.Event()
    release = threading.Event()
    calls = []

    async def preserve(path, document_id, filename):
        calls.append(document_id)
        if len(calls) == 1:
            saving.set()
            assert await asyncio.to_thread(release.wait, 5), "API loop was blocked while saving"
        return f"https://storage.invalid/{document_id}/{filename}"

    monkeypatch.setattr("ingestion.pipeline.preserve", preserve)
    sessions = sessionmaker(bind=postgres, expire_on_commit=False)

    async def upload(filename):
        with sessions() as db:
            return (await accept(db, path, filename, filename, "legacy")).id

    first = asyncio.create_task(upload("first.txt"))
    try:
        assert await asyncio.to_thread(saving.wait, 5)
        second = asyncio.create_task(upload("second.txt"))
        await asyncio.sleep(0.1)  # A blocking advisory lock would prevent this callback.
        release.set()
        ids = await asyncio.wait_for(asyncio.gather(first, second), timeout=10)
        assert len(set(ids)) == 2
    finally:
        release.set()
