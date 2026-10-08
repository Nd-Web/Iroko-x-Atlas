"""
models/filing.py

Persistent state for regulatory filings, scoped to a workspace (the bank):

  FilingProfile — the bank's particulars, entered once and shared by the team
  FilingDraft   — one return for one period: answers, where each answer came
                  from, imported datasets, status through to "submitted"
  FilingMemory  — facts and learned mappings Iroko reuses across periods and
                  returns (e.g. the GL account → MMFBR line mapping)

New tables only — init_db's create_all adds them on startup; no existing table
changes.
"""

from datetime import datetime

from sqlalchemy import JSON, Column, DateTime, String, Text, UniqueConstraint

from models.database import Base, generate_id


class FilingProfile(Base):
    __tablename__ = "filing_profiles"

    workspace_id = Column(String, primary_key=True)
    profile = Column(JSON, default=dict, nullable=False)
    updated_by = Column(String, nullable=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class FilingDraft(Base):
    __tablename__ = "filing_drafts"
    __table_args__ = (UniqueConstraint("workspace_id", "return_id", "period", name="uq_filing_draft_period"),)

    id = Column(String, primary_key=True, default=generate_id)
    workspace_id = Column(String, nullable=False, index=True)
    return_id = Column(String, nullable=False, index=True)
    period = Column(String, nullable=False)  # 2026-09 | 2026-H1 | 2026 | event-<id>
    data = Column(JSON, default=dict, nullable=False)
    # field key -> {"kind": carried|document|derived|profile|import|user, "label", "quote"?, "document_id"?, "confirmed": bool}
    sources = Column(JSON, default=dict, nullable=False)
    datasets = Column(JSON, default=dict, nullable=False)  # kind -> parsed import + review state
    remediation = Column(JSON, default=dict, nullable=False)
    letter_date = Column(String, nullable=True)
    status = Column(String, default="draft", nullable=False)  # draft | generated | submitted
    reference = Column(String, nullable=True)
    submission_ref = Column(String, nullable=True)
    submitted_on = Column(String, nullable=True)
    submitted_by = Column(String, nullable=True)
    generated_at = Column(DateTime, nullable=True)
    created_by = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class FilingMemory(Base):
    __tablename__ = "filing_memory"

    workspace_id = Column(String, primary_key=True)
    key = Column(String, primary_key=True)
    value = Column(JSON, nullable=False)
    note = Column(Text, nullable=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
