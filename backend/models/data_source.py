"""
models/data_source.py — Async SQLAlchemy model for connected data sources.
"""

from __future__ import annotations

import enum
import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import Column, DateTime, Enum, ForeignKey, JSON, String
from sqlalchemy.sql import func

from services.database import Base


# ─── Enums ────────────────────────────────────────────────────────────────────


class DataSourceType(str, enum.Enum):
    sharepoint = "sharepoint"
    servicenow = "servicenow"
    slack = "slack"
    teams = "teams"
    onedrive = "onedrive"
    upload = "upload"


class DataSourceStatus(str, enum.Enum):
    connected = "connected"
    disconnected = "disconnected"
    syncing = "syncing"
    error = "error"


# ─── Model ────────────────────────────────────────────────────────────────────


class DataSource(Base):
    """
    Tracks a connected external data source (connector) for an organisation.

    Attributes
    ----------
    id : str (UUID)
        Primary key.
    org_id : str (UUID)
        Organisation that owns this data source.
    name : str
        Human-readable display name (e.g. "MTN SharePoint").
    type : DataSourceType
        Connector type: sharepoint | servicenow | slack | teams | onedrive | upload.
    status : DataSourceStatus
        Current connection state.
    last_sync_at : datetime | None
        UTC timestamp of last successful sync (null if never synced).
    config : dict
        Connector-specific configuration (encrypted tokens, site IDs, etc.).
    created_at : datetime
        UTC creation timestamp.
    """

    __tablename__ = "data_sources"

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
    name = Column(String(256), nullable=False)
    type = Column(
        Enum(DataSourceType, name="datasourcetype", create_constraint=True),
        nullable=False,
    )
    status = Column(
        Enum(DataSourceStatus, name="datasourcestatus", create_constraint=True),
        nullable=False,
        default=DataSourceStatus.disconnected,
        server_default=DataSourceStatus.disconnected.value,
    )
    last_sync_at = Column(DateTime(timezone=True), nullable=True)
    config = Column(JSON, nullable=False, default=dict, server_default="{}")
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        default=datetime.utcnow,
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<DataSource id={self.id!r} name={self.name!r} type={self.type} status={self.status}>"
