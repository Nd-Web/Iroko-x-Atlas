"""Small Google Calendar REST client for public pilot bookings.

The integration uses an OAuth refresh token belonging to the calendar owner.
Using the owner's OAuth grant (instead of a service account) allows Google to
send genuine invitations to external attendees.
"""

from __future__ import annotations

import asyncio
import logging
import os
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any
from urllib.parse import quote

import httpx

logger = logging.getLogger(__name__)

TOKEN_URL = "https://oauth2.googleapis.com/token"
CALENDAR_API = "https://www.googleapis.com/calendar/v3"


class GoogleCalendarError(RuntimeError):
    """Raised when Google Calendar cannot safely complete an operation."""


@dataclass(frozen=True)
class CalendarEvent:
    event_id: str
    html_link: str | None


_token: str | None = None
_token_expires_at = datetime.min.replace(tzinfo=UTC)
_token_lock = asyncio.Lock()


def is_configured() -> bool:
    return all(
        os.getenv(name)
        for name in (
            "GOOGLE_CALENDAR_ID",
            "GOOGLE_CLIENT_ID",
            "GOOGLE_CLIENT_SECRET",
            "GOOGLE_REFRESH_TOKEN",
        )
    )


def is_required() -> bool:
    return os.getenv("GOOGLE_CALENDAR_REQUIRED", "false").lower() in {
        "1", "true", "yes", "on"
    }


def _calendar_id() -> str:
    calendar_id = os.getenv("GOOGLE_CALENDAR_ID", "")
    if not calendar_id:
        raise GoogleCalendarError("GOOGLE_CALENDAR_ID is not configured")
    return calendar_id


async def _access_token() -> str:
    global _token, _token_expires_at

    if _token and datetime.now(UTC) < _token_expires_at:
        return _token

    async with _token_lock:
        if _token and datetime.now(UTC) < _token_expires_at:
            return _token

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(
                    TOKEN_URL,
                    data={
                        "client_id": os.environ["GOOGLE_CLIENT_ID"],
                        "client_secret": os.environ["GOOGLE_CLIENT_SECRET"],
                        "refresh_token": os.environ["GOOGLE_REFRESH_TOKEN"],
                        "grant_type": "refresh_token",
                    },
                )
                response.raise_for_status()
                payload = response.json()
        except (KeyError, httpx.HTTPError, ValueError) as exc:
            logger.exception("Could not refresh Google Calendar access token")
            raise GoogleCalendarError("Google Calendar authentication failed") from exc

        _token = payload.get("access_token")
        if not _token:
            raise GoogleCalendarError("Google did not return an access token")
        lifetime = max(int(payload.get("expires_in", 3600)) - 60, 60)
        _token_expires_at = datetime.now(UTC) + timedelta(seconds=lifetime)
        return _token


async def _request(method: str, path: str, **kwargs: Any) -> dict[str, Any]:
    token = await _access_token()
    headers = {"Authorization": f"Bearer {token}"}
    try:
        async with httpx.AsyncClient(timeout=12.0) as client:
            response = await client.request(
                method,
                f"{CALENDAR_API}{path}",
                headers=headers,
                **kwargs,
            )
            response.raise_for_status()
            return response.json() if response.content else {}
    except (httpx.HTTPError, ValueError) as exc:
        status = getattr(getattr(exc, "response", None), "status_code", None)
        logger.exception("Google Calendar request failed: %s %s (%s)", method, path, status)
        raise GoogleCalendarError("Google Calendar is temporarily unavailable") from exc


async def busy_periods(time_min: datetime, time_max: datetime) -> list[tuple[datetime, datetime]]:
    """Return busy intervals for the configured calendar in UTC."""
    calendar_id = _calendar_id()
    payload = await _request(
        "POST",
        "/freeBusy",
        json={
            "timeMin": time_min.astimezone(UTC).isoformat(),
            "timeMax": time_max.astimezone(UTC).isoformat(),
            "timeZone": "Africa/Lagos",
            "items": [{"id": calendar_id}],
        },
    )
    calendar = payload.get("calendars", {}).get(calendar_id, {})
    if calendar.get("errors"):
        raise GoogleCalendarError("Google Calendar could not read availability")

    periods: list[tuple[datetime, datetime]] = []
    for item in calendar.get("busy", []):
        try:
            start = datetime.fromisoformat(item["start"].replace("Z", "+00:00")).astimezone(UTC)
            end = datetime.fromisoformat(item["end"].replace("Z", "+00:00")).astimezone(UTC)
        except (KeyError, TypeError, ValueError):
            continue
        periods.append((start, end))
    return periods


async def slot_is_free(slot_start: datetime, slot_end: datetime) -> bool:
    return not await busy_periods(slot_start, slot_end)


async def create_booking_event(
    *,
    booking_id: str,
    slot_start: datetime,
    slot_end: datetime,
    full_name: str,
    work_email: str,
    phone: str,
    company_name: str,
    job_title: str,
    company_type: str,
    country: str,
    pilot_goal: str | None,
) -> CalendarEvent:
    """Create the onboarding event and ask Google to invite the visitor."""
    calendar_id = quote(_calendar_id(), safe="")
    description = "\n".join(
        [
            f"Pilot request: {booking_id}",
            f"Name: {full_name}",
            f"Email: {work_email}",
            f"Phone: {phone}",
            f"Company: {company_name}",
            f"Job title: {job_title}",
            f"Company type: {company_type}",
            f"Country: {country}",
            f"Pilot goal: {pilot_goal or 'Not provided'}",
        ]
    )
    payload = await _request(
        "POST",
        f"/calendars/{calendar_id}/events",
        params={"sendUpdates": "all"},
        json={
            "summary": f"Iroko AI pilot onboarding — {company_name}",
            "description": description,
            "start": {"dateTime": slot_start.astimezone(UTC).isoformat(), "timeZone": "Africa/Lagos"},
            "end": {"dateTime": slot_end.astimezone(UTC).isoformat(), "timeZone": "Africa/Lagos"},
            "attendees": [{"email": work_email, "displayName": full_name}],
            "extendedProperties": {"private": {"irokoPilotRequestId": booking_id}},
        },
    )
    event_id = payload.get("id")
    if not event_id:
        raise GoogleCalendarError("Google Calendar did not confirm the booking")
    return CalendarEvent(event_id=event_id, html_link=payload.get("htmlLink"))
