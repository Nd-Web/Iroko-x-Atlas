"""
models/user.py — Async SQLAlchemy model for platform users.

Uses the shared ``Base`` from ``services.database`` so that the async
engine can auto-create tables.  The sync counterpart (``User`` in
``models/database.py``) is kept intact for existing routes.
"""

from __future__ import annotations

import enum
import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Enum,
    ForeignKey,
    String,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from services.database import Base


# ─── Enums ────────────────────────────────────────────────────────────────────


class UserRole(str, enum.Enum):
    admin = "admin"
    analyst = "analyst"
    viewer = "viewer"


# ─── Model ────────────────────────────────────────────────────────────────────


class User(Base):
    """
    Platform user account.

    Attributes
    ----------
    id : UUID
        Primary key — auto-generated UUIDv4.
    email : str
        Unique, indexed e-mail address used for login.
    hashed_password : str
        bcrypt hash of the user's password.
    full_name : str
        Display name (e.g. "Ndubuisi Ekeh").
    role : UserRole
        Access level — admin | analyst | viewer.  Defaults to analyst.
    org_id : UUID
        Foreign key to the ``organizations`` table.
    is_active : bool
        Soft-delete / account suspension flag.
    created_at : datetime
        UTC timestamp of account creation.
    updated_at : datetime
        UTC timestamp of last modification (auto-updated).
    """

    __tablename__ = "users"

    id = Column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
        nullable=False,
    )
    email = Column(String(320), unique=True, nullable=False, index=True)
    hashed_password = Column(String(256), nullable=False)
    full_name = Column(String(200), nullable=True)
    role = Column(
        Enum(UserRole, name="userrole_async", create_constraint=True),
        nullable=False,
        default=UserRole.analyst,
        server_default=UserRole.analyst.value,
    )
    org_id = Column(
        String(36),
        ForeignKey("organizations.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    is_active = Column(Boolean, nullable=False, default=True, server_default="true")
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

    conversations = relationship(
        "ConversationAsync",
        back_populates="user",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<User id={self.id!r} email={self.email!r} role={self.role}>"
