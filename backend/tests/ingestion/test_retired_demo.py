"""Legacy sample identities are quarantined without hiding real source records."""

from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from ingestion.access import allowed_document_ids
from ingestion.models import Revision
from models.database import Document, User


@pytest.mark.parametrize("dialect,enabled,expected", [("postgresql", False, True), ("sqlite", True, True), ("sqlite", False, False)])
def test_auth_schema_preflight_is_not_skipped_when_processing_is_disabled(monkeypatch, dialect, enabled, expected):
    from ingestion import readiness
    check = Mock()
    monkeypatch.setattr(readiness, "check_schema", check)
    session = SimpleNamespace(get_bind=lambda: SimpleNamespace(dialect=SimpleNamespace(name=dialect)))
    readiness.check_api_schema(session, enabled)
    assert check.called is expected


def test_only_unproven_legacy_samples_are_hidden(db):
    for doc_id in ["doc_001", "doc_002", "doc_003", "real-upload"]:
        db.add(
            Document(
                id=doc_id,
                filename="document.txt",
                file_type="txt",
                title="Test record",
                uploaded_by_id="owner",
                status="indexed",
                blob_url="https://storage.invalid/original" if doc_id == "doc_003" else None,
            )
        )
    db.add(Revision(id="doc_002", source_key="real-source", sha256="a" * 64, is_current=True))
    db.commit()
    ids = allowed_document_ids(db, user=db.get(User, "owner"))
    assert "doc_001" not in ids
    assert {"doc_002", "doc_003", "real-upload"} <= ids
