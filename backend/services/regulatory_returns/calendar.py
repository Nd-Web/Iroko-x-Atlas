"""
services/regulatory_returns/calendar.py

Due dates for each return's reporting periods.

Working days exclude weekends, Nigeria's fixed-date public holidays and the
Easter holidays. Islamic holidays (Eid-el-Fitr, Eid-el-Kabir, Eid-el-Maulud)
and substitute days are declared by the Federal Government each year, so they
cannot be computed — callers surface that caveat beside FinA deadlines.
"""

from __future__ import annotations

import calendar as _cal
from dataclasses import dataclass
from datetime import date, timedelta

from .catalog import RETURNS, ReturnSpec

_FIXED_HOLIDAYS = ((1, 1), (5, 1), (6, 12), (10, 1), (12, 25), (12, 26))


def _easter(year: int) -> date:
    """Gregorian Easter Sunday (Anonymous Gregorian algorithm)."""
    a, b, c = year % 19, year // 100, year % 100
    d, e = b // 4, b % 4
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = c // 4, c % 4
    l = (32 + 2 * e + 2 * i - h - k) % 7  # noqa: E741
    m = (a + 11 * h + 22 * l) // 451
    month = (h + l - 7 * m + 114) // 31
    day = ((h + l - 7 * m + 114) % 31) + 1
    return date(year, month, day)


def public_holidays(year: int) -> set[date]:
    easter = _easter(year)
    return {date(year, m, d) for m, d in _FIXED_HOLIDAYS} | {
        easter - timedelta(days=2),  # Good Friday
        easter + timedelta(days=1),  # Easter Monday
    }


def is_working_day(d: date) -> bool:
    return d.weekday() < 5 and d not in public_holidays(d.year)


def previous_working_day(d: date) -> date:
    while not is_working_day(d):
        d -= timedelta(days=1)
    return d


def month_end(year: int, month: int) -> date:
    return date(year, month, _cal.monthrange(year, month)[1])


def add_months(d: date, months: int) -> date:
    y, m = divmod(d.month - 1 + months, 12)
    year, month = d.year + y, m + 1
    return date(year, month, min(d.day, _cal.monthrange(year, month)[1]))


# ─── Periods ──────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class Period:
    key: str  # 2026-09 | 2026-H1 | 2026
    label: str  # September 2026 | Half-year ended 30 June 2026 | Year ended 31 December 2026
    start: date
    end: date


def parse_period(period_type: str, key: str, fy_end_month: int = 12) -> Period:
    """Parse a period key; raises ValueError with a readable message."""
    key = (key or "").strip()
    try:
        if period_type == "month":
            y, m = (int(p) for p in key.split("-"))
            return Period(key, date(y, m, 1).strftime("%B %Y"), date(y, m, 1), month_end(y, m))
        if period_type == "half_year":
            y_s, h = key.upper().split("-H")
            y, h_i = int(y_s), int(h)
            if h_i == 1:
                return Period(f"{y}-H1", f"Half-year ended 30 June {y}", date(y, 1, 1), date(y, 6, 30))
            if h_i == 2:
                return Period(f"{y}-H2", f"Half-year ended 31 December {y}", date(y, 7, 1), date(y, 12, 31))
            raise ValueError
        if period_type == "year":
            y = int(key)
            end = month_end(y, fy_end_month)
            start = add_months(end, -12) + timedelta(days=1)
            return Period(str(y), f"Year ended {end.day} {end.strftime('%B %Y')}", start, end)
    except (ValueError, TypeError):
        pass
    examples = {"month": "2026-09", "half_year": "2026-H1", "year": "2026"}
    raise ValueError(f"Invalid period '{key}' — expected a {period_type.replace('_', ' ')} like {examples.get(period_type, '')}.")


def due_date(spec: ReturnSpec, period: Period) -> date | None:
    rule = spec.due_rule
    kind = rule["kind"]
    if kind == "monthly_fina":
        nxt = period.end + timedelta(days=1)
        return previous_working_day(date(nxt.year, nxt.month, 5))
    if kind == "semiannual_offset":
        return period.end + timedelta(days=int(rule["offset_days"]))
    if kind == "annual_fixed":
        return date(period.end.year + 1, int(rule["month"]), int(rule["day"]))
    if kind == "fy_offset_months":
        d = add_months(period.end, int(rule["months"]))
        return month_end(d.year, d.month)
    return None


def fy_end_month_for(spec: ReturnSpec, fy_end_month: int) -> int:
    """Only the audited-accounts deadline follows the bank's financial year;
    NDIC deposits and NDPC audits are fixed to the calendar year by statute."""
    return fy_end_month if spec.due_rule["kind"] == "fy_offset_months" else 12


def _period_after(period_type: str, p: Period, fy_end_month: int) -> Period:
    nxt = p.end + timedelta(days=1)
    if period_type == "month":
        return parse_period("month", f"{nxt.year}-{nxt.month:02d}")
    if period_type == "half_year":
        return parse_period("half_year", f"{nxt.year}-H{1 if nxt.month <= 6 else 2}")
    return parse_period("year", str(add_months(nxt, 11).year), fy_end_month)


def _period_containing(period_type: str, d: date, fy_end_month: int) -> Period:
    if period_type == "month":
        return parse_period("month", f"{d.year}-{d.month:02d}")
    if period_type == "half_year":
        return parse_period("half_year", f"{d.year}-H{1 if d.month <= 6 else 2}")
    fy_year = d.year if d.month <= fy_end_month else d.year + 1
    return parse_period("year", str(fy_year), fy_end_month)


def upcoming(today: date, per_return: int = 2, fy_end_month: int = 12) -> list[dict]:
    """The next `per_return` due dates for every return with a calendar rule.

    Starts from the earliest period whose deadline is still today or later, so
    a return due this week shows even though its period has closed.
    """
    items: list[dict] = []
    for spec in RETURNS:
        if spec.period_type == "event":
            continue
        fy = fy_end_month_for(spec, fy_end_month)
        # Begin two periods back so closed periods with open deadlines appear.
        p = _period_containing(spec.period_type, today, fy)
        for _ in range(2):
            p = _previous(spec.period_type, p, fy)
        found = 0
        for _ in range(30):
            due = due_date(spec, p)
            if due and due >= today:
                items.append({
                    "return_id": spec.id,
                    "title": spec.short_title,
                    "regulator": spec.regulator,
                    "period": p.key,
                    "period_label": p.label,
                    "due": due.isoformat(),
                    "days_left": (due - today).days,
                    "generator": spec.generator,
                })
                found += 1
                if found >= per_return:
                    break
            p = _period_after(spec.period_type, p, fy)
    items.sort(key=lambda i: (i["due"], i["regulator"]))
    return items


def _previous(period_type: str, p: Period, fy_end_month: int) -> Period:
    return _period_containing(period_type, p.start - timedelta(days=1), fy_end_month)
