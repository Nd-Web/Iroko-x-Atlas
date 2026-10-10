"""Curated library import: official downloads, exact archive copies, browser files."""
import pytest

from ingestion.manifest import import_entries, import_folder
from ingestion.models import Revision
from ingestion.sources import AccessChallenge
from models.database import Document


def entries(pdf_size):
    return [
        {"id": "sec-rules", "regulator": "SEC", "url": "https://sec.gov.ng/documents/8/Digital-Assets.pdf",
         "title": "Digital asset rules", "published_date": "2022-05-12"},
        {"id": "cbn-pep", "regulator": "CBN", "url": "https://www.cbn.gov.ng/Out/2023/FPRD/PEP%20Guidance.pdf",
         "title": "Guidance Note on PEPs", "published_date": "2023-06-23", "reference_number": "FPR/DIR/PUB/CIR/007/075",
         "catalogue_size": pdf_size},
        {"id": "cbn-ubo", "regulator": "CBN", "url": "https://www.cbn.gov.ng/Out/2023/FPRD/UBO.pdf",
         "title": "Guidance on UBOs", "published_date": "2023-01-13", "catalogue_size": pdf_size + 7},
    ]


class Official:
    def __init__(self, pdf):
        self.pdf, self.calls = pdf, []

    async def fetch(self, url):
        self.calls.append(url)
        if "cbn.gov.ng" in url:
            raise AccessChallenge("browser check")
        return 200, {}, self.pdf

    async def close(self):
        pass


class Archive:
    def __init__(self, pdf):
        self.pdf, self.calls = pdf, []

    async def capture(self, url, expected_size):
        self.calls.append(url)
        if expected_size != len(self.pdf):
            raise ValueError("No archived copy matches the catalogue byte size")
        return self.pdf, f"https://web.archive.org/web/2024id_/{url}"


async def test_official_and_exact_archive_copies_are_accepted_with_provenance(db, adapters, pdf_bytes):
    official, archive = Official(pdf_bytes), Archive(pdf_bytes)
    clients = {"SEC": official, "CBN": official}
    results = await import_entries(db, entries(len(pdf_bytes)), "owner", archive=True,
                                   clients=clients, archive_client=archive)
    by_id = {r["id"]: r for r in results}
    assert by_id["sec-rules"]["status"] == "accepted"
    assert by_id["sec-rules"]["acquisition"] == "official_download"
    assert by_id["cbn-pep"]["status"] == "accepted"
    assert by_id["cbn-pep"]["acquisition"] == "internet_archive_capture"
    # A size that differs from the regulator's catalogue is never accepted.
    assert by_id["cbn-ubo"]["status"] == "failed" and "byte size" in by_id["cbn-ubo"]["error"]
    # The challenging host is asked once per run, not once per file.
    assert sum("cbn.gov.ng" in c for c in official.calls) == 1
    provenance = db.get(Revision, by_id["cbn-pep"]["document_id"]).provenance
    assert provenance["source_url"].startswith("https://www.cbn.gov.ng/")
    assert provenance["archive_url"].startswith("https://web.archive.org/")
    assert provenance["reference_number"] == "FPR/DIR/PUB/CIR/007/075"
    assert db.get(Document, by_id["cbn-pep"]["document_id"]).title == "Guidance Note on PEPs"

    rerun = await import_entries(db, entries(len(pdf_bytes)), "owner", archive=True,
                                 clients={"SEC": Official(pdf_bytes), "CBN": Official(pdf_bytes)},
                                 archive_client=Archive(pdf_bytes))
    assert {r["id"]: r["status"] for r in rerun} == {"sec-rules": "exists", "cbn-pep": "exists", "cbn-ubo": "failed"}


async def test_blocked_files_are_reported_without_an_archive(db, adapters, pdf_bytes):
    results = await import_entries(db, entries(len(pdf_bytes))[1:], "owner",
                                   clients={"CBN": Official(pdf_bytes)})
    assert [r["status"] for r in results] == ["blocked", "blocked"]
    assert db.query(Document).count() == 0


async def test_browser_files_match_by_exact_size_and_name(db, adapters, pdf_bytes, tmp_path):
    (tmp_path / "PEP Guidance.pdf").write_bytes(pdf_bytes)
    (tmp_path / "something-else.pdf").write_bytes(pdf_bytes + b"\n% extra")
    (tmp_path / "notes.txt").write_text("ignored", encoding="utf-8")
    listed = entries(len(pdf_bytes))
    listed[2]["catalogue_size"] = len(pdf_bytes)  # Same size as PEP: the file name decides.
    results = await import_folder(db, tmp_path, listed, "owner")
    by_file = {r["file"]: r for r in results}
    assert by_file["PEP Guidance.pdf"]["status"] == "accepted"
    assert by_file["PEP Guidance.pdf"]["id"] == "cbn-pep"
    assert by_file["something-else.pdf"]["status"] == "unmatched"
    assert "notes.txt" not in by_file
    revision = db.get(Revision, by_file["PEP Guidance.pdf"]["document_id"])
    assert revision.provenance["acquisition"] == "browser_download_import"
    assert revision.provenance["size_verified_against"] == "regulator catalogue"


