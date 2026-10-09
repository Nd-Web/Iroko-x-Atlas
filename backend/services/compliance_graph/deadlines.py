"""
Deadlines a requirement states, as a rule; and when that rule next falls due.

Only deterministic parsing: the model may point at the words ("within seven (7)
days of the transaction"), but a date is computed here or not at all. Rules
that depend on an event ("within 24 hours of the suspicion") have no date and
are shown as event-driven duties.

Working days reuse the returns calendar (weekends, fixed public holidays,
Easter); Islamic holidays are declared yearly and cannot be computed.
"""

from __future__ import annotations

import re
from datetime import date, timedelta

from services.compliance_graph.dates import find_dates
from services.regulatory_returns.calendar import add_months, is_working_day, month_end, previous_working_day

WORD_NUMBERS = {
    "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9,
    "ten": 10, "eleven": 11, "twelve": 12, "fourteen": 14, "fifteen": 15, "twenty": 20, "twenty-one": 21,
    "twenty-four": 24, "thirty": 30, "forty-five": 45, "forty-eight": 48, "sixty": 60, "seventy-two": 72,
    "ninety": 90,
}
ORDINALS = {
    "first": 1, "second": 2, "third": 3, "fourth": 4, "fifth": 5, "sixth": 6, "seventh": 7, "eighth": 8,
    "ninth": 9, "tenth": 10, "eleventh": 11, "twelfth": 12, "fifteenth": 15, "twentieth": 20,
}
_NUMBER = r"(?P<n>\d{1,3}|" + "|".join(sorted(WORD_NUMBERS, key=len, reverse=True)) + r")(?:\s*\(\s*\d{1,3}\s*\))?"
_UNIT = r"(?P<working>working\s+|business\s+)?(?P<unit>hours?|days?|weeks?|months?)"

_FREQUENCIES = (
    ("daily", r"\bdaily\b|\bevery\s+day\b|\beach\s+day\b"),
    ("weekly", r"\bweekly\b|\bevery\s+week\b|\beach\s+week\b"),
    ("monthly", r"\bmonthly\b|\bevery\s+month\b|\beach\s+month\b|\bper\s+month\b"),
    ("quarterly", r"\bquarterly\b|\bevery\s+quarter\b|\beach\s+quarter\b"),
    ("semiannual", r"\bsemi[-\s]?annual(?:ly)?\b|\bbi[-\s]?annual(?:ly)?\b|\bhalf[-\s]?year(?:ly)?\b|\bevery\s+six\s+months\b"),
    ("annual", r"\bannual(?:ly)?\b|\byearly\b|\bevery\s+year\b|\beach\s+(?:financial\s+)?year\b|\bper\s+annum\b"),
)
FREQUENCIES = tuple(name for name, _p in _FREQUENCIES) + ("event", "once")


def _number(value: str) -> int | None:
    value = value.lower()
    if value.isdigit():
        return int(value)
    return WORD_NUMBERS.get(value)


def parse_frequency(text: str | None) -> str | None:
    for name, pattern in _FREQUENCIES:
        if re.search(pattern, text or "", re.I):
            return name
    return None


# "... of the date of this letter", "... from the date of this circular", "... of the date hereof".
_FROM_ISSUE = re.compile(
    r"^\s*(?:of|from|after)\s+(?:the\s+)?(?:date\s+(?:of\s+)?(?:this|the\s+present)\s+(?:letter|circular|directive|"
    r"notice)|date\s+hereof|issuance\s+of\s+this\s+(?:letter|circular|directive))", re.I)


def _after_issue(issued: date, amount: int, unit: str, working: bool) -> date | None:
    if unit == "month":
        return add_months(issued, amount)
    if unit == "week":
        return issued + timedelta(weeks=amount)
    if unit == "day" and working:
        d, left = issued, amount
        while left:
            d += timedelta(days=1)
            left -= is_working_day(d)
        return d
    if unit == "day":
        return issued + timedelta(days=amount)
    return None  # hours after a letter's date are not a meaningful due date


