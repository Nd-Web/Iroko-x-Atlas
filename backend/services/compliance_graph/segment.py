"""
Deterministic sentence segmentation with exact, page-relative offsets.

Page text (ingestion.extraction.normalize) keeps the hard line breaks of the
original PDF, so a sentence usually spans several lines. Segmentation never
rewrites text: every Sentence is an exact slice page.text[start:end], and its
display `quote` only collapses whitespace.

Cue filters then pick the candidates each extraction stage looks at, so the
model only ever classifies numbered sentences that really exist.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

# Same heading rule as ingestion.chunking, so sections match what chat shows.
_HEADING = re.compile(r"^(?:#{1,6} .+|[A-Z][A-Z /&0-9-]{5,100}|\d+(?:\.\d+)*\.? [A-Z][^\n]{2,100})$")
# "a.", "(ii)", "3.1", "•", and OCR's Markdown-escaped "1\." all start a list item.
_LIST_START = re.compile(r"^\s*(?:\(?(?:[a-z]|[ivxlc]{1,5}|\d{1,3})\)|(?:\d{1,3}(?:\.\d{1,3})*|[a-z]|[ivxlc]{1,5})\\?\.|[•▪●◦\-–*·])\s+", re.I)
_ABBREVIATIONS = {
    "no", "nos", "s", "ss", "sec", "secs", "cap", "para", "paras", "art", "fig", "vol", "ltd", "plc",
    "mr", "mrs", "ms", "dr", "prof", "st", "i.e", "e.g", "etc", "vs", "jan", "feb", "mar", "apr",
    "jun", "jul", "aug", "sep", "sept", "oct", "nov", "dec", "approx", "dept", "govt", "inc", "co",
    "corp", "rev", "ref", "pg", "pp", "op", "cf", "al", "viz", "u.s", "n.b", "nb", "a.m", "p.m",
}
MAX_SENTENCE = 1500


@dataclass
class Sentence:
    index: int
    page_position: int
    page_number: int | None
    locator: str | None
    start: int
    end: int
    raw: str  # exact page text slice
    section_heading: str | None = None
    chunk_id: str | None = None
    tags: set = field(default_factory=set)
    clean: str = ""  # the same slice with layout markup blanked out
    lead_in: int | None = None  # index of the "... are required to:" sentence this list item completes

    @property
    def quote(self) -> str:
        """What a reader sees: layout markup and heading marks removed, whitespace collapsed."""
        return re.sub(r"^#{1,6}\s+", "", " ".join((self.clean or self.raw).split()))


# OCR layout markup (Azure Document Intelligence): comments, figures, table tags.
_MARKUP = re.compile(r"<!--.*?-->|<[^>\n]{1,200}>", re.S)


def mask_markup(text: str) -> str:
    """Same length as text, markup replaced by spaces, so offsets stay exact."""
    return _MARKUP.sub(lambda m: re.sub(r"[^\n]", " ", m.group()), text or "")


def _is_abbreviation(text: str, dot: int) -> bool:
    """Whether the full stop at text[dot] ends an abbreviation, an initial or a list number."""
    # "1.", "ii.", "3.2." or OCR's "1\." opening a line numbers a list item; the item follows.
    line_start = text.rfind("\n", 0, dot) + 1
    if re.fullmatch(r"[ \t]*(?:#{1,6}[ \t]*)?(?:\d{1,3}(?:\.\d{1,3})*|[A-Za-z]|[ivxlcIVXLC]{1,5})\\?", text[line_start:dot]):
        return True
    word = re.search(r"([A-Za-z.]+)$", text[max(0, dot - 12):dot])
    if word:
        token = word.group(1).lower().strip(".")
        if token in _ABBREVIATIONS or len(token) == 1:
            return True
    # "4.2.7" or "No. 5." inside a reference: digits on both sides of the dot.
    if dot > 0 and text[dot - 1].isdigit() and dot + 1 < len(text) and text[dot + 1].isdigit():
        return True
    return False


def _breaks(text: str) -> list[int]:
    """Sentence end offsets within one page's text."""
    ends = []
    length = len(text)
    i = 0
    while i < length:
        ch = text[i]
        if ch in ".!?":
            j = i + 1
            while j < length and text[j] in "\"')]”’":
                j += 1
            if j >= length:
                ends.append(j)
                i = j
                continue
            if text[j].isspace():
                k = j
                while k < length and text[k].isspace():
                    k += 1
                nxt = text[k] if k < length else ""
                if (nxt.isupper() or nxt.isdigit() or nxt in "(\"'“‘•") and not (ch == "." and _is_abbreviation(text, i)):
                    ends.append(j)
        elif ch == "\n":
            # Blank line, or a line break before a list item or heading, ends a segment.
            k = i + 1
            if k < length and text[k] == "\n":
                ends.append(i)
            else:
                line_end = text.find("\n", k)
                line = text[k:line_end if line_end != -1 else length]
                prev_line_start = text.rfind("\n", 0, i) + 1
                prev = text[prev_line_start:i].rstrip()
                if _LIST_START.match(line) or _HEADING.match(line.strip()) or (prev and prev[-1] in ":;" ) \
                        or (prev and _HEADING.match(prev.strip())):
                    ends.append(i)
        i += 1
    return sorted(set(e for e in ends if 0 < e <= length))


