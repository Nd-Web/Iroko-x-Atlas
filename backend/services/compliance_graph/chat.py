"""
The compliance graph in chat.

expand_context — relationship questions only ("how does this circular relate
to our onboarding policy?", "what did the amendment change?"). From the
passages search already found, it follows at most two hops of confirmed links
(or library links stated in the source) and adds:
  * the exact passages those links rest on, re-checked with the same gates as
    grounded_answers.retrieve (permitted, indexed, current, text unchanged);
  * "Iroko record" sources for the workspace's CONFIRMED facts, so the existing
    quote validator checks relationship claims too.
Suggestions are never sources; they are only counted ("N suggested links ...").

records_answer — deterministic answers about the organisation's own records:
gaps, owners, due dates, what needs re-review, one requirement's chain. No
model call; every requirement is cited by its exact words.

Both read only the database, scoped to the signed-in user's workspace.
"""

from __future__ import annotations

import re

from sqlalchemy import and_, or_

from ingestion.access import allowed_document_ids, principal
from services.compliance_graph.common import enabled

RELATIONSHIP_CUES = re.compile(
    r"\b(?:relat\w*|connect\w*|linked|affect\w*|impact\w*|chang\w*|amend\w*|supersed\w*|revok\w*|repeal\w*|"
    r"replac\w*|extend\w*|extension|map(?:s|ped|ping)?|trac(?:e|ed|es|ing|eability)|which\s+controls?|"
    r"our\s+(?:policy|policies|procedures?|controls?|records?|evidence)|covered\s+by|"
    r"how\s+does\s+(?:this|the|our)\s+\w+\s+(?:compare|fit))\b",
    re.I,
)
MAX_PASSAGES = 6
MAX_RECORDS = 6
CHAT_RELATIONS = ("amends", "supersedes", "revokes", "extends_deadline_of", "references", "addresses", "evidences")


def wanted(question: str) -> bool:
    """Cheap check before any database access: the feature is on and the question is relational."""
    return enabled() and bool(RELATIONSHIP_CUES.search(question or ""))


# ─── Graph step for factual questions ────────────────────────────────────────


def expand_context(question: str, context: dict) -> dict:
    actor = principal.get()
    if actor is None or not wanted(question):
        return context
    from ingestion.db import Session

    with Session() as db:
        return _expand(db, actor, question, context)


def _is_internal(identifier) -> bool:
    return isinstance(identifier, str) and not identifier.startswith(("record:", "public:"))


def chunk_source(db, actor, chunk_id: str) -> dict | None:
    """A passage, only if the caller may read it now (the same gates as grounded_answers.retrieve)."""
    from ingestion.models import Chunk, Revision
    from models.database import Document

    chunk = db.get(Chunk, chunk_id) if chunk_id else None
    if chunk is None:
        return None
    doc, rev = db.get(Document, chunk.document_id), db.get(Revision, chunk.document_id)
    if (chunk.document_id not in allowed_document_ids(db, [chunk.document_id], user=actor) or doc is None
            or doc.status != "indexed" or rev is None or not rev.is_current):
        return None
    return {"document_id": doc.id, "chunk_id": chunk.id, "title": doc.title, "content": chunk.content,
            "provenance": {**(rev.provenance or {}), **(chunk.provenance or {})}, "full_document": False}


