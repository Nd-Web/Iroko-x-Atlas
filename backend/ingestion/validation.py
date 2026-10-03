"""Bounded input validation shared by uploads, connectors and regulator imports."""

import os
import zipfile
from pathlib import Path, PurePosixPath


class UploadLimitError(ValueError):
    pass


def validate_file(path, filename):
    path = Path(path)
    size = path.stat().st_size
    maximum = int(os.getenv("DOCUMENT_MAX_BYTES", str(50 * 1024 * 1024)))
    if not size or size > maximum:
        raise UploadLimitError("Document is empty or exceeds the configured size limit")
    ext = filename.rsplit(".", 1)[-1].lower()
    with path.open("rb") as stream:
        head = stream.read(1024)
    if ext == "pdf":
        if not head.startswith(b"%PDF-"):
            raise ValueError("Expected a PDF file, not a renamed file or HTML page")
        with path.open("rb") as stream:
            stream.seek(max(0, size - 65536))
            if b"%%EOF" not in stream.read():
                raise ValueError("PDF is incomplete or malformed")
    elif ext in {"docx", "xlsx"}:
        if not zipfile.is_zipfile(path):
            raise ValueError("Expected an Office Open XML document")
        with zipfile.ZipFile(path) as archive:
            members = archive.infolist()
            if len(members) > 2000 or sum(i.file_size for i in members) > 100 * 1024 * 1024:
                raise UploadLimitError("Office archive exceeds expansion limits")
            names = {i.filename for i in members}
            required = "word/document.xml" if ext == "docx" else "xl/workbook.xml"
            if required not in names or "[Content_Types].xml" not in names:
                raise ValueError("Office document contents do not match its extension")
            for item in members:
                name = item.filename.replace("\\", "/")
                if PurePosixPath(name).is_absolute() or ".." in PurePosixPath(name).parts:
                    raise ValueError("Unsafe Office archive member")
                if item.flag_bits & 1:
                    raise ValueError("Encrypted Office documents are not supported")
                if (
                    item.file_size > 32 * 1024 * 1024
                    or item.file_size > max(1, item.compress_size) * 200
                ):
                    raise UploadLimitError("Office archive member exceeds expansion limits")
                if "vbaproject" in name.lower() or "/embeddings/" in name.lower():
                    raise ValueError("Macros and embedded binary objects are not supported")
                if name.endswith((".xml", ".rels")):
                    body = archive.read(item).replace(b"\x00", b"").upper()
                    if b"<!DOCTYPE" in body or b"<!ENTITY" in body or b"MACROENABLED" in body:
                        raise ValueError("Unsafe XML or macros in Office document")
    elif ext in {"txt", "md", "csv"}:
        try:
            text = path.read_text(encoding="utf-8-sig")
        except UnicodeError as exc:
            raise ValueError("Text documents must use UTF-8 encoding") from exc
        if "\x00" in text or not text.strip():
            raise ValueError("Expected nonempty text, not binary data")
    else:
        raise ValueError("Unsupported document format")
    return size
