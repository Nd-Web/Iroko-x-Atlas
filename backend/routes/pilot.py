"""Public availability and booking endpoints for the free 30-day pilot."""

from __future__ import annotations

import os
from datetime import UTC, datetime, time, timedelta, timezone
from typing import Literal

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr, Field, field_validator
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from models.database import get_db
from models.pilot_request import PilotRequest
from services.pilot_email import send_pilot_booking_emails

router = APIRouter(prefix="/api/pilot", tags=["Pilot requests"])

WAT = timezone(timedelta(hours=1), name="WAT")
SLOT_MINUTES = 30
MIN_NOTICE = timedelta(hours=24)
BOOKABLE_WINDOW = timedelta(days=30)


def _business_hour(name: str, default: int) -> int:
    value = int(os.getenv(name, str(default)))
    return min(max(value, 0), 23)


def _normalise_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def available_slot_starts(db: Session, now: datetime | None = None) -> list[datetime]:
    now_utc = _normalise_utc(now or datetime.now(UTC))
    earliest = now_utc + MIN_NOTICE
    latest = now_utc + BOOKABLE_WINDOW
    start_hour = _business_hour("PILOT_BUSINESS_START_HOUR_WAT", 9)
    end_hour = _business_hour("PILOT_BUSINESS_END_HOUR_WAT", 17)
    if end_hour <= start_hour:
        return []

    booked_values = db.query(PilotRequest.slot_start).filter(
        PilotRequest.slot_start >= now_utc,
        PilotRequest.slot_start <= latest,
    ).all()
    booked = {_normalise_utc(row[0]) for row in booked_values}

    slots: list[datetime] = []
    day = earliest.astimezone(WAT).date()
    last_day = latest.astimezone(WAT).date()
    while day <= last_day:
        if day.weekday() < 5:
            cursor = datetime.combine(day, time(start_hour), tzinfo=WAT)
            closing = datetime.combine(day, time(end_hour), tzinfo=WAT)
            while cursor + timedelta(minutes=SLOT_MINUTES) <= closing:
                candidate = cursor.astimezone(UTC)
                if earliest <= candidate <= latest and candidate not in booked:
                    slots.append(candidate)
                cursor += timedelta(minutes=SLOT_MINUTES)
        day += timedelta(days=1)
    return slots


class PilotRequestCreate(BaseModel):
    full_name: str = Field(min_length=2, max_length=160)
    work_email: EmailStr
    phone: str = Field(min_length=7, max_length=64)
    company_name: str = Field(min_length=2, max_length=200)
    job_title: str = Field(min_length=2, max_length=160)
    company_type: Literal["Microfinance Bank", "Fintech", "Other"]
    country: str = Field(min_length=2, max_length=100)
    pilot_goal: str | None = Field(default=None, max_length=1000)
    consent_to_contact: Literal[True]
    slot_start: datetime

    @field_validator("full_name", "phone", "company_name", "job_title", "country")
    @classmethod
    def strip_required_text(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("This field is required")
        return value

    @field_validator("pilot_goal")
    @classmethod
    def strip_optional_text(cls, value: str | None) -> str | None:
        return value.strip() or None if value is not None else None


class AvailabilityResponse(BaseModel):
    timezone: str
    slot_minutes: int
    business_hours: str
    slots: list[datetime]


class PilotRequestResponse(BaseModel):
    id: str
    slot_start: datetime
    slot_end: datetime
    timezone: str = "WAT"


@router.get("/availability", response_model=AvailabilityResponse)
def get_availability(db: Session = Depends(get_db)) -> AvailabilityResponse:
    start_hour = _business_hour("PILOT_BUSINESS_START_HOUR_WAT", 9)
    end_hour = _business_hour("PILOT_BUSINESS_END_HOUR_WAT", 17)
    return AvailabilityResponse(
        timezone="Africa/Lagos (WAT, UTC+1)",
        slot_minutes=SLOT_MINUTES,
        business_hours=f"{start_hour:02d}:00-{end_hour:02d}:00",
        slots=available_slot_starts(db),
    )


@router.post("/requests", response_model=PilotRequestResponse, status_code=status.HTTP_201_CREATED)
def create_pilot_request(
    payload: PilotRequestCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
) -> PilotRequestResponse:
    requested_slot = _normalise_utc(payload.slot_start).replace(second=0, microsecond=0)
    currently_available = set(available_slot_starts(db))
    if requested_slot not in currently_available:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "slot_unavailable",
                "message": "That time is no longer available. Please choose another slot.",
            },
        )

    booking = PilotRequest(
        full_name=payload.full_name,
        work_email=str(payload.work_email).lower(),
        phone=payload.phone,
        company_name=payload.company_name,
        job_title=payload.job_title,
        company_type=payload.company_type,
        country=payload.country,
        pilot_goal=payload.pilot_goal,
        consent_to_contact=payload.consent_to_contact,
        slot_start=requested_slot,
        slot_end=requested_slot + timedelta(minutes=SLOT_MINUTES),
    )
    db.add(booking)
    try:
        db.commit()
        db.refresh(booking)
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "slot_unavailable",
                "message": "That time was just booked. Please choose another slot.",
            },
        ) from exc

    # Copy scalar values before the request-scoped DB session closes.
    email_booking = PilotRequest(
        id=booking.id,
        full_name=booking.full_name,
        work_email=booking.work_email,
        phone=booking.phone,
        company_name=booking.company_name,
        job_title=booking.job_title,
        company_type=booking.company_type,
        country=booking.country,
        pilot_goal=booking.pilot_goal,
        consent_to_contact=booking.consent_to_contact,
        slot_start=_normalise_utc(booking.slot_start).astimezone(WAT),
        slot_end=_normalise_utc(booking.slot_end).astimezone(WAT),
    )
    background_tasks.add_task(send_pilot_booking_emails, email_booking)
    return PilotRequestResponse(
        id=booking.id,
        slot_start=_normalise_utc(booking.slot_start),
        slot_end=_normalise_utc(booking.slot_end),
    )