def _record_source(db, scope, link, titles, people) -> dict | None:
    from models.compliance_graph import Control
    from services.compliance_graph import core

    when = link.reviewed_at.date().isoformat() if link.reviewed_at else "an earlier date"
    who = people.get(link.reviewed_by) or "your team"
    partly = "partly " if (link.attributes or {}).get("coverage") == "partial" else ""
    if link.relation == "addresses":
        control = db.get(Control, link.from_id)
        requirement = core.obligations_by_lineage(db, scope, [link.to_id]).get(link.to_id)
        if control is None or requirement is None:
            return None
        policy = titles.get(control.document_id)
        text = (f"Iroko record: {who} confirmed on {when} that the control “{control.name}”"
                f"{f' in {policy}' if policy else ''} {partly}addresses this requirement in "
                f"{titles.get(requirement.document_id, 'a regulation')}: “{requirement.quote[:400]}”.")
    elif link.relation == "evidences":
        if link.to_type == "control":
            control = db.get(Control, link.to_id)
            target = f"the control “{control.name}”" if control else None
        else:
            requirement = core.obligations_by_lineage(db, scope, [link.to_id]).get(link.to_id)
            target = f"the requirement “{requirement.quote[:300]}”" if requirement else None
        if target is None:
            return None
        attributes = link.attributes or {}
        period = " to ".join(p for p in (attributes.get("period_start"), attributes.get("period_end")) if p)
        text = (f"Iroko record: {who} confirmed on {when} that “{titles.get(link.from_id, 'a record')}”"
                f"{f' (covering {period})' if period else ''} {partly}is evidence for {target}.")
    else:
        return None
    return {"document_id": f"record:{scope.workspace_id}", "chunk_id": f"record:link:{link.id}",
            "title": "Iroko compliance record", "content": text, "full_document": False,
            "provenance": {"source_kind": "iroko_record", "record_url": f"/knowledge-graph?link={link.id}",
                           "relation": link.relation, "confirmed_on": when}}


def _expand(db, actor, question, context) -> dict:
    from models.compliance_graph import Link, Obligation
    from models.database import Document
    from services.compliance_graph import queries
    from services.compliance_graph.visibility import for_user, link_visible, obligation_visible

    scope = for_user(db, actor)
    sources = list(context.get("sources") or [])
    doc_ids = {s["document_id"] for s in sources if _is_internal(s.get("document_id"))}
    chunk_ids = {s["chunk_id"] for s in sources if _is_internal(s.get("chunk_id"))}
    if not doc_ids:
        return context
    seeds = (db.query(Obligation)
             .filter(or_(Obligation.chunk_id.in_(chunk_ids or {""}), Obligation.document_id.in_(doc_ids)),
                     obligation_visible(scope, Obligation, current=True))
             .limit(80).all())
    lineages = {o.lineage_id for o in seeds}
    first = (db.query(Link)
             .filter(link_visible(scope, Link), Link.relation.in_(CHAT_RELATIONS), Link.review_status != "rejected",
                     or_(and_(Link.from_type == "document", Link.from_id.in_(doc_ids)),
                         and_(Link.to_type == "document", Link.to_id.in_(doc_ids)),
                         and_(Link.to_type == "obligation", Link.to_id.in_(lineages or {""}))))
             .all())

    def usable(link):
        if link.review_status == "confirmed":
            return True
        return link.layer == "library" and link.basis == "stated" and link.review_status == "proposed"

    chosen = [link for link in first if usable(link)]
    pending = [link for link in first if not usable(link) and link.relation not in ("references",)]
    controls = {link.from_id for link in chosen if link.relation == "addresses"}
    if controls:
        second = (db.query(Link)
                  .filter(link_visible(scope, Link), Link.relation == "evidences", Link.to_type == "control",
                          Link.to_id.in_(controls), Link.review_status != "rejected").all())
        chosen += [link for link in second if link.review_status == "confirmed"]
        pending += [link for link in second if link.review_status != "confirmed"]

    titles = {d.id: d.title for d in db.query(Document).filter(Document.id.in_(
        {link.from_document_id for link in chosen} | {link.to_document_id for link in chosen}
        | {link.from_id for link in chosen if link.relation == "evidences"} | {""}))}
    people = queries.names(db, [link.reviewed_by for link in chosen])
    known = {s.get("chunk_id") for s in sources}
    passages, records = [], []
    order = {"addresses": 0, "evidences": 1, "amends": 2, "supersedes": 2, "revokes": 2, "extends_deadline_of": 2,
             "references": 3}
    for link in sorted(chosen, key=lambda item: order.get(item.relation, 9)):
        for anchor in link.anchors or []:
            chunk_id = anchor.get("chunk_id")
            if len(passages) < MAX_PASSAGES and chunk_id and chunk_id not in known:
                source = chunk_source(db, actor, chunk_id)
                if source is not None:
                    passages.append(source)
                    known.add(chunk_id)
        if link.layer == "workspace" and len(records) < MAX_RECORDS:
            record = _record_source(db, scope, link, titles, people)
            if record is not None and record["chunk_id"] not in known:
                records.append(record)
                known.add(record["chunk_id"])
    out = dict(context)
    out["sources"] = sources + passages + records
    if passages or records:
        out["knowledge_gap"] = False
        out["retrieval_status"] = "ok"
    out["graph"] = {"passages": len(passages), "records": len(records), "pending": len({p.id for p in pending})}
    return out


