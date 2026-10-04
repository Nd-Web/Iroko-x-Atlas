"""Evidence-preserving extraction. No generated text or guessed PDF page numbers."""

import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path


def normalize(text):
    text = text.replace("\r\n", "\n").replace("\r", "\n").replace("\u00a0", " ")
    return re.sub(r"\n{3,}", "\n\n", "\n".join(line.rstrip() for line in text.split("\n")))


def quality(text):
    count = len(re.sub(r"\s", "", text))
    bad = len(re.findall(r"\ufffd|\(cid:\d+\)|[\x00-\x08\x0b\x0c\x0e-\x1f]", text))
    return {"characters": count, "bad_character_ratio": bad / max(1, len(text))}


def page(raw, number=None, locator=None, method="native", **metrics):
    return {
        "page_number": number,
        "locator": locator,
        "method": method,
        "raw_text": raw,
        "text": normalize(raw),
        "quality": {**quality(raw), **metrics},
    }


def needs_ocr(item):
    q = item["quality"]
    return (
        q["characters"] < int(os.getenv("QUALITY_MIN_CHARS_PER_PAGE", "80"))
        or q["bad_character_ratio"] > float(os.getenv("QUALITY_MAX_BAD_CHAR_RATIO", "0.05"))
        or q.get("tables", False)
    )


def native_pages(path, file_type):
    if file_type == "pdf":
        import pdfplumber

        result = []
        with pdfplumber.open(path) as pdf:
            if len(pdf.pages) > int(os.getenv("DOCUMENT_MAX_PAGES", "250")):
                raise ValueError("PDF exceeds the configured page limit")
            for i, item in enumerate(pdf.pages):
                raw = item.extract_text(layout=False) or ""
                tables = bool(item.find_tables())
                result.append(page(raw, i + 1, method="pdf_text", tables=tables))
        return result
    if file_type == "docx":
        from docx import Document
        from docx.table import Table
        from docx.text.paragraph import Paragraph

        doc = Document(path)
        parts = []
        # Preserve body order: tables must stay alongside the paragraphs referring to them.
        for element in doc.element.body:
            if element.tag.endswith("}p"):
                parts.append(Paragraph(element, doc).text)
            elif element.tag.endswith("}tbl"):
                parts.extend(
                    "\t".join(c.text for c in row.cells) for row in Table(element, doc).rows
                )
        return [page("\n\n".join(parts), locator="Document body")]
    if file_type == "xlsx":
        import openpyxl

        book = openpyxl.load_workbook(path, read_only=True, data_only=True)
        if len(book.sheetnames) > 100:
            book.close()
            raise ValueError("Workbook exceeds sheet limit")
        try:
            for sheet in book.worksheets:
                if (sheet.max_row or 0) * (sheet.max_column or 0) > 250000:
                    raise ValueError("Workbook exceeds cell limit")
            return [
                page(
                    "\n".join(
                        "\t".join("" if v is None else str(v) for v in row)
                        for row in sheet.iter_rows(values_only=True)
                    ),
                    locator=sheet.title,
                )
                for sheet in book.worksheets
            ]
        finally:
            book.close()
    if file_type in {"txt", "md", "csv"}:
        return [page(Path(path).read_text(encoding="utf-8-sig", errors="replace"), locator="Text")]
    raise ValueError(f"Unsupported document format: {file_type}")


