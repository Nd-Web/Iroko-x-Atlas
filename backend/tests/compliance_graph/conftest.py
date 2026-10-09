"""Isolated in-memory SQLite; every model call is a deterministic fake."""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import models.compliance_graph  # noqa: F401  (registers the cg_* tables)
import models.filing  # noqa: F401
import models.workflow  # noqa: F401
from ingestion.models import PipelineBase
from models.database import Base


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
    yield session
    session.close()
    engine.dispose()


@pytest.fixture(autouse=True)
def graph_env(monkeypatch):
    monkeypatch.setenv("COMPLIANCE_GRAPH_ENABLED", "true")
    monkeypatch.setenv("GRAPH_TOKENS_PER_MINUTE", "0")
    for name in ("AZURE_OPENAI_RESPONSES_ENDPOINT", "AZURE_OPENAI_RESPONSES_API_KEY"):
        monkeypatch.delenv(name, raising=False)
