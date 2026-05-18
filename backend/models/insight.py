"""
models/insight.py — Async SQLAlchemy model for AI-generated insights.
"""

from __future__ import annotations

import enum
import uuid
from datetime import datetime

from sqlalchemy import Column, DateTime, Enum, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from services.database import Base


# ─── Enum ─────────────────────────────────────────────────────────────────────


class InsightStatus(str, enum.Enum):
    new = "new"
    reviewed = "reviewed"
    dismissed = "dismissed"


# ─── Model ────────────────────────────────────────────────────────────────────


class Insight(Base):
    """
    A proactive AI-generated insight surfaced by one of the background agents.

    Attributes
    ----------
    id : str (UUID)
        Primary key.
    org_id : str (UUID)
        Organisation this insight belongs to.
    document_id : str | None
        Optional FK to the source document that triggered the insight.
    title : str
        Short headline.
    summary : str
        Full description / reasoning.
    category : str
        Arbitrary tag, e.g. "SLA", "compliance", "contract", "network".
    severity : int
        1 (informational) – 10 (critical).
    agent_source : str
        Name of the agent that generated this insight.
    status : InsightStatus
        Lifecycle state: new → reviewed | dismissed.
    created_at : datetime
        UTC creation timestamp.
    """

    __tablename__ = "insights"

    id = Column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
        nullable=False,
    )
    org_id = Column(
        String(36),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    document_id = Column(
        String(36),
        nullable=True,
        index=True,
    )
    title = Column(String(512), nullable=False)
    summary = Column(Text, nullable=False)
    category = Column(String(128), nullable=False, index=True)
    severity = Column(Integer, nullable=False, default=5)
    agent_source = Column(String(128), nullable=False)
    status = Column(
        Enum(InsightStatus, name="insightstatus", create_constraint=True),
        nullable=False,
        default=InsightStatus.new,
        server_default=InsightStatus.new.value,
        index=True,
    )
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        default=datetime.utcnow,
        index=True,
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Insight id={self.id!r} category={self.category!r} severity={self.severity}>"