def bounded_native_pages(path, file_type, *, timeout_seconds=None, max_pages=None):
    """Timeout and memory boundary around parsers; stdout is bounded on disk."""
    with tempfile.TemporaryFile() as output, tempfile.TemporaryFile() as errors:
        result = subprocess.run(
            [sys.executable, "-m", "ingestion.extract_task", str(Path(path).resolve()), file_type],
            cwd=Path(__file__).resolve().parents[1],
            stdout=output,
            stderr=errors,
            timeout=timeout_seconds or int(os.getenv("EXTRACTION_TIMEOUT_SECONDS", "150")),
            check=False,
            env={**{
                k: v
                for k, v in os.environ.items()
                if not any(
                    secret in k.upper()
                    for secret in (
                        "KEY",
                        "SECRET",
                        "TOKEN",
                        "PASSWORD",
                        "CONNECTION",
                        "DATABASE_URL",
                    )
                )
            }, **({"DOCUMENT_MAX_PAGES": str(max_pages)} if max_pages else {})},
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        if result.returncode:
            raise ValueError("Document parser rejected the file or exceeded its resource limit")
        if output.tell() > 32 * 1024 * 1024:
            raise ValueError("Extracted content exceeds the configured output limit")
        output.seek(0)
        return json.load(output)


def ocr_pages(path, numbers):
    """Analyze only flagged PDF pages. Caller reserves the page budget first."""
    from azure.ai.documentintelligence import DocumentIntelligenceClient
    from azure.core.credentials import AzureKeyCredential

    endpoint = os.getenv("AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT")
    key = os.getenv("AZURE_DOCUMENT_INTELLIGENCE_KEY")
    if not endpoint or not key:
        raise RuntimeError("Azure Document Intelligence is not configured")
    with (
        DocumentIntelligenceClient(endpoint, AzureKeyCredential(key)) as client,
        open(path, "rb") as stream,
    ):
        result = client.begin_analyze_document(
            "prebuilt-layout",
            body=stream,
            pages=",".join(map(str, numbers)),
            output_content_format="markdown",
            string_index_type="unicodeCodePoint",
        ).result(timeout=240)
    extracted = {}
    for item in result.pages:
        # Unicode code-point indexing makes Azure offsets match Python string slicing.
        raw = "\n".join(result.content[s.offset : s.offset + s.length] for s in item.spans or [])
        confidences = [word.confidence for word in item.words or [] if word.confidence is not None]
        extracted[item.page_number] = page(
            raw,
            item.page_number,
            method="azure_layout",
            ocr_confidence=sum(confidences) / len(confidences) if confidences else None,
        )
    return extracted


def extraction_issues(pages):
    issues = []
    for item in pages:
        q = item["quality"]
        reasons = []
        # Sparse text signals a scan only on a physical PDF page. Word, sheet and
        # text records are exact; a short note or small sheet is not a failure.
        if item["page_number"] is not None and q["characters"] < int(
            os.getenv("QUALITY_MIN_CHARS_PER_PAGE", "80")
        ):
            reasons.append("little_or_no_text")
        if q["bad_character_ratio"] > float(os.getenv("QUALITY_MAX_BAD_CHAR_RATIO", "0.05")):
            reasons.append("damaged_text")
        if q.get("pending_ocr"):
            reasons.append("pending_ocr")
        if q.get("ocr_confidence") is not None and q["ocr_confidence"] < 0.85:
            reasons.append("low_ocr_confidence")
        if reasons:
            issues.append(
                {"page": item["page_number"], "locator": item["locator"], "reasons": reasons}
            )
    return issues


def regulatory_evidence(pages, provenance):
    """Conservative candidates for review, each an exact quote with source location."""
    obligations = []
    for item in pages:
        for match in re.finditer(
            r"[^\n.!?]*(?:\bshall\b|\bmust\b|\brequired to\b)[^\n.!?]*[.!?]?", item["text"], re.I
        ):
            quote = match.group().strip()
            if quote:
                start = match.start() + len(match.group()) - len(match.group().lstrip())
                obligations.append(
                    {
                        "quote": quote,
                        "page": item["page_number"],
                        "locator": item["locator"],
                        "char_start": start,
                        "char_end": start + len(quote),
                        "status": "candidate_requires_review",
                    }
                )
    return {
        "regulator": provenance.get("regulator"),
        "reference_number": provenance.get("reference_number"),
        "published_date": provenance.get("published_date"),
        "effective_date": provenance.get("effective_date"),
        "obligation_candidates": obligations[:200],
        "interpretation": "Extracted quotations; applicability and legal meaning require review.",
    }