def _split_long(text: str, start: int, end: int) -> list[tuple[int, int]]:
    if end - start <= MAX_SENTENCE:
        return [(start, end)]
    pieces, cursor = [], start
    while end - cursor > MAX_SENTENCE:
        cut = text.rfind(";", cursor, cursor + MAX_SENTENCE)
        if cut <= cursor:
            cut = text.rfind(" ", cursor, cursor + MAX_SENTENCE)
        if cut <= cursor:
            cut = cursor + MAX_SENTENCE
        pieces.append((cursor, cut + 1))
        cursor = cut + 1
    pieces.append((cursor, end))
    return pieces


def _trim(text: str, start: int, end: int) -> tuple[int, int]:
    while start < end and text[start].isspace():
        start += 1
    while end > start and text[end - 1].isspace():
        end -= 1
    return start, end


def page_offsets(pages) -> list[int]:
    """Start of each page inside "\\n\\n".join(page texts): the chunks' coordinate system."""
    offsets, cursor = [], 0
    for page in pages:
        offsets.append(cursor)
        cursor += len(page.text) + 2
    return offsets


def segment(pages, chunks=()) -> list[Sentence]:
    """Sentences of a document in reading order. pages are ordered Page rows (or alikes)."""
    offsets = page_offsets(pages)
    spans = sorted(
        ((c.provenance or {}).get("char_start"), (c.provenance or {}).get("char_end"), c.id)
        for c in chunks
        if isinstance((c.provenance or {}).get("char_start"), int)
    )
    sentences: list[Sentence] = []
    heading = None
    for page, offset in zip(pages, offsets):
        text = page.text or ""
        masked = mask_markup(text)
        line_starts = [0] + [m.end() for m in re.finditer(r"\n", masked)]
        headings = []
        for ls in line_starts:
            le = masked.find("\n", ls)
            line = masked[ls:le if le != -1 else len(masked)].strip()
            if line and _HEADING.match(line):
                headings.append((ls, re.sub(r"^#{1,6}\s+", "", line)))
        cursor = 0
        for end in _breaks(masked) + [len(masked)]:
            if end <= cursor:
                continue
            for a, b in _split_long(masked, cursor, end):
                a, b = _trim(masked, a, b)
                raw, clean = text[a:b], masked[a:b]
                if len(clean.strip()) >= 12 and re.search(r"[A-Za-z]{3}", clean):
                    current = next((h for pos, h in reversed(headings) if pos <= a), None)
                    if current:
                        heading = current
                    joined_a, joined_b = offset + a, offset + b
                    chunk_id = next((cid for cs, ce, cid in spans if cs <= joined_a and joined_b <= ce), None)
                    sentences.append(Sentence(
                        index=len(sentences),
                        page_position=page.position,
                        page_number=page.page_number,
                        locator=page.locator,
                        start=a,
                        end=b,
                        raw=raw,
                        section_heading=heading,
                        chunk_id=chunk_id,
                        clean=clean,
                    ))
            cursor = end
    return sentences


# ─── Cue filters ─────────────────────────────────────────────────────────────

