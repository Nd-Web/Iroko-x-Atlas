"""
services/regulatory_memory.py — Institutional Memory Layer for Iroko AI.
=========================================================================
Gives agents persistent memory of past regulatory events so that when a new
NCC change is detected, the system can surface context like:

    "A similar ruling happened in 2024. MTN paid a ₦5bn fine.
     Lesson: file QoS reports two weeks early to avoid penalties."

Architecture (inspired by ContextBridge's memory-augmentation pattern):
  - ``RegulatoryMemoryEntry`` — SQLAlchemy model stored in ``regulatory_memory`` table.
  - ``find_similar_events``   — Keyword-overlap scoring (no embeddings required).
  - ``generate_historical_context`` — Formats matched memories into an agent-injectable
                                      context string.
  - ``auto_store_from_audit_trail`` — Promotes significant audit trail entries (NO-GO
                                      verdicts, regulatory alerts, fraud flags) into
                                      long-term institutional memory automatically.

Design constraints:
  - No vector embeddings — similarity is computed via keyword overlap on words > 4 chars.
  - All public methods are ``async`` (I/O bound: DB queries + optional LLM formatting).
  - Extends ``Base`` from ``models.database`` — table is created by ``init_db()``.
  - Thread-safe singleton exported as ``regulatory_memory``.

Usage::

    from services.regulatory_memory import regulatory_memory
    from models.database import SessionLocal

    db = SessionLocal()

    # Store a new institutional memory event
    entry = await regulatory_memory.store_event(
        db,
        event_type="ncc_ruling",
        title="NCC ₦5bn QoS Fine — MTN Nigeria Q2 2024",
        description="NCC issued a ₦5bn fine to MTN for persistent QoS failures ...",
        ncc_ref="NCC-003",
        outcome="Fine paid. MTN deployed 1,200 new base stations within 90 days.",
        workspace_id="mtn-ng",
    )

    # Retrieve context for injection into an agent prompt
    context = await regulatory_memory.generate_historical_context(
        db,
        current_signal={"description": "NCC QoS threshold breach detected on Ikeja cluster."},
    )
    # → "Similar past event: NCC ₦5bn QoS Fine — MTN Nigeria Q2 2024 (2024-06-01). ..."
"""

from __future__ import annotations

import logging
import re
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import Column, DateTime, String, Text
from sqlalchemy.orm import Session

from models.database import Base, generate_id
from models.audit_trail import AuditTrailEntry

logger = logging.getLogger(__name__)

# ── Significance filter for auto-promotion from audit trail ───────────────────

_SIGNIFICANT_VERDICTS    = {"NO-GO"}
_SIGNIFICANT_ACTION_TYPES = {"regulatory_alert", "fraud_flag"}


# ── SQLAlchemy model ──────────────────────────────────────────────────────────