def pending_note(count: int) -> str:
    if not count:
        return ""
    noun = "suggested link about this awaits" if count == 1 else "suggested links about this await"
    return f"\n\n_{count} {noun} review in the [Knowledge Graph](/knowledge-graph?tab=review)._"


# ─── Records answers ─────────────────────────────────────────────────────────

KIND_ORDER = ("gaps", "re_review", "owners", "due", "trace", "review")


def records_answer(kinds, question: str) -> dict:
    actor = principal.get()
    if actor is None:
        return {"answer": "Sign in to see your organisation's compliance records.", "citations": [],
                "confidence": "low", "_grounded": True, "answer_status": "needs_clarification"}
    from ingestion.db import Session

    with Session() as db:
        return _records(db, actor, [k for k in KIND_ORDER if k in set(kinds or ())] or ["gaps"], question)


# Words that say what kind of records question it is, not what it is about. "Which requirements
# don't have supporting evidence?" must cover every requirement, not ones that mention "support".
_TOPIC_STOP_WORDS = """who what which when where how is are the a an of for to in on our my we us this that these those it its
owns own owner owners responsible handles handle due next coming up show trace traceability requirement requirements
obligation obligations control controls evidence records record review history chain and or please me tell list give
do does have has not without lack missing gap gaps need needs reviewing changed change what's
support supporting supported proof documentation documents document don dont doesn didn isn aren haven hasn
any all yet currently still now linked link links covered cover coverage mapped map confirmed confirm
cbn circular circulars letter letters regulation regulations rule rules iroko organisation organization institution
compliance compliant status latest current new recent recently""".split()


def _topic_stop() -> set:
    from services.compliance_graph.mapping import tokens

    return set(_TOPIC_STOP_WORDS) | set(tokens(" ".join(_TOPIC_STOP_WORDS)))  # tokens() stems words


def _topic_rows(question, rows):
    from services.compliance_graph.mapping import tokens

    stop = _topic_stop()
    words = [w for w in tokens(question) if w not in stop]
    if not words:
        return []
    scored = []
    for row in rows:
        haystack = set(tokens(" ".join(str(x or "") for x in (row["summary"], row["quote"], row["document"].get("title"),
                                                               row["document"].get("reference")))))
        score = sum(1 for w in words if w in haystack)
        if score:
            scored.append((score, row))
    if not scored:
        return []
    best = max(score for score, _r in scored)
    return [row for score, row in sorted(scored, key=lambda pair: -pair[0]) if score == best][:5]


def _requirement_citation(db, actor, row) -> dict | None:
    source = chunk_source(db, actor, row.get("chunk_id"))
    if source is None:
        return None
    return {"document_id": source["document_id"], "document_title": source["title"], "chunk_id": source["chunk_id"],
            "excerpt": row["quote"][:600], "provenance": source["provenance"]}


def _record_citation(scope, link_id, text) -> dict:
    return {"document_id": f"record:{scope.workspace_id}", "document_title": "Iroko compliance record",
            "chunk_id": f"record:link:{link_id}", "excerpt": text,
            "provenance": {"source_kind": "iroko_record", "record_url": f"/knowledge-graph?link={link_id}"}}