# "are hereby required", "are by this circular, required", "are hereby requested to", "are advised to".
REQUIREMENT_CUES = re.compile(
    r"\b(?:shall|must|(?:are|is)\s+(?:[\w,]+\s+){0,5}?(?:required|directed|expected|mandated|obliged)|"
    r"(?:are|is)\s+(?:hereby\s+|once\s+more\s+|further\s+|strongly\s+)?(?:requested|advised|enjoined|urged|reminded)\s+to|"
    r"required\s+to|should|"
    r"ensure\s+that|not\s+later\s+than|no\s+later\s+than|on\s+or\s+before|within\s+(?:\d+|one|two|three|"
    r"five|seven|ten|fourteen|thirty)\b|prohibit\w*|(?:is|are)\s+not\s+(?:permitted|allowed)|may\s+not|"
    r"with\s+immediate\s+effect|forbidden|mandatory|obligat\w+)\b",
    re.I,
)
RELATION_CUES = re.compile(
    r"\b(?:amend\w*|supersed\w*|revok\w*|revocation|repeal\w*|rescind\w*|replac\w*|extend\w*|extension|"
    r"in\s+lieu\s+of|with\s+reference\s+to|further\s+to|pursuant\s+to|in\s+exercise\s+of|withdraw\w*|"
    r"cancel\w*|refer(?:s|red)?\s+to|our\s+(?:circular|letter))\b",
    re.I,
)
EFFECTIVE_CUES = re.compile(
    r"\b(?:with\s+effect\s+from|effective\s+(?:date|from|immediately|on|as\s+from)|take[sn]?\s+effect|"
    r"shall\s+take\s+effect|commenc\w+|come\s+into\s+(?:force|effect)|with\s+immediate\s+effect|"
    r"effective\s+[A-Z0-9])",
    re.I,
)
# "# LETTER TO ALL OTHER FINANCIAL INSTITUTIONS (OFIs)", "RE: CIRCULAR TO ALL MFBs ON ...",
# "To: All Microfinance Banks". A wrapped body line that merely starts with
# "to" ("to forward the audited ...") is rejected by addressee_lines().
ADDRESSEE_LINE = re.compile(
    r"(?im)^[ \t]*(?:#{1,6}[ \t]*)?(?:RE[ \t]*:[ \t]*)?(?P<prefix>(?:circular|letter|notice|memo(?:randum)?)[ \t]+)?"
    r"to(?P<colon>[ \t]*:)?[ \t]+(?P<rest>[^\n]{3,220})$"
)
REFERENCE = re.compile(r"\b[A-Z]{2,6}(?:\s*/\s*[A-Z0-9]{1,10}){2,8}\b")
REF_LINE = re.compile(r"(?im)^\s*(?:our\s+)?ref(?:erence)?\.?\s*(?:no\.?)?\s*[:\-]?\s*(?P<ref>[^\n]{4,80})$")
_PAGE_HEADER = re.compile(r'PageHeader="(?P<value>[^"]{4,200})"')
_BODY_REFERENCE_CONTEXT = re.compile(r"(?i)(?:further\s+to|circular|letter|dated|refer|reference\s+to|our\s+circular)[^\n]{0,40}$")


def normalize_reference(value: str | None) -> str | None:
    """OFI/DIR/CIR/GEN/17/139 regardless of spacing, case or trailing punctuation."""
    if not value:
        return None
    text = re.sub(r"\s*/\s*", "/", value.strip()).upper()
    text = re.sub(r"^(?:REF(?:ERENCE)?\.?\s*(?:NO\.?)?\s*[:\-]?\s*)", "", text)
    text = text.strip(" .,;:)(")
    text = re.sub(r"\s+", "", text)
    return text if REFERENCE.fullmatch(text) else None


# An introduction whose whole duty is in its list: "all OFIs are required to:", "DFIs are required to note that:".
BARE_LEAD_IN = re.compile(
    r"(?:(?:required|expected|directed|mandated|obliged|requested)\s+to(?:\s+(?:undertake|do|note(?:\s+that)?|"
    r"comply\s+with))?(?:\s+the\s+following)?|(?:shall|must|should)(?:\s+(?:ensure|note))?(?:\s+that)?)\s*:$", re.I)


# "... our letter ... in which all OFIs were required to undertake the following:"
PAST_LEAD_IN = re.compile(
    r"\b(?:were|was|had\s+been)\s+(?:\w+\s+){0,2}?(?:required|directed|expected|mandated|obliged|requested)\b", re.I)


def _names_an_act(text: str) -> bool:
    """A citation of an Act ("sanctions under the CBN Act and BOFIA") is a reference like a circular number."""
    from services.compliance_graph import taxonomy

    return bool(taxonomy.match_acts(text))


def is_heading(sentence: Sentence) -> bool:
    text = (sentence.clean or sentence.raw).strip()
    return text.startswith("#") or (bool(_HEADING.match(text)) and _mostly_upper(text))


