"""Test data: users, workspaces, versioned documents and a deterministic fake model."""

from __future__ import annotations

import json
import re
from datetime import datetime, timedelta

from ingestion.chunking import chunk_pages
from ingestion.models import Chunk, DocumentAccess, Membership, Page, Revision, Workspace
from ingestion.queue import claim, enqueue
from models.database import Document, User

_clock = [datetime(2026, 1, 1, 8, 0, 0)]


def tick() -> datetime:
    _clock[0] += timedelta(seconds=1)
    return _clock[0]


def user(db, user_id, *, role="admin", workspace="ws-a", active=True):
    if workspace and not db.get(Workspace, workspace):
        db.add(Workspace(id=workspace, name=workspace))
    row = User(id=user_id, email=f"{user_id}@example.invalid", hashed_password="unused", role=role,
               full_name=user_id.title(), is_active=active)
    db.add(row)
    if workspace:
        db.add(Membership(user_id=user_id, workspace_id=workspace))
    db.commit()
    return row


def document(db, doc_id, *, title, pages, workspace="ws-a", shared=False, regulator=None, reference=None,
             published=None, role=None, source_key=None, previous_id=None, status="indexed", current=True,
             uploaded_by=None):
    if not db.get(Workspace, workspace):
        db.add(Workspace(id=workspace, name=workspace))
    provenance = {"filename": f"{doc_id}.pdf", "file_type": "pdf"}
    if regulator:
        provenance.update(regulator=regulator, doc_type="regulatory", classification="public")
    if reference:
        provenance.update(reference_number=reference, reference_number_normalized=reference)
    if published:
        provenance["published_date"] = published
    if role:
        provenance["document_role"] = role
    db.add(Document(id=doc_id, title=title, filename=f"{doc_id}.pdf", file_type="pdf", status=status,
                    uploaded_by_id=uploaded_by, extra_metadata={"pipeline": "v1"}))
    db.add(DocumentAccess(document_id=doc_id, workspace_id=workspace, shared_regulatory=shared))
    db.add(Revision(id=doc_id, source_key=source_key or f"key:{doc_id}", sha256=doc_id.ljust(64, "0")[:64],
                    previous_id=previous_id, is_current=current, provenance=provenance, review_status="approved",
                    created_at=tick()))
    page_items = []
    for position, text in enumerate(pages):
        db.add(Page(document_id=doc_id, position=position, page_number=position + 1, locator=None,
                    method="pdf_text", raw_text=text, text=text, quality={}))
        page_items.append({"text": text, "page_number": position + 1, "locator": None})
    for chunk in chunk_pages(page_items):
        db.add(Chunk(id=f"{doc_id}_chunk_{chunk['chunk_index']}", document_id=doc_id,
                     chunk_index=chunk["chunk_index"], content=chunk["content"],
                     provenance={k: v for k, v in chunk.items() if k not in {"content", "chunk_index"}}))
    db.commit()
    return db.get(Document, doc_id)


def supersede(db, old_id):
    db.get(Document, old_id).status = "superseded"
    db.get(Revision, old_id).is_current = False
    db.commit()


def claim_key(db, key):
    """Claim one specific job: every other waiting job is parked for the call."""
    from ingestion.models import Job

    others = db.query(Job).filter(Job.id != key, Job.state.in_(["queued", "retry"])).all()
    saved = [(job, job.available_at) for job in others]
    for job in others:
        job.available_at = datetime(2999, 1, 1)
    db.commit()
    lease = claim(db)
    for job, available_at in saved:
        job.available_at = available_at
    db.commit()
    assert lease and lease[0] == key, lease
    return lease


def claim_job(db, kind, target):
    enqueue(db, kind, target)
    db.commit()
    return claim_key(db, f"{kind}:{target}")


# ─── Letters ─────────────────────────────────────────────────────────────────