def _label(row) -> str:
    summary = row["summary"] or row["quote"][:160]
    return f"{summary} — *{row['document'].get('title') or 'a regulation'}*"


def _records(db, actor, kinds, question) -> dict:
    from services.compliance_graph import applicability, core, queries
    from services.compliance_graph.visibility import for_user

    scope = for_user(db, actor)
    rows = queries.requirement_rows(db, scope)
    applying = [r for r in rows if r["applicability"]["state"] in applicability.APPLYING_STATES]
    topic = _topic_rows(question, applying or rows)
    sections, citations, followups = [], [], []
    profile = core.profile(db, scope.workspace_id)
    if not profile["category_codes"]:
        sections.append("_Set your licence categories in the [Knowledge Graph](/knowledge-graph) so Iroko can tell "
                        "which requirements apply to you. Until then the lists below cover every requirement in "
                        "your library._")
        applying = rows

    def cite(row):
        c = _requirement_citation(db, actor, row)
        if c is not None and all(x.get("chunk_id") != c["chunk_id"] for x in citations):
            citations.append(c)

    for kind in kinds:
        if kind == "gaps":
            pool = topic or applying
            gaps = [r for r in pool if r["coverage"]["state"] in ("no_control_linked", "control_confirmed_no_evidence",
                                                                  "evidence_out_of_date", "control_suggested")]
            if not pool:
                sections.append("There are no requirements in your library yet. Upload regulations or ask the Iroko "
                                "team to share the regulator library with your workspace.")
                continue
            lines = [f"**Not established in Iroko's records:** {len(gaps)} of the {len(pool)} requirements "
                     f"{'that apply to your licence ' if profile['category_codes'] and not topic else ''}"
                     "have no confirmed control and evidence linked yet. This is not a compliance finding; it shows "
                     "what your records in Iroko do not yet cover."]
            for row in gaps[:8]:
                lines.append(f"- {_label(row)} ({row['coverage']['label'].lower()})")
                cite(row)
            if len(gaps) > 8:
                lines.append(f"- …and {len(gaps) - 8} more in the [requirements list]"
                             "(/knowledge-graph?tab=requirements&coverage=no_control_linked,control_confirmed_no_evidence,"
                             "evidence_out_of_date,control_suggested).")
            sections.append("\n".join(lines))
            followups.append("Which controls need reviewing after recent changes?")
        elif kind == "re_review":
            open_impacts = queries.impacts(db, scope, "open")
            flagged = [r for r in applying if r["coverage"]["state"] == "needs_re_review"]
            if not open_impacts and not flagged:
                sections.append("No recorded change currently needs your team to re-review a control or evidence link.")
                continue
            lines = ["**Changes that need a look:**"]
            for impact in open_impacts[:6]:
                controls = ", ".join(f"“{c['name']}”" for c in impact["controls"][:4])
                lines.append(f"- {impact['summary']}" + (f" Controls: {controls}." if controls else "")
                             + (f" {impact['flagged']} confirmed link(s) are marked for re-review." if impact["flagged"] else ""))
            for row in flagged[:6]:
                lines.append(f"- Re-review: {_label(row)}")
                cite(row)
            lines.append("Open the [Changes tab](/knowledge-graph?tab=changes) to compare old and new wording.")
            sections.append("\n".join(lines))
        elif kind == "owners":
            pool = topic or [r for r in applying if not (r["owner"]["user_id"] or r["owner"]["team"])]
            if topic:
                lines = ["**Who owns it, according to Iroko's records:**"]
                for row in topic[:3]:
                    owner = row["owner"]["name"] or row["owner"]["team"] or "no owner recorded in Iroko"
                    lines.append(f"- {_label(row)}: {owner}.")
                    cite(row)
            else:
                lines = [f"**{len(pool)}** requirement(s) that apply to you have no owner recorded in Iroko."]
                for row in pool[:6]:
                    lines.append(f"- {_label(row)}")
                    cite(row)
                lines.append("An admin can set owners from each requirement in the Knowledge Graph.")
            sections.append("\n".join(lines))
        elif kind == "due":
            due = queries.due_items(db, scope, days=30, rows=rows)
            items = due["items"]
            if topic:
                keys = {r["lineage_id"] for r in topic}
                items = [i for i in items if i.get("lineage_id") in keys] or items
            if not items and not due["event_driven"]:
                sections.append("Nothing in Iroko's records falls due in the next 30 days.")
                continue
            lines = ["**Due in the next 30 days (Lagos time):**"] if items else []
            kind_labels = {"requirement": "requirement", "return": "regulatory return", "effective": "takes effect",
                           "control_cycle": "evidence expected"}
            for item in items[:10]:
                when = f"overdue since {item['date']}" if item.get("overdue") else item["date"]
                lines.append(f"- {when}: {item['title']} ({kind_labels.get(item['kind'], item['kind'])})")
            if due["event_driven"]:
                lines.append(f"{len(due['event_driven'])} duty(ies) are triggered by events instead of dates, for "
                             f"example: {due['event_driven'][0]['description']}.")
            sections.append("\n".join(lines))
        elif kind == "trace":
            if not topic:
                chained = [r for r in applying if r["coverage"]["controls_confirmed"]][:5]
                lines = ["Which requirement should I trace? These have confirmed controls in Iroko:" if chained
                         else "Name the requirement to trace, for example “trace the BVN requirement”."]
                for row in chained:
                    lines.append(f"- {_label(row)}")
                sections.append("\n".join(lines))
                continue
            detail = queries.requirement_detail(db, scope, topic[0]["lineage_id"])
            row = topic[0]
            cite(row)
            lines = [f"**Requirement:** “{row['quote']}” — *{row['document'].get('title')}*"
                     + (f", page {row['page_number']}" if row["page_number"] else "")]
            controls = [link for link in detail["links"] if link["relation"] == "addresses"]
            evidence = [link for link in detail["links"] if link["relation"] == "evidences"]
            if not controls:
                lines.append("**Controls:** none confirmed in Iroko's records yet.")
            for link in controls:
                text = f"{link['from'].get('label') or 'A control'} — {link['status']['label']}"
                lines.append(f"**Control:** {text}")
                citations.append(_record_citation(scope, link["id"], text))
            for link in evidence:
                text = f"{link['from'].get('label') or 'A record'} — {link['status']['label']}"
                lines.append(f"**Evidence:** {text}")
                citations.append(_record_citation(scope, link["id"], text))
            for event in detail["history"][:4]:
                lines.append(f"- {event['at'][:10] if event['at'] else ''} {event['actor']}: {event['action'].replace('_', ' ')}"
                             + (f" ({event['note']})" if event["note"] else ""))
            lines.append(f"[Open the full chain](/knowledge-graph?requirement={row['lineage_id']})")
            sections.append("\n".join(lines))
        elif kind == "review":
            counts = queries.review_counts(db, scope)
            total = sum(counts.values())
            if not total:
                sections.append("Nothing is waiting for your review.")
                continue
            names = {"control_mappings": "control mappings", "evidence_links": "evidence links",
                     "controls": "controls found in your policies", "document_roles": "document roles",
                     "regulation_facts": "regulation relationships", "applicability": "addressee facts",
                     "effective_dates": "effective dates", "share_new_version": "newer versions to share"}
            parts = [f"{n} {names.get(k, k)}" for k, n in counts.items() if n]
            sections.append(f"**Waiting for review:** {', '.join(parts)}. Open the [Review tab](/knowledge-graph?tab=review).")
    answer = "\n\n".join(s for s in sections if s)
    return {"answer": answer, "citations": citations[:12], "confidence": "high", "_grounded": True,
            "knowledge_gap": False, "answer_status": "answered", "suggested_followups": followups[:3]}