def tag(sentences: list[Sentence]) -> list[Sentence]:
    lead: Sentence | None = None
    for s in sentences:
        text = s.clean or s.raw
        if REQUIREMENT_CUES.search(text) and not is_heading(s):  # "PROHIBITION OF PLACEMENT ..." is a title
            s.tags.add("requirement")
        if RELATION_CUES.search(text) or REFERENCE.search(text) or _names_an_act(text):
            s.tags.add("relation")
        if EFFECTIVE_CUES.search(text):
            s.tags.add("effective")
        # "all OFIs are required to:" followed by "b. Conspicuously display notices ..."; the items
        # carry no cue of their own but complete the obligation, so they are candidates too. Under
        # "... in which all OFIs were required to:" they restate an earlier instrument's duties.
        if _LIST_START.match(text):
            if lead is not None and s.page_position - lead.page_position <= 1 and s.index - lead.index <= 30:
                s.lead_in = lead.index
                if PAST_LEAD_IN.search(lead.clean or lead.raw):
                    s.tags.discard("requirement")
                    s.tags.add("history")
                else:
                    s.tags.add("requirement")
        else:
            lead = s if REQUIREMENT_CUES.search(text) and text.rstrip().endswith(":") else None
    return sentences


def first_page_text(pages) -> tuple[object | None, str]:
    first = pages[0] if pages else None
    return first, (first.text if first else "")


def _mostly_upper(text: str) -> bool:
    letters = [c for c in text if c.isalpha()]
    return bool(letters) and sum(c.isupper() for c in letters) / len(letters) >= 0.6


def addressee_lines(pages) -> list[tuple[object, int, int, str]]:
    """(page, start, end, text) for header lines such as "# LETTER TO ALL OTHER FINANCIAL INSTITUTIONS"."""
    page, text = first_page_text(pages)
    out = []
    if page is None:
        return out
    masked = mask_markup(text[:5000])
    for m in ADDRESSEE_LINE.finditer(masked):
        rest = m.group("rest").strip()
        header_like = (
            bool(m.group("prefix")) or bool(m.group("colon"))
            or re.match(r"(?i)all\b", rest) is not None
            or _mostly_upper(m.group())
        )
        if not header_like:
            continue
        line = m.group().strip()
        start = m.start() + (len(m.group()) - len(m.group().lstrip()))
        out.append((page, start, start + len(line), re.sub(r"^#{1,6}\s+", "", line)))
    return out


def _header_end(head: str, default: int) -> int:
    """Where the letterhead block (address, Ref, date) ends: the addressee line, else the first heading.

    OCR often turns the department name ("# OTHER FINANCIAL INSTITUTIONS
    SUPERVISION DEPARTMENT") or the reference itself into a heading above the
    Ref line and date, so the addressee line ("LETTER TO ALL ...") is the more
    reliable boundary when there is one.
    """
    masked = mask_markup(head)
    for m in ADDRESSEE_LINE.finditer(masked):
        rest = m.group("rest").strip()
        if m.group("prefix") or m.group("colon") or re.match(r"(?i)all\b", rest) or _mostly_upper(m.group()):
            return m.start()
    title = re.search(r"(?im)^#{1,6}\s+\S", head)
    return title.start() if title else default


def reference_from_pages(pages) -> str | None:
    """The instrument's own reference number, from its first page.

    Letters carry it on a "Ref:" line, alone on a line above the date, or in an
    OCR page-header comment, always in the letterhead block before the
    addressee line or title. References in the body ("Further to our circular
    ref: ...") point at OTHER instruments.
    """
    _page, text = first_page_text(pages)
    head = text[:3000]
    cutoff = _header_end(head, 1500)
    for m in REF_LINE.finditer(head[:cutoff]):
        found = REFERENCE.search(m.group("ref"))
        if found:
            return normalize_reference(found.group())
    for m in _PAGE_HEADER.finditer(head[:cutoff]):
        found = REFERENCE.search(m.group("value"))
        if found:
            return normalize_reference(found.group())
    masked = mask_markup(head[:cutoff])
    for found in REFERENCE.finditer(masked):
        line_start = masked.rfind("\n", 0, found.start()) + 1
        if not _BODY_REFERENCE_CONTEXT.search(masked[line_start:found.start()]):
            return normalize_reference(found.group())
    return None


def letter_date(pages):
    """The date printed on the letter (top of page 1), never the catalogue date."""
    from services.compliance_graph.dates import first_date

    _page, text = first_page_text(pages)
    head = text[:2000]
    cutoff = _header_end(head, 1200)
    found = first_date(mask_markup(head[:cutoff]))
    if found:
        return found
    # OCR sometimes lifts the date into a page-header comment: <!-- PageHeader="May 2, 2017" -->
    for m in _PAGE_HEADER.finditer(head[:cutoff]):
        found = first_date(m.group("value"))
        if found:
            return found
    return None