async def test_archive_copies_and_download_handler_links(db, adapters, pdf_bytes):
    from ingestion.manifest import load_manifest

    class Any:
        async def fetch(self, url):
            return 200, {}, pdf_bytes

        async def close(self):
            pass

    listed = [
        {"id": "law-cra", "copy": True, "publisher": "PLAC", "issuer": "National Assembly",
         "url": "https://placng.org/i/wp-content/uploads/2019/12/Credit-Reporting-Act-2017.pdf",
         "title": "Credit Reporting Act 2017", "published_date": "2017-05-30"},
        {"id": "nfiu-str", "regulator": "NFIU", "title": "2023 NFIU Guidelines on STR Filing",
         "url": "https://www.nfiu.gov.ng/AdvisoryAndGuidance?filePath=docs%5Cx&fileName=2023+NFIU+Guidelines+on+STR+Filing&handler=PreviewFile",
         "published_date": "2023-05-02"},
        {"id": "law-nta", "regulator": "NASS", "url": "https://nass.gov.ng/documents/download/11249",
         "title": "Nigeria Tax Act 2025", "published_date": "2025-06-26", "filename": "Nigeria Tax Act 2025.pdf"},
    ]
    import json
    import tempfile
    from pathlib import Path

    with tempfile.TemporaryDirectory() as d:
        path = Path(d) / "m.json"
        path.write_text(json.dumps(listed), encoding="utf-8")
        loaded = load_manifest(path)
    results = await import_entries(db, loaded, "owner", clients={"COPY": Any(), "NFIU": Any(), "NASS": Any()})
    by_id = {r["id"]: r for r in results}
    assert all(r["status"] == "accepted" for r in results), results

    copy = db.get(Revision, by_id["law-cra"]["document_id"])
    assert copy.source_key.startswith("copy:placng.org:")
    assert "regulator" not in copy.provenance and copy.provenance["official_copy"] is False
    assert copy.provenance["acquisition"] == "public_archive_copy"

    nfiu = db.get(Document, by_id["nfiu-str"]["document_id"])
    assert nfiu.filename == "2023 NFIU Guidelines on STR Filing.pdf" and nfiu.file_type == "pdf"
    assert db.get(Document, by_id["law-nta"]["document_id"]).filename == "Nigeria Tax Act 2025.pdf"


async def test_browser_files_without_catalogue_size_match_by_official_name(db, adapters, pdf_bytes, tmp_path):
    (tmp_path / "cbnact.pdf").write_bytes(pdf_bytes)
    listed = [{"id": "law-cbn-act", "regulator": "CBN", "title": "Central Bank of Nigeria Act 2007",
               "url": "https://www.cbn.gov.ng/out/publications/bsd/2007/cbnact.pdf", "published_date": "2007"}]
    results = await import_folder(db, tmp_path, listed, "owner")
    assert results[0]["status"] == "accepted" and results[0]["id"] == "law-cbn-act"
    provenance = db.get(Revision, results[0]["document_id"]).provenance
    assert provenance["matched_by"] == "official file name"
    assert "size_verified_against" not in provenance  # Nothing was checked against a catalogue size.


async def test_archive_client_returns_only_an_exact_size_capture(monkeypatch):
    import httpx

    from ingestion.manifest import ArchiveClient

    good, bad = b"%PDF-1.4 exact", b"%PDF-1.4 a different capture"

    def handler(request):
        if request.url.path == "/cdx/search/cdx":
            assert request.url.params["url"] == "www.cbn.gov.ng/Out/2023/A B.pdf"
            return httpx.Response(200, json=[["timestamp", "original"],
                                             ["2023", "https://www.cbn.gov.ng/Out/2023/A%20B.pdf"],
                                             ["2024", "https://www.cbn.gov.ng/Out/2023/A%20B.pdf"]])
        return httpx.Response(200, content=bad if "/2024id_/" in str(request.url) else good)

    client = ArchiveClient(delay=0)
    await client.client.aclose()
    client.client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    try:
        data, url = await client.capture("https://www.cbn.gov.ng/Out/2023/A%20B.pdf", len(good))
        assert data == good and "/2023id_/" in url  # The newer capture had different bytes.
        with pytest.raises(ValueError, match="byte size"):
            await client.capture("https://www.cbn.gov.ng/Out/2023/A%20B.pdf", 3)
    finally:
        await client.close()