def parse_deadline(span: str | None, *, issued: date | None = None, sentence: str | None = None) -> dict | None:
    """A rule from the words that state a deadline, or None.

    issued: the date printed on the letter, so "within 90 days of the date of
    this letter" becomes a fixed date; sentence: the requirement's full text,
    in case the span stops before those words.
    """
    if not span:
        return None
    text = " ".join(span.split())
    m = re.search(rf"\bwithin\s+{_NUMBER}\s+{_UNIT}", text, re.I)
    if m and _number(m.group("n")):
        unit = m.group("unit").lower().rstrip("s")
        amount, working = _number(m.group("n")), bool(m.group("working"))
        rule = {"kind": "within", "amount": amount, "unit": unit, "working": working, "text": m.group()}
        following = text[m.end():]
        if not following.strip() and sentence:
            whole = " ".join(sentence.split())
            at = whole.lower().find(m.group().lower())
            following = whole[at + len(m.group()):] if at >= 0 else ""
        if _FROM_ISSUE.match(following):
            due = _after_issue(issued, amount, unit, working) if issued else None
            if due:
                return {"kind": "fixed_date", "date": due.isoformat(), "text": m.group() + following[:40].rstrip(),
                        "from": "letter_date"}
            rule["anchor"] = "letter"
        return rule
    m = re.search(
        r"\b(?:not\s+later\s+than|no\s+later\s+than|on\s+or\s+before|by)\s+(?:the\s+)?"
        r"(?P<d>\d{1,2})(?:st|nd|rd|th)?\s+(?P<working>working\s+|business\s+)?day\s+"
        r"(?:of|after\s+the\s+end\s+of)\s+(?:the\s+|each\s+|every\s+)?"
        r"(?:following|next|succeeding|subsequent|reporting|calendar)?\s*month",
        text, re.I,
    )
    if m:
        return {"kind": "monthly_day", "day": int(m.group("d")), "working": bool(m.group("working")),
                "text": m.group()}
    m = re.search(
        rf"\b{_NUMBER}\s+months?\s+(?:after|following|from)\s+(?:the\s+end\s+of\s+)?(?:its|the|each|every)\s+"
        r"(?:financial|accounting)\s+year", text, re.I)
    if m and _number(m.group("n")):
        return {"kind": "fy_offset_months", "months": _number(m.group("n")), "text": m.group()}
    m = re.search(r"\bend\s+of\s+the\s+(?P<ord>" + "|".join(ORDINALS) + r")\s+month\s+following\s+the\s+(?:financial\s+)?year",
                  text, re.I)
    if m:
        return {"kind": "fy_offset_months", "months": ORDINALS[m.group("ord").lower()], "text": m.group()}
    # A bare "on <date>" counts only as a short deadline span ("on August 7, 2017"), never inside a long sentence.
    prefixes = r"on\s+or\s+before|not\s+later\s+than|no\s+later\s+than|by|before|deadline\s+(?:of|is)"
    m = re.search(rf"\b(?:{prefixes}{'|on' if len(text) <= 60 else ''})\s+", text, re.I)
    if m:
        dates = [d for d in find_dates(text[m.end():m.end() + 40]) if d.start <= 6]
        if dates:
            return {"kind": "fixed_date", "date": dates[0].value.isoformat(), "text": text[m.start():m.end() + dates[0].end]}
    frequency = parse_frequency(text)
    if frequency:
        return {"kind": "periodic", "frequency": frequency, "text": text}
    return None


def _nth_working_day(year: int, month: int, n: int) -> date:
    d = date(year, month, 1)
    count = 0
    while True:
        if is_working_day(d):
            count += 1
            if count == n:
                return d
        d += timedelta(days=1)


def _monthly(year: int, month: int, rule: dict) -> date:
    if rule.get("working"):
        return _nth_working_day(year, month, int(rule["day"]))
    end = month_end(year, month)
    return previous_working_day(date(year, month, min(int(rule["day"]), end.day)))


def next_due(rule: dict | None, today: date, fy_end_month: int = 12) -> date | None:
    """The next date on or after today the rule falls due; None when it has no date."""
    if not isinstance(rule, dict):
        return None
    kind = rule.get("kind")
    if kind == "fixed_date":
        try:
            value = date.fromisoformat(rule["date"])
        except (KeyError, ValueError):
            return None
        return value if value >= today else None
    if kind == "monthly_day":
        candidate = _monthly(today.year, today.month, rule)
        if candidate < today:
            following = add_months(date(today.year, today.month, 1), 1)
            candidate = _monthly(following.year, following.month, rule)
        return candidate
    if kind == "fy_offset_months":
        months = int(rule.get("months") or 0)
        for year in (today.year - 1, today.year, today.year + 1):
            fy_end = month_end(year, fy_end_month)
            due_month = add_months(date(fy_end.year, fy_end.month, 1), months)
            due = month_end(due_month.year, due_month.month)
            if due >= today:
                return due
    return None


def describe(rule: dict | None) -> str | None:
    """A short human description of a rule, for event-driven or undated duties."""
    if not isinstance(rule, dict):
        return None
    kind = rule.get("kind")
    if kind == "within":
        working = "working " if rule.get("working") else ""
        amount = rule.get("amount")
        unit = rule.get("unit", "day")
        anchor = "the date of the letter" if rule.get("anchor") == "letter" else "the triggering event"
        return f"Within {amount} {working}{unit}{'' if amount == 1 else 's'} of {anchor}"
    if kind == "periodic":
        return f"Recurs {rule.get('frequency')}"
    return rule.get("text")


def recurrence_after(due: date, recurrence: str | None) -> date | None:
    """The following occurrence for an owner-entered recurring date."""
    months = {"monthly": 1, "quarterly": 3, "semiannual": 6, "annual": 12}.get(recurrence or "")
    if not months:
        return None
    return add_months(due, months)