BVN_LETTER = """CENTRAL BANK OF NIGERIA
Other Financial Institutions Supervision Department

Ref: OFI/DIR/CIR/GEN/17/139

April 21, 2017

# LETTER TO ALL OTHER FINANCIAL INSTITUTIONS (OFIs)

## BANK VERIFICATION NUMBER (BVN) ENROLLMENT FOR CUSTOMERS

The absence of a unique identifier has been a major challenge for the
industry. All OFIs shall ensure that every customer account is linked to a
valid Bank Verification Number before any withdrawal is permitted.
OFIs are required to render monthly returns on BVN enrollment not later
than the 10th day of the following month.
Effective August 1, 2017, OFIs shall not open accounts for customers without
a BVN.

Yours faithfully,
Director
"""

EXTENSION_LETTER = """CENTRAL BANK OF NIGERIA

Ref: OFI/DIR/CIR/GEN/18/011

January 2, 2018

# LETTER TO ALL OTHER FINANCIAL INSTITUTIONS (OFIs)

Your attention is drawn to our letter referenced OFI/DIR/CIR/GEN/17/139
dated April 21, 2017. The deadline for BVN enrollment is hereby extended to
June 30, 2018 by circular OFI/DIR/CIR/GEN/17/139.
"""

REVOCATION_GAZETTE = """Federal Republic of Nigeria Official Gazette

NOW THEREFORE, I, the Governor of the Central Bank of Nigeria, in exercise of the
powers conferred on the CBN by Section 12 of the Banks and Other Financial
Institutions Act (BOFIA), 2020, hereby revoke the licenses of the 47
Microfinance Banks listed in the schedule to this order.
"""

AMENDING_LETTER = """CENTRAL BANK OF NIGERIA

Ref: OFI/DIR/CIR/GEN/19/001

March 1, 2019

# LETTER TO ALL MICROFINANCE BANKS (MFBs)

This circular hereby amends circular OFI/DIR/CIR/GEN/17/139 on BVN enrollment.
Microfinance banks must report BVN exceptions to the CBN within seven (7) days.
This is contrary to the Money Laundering (Prohibition) Act (MLPA) 2011 (as amended).
"""

BDC_LETTER = """CENTRAL BANK OF NIGERIA

Ref: OFI/DIR/DOC/GEN/019/241

December 20, 2018

# LETTER TO ALL BUREAUX DE CHANGE (BDCs) ON SUBMISSION OF AUDITED FINANCIAL STATEMENTS

Every licensed BDC shall submit its audited financial statements to the CBN not later
than three (3) months after the end of its accounting year.
"""

AML_POLICY = """ACME MICROFINANCE BANK
AML/CFT POLICY

3. CUSTOMER DUE DILIGENCE

The Compliance Officer shall review every customer account for a valid BVN before
activation. The Head of Operations shall reconcile BVN exceptions monthly and report
them to the Board Audit Committee.
Staff are encouraged to be courteous at all times.
"""

TRAINING_REGISTER = """ACME MICROFINANCE BANK
AML/CFT TRAINING ATTENDANCE REGISTER
Period: 1 January 2026 to 31 March 2026
All front-office staff completed the BVN and KYC refresher training on 15 March 2026.
Signed by the Chief Compliance Officer on 20 March 2026.
"""


# ─── Fake model ──────────────────────────────────────────────────────────────

_ADDRESSEE = re.compile(r"\b(?:All\s+OFIs|OFIs|Microfinance\s+banks|MFBs|Every\s+licensed\s+BDC|BDCs?)\b", re.I)
_DEADLINE = re.compile(r"(not\s+later\s+than\s+the\s+\d+(?:st|nd|rd|th)\s+day\s+of\s+the\s+following\s+month|"
                       r"within\s+seven\s+\(7\)\s+days|within\s+\d+\s+days|"
                       r"not\s+later\s+than\s+three\s+\(3\)\s+months\s+after\s+the\s+end\s+"
                       r"of\s+its\s+accounting\s+year)", re.I)


