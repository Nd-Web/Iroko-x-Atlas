"""
models/audit_trail.py — Hash-chained immutable audit trail for Iroko AI.
=========================================================================
Inspired by AuditShield AI's ``backend/audit/models.py`` pattern: each row
carries a SHA-256 hash of the previous entry so any off-chain tamper is
immediately detectable by replaying the chain.

Three hash columns:
  - ``entry_hash``  — SHA-256 of this entry's canonical content string.
  - ``prev_hash``   — SHA-256 of the immediately preceding entry
                      (genesis sentinel = "0" * 64).
  - ``chain_hash``  — SHA-256 of (entry_hash + prev_hash); this is the
                      primary integrity proof used by verify_chain_integrity().

NCC Nigeria compliance context:
  - ``ncc_regulation_ref`` ties each agent decision to a specific NCC
    regulation ID (e.g. "NCC-001").
  - ``verdict`` encodes the three-state outcome:
      "GO"      — compliant, safe to proceed.
      "NO-GO"   — non-compliant, escalate immediately.
      "MONITOR" — ambiguous; flag for human review.

Usage::

    from models.audit_trail import AuditTrailEntry
    from models.database import SessionLocal

    db = SessionLocal()
    entry = db.query(AuditTrailEntry).order_by(AuditTrailEntry.created_at.desc()).first()
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import Column, DateTime, Float, String, Text

from models.database import Base, generate_id

# Genesis sentinel — used as prev_hash for the very first entry in the chain.
GENESIS_HASH: str = "0" * 64


class AuditTrailEntry(Base):
    """
    Append-only, hash-chained record of every agent decision made by Iroko AI.

    The chain invariant is:
        chain_hash == SHA-256(entry_hash + prev_hash)

    A broken chain_hash on any row means that row (or a predecessor) was
    modified after the fact, which is a compliance violation.
    """

    __tablename__ = "audit_trail"

    # ── Identity ──────────────────────────────────────────────────────────────

    id: str = Column(
        String,
        primary_key=True,
        default=generate_id,
        doc="UUID primary key, generated at insert time.",
    )

    # ── Chain integrity ───────────────────────────────────────────────────────

    entry_hash: str = Column(
        String(64),
        nullable=False,
        index=True,
        doc="SHA-256 of the canonical content string for this entry.",
    )
    prev_hash: str = Column(
        String(64),
        nullable=False,
        doc="SHA-256 of the previous entry's entry_hash. '0'*64 for genesis.",
    )
    chain_hash: str = Column(
        String(64),
        nullable=False,
        index=True,
        doc="SHA-256 of (entry_hash + prev_hash). Primary tamper-detection proof.",
    )

    # ── Agent provenance ──────────────────────────────────────────────────────

    agent_name: str = Column(
        String,
        nullable=False,
        index=True,
        doc="Name of the Iroko AI agent that produced this decision "
            "(e.g. 'WatchdogAgent', 'ResearcherAgent').",
    )
    action_type: str = Column(
        String,
        nullable=False,
        index=True,
        doc="Category of decision: 'regulatory_alert', 'competitor_signal', "
            "'fraud_flag', 'market_insight', etc.",
    )

    # ── Decision payload ──────────────────────────────────────────────────────

    decision_summary: str = Column(
        Text,
        nullable=False,
        doc="Human-readable summary of what the agent decided or found.",
    )
    source_url: Optional[str] = Column(
        String,
        nullable=True,
        doc="URL of the external page or document that triggered this decision.",
    )

    # ── NCC Nigeria compliance references ─────────────────────────────────────

    ncc_regulation_ref: Optional[str] = Column(
        String,
        nullable=True,
        index=True,
        doc="NCC regulation identifier, e.g. 'NCC-001', 'NCC-007'. "
            "Soft reference — no DB-level FK to allow partial entries.",
    )
    ncc_section_ref: Optional[str] = Column(
        String,
        nullable=True,
        doc="Specific section within the regulation, e.g. 'Section 70', 'Section 73'.",
    )

    # ── Scoring & verdict ─────────────────────────────────────────────────────

    confidence_score: Optional[float] = Column(
        Float,
        nullable=True,
        doc="Agent confidence in this decision (0.0–1.0).",
    )
    verdict: Optional[str] = Column(
        String,
        nullable=True,
        index=True,
        doc="Three-state compliance verdict: 'GO' | 'NO-GO' | 'MONITOR'.",
    )

    # ── Multi-tenancy ─────────────────────────────────────────────────────────

    workspace_id: Optional[str] = Column(
        String,
        nullable=True,
        index=True,
        doc="Workspace / tenant identifier for multi-org deployments.",
    )

    # ── Timestamps ────────────────────────────────────────────────────────────

    created_at: datetime = Column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
        index=True,
        doc="UTC timestamp of when this entry was persisted.",
    )

    # ── Helpers ───────────────────────────────────────────────────────────────

    def to_dict(self) -> dict:
        """Return a JSON-serialisable representation of this entry."""
        return {
            "id": self.id,
            "entry_hash": self.entry_hash,
            "prev_hash": self.prev_hash,
            "chain_hash": self.chain_hash,
            "agent_name": self.agent_name,
            "action_type": self.action_type,
            "decision_summary": self.decision_summary,
            "source_url": self.source_url,
            "ncc_regulation_ref": self.ncc_regulation_ref,
            "ncc_section_ref": self.ncc_section_ref,
            "confidence_score": self.confidence_score,
            "verdict": self.verdict,
            "workspace_id": self.workspace_id,
            "created_at": self.created_at.isoformat() + "Z" if self.created_at else None,
        }

    def __repr__(self) -> str:
        return (
            f"<AuditTrailEntry id={self.id!r} agent={self.agent_name!r} "
            f"action={self.action_type!r} verdict={self.verdict!r}>"
        )
