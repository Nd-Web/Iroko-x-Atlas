"""Dates as Nigerian regulators write them: "21st April, 2017", "April 21, 2017", "1 st January, 2023", 21/04/2017."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date

MONTHS = {
    "january": 1, "jan": 1, "february": 2, "feb": 2, "march": 3, "mar": 3, "april": 4, "apr": 4,
    "may": 5, "june": 6, "jun": 6, "july": 7, "jul": 7, "august": 8, "aug": 8, "september": 9,
    "sept": 9, "sep": 9, "october": 10, "oct": 10, "november": 11, "nov": 11, "december": 12, "dec": 12,
}
_MONTH = r"(?P<month>January|February|March|April|May|June|July|August|September|October|November|December|" \
         r"Jan|Feb|Mar|Apr|Jun|Jul|Aug|Sept|Sep|Oct|Nov|Dec)\.?"
_DAY = r"(?P<day>\d{1,2})\s*(?:st|nd|rd|th)?"
_YEAR = r"(?P<year>(?:19|20)\d{2})"

_PATTERNS = (
    re.compile(rf"\b{_DAY}\s+(?:day\s+of\s+)?{_MONTH}\s*,?\s*{_YEAR}\b", re.I),
    re.compile(rf"\b{_MONTH}\s+{_DAY}\s*,?\s*{_YEAR}\b", re.I),
    re.compile(r"\b(?P<day>\d{1,2})[/.-](?P<month>\d{1,2})[/.-](?P<year>(?:19|20)\d{2})\b"),
    re.compile(r"\b(?P<year>(?:19|20)\d{2})-(?P<month>\d{2})-(?P<day>\d{2})\b"),
)


@dataclass(frozen=True)
class FoundDate:
    value: date
    span: str
    start: int
    end: int


def find_dates(text: str) -> list[FoundDate]:
    found: list[FoundDate] = []
    taken: list[tuple[int, int]] = []
    for pattern in _PATTERNS:
        for m in pattern.finditer(text or ""):
            if any(a < m.end() and m.start() < b for a, b in taken):
                continue
            month = m.group("month")
            month_number = int(month) if month.isdigit() else MONTHS.get(month.lower().rstrip("."))
            try:
                value = date(int(m.group("year")), int(month_number or 0), int(m.group("day")))
            except (TypeError, ValueError):
                continue
            found.append(FoundDate(value, m.group(), m.start(), m.end()))
            taken.append((m.start(), m.end()))
    return sorted(found, key=lambda f: f.start)


def first_date(text: str) -> date | None:
    dates = find_dates(text)
    return dates[0].value if dates else None
