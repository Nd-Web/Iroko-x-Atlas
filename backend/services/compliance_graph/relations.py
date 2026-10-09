"""
How an instrument relates to other instruments and Acts, and when it takes effect.

"Stated" is deterministic and deliberately strict:
  * a performative cue in the document's own words ("hereby revoke",
    "this circular amends", "is hereby extended") ...
  * bound to its target in the same clause (no full stop or semicolon between),
  * not about something else ("revoke the licences of 47 microfinance banks",
    "the Act (as amended)"),
  * and a target that resolves to exactly one instrument by its reference
    number or Act name. Dates and titles alone never resolve a target.
Everything else is at most "suggested" (the model's reading) or a plain
"references" citation.

Target audiences: a shared library document may only point at shared
documents; a workspace's private regulation may point at its own documents and
the shared library. Private documents of two workspaces are never linked.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from services.compliance_graph import taxonomy
from services.compliance_graph.dates import find_dates
from services.compliance_graph.segment import EFFECTIVE_CUES, REFERENCE, letter_date, normalize_reference

_VERB = (r"(?P<verb>amend(?:s|ed|ing)?|revok(?:e|es|ed|ing)|repeal(?:s|ed|ing)?|rescind(?:s|ed|ing)?|"
         r"supersed(?:e|es|ed|ing)|replac(?:e|es|ed|ing)|withdraw(?:s|n|ing)?|extend(?:s|ed|ing)?|cancel(?:s|led|ed|ling)?)")
PERFORMATIVE = re.compile(
    r"\b(?:hereby\s+"
    r"|(?:this|the\s+present)\s+(?:circular|letter|guidelines?|framework|regulations?|directive|notice|policy|instrument)"
    r"\s+(?:hereby\s+)?)"
    rf"{_VERB}\b",
    re.I,
)
EXCLUDED_OBJECT = re.compile(r"\blicen[cs]es?\b|\boperating\s+licen[cs]e|\(\s*as\s+amended\s*\)|\bas\s+amended\b", re.I)
DEADLINE_WORDS = re.compile(r"\b(?:deadline|timeline|time\s*frame|timeframe|date|period|submission|window)\b", re.I)
# Words that describe this instrument changing another; used only to decide whether the model is asked.
CHANGE_WORDS = re.compile(
    r"\b(?:amend(?:s|ed|ing|ment)?|supersed\w*|revok\w*|revocation|repeal\w*|rescind\w*|replac\w*|extend\w*|"
    r"extension|withdraw\w*|cancel\w*|in\s+lieu\s+of)\b", re.I)
ISSUED_UNDER = re.compile(r"\bin\s+exercise\s+of\s+(?:the\s+)?powers?\s+conferred\b", re.I)

RELATION_OF_VERB = {
    "amend": "amends", "revok": "revokes", "repeal": "revokes", "rescind": "revokes", "withdraw": "revokes",
    "cancel": "revokes", "supersed": "supersedes", "replac": "supersedes", "extend": "extends_deadline_of",
}
LIBRARY_RELATIONS = ("amends", "supersedes", "revokes", "extends_deadline_of", "references", "issued_under")


def verb_relation(verb: str) -> str | None:
    verb = verb.lower()
    return next((rel for stem, rel in RELATION_OF_VERB.items() if verb.startswith(stem)), None)


@dataclass
class Mention:
    kind: str  # "reference" (an instrument reference number) | "act"
    key: str  # normalised reference | act code
    span: str
    start: int
    end: int


@dataclass
class Finding:
    sentence: object
    mention: Mention
    relation: str
    basis: str  # stated | suggested
    cue_span: str | None = None
    notes: list = field(default_factory=list)


def mentions(text: str, own_reference: str | None = None) -> list[Mention]:
    found: list[Mention] = []
    for m in REFERENCE.finditer(text or ""):
        ref = normalize_reference(m.group())
        if ref and ref != own_reference:
            found.append(Mention("reference", ref, m.group(), m.start(), m.end()))
    for a in taxonomy.match_acts(text or ""):
        found.append(Mention("act", a.code, a.span, a.start, a.end))
    return sorted(found, key=lambda m: m.start)


def performative_relation(text: str, mention: Mention) -> tuple[str, str] | None:
    """(relation, cue span) when the text performatively acts on this mention, else None."""
    for cue in PERFORMATIVE.finditer(text):
        if cue.end() > mention.start:
            continue
        between = text[cue.end():mention.start]
        if len(between) > 220 or re.search(r"[.;]\s", between) or EXCLUDED_OBJECT.search(between):
            continue
        relation = verb_relation(cue.group("verb"))
        if relation == "extends_deadline_of" and not DEADLINE_WORDS.search(text):
            continue
        if relation and mention.kind == "act" and relation != "amends":
            # An instrument does not revoke or supersede an Act; an Act named in such
            # a sentence is the power exercised, not the object.
            continue
        return relation, cue.group()
    return None


def deterministic_findings(sentences, own_reference: str | None) -> list[Finding]:
    """Findings that need no model: performative relations, exercise of powers, plain citations."""
    out: list[Finding] = []
    for s in sentences:
        text = s.clean or s.raw
        for mention in mentions(text, own_reference):
            performed = performative_relation(text, mention)
            if performed:
                out.append(Finding(s, mention, performed[0], "stated", performed[1]))
            elif mention.kind == "act" and ISSUED_UNDER.search(text[:mention.start]):
                cue = ISSUED_UNDER.search(text[:mention.start])
                if not re.search(r"[.;]\s", text[cue.end():mention.start]):
                    out.append(Finding(s, mention, "issued_under", "stated", cue.group()))
                else:
                    out.append(Finding(s, mention, "references", "stated"))
            else:
                out.append(Finding(s, mention, "references", "stated"))
    return out


# "This circular", "these Guidelines", "this new provision": the instrument speaking of itself.
_NAMES_ITSELF = re.compile(
    r"\b(?:this|these|the\s+present)\s+(?:new\s+|revised\s+|amended\s+)?(?:circular|letter|guidelines?|guidance(?:\s+notes?)?|"
    r"framework|regulations?|directives?|code|policy|provisions?|amendments?|order|notice|rules?|standards?|instrument|"
    r"exposure\s+draft)\b", re.I)
# "the Guidelines", "the attached Framework": usually the instrument a cover letter issues, but not certainly.
_NAMES_ATTACHED = re.compile(
    r"\b(?:the|its)\s+(?:attached\s+|revised\s+|new\s+)?(?:code|guidelines?|framework|regulations?|rules?|standards?)\b", re.I)
# Reported speech about an earlier instrument: "The letter also stated that effective from ...".
_REPORTED = re.compile(
    r"\b(?:stated|provided|required|directed|indicated|specified|approved|announced)\b(?:\s+that)?|"
    r"\b(?:our|the|that|earlier|previous|above)\s+(?:earlier\s+|previous\s+)?(?:letter|circular|directive)\b", re.I)
# Nigerian statutory instruments carry a margin note: "[22nd Day of May, 2023] Commencement."
_COMMENCEMENT = re.compile(r"\[\s*(?P<date>[^\]\n]{6,40}?)\s*\]?\s*Commence-?\s*(?:ment)?", re.I)


def effective_date(sentences, pages) -> dict | None:
    """When this instrument takes effect, from its own words. Never the catalogue date.

    Stated only when the sentence names the instrument itself ("This Guideline
    shall take effect from January 1, 2023") or is a statutory instrument's
    commencement note. A date for one requirement ("Effective August 1, 2017,
    customers without BVN shall not ...") belongs to that requirement, not the
    instrument, and a date reported from an earlier letter is never this one's.
    """
    found: list[dict] = []
    for s in sentences:
        text = s.clean or s.raw
        cue = EFFECTIVE_CUES.search(text)
        if not cue:
            continue
        commencement = _COMMENCEMENT.search(text)
        if commencement:
            dates = find_dates(commencement.group("date"))
            if dates:
                found.append({"date": dates[0].value, "basis": "stated", "sentence": s,
                              "span": commencement.group().strip(), "rank": 0})
                continue
        before = text[:cue.start()]
        names_itself = bool(_NAMES_ITSELF.search(text))
        if not names_itself and (_REPORTED.search(before) or any(m.kind == "reference" for m in mentions(text))):
            continue  # about another instrument
        attached = not names_itself and bool(_NAMES_ATTACHED.search(text))
        if not (names_itself or attached):
            continue  # a date for one requirement, not for the instrument
        reach = 40
        if re.match(r"effective\s+date", cue.group(), re.I):
            # "The effective date for full compliance with ... is January 1, 2023"
            verb = re.search(r"\b(?:is|shall\s+be|will\s+be)\b|:", text[cue.end():cue.end() + 120])
            if verb and not re.search(r"[.;]\s", text[cue.end():cue.end() + verb.start()]):
                reach = cue.end() - cue.start() + verb.end() + 6
        nearby = [d for d in find_dates(text[cue.start():cue.end() + 160]) if d.start <= reach]
        if nearby:
            found.append({"date": nearby[0].value, "basis": "stated" if names_itself else "suggested", "sentence": s,
                          "span": text[cue.start():cue.start() + nearby[0].end], "rank": 0 if names_itself else 2})
        elif re.search(r"\bimmediate(?:ly)?\b", text[cue.start():cue.end() + 30], re.I):
            issued = letter_date(pages)
            if issued:
                found.append({"date": issued, "basis": "suggested", "sentence": s, "span": cue.group(), "rank": 1,
                              "note": "Takes effect immediately; the date is the date printed on the letter"})
    if not found:
        return None
    best = min(found, key=lambda f: f["rank"])
    best.pop("rank")
    return best


# ─── Model typing (suggestions only) ─────────────────────────────────────────

RELATION_SYSTEM = (
    "You read sentences from a Nigerian financial regulator's instrument. Each item is a sentence that cites "
    "another instrument; `mention` is the citation. `instrument` gives THIS instrument's title and the "
    "sentences in which it describes a change it makes. For each item say how THIS instrument relates to the "
    "cited one: amends (changes some of its provisions), supersedes (replaces it), revokes (cancels or "
    "repeals it), extends_deadline_of (extends a deadline the cited instrument set), references (only cites "
    "it), or none. Choose a change only when the change sentences or the title clearly apply it to the cited "
    "instrument. Revoking licences, approvals or registrations of institutions is NOT revoking an "
    "instrument. \"(as amended)\" describes the cited Act; it is not this instrument amending it. "
    "When unsure, answer references."
)
_RELATION_ENUM = ["amends", "supersedes", "revokes", "extends_deadline_of", "references", "none"]


def relation_schema():
    from services.grounded_answers import object_schema

    return object_schema({
        "items": {"type": "array", "items": object_schema({
            "id": {"type": "string"},
            "mention": {"type": "string"},
            "relation": {"type": "string", "enum": _RELATION_ENUM},
        })}
    })
