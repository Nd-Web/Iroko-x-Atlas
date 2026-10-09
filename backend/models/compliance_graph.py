"""
models/compliance_graph.py

The compliance knowledge graph: requirements found in regulations, how
instruments relate to each other, and each workspace's own controls, evidence
and decisions.

Rules the tables are designed around:
  * Visibility is never decided by these tables alone. Every read goes through
    services/compliance_graph/visibility.py, which joins back to the
    permission-checked documents.
  * Nothing here stores a compliance verdict. Applicability and coverage are
    computed when asked; only explicit human decisions are stored.
  * Every relationship keeps how it was established (basis: stated | suggested
    | manual) separately from what a reviewer decided (review_status).
  * Requirements keep a stable lineage_id across document versions, so links,
    owners and decisions survive a new version of a circular or policy.

New tables only: init_db's create_all adds them on startup.
"""

from datetime import datetime

from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    Date,
    DateTime,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)

from models.database import Base, generate_id


class GraphDocument(Base):
    """One row per document that takes part in the graph."""

    __tablename__ = "cg_documents"

    document_id = Column(String, primary_key=True)  # Document.id == Revision.id
    workspace_id = Column(String, index=True)  # owning workspace when extracted
    role = Column(String, nullable=False, default="other")
    # regulation | policy | procedure | evidence_record | other
    role_basis = Column(String, nullable=False, default="suggested")
    # uploader | stated | suggested | confirmed
    role_suggestion = Column(String)  # Iroko's content-based view when it disagrees
    regulator = Column(String, index=True)
    reference_number = Column(String, index=True)  # normalised
    title = Column(String)
    published_date = Column(Date)
    effective_date = Column(Date)
    effective_basis = Column(String)  # stated | suggested | confirmed
    effective_anchor = Column(JSON)
    lineage_key = Column(String, index=True)  # Revision.source_key
    previous_document_id = Column(String)
    # Role-specific facts read from the document: letter date, own reference,
    # what an evidence record shows and the period it covers.
    facts = Column(JSON, nullable=False, default=dict)
    extraction_status = Column(String, nullable=False, default="pending")
    # pending | running | deferred | done | failed | retired
    stage_state = Column(JSON, nullable=False, default=dict)
    prompt_version = Column(String)
    rerun_requested = Column(Boolean, nullable=False, default=False)
    error = Column(Text)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class Obligation(Base):
    """A requirement stated in a regulation, anchored to its exact words."""

    __tablename__ = "cg_obligations"

    id = Column(String, primary_key=True)  # hash(document, normalised quote, occurrence)
    lineage_id = Column(String, nullable=False, index=True)  # stable across versions
    document_id = Column(String, nullable=False, index=True)
    occurrence = Column(Integer, nullable=False, default=0)
    position = Column(Integer, nullable=False, default=0)  # reading order in the document
    quote = Column(Text, nullable=False)
    page_number = Column(Integer)
    page_position = Column(Integer)  # Page.position
    locator = Column(String)
    page_char_start = Column(Integer)
    page_char_end = Column(Integer)
    chunk_id = Column(String, index=True)
    section_heading = Column(String)
    summary = Column(Text)  # Iroko's plain-English summary; always labelled as such
    kind = Column(String, nullable=False, default="obligation")
    # obligation | prohibition | expectation
    addressee_span = Column(Text)
    addressee_codes = Column(JSON, nullable=False, default=list)
    addressee_basis = Column(String)  # stated | suggested | inherited | None
    deadline_span = Column(Text)
    deadline_rule = Column(JSON)
    frequency = Column(String)
    effective_span = Column(Text)
    effective_date = Column(Date)
    topics = Column(JSON, nullable=False, default=list)
    text_hash = Column(String, nullable=False, index=True)
    status = Column(String, nullable=False, default="active")  # active | withdrawn
    review_status = Column(String, nullable=False, default="proposed")
    proposal = Column(JSON)  # newer machine output for an already reviewed row
    reviewed_by = Column(String)
    reviewed_at = Column(DateTime)
    review_note = Column(Text)
    run_id = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class Control(Base):
    """Something a workspace does to meet its requirements.

    The id is stable: a new version of the policy updates the row in place and
    moves the old anchor into anchor_history, so owner, frequency and review
    survive.
    """

    __tablename__ = "cg_controls"
    __table_args__ = (UniqueConstraint("workspace_id", "extraction_key", name="uq_cg_control_key"),)

    id = Column(String, primary_key=True, default=generate_id)
    workspace_id = Column(String, nullable=False, index=True)
    extraction_key = Column(String)  # null for manually entered controls
    document_id = Column(String, index=True)  # current anchor document
    quote = Column(Text)
    page_number = Column(Integer)
    page_position = Column(Integer)
    locator = Column(String)
    page_char_start = Column(Integer)
    page_char_end = Column(Integer)
    chunk_id = Column(String)
    section_heading = Column(String)
    anchor_history = Column(JSON, nullable=False, default=list)
    name = Column(String, nullable=False)
    summary = Column(Text)
    performer_span = Column(Text)
    owner_user_id = Column(String)
    owner_team = Column(String)
    frequency = Column(String)
    evidence_expected = Column(Text)
    topics = Column(JSON, nullable=False, default=list)
    basis = Column(String, nullable=False, default="stated")  # stated | manual
    review_status = Column(String, nullable=False, default="proposed")
    status = Column(String, nullable=False, default="active")  # active | retired
    text_hash = Column(String, index=True)
    proposal = Column(JSON)
    created_by = Column(String)
    reviewed_by = Column(String)
    reviewed_at = Column(DateTime)
    review_note = Column(Text)
    run_id = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class Link(Base):
    """Every relationship, library-level (workspace_id null) or workspace-level."""

    __tablename__ = "cg_links"
    __table_args__ = (
        Index("ix_cg_links_from", "from_type", "from_id"),
        Index("ix_cg_links_to", "to_type", "to_id"),
    )

    id = Column(String, primary_key=True)  # hash(relation, from, to, workspace)
    workspace_id = Column(String, index=True)
    layer = Column(String, nullable=False)  # library | workspace
    relation = Column(String, nullable=False, index=True)
    from_type = Column(String, nullable=False)
    from_id = Column(String, nullable=False)
    to_type = Column(String, nullable=False)
    to_id = Column(String, nullable=False)
    from_document_id = Column(String, index=True)
    to_document_id = Column(String, index=True)
    attributes = Column(JSON, nullable=False, default=dict)
    basis = Column(String, nullable=False)  # stated | suggested | manual
    review_status = Column(String, nullable=False, default="proposed")
    # proposed | confirmed | rejected | needs_re_review
    anchors = Column(JSON, nullable=False, default=list)  # frozen once reviewed
    proposal = Column(JSON)
    rationale = Column(Text)  # Iroko's reasoning; never shown as fact
    stale_reason = Column(Text)
    status = Column(String, nullable=False, default="active")  # active | withdrawn
    created_by = Column(String)
    reviewed_by = Column(String)
    reviewed_at = Column(DateTime)
    review_note = Column(Text)
    run_id = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class GraphEvent(Base):
    """Append-only history. The application never updates or deletes these rows."""

    __tablename__ = "cg_events"

    id = Column(String, primary_key=True, default=generate_id)
    subject_type = Column(String, nullable=False)
    subject_id = Column(String, nullable=False, index=True)
    workspace_id = Column(String, index=True)
    action = Column(String, nullable=False)
    from_status = Column(String)
    to_status = Column(String)
    actor_user_id = Column(String)  # null: Iroko
    note = Column(Text)
    snapshot = Column(JSON, nullable=False, default=dict)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)


