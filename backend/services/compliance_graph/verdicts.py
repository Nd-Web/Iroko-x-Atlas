"""
Whether the rule a compliance verdict rests on is still the current rule.

Flags only. A confirmed revocation or supersession of the deciding instrument
turns GO into MONITOR; an amendment (stated in the source or confirmed) or a
future effective date adds a flag. This never produces GO and never softens a
NO-GO.
"""

from __future__ import annotations

from models.compliance_graph import GraphDocument, Link
from models.database import Document
from services.compliance_graph.common import enabled, lagos_today
from services.compliance_graph.visibility import for_user, link_visible


def rule_status(db, scope, document_id: str) -> dict:
    links = (db.query(Link)
             .filter(Link.to_type == "document", Link.to_id == document_id,
                     Link.relation.in_(("amends", "supersedes", "revokes")), Link.review_status != "rejected",
                     link_visible(scope, Link))
             .all())
    titles = {d.id: d.title for d in db.query(Document).filter(Document.id.in_({link.from_id for link in links} | {""}))}
    replaced = [titles.get(link.from_id, "a later instrument") for link in links
                if link.relation in ("revokes", "supersedes") and link.review_status == "confirmed"]
    amended = [titles.get(link.from_id, "a later instrument") for link in links
               if link.relation == "amends" and (link.review_status == "confirmed" or link.basis == "stated")]
    gd = db.get(GraphDocument, document_id)
    future = None
    if gd is not None and gd.effective_date and gd.effective_basis in ("stated", "confirmed") \
            and gd.effective_date > lagos_today():
        future = gd.effective_date
    return {"replaced_by": replaced, "amended_by": amended, "takes_effect": future}


def apply_rule_status(db, user, assessment: dict, result: dict) -> dict:
    if not enabled():
        return result
    document_id = (assessment.get("evidence") or {}).get("document_id")
    if not document_id:
        return result
    status = rule_status(db, for_user(db, user), document_id)
    flags = list(result.get("flags") or [])
    out = dict(result)
    if status["replaced_by"]:
        flags.append("The instrument this rule comes from was revoked or replaced by "
                     + ", ".join(f"“{t}”" for t in status["replaced_by"])
                     + " (confirmed in Iroko's library). Check the current rule before relying on this.")
        if out.get("verdict") == "GO":
            out["verdict"] = "MONITOR"
            out["confidence"] = min(float(out.get("confidence") or 0.5), 0.5)
    if status["amended_by"]:
        flags.append("The instrument this rule comes from has been amended by "
                     + ", ".join(f"“{t}”" for t in status["amended_by"]) + ". Check the amended text.")
    if status["takes_effect"]:
        flags.append(f"This rule takes effect on {status['takes_effect'].isoformat()}; it is not yet in force.")
    out["flags"] = flags
    return out
