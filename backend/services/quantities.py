"""Exact numeric scale normalization; never silently strip a monetary suffix."""

import re
from decimal import Decimal, InvalidOperation

SCALES = {
    "k": 1000, "thousand": 1000,
    "m": 1000000, "mn": 1000000, "million": 1000000,
    "b": 1000000000, "bn": 1000000000, "billion": 1000000000,
    "trillion": 1000000000000, "tn": 1000000000000,
}
NUMBER = r"[+-]?(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?"
SUFFIX = "|".join(sorted(SCALES, key=len, reverse=True))
CURRENCY = r"(?:₦|\$|€|£|NGN|USD|EUR|GBP|N)"
QUANTITY = re.compile(
    rf"(?<![\w.])(?P<currency>{CURRENCY})?\s*(?P<number>{NUMBER})"
    rf"(?:\s*(?P<scale>{SUFFIX})(?!\w))?(?P<percent>\s*%)?", re.I
)
OPERAND = re.compile(
    rf"\s*(?:[×*]\s*)?(?P<currency>{CURRENCY})?\s*(?P<number>{NUMBER})"
    rf"(?:\s*(?P<scale>{SUFFIX}))?(?P<percent>\s*%)?\s*", re.I
)


def value(match):
    return Decimal(match['number'].replace(',', '')) * SCALES.get((match['scale'] or '').lower(), 1)


def parse_operand(text):
    match = OPERAND.fullmatch(text) if isinstance(text, str) else None
    if not match:
        raise InvalidOperation('Unrecognized numeric unit')
    return value(match) / 100 if match['percent'] else value(match)


def unit(text):
    match = OPERAND.fullmatch(text) if isinstance(text, str) else None
    if not match:
        raise InvalidOperation('Unrecognized numeric unit')
    currency = (match['currency'] or '').upper()
    currency = {'₦': 'NGN', 'N': 'NGN', '$': 'USD', '€': 'EUR', '£': 'GBP'}.get(currency, currency)
    return currency or ('percent' if match['percent'] else '')


def numeric_values(text):
    return {format(value(match).normalize(), 'f') for match in QUANTITY.finditer(text)}


def calculation_values(text):
    return {format((value(match) / 100 if match['percent'] else value(match)).normalize(), 'f')
            for match in QUANTITY.finditer(text)}