class ObligationStatus(Base):
    """A workspace's explicit decisions about one requirement (by lineage)."""

    __tablename__ = "cg_obligation_status"

    workspace_id = Column(String, primary_key=True)
    lineage_id = Column(String, primary_key=True)
    applicability_decision = Column(String)  # applies | not_applicable | None
    applicability_note = Column(Text)
    decided_by = Column(String)
    decided_at = Column(DateTime)
    owner_user_id = Column(String)
    owner_team = Column(String)
    next_due_date = Column(Date)
    recurrence = Column(String)  # monthly | quarterly | semiannual | annual | None
    due_basis = Column(String)  # owner | rule | return
    updated_by = Column(String)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class InstitutionProfile(Base):
    """Which licence categories a workspace holds."""

    __tablename__ = "cg_institution_profiles"

    workspace_id = Column(String, primary_key=True)
    category_codes = Column(JSON, nullable=False, default=list)
    basis = Column(String, nullable=False, default="confirmed")  # confirmed | from_filing_profile
    updated_by = Column(String)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class ChangeEvent(Base):
    """A library-level fact about change: never workspace data."""

    __tablename__ = "cg_change_events"

    id = Column(String, primary_key=True)
    kind = Column(String, nullable=False)
    # new_version | amended_by | revoked_by | superseded_by | deadline_extended | withdrawn
    subject_document_id = Column(String, index=True)
    trigger_document_id = Column(String, index=True)
    link_id = Column(String)
    details = Column(JSON, nullable=False, default=dict)
    summary = Column(Text, nullable=False)
    status = Column(String, nullable=False, default="active")  # active | withdrawn
    created_at = Column(DateTime, default=datetime.utcnow, index=True)


