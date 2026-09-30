"""Disposable local Postgres cluster; never connects to a configured app database."""

import os
import socket
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import sessionmaker

from ingestion.models import Job
from ingestion.queue import claim, enqueue
from models.database import Base

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
