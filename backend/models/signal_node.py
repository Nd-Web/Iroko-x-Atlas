"""
models/signal_node.py — Persistent signal storage for the knowledge graph.

Each scraped signal is stored so the graph can accumulate history across
restarts and apply temporal decay over days, not just within a single request.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Column, DateTime, Float, Index, String, Text

from models.database import Base, generate_id


class SignalNode(Base):
    """
    One row per unique scraped signal (keyed on url+title hash).
    Upserted on every run_all_signals() call — existing rows just get
    their last_seen_at refreshed so decay is computed from the most
    recent sighting, not the first.
    """

    __tablename__ = "signal_nodes"

    id          = Column(String, primary_key=True, default=generate_id)
    signal_hash = Column(String(32), unique=True, nullable=False, index=True)
    category    = Column(String(32), nullable=False)
    title       = Column(Text,   nullable=False, default="")
    url         = Column(Text,   nullable=False, default="")
    snippet     = Column(Text,   nullable=False, default="")
    source_host = Column(String(128), nullable=True)
    base_score  = Column(Float,  nullable=False, default=0.2)
    first_seen  = Column(DateTime, nullable=False, default=datetime.utcnow)
    last_seen   = Column(DateTime, nullable=False, default=datetime.utcnow,
                         onupdate=datetime.utcnow)

    __table_args__ = (
        Index("ix_signal_nodes_category_last_seen", "category", "last_seen"),
    )