class Impact(Base):
    """What a change means for one workspace's own records."""

    __tablename__ = "cg_impacts"
    __table_args__ = (UniqueConstraint("workspace_id", "dedupe_key", name="uq_cg_impact"),)

    id = Column(String, primary_key=True, default=generate_id)
    workspace_id = Column(String, nullable=False, index=True)
    event_id = Column(String, index=True)
    dedupe_key = Column(String, nullable=False)
    kind = Column(String, nullable=False)
    summary = Column(Text, nullable=False)
    affected = Column(JSON, nullable=False, default=dict)
    status = Column(String, nullable=False, default="open")  # open | acknowledged | withdrawn
    acknowledged_by = Column(String)
    acknowledged_at = Column(DateTime)
    task_id = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)


class Judgement(Base):
    """Cached model judgement for a pair of texts; unchanged pairs are never re-judged."""

    __tablename__ = "cg_judgements"

    id = Column(String, primary_key=True)  # hash(kind, workspace, hash_a, hash_b, prompt_version)
    kind = Column(String, nullable=False)
    workspace_id = Column(String, nullable=False, index=True)
    hash_a = Column(String, nullable=False)
    hash_b = Column(String, nullable=False)
    prompt_version = Column(String, nullable=False)
    result = Column(JSON, nullable=False, default=dict)
    created_at = Column(DateTime, default=datetime.utcnow)


class WorkspaceSync(Base):
    """Progress marker for a workspace's incremental graph sync."""

    __tablename__ = "cg_workspace_sync"

    workspace_id = Column(String, primary_key=True)
    events_watermark = Column(DateTime)
    rerun_requested = Column(Boolean, nullable=False, default=False)
    last_run_at = Column(DateTime)
    last_error = Column(Text)
    outage_since = Column(DateTime)


class GraphRun(Base):
    __tablename__ = "cg_runs"

    id = Column(String, primary_key=True, default=generate_id)
    scope = Column(String, nullable=False)  # document | workspace
    target_id = Column(String, nullable=False, index=True)
    workspace_id = Column(String, index=True)
    stage = Column(String, nullable=False)
    status = Column(String, nullable=False, default="running")
    model = Column(String)
    prompt_version = Column(String)
    tokens_estimated = Column(Integer, nullable=False, default=0)
    counts = Column(JSON, nullable=False, default=dict)
    error = Column(Text)
    started_at = Column(DateTime, default=datetime.utcnow, index=True)
    finished_at = Column(DateTime)


class GraphBudget(Base):
    """Daily model-token reservations: scope is "global" or a workspace id."""

    __tablename__ = "cg_budget"

    day = Column(String, primary_key=True)
    scope = Column(String, primary_key=True)
    tokens = Column(Integer, nullable=False, default=0)
