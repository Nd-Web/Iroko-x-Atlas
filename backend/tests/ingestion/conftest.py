from pathlib import Path
from unittest.mock import AsyncMock

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from ingestion.models import PipelineBase
from models.database import Base, User


@pytest.fixture
def pdf_bytes():
    from io import BytesIO

    from reportlab.pdfgen.canvas import Canvas

    stream = BytesIO()
    canvas = Canvas(stream)
    canvas.showPage()
    canvas.save()
    return stream.getvalue()


@pytest.fixture
def db():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        execution_options={"schema_translate_map": {"ingestion": None}},
    )
    Base.metadata.create_all(engine)
    PipelineBase.metadata.create_all(engine)
    session = sessionmaker(bind=engine, expire_on_commit=False)()
    session.add(
        User(
            id="owner", email="test@example.invalid", hashed_password="not-a-password", role="admin"
        )
    )
    session.commit()
    yield session
    session.close()
    engine.dispose()


@pytest.fixture
def content(tmp_path):
    path = tmp_path / "policy.txt"
    path.write_text(
        "POLICY\n\n"
        + "Each institution must retain its records and maintain a complete register of compliance reviews.\n"
        * 20,
        encoding="utf-8",
    )
    return path


@pytest.fixture
def adapters(monkeypatch):
    import ingestion.pipeline as pipeline
    import services.azure_search as search
    import services.blob_storage as blob

    archive = {}

    async def preserve(path, document_id, filename):
        archive[document_id] = Path(path).read_bytes()
        return f"https://storage.invalid/{document_id}/{filename}"

    async def download(document_id, filename, path):
        Path(path).write_bytes(archive[document_id])
        return True

    monkeypatch.setattr(pipeline, "preserve", preserve)
    monkeypatch.setattr(blob, "download_document", download)
    index = AsyncMock(return_value=True)
    monkeypatch.setattr(search, "index_document_chunks", index)
    return archive, index