class RegulatoryMemoryEntry(Base):
    """
    Persistent record of a past regulatory event, fine, directive, competitor
    move, or fraud pattern — the institutional long-term memory of Iroko AI.

    Similarity matching uses keyword overlap against ``title`` + ``description``
    so no vector index is required.
    """

    __tablename__ = "regulatory_memory"

    # ── Identity ──────────────────────────────────────────────────────────────

    id: str = Column(
        String,
        primary_key=True,
        default=generate_id,
        doc="UUID primary key.",
    )

    # ── Classification ────────────────────────────────────────────────────────

    event_type: str = Column(
        String,
        nullable=False,
        index=True,
        doc=(
            "Category of the memory event: "
            "'ncc_ruling' | 'fine' | 'directive' | 'competitor_move' | 'fraud_pattern'"
        ),
    )

    # ── Content ───────────────────────────────────────────────────────────────

    title: str = Column(
        String,
        nullable=False,
        doc="Short human-readable title, e.g. 'NCC ₦5bn QoS Fine — MTN Q2 2024'.",
    )
    description: str = Column(
        Text,
        nullable=False,
        doc="Full narrative description of what happened.",
    )
    outcome: Optional[str] = Column(
        Text,
        nullable=True,
        doc="What happened as a result of this event.",
    )
    lessons_learned: Optional[str] = Column(
        Text,
        nullable=True,
        doc="Distilled lesson for future agent decision-making.",
    )

    # ── NCC reference ─────────────────────────────────────────────────────────

    ncc_regulation_ref: Optional[str] = Column(
        String,
        nullable=True,
        index=True,
        doc="NCC regulation ID this event relates to, e.g. 'NCC-003'.",
    )

    # ── Multi-tenancy & provenance ────────────────────────────────────────────

    workspace_id: Optional[str] = Column(
        String,
        nullable=True,
        index=True,
        doc="Workspace / tenant identifier.",
    )
    source_url: Optional[str] = Column(
        String,
        nullable=True,
        doc="URL of the original source that triggered this memory.",
    )

    # ── Timestamps ────────────────────────────────────────────────────────────

    event_date: Optional[datetime] = Column(
        DateTime,
        nullable=True,
        doc="When the real-world event occurred (may differ from created_at).",
    )
    created_at: datetime = Column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
        index=True,
        doc="UTC timestamp of when this memory entry was persisted.",
    )

    # ── Helpers ───────────────────────────────────────────────────────────────

    def to_dict(self) -> dict:
        """Return a JSON-serialisable representation of this entry."""
        return {
            "id":                 self.id,
            "event_type":         self.event_type,
            "title":              self.title,
            "description":        self.description,
            "outcome":            self.outcome,
            "lessons_learned":    self.lessons_learned,
            "ncc_regulation_ref": self.ncc_regulation_ref,
            "workspace_id":       self.workspace_id,
            "source_url":         self.source_url,
            "event_date":         self.event_date.isoformat() if self.event_date else None,
            "created_at":         self.created_at.isoformat() + "Z" if self.created_at else None,
        }

    def __repr__(self) -> str:
        return (
            f"<RegulatoryMemoryEntry id={self.id!r} type={self.event_type!r} "
            f"title={self.title[:40]!r}>"
        )


# ── Keyword helpers ───────────────────────────────────────────────────────────


def _extract_keywords(text: str) -> set[str]:
    """
    Extract normalised content words longer than 4 characters from ``text``.

    Strips punctuation, lowercases, and discards stop-words and short tokens
    so that overlap scoring reflects meaningful term matches.
    """
    if not text:
        return set()
    # Tokenise on any non-alphanumeric character
    tokens = re.findall(r"[a-zA-Z0-9]+", text.lower())
    # Drop trivially short tokens; a minimal stop-word filter keeps noise low
    _STOP = {
        "about", "after", "again", "against", "their", "there", "these",
        "those", "which", "while", "where", "would", "should", "could",
        "shall", "being", "since", "until", "under", "other", "every",
        "between", "because", "through", "during", "before", "without",
        "within", "although", "however", "therefore", "nigeria", "iroko",
    }
    return {t for t in tokens if len(t) > 4 and t not in _STOP}


def _overlap_score(kw_query: set[str], kw_target: set[str]) -> float:
    """
    Jaccard-like overlap score between two keyword sets.

    Returns a float in [0.0, 1.0].  Returns 0.0 if either set is empty.
    """
    if not kw_query or not kw_target:
        return 0.0
    intersection = len(kw_query & kw_target)
    union = len(kw_query | kw_target)
    return intersection / union if union > 0 else 0.0


# ── Service class ─────────────────────────────────────────────────────────────


