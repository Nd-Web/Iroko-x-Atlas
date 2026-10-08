import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import models.filing  # noqa: F401 — registers the filing tables
from ingestion.models import PipelineBase
from models.database import Base, User


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
    session.add(User(id="cco", email="cco@example.invalid", hashed_password="not-a-password", role="analyst", full_name="Chinedu Okafor"))
    session.commit()
    yield session
    session.close()
    engine.dispose()


@pytest.fixture
def user(db):
    return db.get(User, "cco")
