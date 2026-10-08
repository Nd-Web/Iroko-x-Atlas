"""Answer "what documents do you have?" from the permitted library, without a model.

Titles, regulators and dates come straight from the database under the caller's
document permissions, so this answer cannot invent a source. Only documents with a
current extracted revision are listed: those are the ones chat can actually cite.
"""

from __future__ import annotations

import re
from datetime import date

MAX_LISTED = 30
_STOPWORDS = {
    "a", "an", "the", "and", "or", "of", "to", "in", "on", "for", "about", "with", "any", "all",
    "our", "my", "your", "their", "that", "this", "these", "those", "is", "are", "be", "by",
    "document", "documents", "file", "files", "circular", "circulars", "letter", "letters",
}


def topic_terms(topic: str | None) -> list[str]:
    words = re.findall(r"[^\W_][\w/-]*", topic or "")
    return list(dict.fromkeys(w.lower() for w in words if w.lower() not in _STOPWORDS and len(w) > 1))[:6]


def _published(provenance: dict) -> date | None:
    for key in ("published_date", "document_date", "catalogue_published_date"):
        value = provenance.get(key)
        if isinstance(value, str):
            try:
                return date.fromisoformat(value[:10])
            except ValueError:
                continue
    return None


def _matches(db, documents, terms) -> set[str]:
    """Documents whose title, reference or extracted text contains every topic term."""
    from ingestion.models import Page

    matched = set()
    for doc_id, (title, reference) in documents.items():
        text = f"{title} {reference}".lower()
        if all(term in text for term in terms):
            matched.add(doc_id)
    remaining = set(documents) - matched
    if remaining:
        candidates = remaining
        for term in terms:
            rows = db.query(Page.document_id).filter(
                Page.document_id.in_(candidates), Page.text.ilike(f"%{term}%")
            ).distinct()
            candidates = {row[0] for row in rows}
            if not candidates:
                break
        matched |= candidates
    return matched


def list_documents(topic: str | None = None) -> list[dict]:
    """Permitted, indexed documents with a current revision, newest first."""
    from ingestion.access import document_predicate
    from ingestion.db import Session
    from ingestion.models import Revision
    from models.database import Document

    with Session() as db:
        # Two queries, not a join: the permission predicate has its own Revision
        # subquery, which a joined Revision would wrongly correlate with.
        documents = db.query(Document).filter(document_predicate(db), Document.status == "indexed").all()
        revisions = {
            r.id: r for r in db.query(Revision).filter(
                Revision.id.in_([d.id for d in documents]), Revision.is_current.is_(True))
        }
        entries = {}
        for document in documents:
            revision = revisions.get(document.id)
            if revision is None:
                continue  # Legacy records without an extracted revision are never cited.
            provenance = revision.provenance or {}
            entries[document.id] = {
                "document_id": document.id,
                "title": " ".join((document.title or provenance.get("title") or "Untitled document").split()),
                "regulator": provenance.get("regulator"),
                "reference": provenance.get("reference_number") or "",
                "published": _published(provenance),
            }
        terms = topic_terms(topic)
        if terms:
            keep = _matches(db, {k: (v["title"], v["reference"]) for k, v in entries.items()}, terms)
            entries = {k: v for k, v in entries.items() if k in keep}
    return sorted(entries.values(), key=lambda e: (e["published"] or date.min, e["title"]), reverse=True)


def _line(entry: dict) -> str:
    published = entry["published"]
    # Built by hand because strftime's "%-d" (no leading zero) is not portable to Windows.
    details = [f"{published.day} {published.strftime('%B %Y')}"] if published else []
    if entry["reference"]:
        details.append(entry["reference"])
    return f"- {entry['title']}" + (f" ({'; '.join(details)})" if details else "")


def catalog_answer(topic: str | None = None) -> dict:
    entries = list_documents(topic)
    terms = topic_terms(topic)
    label = " ".join((topic or "").split())[:80]
    if not entries:
        if terms:
            answer = (f"None of the documents you can access mention “{label}” in their title or extracted text. "
                      "Try another keyword, or ask your question directly and I'll search the passages.")
        else:
            answer = ("You don't have any processed documents yet. Upload a document or import regulatory "
                      "sources on the Documents page, and I'll answer from them once they're processed.")
        return {"answer": answer, "citations": [], "confidence": "high", "_grounded": True,
                "answer_status": "answered", "suggested_followups": [], "catalog": []}
    count = len(entries)
    noun = "document" if count == 1 else "documents"
    verb = "mentions" if count == 1 else "mention"
    heading = (f"{count} {noun} you can access {verb} “{label}”:" if terms
               else f"You can access {count} processed {noun}:")
    groups: dict[str, list[dict]] = {}
    for entry in entries[:MAX_LISTED]:
        groups.setdefault(entry["regulator"] or "Your uploads", []).append(entry)
    lines = [heading]
    for group, members in groups.items():
        lines.append(f"\n**{group}**\n")
        lines.extend(_line(entry) for entry in members)
    if count > MAX_LISTED:
        lines.append(f"\n…and {count - MAX_LISTED} more. Name a topic to narrow the list, "
                     "for example “which documents mention BVN?”.")
    lines.append("\nAsk about any of them by title, and I'll answer with cited passages.")
    # Distinct titles only: two gazettes can share a name and differ only by date.
    titles = list(dict.fromkeys(entry["title"] for entry in entries))[:3]
    followups = [f"What are the key points in “{title}”?" for title in titles]
    return {
        "answer": "\n".join(lines),
        "citations": [],
        "confidence": "high",
        "_grounded": True,
        "answer_status": "answered",
        "suggested_followups": followups,
        "catalog": [{"document_id": e["document_id"], "title": e["title"]} for e in entries[:MAX_LISTED]],
    }