class FakeModel:
    """Answers each extraction schema from the candidate text itself."""

    def __init__(self, *, role="regulation", broken=0, fail=None, relation=None, judge=None):
        self.calls = []
        self.role = role
        self.broken = broken  # number of malformed replies to give first
        self.fail = fail  # exception to raise
        self.relation = relation or "references"
        self.judge = judge  # callable(payload) -> list for mapping judgements

    async def __call__(self, prompt, *, max_tokens=1000, system_prompt="", json_schema=None, service_id="gpt4o",
                       temperature=0.3):
        payload = json.loads(prompt)
        properties = (json_schema or {}).get("properties", {})
        self.calls.append({"properties": sorted(properties), "payload": payload, "max_tokens": max_tokens})
        if self.fail is not None:
            raise self.fail
        if self.broken > 0:
            self.broken -= 1
            return "{not json"
        if "role" in properties:
            return json.dumps({"role": self.role, "reason_span": None})
        if "activity" in properties:
            return json.dumps({"activity": "Front-office staff completed BVN and KYC refresher training.",
                               "activity_span": "completed the BVN and KYC refresher training",
                               "period_span": "1 January 2026 to 31 March 2026",
                               "record_date_span": "20 March 2026", "topics": ["training", "kyc_cdd"]})
        if "judgements" in properties:
            return json.dumps({"judgements": (self.judge or self._judge)(payload)})
        items_schema = properties.get("items", {}).get("items", {}).get("properties", {})
        if "is_requirement" in items_schema:
            return json.dumps({"items": [self._requirement(c) for c in payload["candidates"]]})
        if "is_control" in items_schema:
            return json.dumps({"items": [self._control(c) for c in payload["candidates"]]})
        if "relation" in items_schema:
            return json.dumps({"items": [{"id": i["id"], "mention": i["mention"], "relation": self.relation}
                                         for i in payload["items"]]})
        raise AssertionError(f"Unexpected schema {sorted(properties)}")

    @staticmethod
    def _judge(payload):
        """Controls and records about BVN address/support BVN requirements; nothing else matches."""
        if "control" in payload:
            subject, a, b, yes = payload["control"]["text"], "control_span", "requirement_span", "addresses"
        else:
            subject, a, b, yes = payload["record"]["text"], "record_span", "target_span", "supports"
        out = []
        for target in payload["targets"]:
            match = "BVN" in subject and "BVN" in target["text"]
            out.append({"target_id": target["id"], "relation": yes if match else "unrelated",
                        a: "BVN" if match else None, b: "BVN" if match else None,
                        "rationale": "Both concern checking customers' BVNs." if match else "Different subject."})
        return out

    @staticmethod
    def _requirement(candidate):
        text = candidate["text"]
        introduced = candidate.get("lead_in") or candidate.get("before") or ""
        is_req = bool(re.search(r"\b(shall|must|required)\b", text, re.I)) or (
            bool(re.search(r"\bare\s+required\s+to\s*:\s*$", introduced, re.I)))  # a list item completing a duty
        addressee = _ADDRESSEE.search(text)
        deadline = _DEADLINE.search(text)
        return {
            "id": candidate["id"], "is_requirement": is_req,
            "kind": ("prohibition" if re.search(r"shall\s+not", text, re.I) else "obligation") if is_req else "none",
            "addressee_span": addressee.group() if addressee else None,
            "summary": " ".join(text.split()[:18]),
            "deadline_span": deadline.group() if deadline else None,
            "effective_span": None,
            "frequency": "monthly" if "monthly" in text.lower() else None,
            "topics": ["bvn_identity"] if "BVN" in text else ["financial_reporting"],
            "categories": [],
        }

    @staticmethod
    def _control(candidate):
        text = candidate["text"]
        is_control = bool(re.search(r"\bshall\s+(review|reconcile)", text, re.I))
        performer = re.search(r"The\s+(Compliance\s+Officer|Head\s+of\s+Operations)", text)
        return {
            "id": candidate["id"], "is_control": is_control,
            "name": "BVN review before activation" if "review" in text else "Monthly BVN exception reconciliation",
            "summary": " ".join(text.split()[:20]),
            "performer_span": performer.group() if performer else None,
            "frequency": "monthly" if "monthly" in text else None,
            "evidence_expected": "Review log",
            "topics": ["bvn_identity", "kyc_cdd"],
        }