class RegulatoryMemoryService:
    """
    Institutional memory service for Iroko AI regulatory events.

    All public methods are ``async`` for consistency with the wider async
    FastAPI / agent stack, even though the underlying DB calls are synchronous
    SQLAlchemy (wrapped in ``asyncio.to_thread`` is not needed here because
    the ORM calls are short and the event loop is not blocked meaningfully).

    Callers are responsible for opening and closing the ``db`` Session.
    """

    # ── 1. Store a new memory event ───────────────────────────────────────────

    async def store_event(
        self,
        db: Session,
        event_type: str,
        title: str,
        description: str,
        ncc_ref: Optional[str] = None,
        outcome: Optional[str] = None,
        lessons_learned: Optional[str] = None,
        workspace_id: Optional[str] = None,
        source_url: Optional[str] = None,
        event_date: Optional[datetime] = None,
    ) -> RegulatoryMemoryEntry:
        """
        Persist a new institutional memory entry.

        Parameters
        ----------
        db : Session
            Active SQLAlchemy session.
        event_type : str
            One of: ``"ncc_ruling"``, ``"fine"``, ``"directive"``,
            ``"competitor_move"``, ``"fraud_pattern"``.
        title : str
            Short descriptive title for the event.
        description : str
            Full narrative of what happened.
        ncc_ref : str, optional
            NCC regulation ID (e.g. ``"NCC-003"``).
        outcome : str, optional
            What resulted from this event.
        lessons_learned : str, optional
            Distilled lesson for future decisions.
        workspace_id : str, optional
            Tenant / workspace identifier.
        source_url : str, optional
            Originating source URL.
        event_date : datetime, optional
            When the real-world event occurred.

        Returns
        -------
        RegulatoryMemoryEntry
            The newly persisted entry.
        """
        entry = RegulatoryMemoryEntry(
            id=generate_id(),
            event_type=event_type,
            title=title,
            description=description,
            ncc_regulation_ref=ncc_ref,
            outcome=outcome,
            lessons_learned=lessons_learned,
            workspace_id=workspace_id,
            source_url=source_url,
            event_date=event_date,
            created_at=datetime.utcnow(),
        )
        db.add(entry)
        db.commit()
        db.refresh(entry)

        logger.info(
            "[RegulatoryMemory] Stored event: type=%s title=%r ncc_ref=%s",
            event_type, title[:60], ncc_ref,
        )
        return entry

    # ── 2. Find similar events via keyword overlap ────────────────────────────

    async def find_similar_events(
        self,
        db: Session,
        current_event_description: str,
        ncc_ref: Optional[str] = None,
        limit: int = 3,
    ) -> list[dict]:
        """
        Search institutional memory for events similar to the current one.

        Similarity is computed as keyword overlap (Jaccard coefficient) between
        the query description and each stored entry's ``title + description``
        corpus — no embedding model required.

        Parameters
        ----------
        db : Session
            Active SQLAlchemy session.
        current_event_description : str
            Description of the current signal or event to match against.
        ncc_ref : str, optional
            When provided, candidate entries are pre-filtered to those sharing
            the same ``ncc_regulation_ref`` before scoring — dramatically
            improving precision for regulation-specific searches.
        limit : int
            Maximum number of results to return (default 3).

        Returns
        -------
        list[dict]
            Each element has the shape::

                {
                    "event":            RegulatoryMemoryEntry,
                    "similarity_score": float,          # 0.0–1.0 Jaccard overlap
                    "lesson":           str,            # lessons_learned or outcome fallback
                }

            Sorted by ``similarity_score`` descending.  Empty list if no
            entries exist or no meaningful overlap is found.
        """
        # ── Build query keyword set ───────────────────────────────────────────
        query_kw = _extract_keywords(current_event_description)
        if not query_kw:
            logger.debug("[RegulatoryMemory] find_similar_events: empty keyword set — returning []")
            return []

        # ── Fetch candidate entries ───────────────────────────────────────────
        q = db.query(RegulatoryMemoryEntry)
        if ncc_ref:
            q = q.filter(RegulatoryMemoryEntry.ncc_regulation_ref == ncc_ref)
        candidates: list[RegulatoryMemoryEntry] = q.order_by(
            RegulatoryMemoryEntry.created_at.desc()
        ).all()

        if not candidates:
            return []

        # ── Score each candidate ──────────────────────────────────────────────
        scored: list[tuple[float, RegulatoryMemoryEntry]] = []
        for entry in candidates:
            target_text = f"{entry.title} {entry.description}"
            target_kw   = _extract_keywords(target_text)
            score       = _overlap_score(query_kw, target_kw)
            if score > 0.0:
                scored.append((score, entry))

        # Sort descending by score, take top ``limit``
        scored.sort(key=lambda t: t[0], reverse=True)
        top = scored[:limit]

        results = []
        for score, entry in top:
            lesson = (
                entry.lessons_learned
                or entry.outcome
                or "No specific lesson recorded for this event."
            )
            results.append({
                "event":            entry,
                "similarity_score": round(score, 4),
                "lesson":           lesson,
            })

        logger.info(
            "[RegulatoryMemory] find_similar_events: %d candidates, %d scored, %d returned",
            len(candidates), len(scored), len(results),
        )
        return results

    # ── 3. Generate agent-injectable historical context string ────────────────

    async def generate_historical_context(
        self,
        db: Session,
        current_signal: dict,
    ) -> str:
        """
        Produce a memory-augmented context string for injection into agent prompts.

        Calls ``find_similar_events`` and formats the top matches into a
        concise narrative paragraph that agents can prepend to their reasoning.

        Parameters
        ----------
        db : Session
            Active SQLAlchemy session.
        current_signal : dict
            A web intelligence signal dict.  The following keys are used when
            present (all optional):

            - ``"description"`` — primary text for keyword matching.
            - ``"title"``       — appended to description for richer matching.
            - ``"ncc_ref"``     — regulation reference for pre-filtering.
            - ``"workspace_id"``— currently unused but reserved for future filtering.

        Returns
        -------
        str
            A formatted multi-line context string, e.g.::

                Historical context from institutional memory:
                1. Similar past event: NCC ₦5bn QoS Fine (2024-06-01).
                   Outcome: Fine paid. MTN deployed 1,200 new base stations.
                   Lesson: File QoS reports two weeks early to avoid penalties.

            Or if nothing found::

                No similar historical events found in institutional memory.
        """
        description = " ".join(filter(None, [
            current_signal.get("title", ""),
            current_signal.get("description", ""),
        ]))
        ncc_ref: Optional[str] = current_signal.get("ncc_ref") or current_signal.get("ncc_regulation_ref")

        matches = await self.find_similar_events(
            db,
            current_event_description=description,
            ncc_ref=ncc_ref,
            limit=3,
        )

        if not matches:
            return "No similar historical events found in institutional memory."

        lines = ["Historical context from institutional memory:"]
        for i, match in enumerate(matches, start=1):
            entry: RegulatoryMemoryEntry = match["event"]
            score: float                 = match["similarity_score"]
            lesson: str                  = match["lesson"]

            # Format event_date — prefer event_date, fall back to created_at
            date_obj   = entry.event_date or entry.created_at
            date_label = date_obj.strftime("%Y-%m-%d") if date_obj else "unknown date"

            lines.append(
                f"{i}. Similar past event: {entry.title} ({date_label}) "
                f"[similarity: {score:.0%}]."
            )
            if entry.outcome:
                lines.append(f"   Outcome: {entry.outcome.strip()}")
            lines.append(f"   Lesson: {lesson.strip()}")

        context = "\n".join(lines)
        logger.debug("[RegulatoryMemory] generate_historical_context: %d matches formatted", len(matches))
        return context

    # ── 4. Auto-promote significant audit trail entries to memory ─────────────

    async def auto_store_from_audit_trail(
        self,
        db: Session,
        workspace_id: Optional[str] = None,
    ) -> list[RegulatoryMemoryEntry]:
        """
        Scan the last 24 hours of the audit trail and auto-promote significant
        entries into long-term institutional memory.

        **Significance criteria** (either condition is sufficient):

        - ``verdict == "NO-GO"`` — compliance violations are always remembered.
        - ``action_type`` in ``{"regulatory_alert", "fraud_flag"}`` — high-signal
          agent actions that agents should recall in future similar situations.

        Duplicate prevention: entries already promoted are skipped by checking
        whether a ``RegulatoryMemoryEntry`` with the same ``source_url`` and
        ``title`` already exists.

        Parameters
        ----------
        db : Session
            Active SQLAlchemy session.
        workspace_id : str, optional
            Scope to a specific tenant.

        Returns
        -------
        list[RegulatoryMemoryEntry]
            Newly created memory entries (empty list if nothing significant or
            all significant entries were already stored).
        """
        cutoff = datetime.utcnow() - timedelta(hours=24)

        # ── Fetch recent audit trail entries ──────────────────────────────────
        q = (
            db.query(AuditTrailEntry)
            .filter(AuditTrailEntry.created_at >= cutoff)
            .order_by(AuditTrailEntry.created_at.desc())
        )
        if workspace_id:
            q = q.filter(AuditTrailEntry.workspace_id == workspace_id)

        recent_entries: list[AuditTrailEntry] = q.all()

        # ── Filter to significant entries ─────────────────────────────────────
        significant = [
            e for e in recent_entries
            if (e.verdict in _SIGNIFICANT_VERDICTS)
            or (e.action_type in _SIGNIFICANT_ACTION_TYPES)
        ]

        if not significant:
            logger.info("[RegulatoryMemory] auto_store_from_audit_trail: no significant entries in last 24h")
            return []

        # ── Map audit action_type → memory event_type ─────────────────────────
        _ACTION_TO_EVENT_TYPE: dict[str, str] = {
            "regulatory_alert":  "ncc_ruling",
            "fraud_flag":        "fraud_pattern",
            "compliance_check":  "ncc_ruling",
            "competitor_signal": "competitor_move",
        }

        promoted: list[RegulatoryMemoryEntry] = []

        for audit in significant:
            title = (
                f"[Auto] {audit.action_type.replace('_', ' ').title()}: "
                f"{audit.decision_summary[:80]}"
            )

            # Deduplicate: skip if an entry with the same title already exists
            existing = (
                db.query(RegulatoryMemoryEntry)
                .filter(RegulatoryMemoryEntry.title == title)
                .first()
            )
            if existing:
                logger.debug(
                    "[RegulatoryMemory] auto_store: skipping duplicate title=%r", title[:60]
                )
                continue

            event_type = _ACTION_TO_EVENT_TYPE.get(audit.action_type, "ncc_ruling")
            outcome    = f"Verdict: {audit.verdict}" if audit.verdict else None
            lesson     = (
                f"Agent '{audit.agent_name}' flagged this as '{audit.action_type}' "
                f"with verdict '{audit.verdict}'. Review and update compliance posture accordingly."
                if audit.verdict else None
            )

            entry = await self.store_event(
                db,
                event_type=event_type,
                title=title,
                description=audit.decision_summary,
                ncc_ref=audit.ncc_regulation_ref,
                outcome=outcome,
                lessons_learned=lesson,
                workspace_id=audit.workspace_id or workspace_id,
                source_url=audit.source_url,
                event_date=audit.created_at,
            )
            promoted.append(entry)

        logger.info(
            "[RegulatoryMemory] auto_store_from_audit_trail: %d/%d entries promoted to memory",
            len(promoted), len(significant),
        )
        return promoted


# ── Module-level singleton ────────────────────────────────────────────────────

regulatory_memory = RegulatoryMemoryService()
"""
Shared ``RegulatoryMemoryService`` singleton.

Import and use directly in agents and API routes::

    from services.regulatory_memory import regulatory_memory
    from models.database import SessionLocal

    db = SessionLocal()

    context = await regulatory_memory.generate_historical_context(
        db,
        current_signal={"description": "NCC QoS directive on dropped call rates."},
    )
    # Inject ``context`` into the agent's system prompt before reasoning.
"""
