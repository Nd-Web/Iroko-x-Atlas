from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from models.database import Base
from models.pilot_request import PilotRequest
from routes.pilot import available_slot_starts


@pytest.fixture()
def db():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    try:
        yield session
    finally:
        session.close()


def booking(slot_start: datetime, email: str = "ada@example.com") -> PilotRequest:
    return PilotRequest(
        full_name="Ada Okonkwo",
        work_email=email,
        phone="+2348012345678",
        company_name="Example MFB",
        job_title="Head of Compliance",
        company_type="Microfinance Bank",
        country="Nigeria",
        consent_to_contact=True,
        slot_start=slot_start,
        slot_end=slot_start + timedelta(minutes=30),
    )


def test_availability_obeys_notice_weekdays_and_business_hours(db):
    # Monday 08:00 WAT: the first legal time is Tuesday 09:00 WAT.
    now = datetime(2026, 9, 21, 7, 0, tzinfo=UTC)
    slots = available_slot_starts(db, now=now)

    assert slots[0] == datetime(2026, 9, 22, 8, 0, tzinfo=UTC)
    assert all(slot.weekday() < 5 for slot in slots)
    assert all(slot.minute in (0, 30) for slot in slots)
    assert all(8 <= slot.hour <= 15 or (slot.hour == 16 and slot.minute == 0) for slot in slots)


def test_availability_excludes_a_booked_slot(db):
    now = datetime(2026, 9, 21, 7, 0, tzinfo=UTC)
    slot = datetime(2026, 9, 22, 8, 0, tzinfo=UTC)
    db.add(booking(slot))
    db.commit()

    assert slot not in available_slot_starts(db, now=now)


def test_database_rejects_double_booking(db):
    slot = datetime(2026, 9, 22, 8, 0, tzinfo=UTC)
    db.add(booking(slot))
    db.commit()
    db.add(booking(slot, email="chioma@example.com"))

    with pytest.raises(IntegrityError):
        db.commit()
