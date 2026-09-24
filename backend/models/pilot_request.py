"""Database model for public 30-day pilot requests."""

from sqlalchemy import Boolean, Column, DateTime, String, Text, UniqueConstraint
from sqlalchemy.sql import func

from models.database import Base, generate_id


class PilotRequest(Base):
    __tablename__ = "pilot_requests"
    __table_args__ = (
        UniqueConstraint("slot_start", name="uq_pilot_requests_slot_start"),
    )

    id = Column(String, primary_key=True, default=generate_id)
    full_name = Column(String(160), nullable=False)
    work_email = Column(String(320), nullable=False, index=True)
    phone = Column(String(64), nullable=False)
    company_name = Column(String(200), nullable=False)
    job_title = Column(String(160), nullable=False)
    company_type = Column(String(40), nullable=False)
    country = Column(String(100), nullable=False)
    pilot_goal = Column(Text, nullable=True)
    consent_to_contact = Column(Boolean, nullable=False)
    slot_start = Column(DateTime(timezone=True), nullable=False, index=True)
    slot_end = Column(DateTime(timezone=True), nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
