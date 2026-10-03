import json
from datetime import datetime, timedelta
from unittest.mock import AsyncMock

import pytest
from pydantic import ValidationError

from ingestion.api import SourceRequest
from ingestion.models import Job, Source
from ingestion.sources import collect
from ingestion.worker import schedule
from models.database import Document


def test_source_request_defaults_to_twenty_manual_documents():
    request = SourceRequest(
        regulator="CBN", url="https://www.cbn.gov.ng/api/GetOFISCirculars", parser="cbn_json"
    )
    assert request.max_documents == 20
    assert request.interval_hours == 0
    assert not request.enabled
    with pytest.raises(ValidationError):
        SourceRequest(**{**request.model_dump(), "interval_hours": 1})


async def test_initial_collection_is_bounded_and_does_not_repeat(
    db, adapters, monkeypatch, pdf_bytes
):
    catalog = json.dumps(
        [
            {
                "title": f"Circular {i}",
                "link": f"/Out/{i}.pdf",
                "refNo": f"CBN/TEST/{i}",
                "documentDate": "30/09/2026",
            }
            for i in range(25)
        ]
    ).encode()
    downloads = []

    class Client:
        def __init__(self, regulator):
            pass

        async def fetch(self, url):
            if "/api/" in url:
                return 200, {}, catalog
            downloads.append(url)
            return 200, {}, pdf_bytes

        async def close(self):
            pass

    monkeypatch.setattr("ingestion.sources.OfficialClient", Client)
    monkeypatch.setattr(
        "ingestion.sources.preserve", AsyncMock(return_value="https://storage.invalid/snapshot")
    )
    source = Source(
        id="initial",
        regulator="CBN",
        parser="cbn_json",
        enabled=True,
        url="https://www.cbn.gov.ng/api/GetOFISCirculars",
        owner_id="owner",
    )
    db.add(source)
    db.commit()
    assert source.max_documents == 20
    assert source.interval_hours == 0
    schedule(db)
    assert db.query(Job).count() == 0
    await collect(db, source.id)
    assert len(downloads) == 20
    assert db.query(Document).count() == 20
    assert source.result["accepted"] == 20
    source.last_run = datetime.utcnow() - timedelta(days=60)
    db.commit()
    schedule(db)
    assert db.query(Job).filter_by(kind="source").count() == 0
    # Recurrence still works when explicitly configured.
    source.interval_hours = 24
    db.commit()
    schedule(db)
    assert db.query(Job).filter_by(kind="source").count() == 1
