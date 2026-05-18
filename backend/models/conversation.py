"""
models/conversation.py — Async SQLAlchemy model for chat conversations.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, String
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from services.database import Base


class ConversationAsync(Base):
    """
    A single conversation thread owned by a user within an org.

    The suffix ``Async`` avoids collision with the sync ``Conversation``
    model in ``models/database.py`` during the transition period.

    Attributes
    ----------
    id : str (UUID)
        Primary key.
    org_id : str (UUID)
        Organisation the conversation belongs to.
    user_id : str (UUID)
        FK to ``users.id``.
    title : str
        Short label for the conversation (auto-generated or user-set).
    created_at / updated_at : datetime
        UTC timestamps.
    messages : list[MessageAsync]
        Child messages, ordered by ``created_at`` ascending.
    """

    __tablename__ = "conversations_v2"

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
    user_id = Column(
        String(36),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    title = Column(String(512), nullable=True)
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        default=datetime.utcnow,
    )
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )

    # ── Relationships ──────────────────────────────────────────────────────────

    user = relationship("User", back_populates="conversations")
    messages = relationship(
        "MessageAsync",
        back_populates="conversation",
        cascade="all, delete-orphan",
        order_by="MessageAsync.created_at",
        lazy="selectin",
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Conversation id={self.id!r} title={self.title!r}>"
