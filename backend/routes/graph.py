"""
Graph Route — LIVE knowledge graph built from real data.

Replaces the previously hardcoded frontend graph. Nodes and edges are
derived from the actual corpus and operational state:

  - Document rows (indexed)                → document nodes
  - Entities extracted at ingestion        → entity nodes + "mentions" edges
    (with a title/tags fallback for documents ingested before extraction)
  - VendorContract rows                    → contract nodes + vendor edges
  - Active Alert rows                      → alert nodes + document edges
  - Active WorkflowTask rows               → task nodes + alert edges

No data here is invented: an empty corpus returns an empty graph.
"""
import logging
from typing import Any, Optional

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from models.database import get_db, User, Document, Alert
from models.workflow import WorkflowTask, TaskStatus
from services.auth_utils import get_current_user
from services.entity_extraction import extract_entities, entity_id

router = APIRouter(prefix="/api/graph", tags=["Knowledge Graph"])
logger = logging.getLogger(__name__)

_MAX_DOCS = 60
_MAX_ENTITY_EDGES_PER_DOC = 8


@router.get("")
async def get_knowledge_graph(
    department: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Return {nodes, edges, stats} for the live knowledge graph."""
    nodes: dict[str, dict[str, Any]] = {}
    edges: list[dict[str, Any]] = []

    def add_node(nid: str, label: str, ntype: str, meta: Optional[dict] = None):
        if nid not in nodes:
            nodes[nid] = {"id": nid, "label": label, "type": ntype, "meta": meta or {}}

    def add_edge(src: str, dst: str, label: str):
        if src in nodes and dst in nodes:
            edges.append({"from": src, "to": dst, "label": label})

    # ── 1. Documents + entities ───────────────────────────────────────────
    q = db.query(Document).filter(Document.status == "indexed")
    if department:
        q = q.filter(Document.department == department)
    documents = q.order_by(Document.created_at.desc()).limit(_MAX_DOCS).all()

    for doc in documents:
        add_node(
            doc.id,
            doc.title,
            "document",
            {"department": doc.department, "file_type": doc.file_type,
             "created_at": doc.created_at.isoformat() if doc.created_at else None},
        )

        entities = (doc.extra_metadata or {}).get("entities") or []
        if not entities:
            # Backfill: documents ingested before extraction existed —
            # extract from title + tags so the graph is live immediately.
            tag_text = " ".join(doc.tags or []) if isinstance(doc.tags, list) else ""
            entities = extract_entities(f"{doc.title} {tag_text} {doc.department or ''}")

        for ent in entities[:_MAX_ENTITY_EDGES_PER_DOC]:
            eid = entity_id(ent["name"])
            add_node(eid, ent["name"], ent["type"], {"mentions": ent.get("mentions", 1)})
            add_edge(doc.id, eid, "mentions")

    # ── 2. Vendor contracts (real network-ops data when present) ─────────
    try:
        from models.network_models import VendorContract
        contracts = db.query(VendorContract).limit(40).all()
        for c in contracts:
            cid = f"contract_{c.id}"
            label = getattr(c, "contract_name", None) or f"{getattr(c, 'vendor_name', 'Vendor')} contract"
            add_node(cid, label, "contract", {
                "vendor": getattr(c, "vendor_name", None),
                "expiry": str(getattr(c, "expiry_date", "") or ""),
            })
            vendor_name = getattr(c, "vendor_name", None)
            if vendor_name:
                vid = entity_id(vendor_name)
                add_node(vid, vendor_name, "vendor", {})
                add_edge(cid, vid, "with vendor")
    except Exception as exc:
        logger.debug(f"Vendor contracts unavailable for graph: {exc}")

    # ── 3. Active alerts ──────────────────────────────────────────────────
    alerts = (
        db.query(Alert)
        .filter(Alert.status.in_(["new", "acknowledged"]))
        .order_by(Alert.created_at.desc())
        .limit(30)
        .all()
    )
    for a in alerts:
        aid = f"alert_{a.id}"
        add_node(aid, a.title, "alert", {"severity": a.severity, "alert_type": a.alert_type})
        for did in (a.related_document_ids or []):
            add_edge(aid, did, "raised from")
        # Link alerts to entities mentioned in their titles/summaries
        for ent in extract_entities(f"{a.title} {a.summary or ''}")[:4]:
            eid = entity_id(ent["name"])
            add_node(eid, ent["name"], ent["type"], {})
            add_edge(aid, eid, "concerns")

    # ── 4. Active workflow tasks (document → insight → ACTION) ───────────
    tasks = (
        db.query(WorkflowTask)
        .filter(WorkflowTask.status.in_([TaskStatus.open, TaskStatus.in_progress]))
        .order_by(WorkflowTask.created_at.desc())
        .limit(30)
        .all()
    )
    for t in tasks:
        tid = f"task_{t.id}"
        add_node(tid, t.title, "task", {
            "priority": t.priority, "department": t.department, "status": t.status,
        })
        if t.source_id:
            add_edge(tid, f"alert_{t.source_id}", "actions")
        for did in (t.related_document_ids or []):
            add_edge(tid, did, "references")

    type_counts: dict[str, int] = {}
    for n in nodes.values():
        type_counts[n["type"]] = type_counts.get(n["type"], 0) + 1

    return {
        "nodes": list(nodes.values()),
        "edges": edges,
        "stats": {
            "node_count": len(nodes),
            "edge_count": len(edges),
            "by_type": type_counts,
            "documents_scanned": len(documents),
        },
    }
