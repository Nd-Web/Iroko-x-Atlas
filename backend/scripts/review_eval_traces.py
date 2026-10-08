"""Turn evaluation traces into a review sheet and a failure-mode count (error analysis).

Looking at traces is the highest-value evaluation activity: read answers, note what went
wrong in free text (open coding), group notes into failure modes (axial coding), count them,
and fix the most frequent mode first. This script does the bookkeeping so a reviewer can
spend their time reading.

Run from backend:
  python scripts/review_eval_traces.py .dist/rag-evaluation/nano-*/results.json

Writes .dist/rag-evaluation/review-<time>.csv with one row per answer, the pipeline facts a
reviewer needs (status, which validation stage dropped claims, auditor issues), and empty
"pass" and "notes" columns for the reviewer. Prints automatic failure-mode counts. The
automatic modes describe the pipeline, not answer quality: only human review says whether an
answer is good.
"""

import csv
import glob
import json
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))
ARTIFACTS = BACKEND.parent / ".dist" / "rag-evaluation"


def pipeline_facts(record):
    """What happened inside the answer pipeline for one evaluated question."""
    from services.grounded_answers import validated_candidates

    result = record.get("result", {})
    trace = record.get("trace", {})
    facts = {"status": result.get("answer_status") or record.get("error_type", "error"),
             "missing": result.get("missing_information", []), "exact_drops": 0, "audit_rejections": 0,
             "verdict_count_mismatch": 0, "lead_shown": "**What the sources say**" in result.get("answer", ""),
             "audit_issues": []}
    contexts = trace.get("contexts") or []
    sources = {s["chunk_id"]: s for s in contexts[-1].get("sources", [])} if contexts else {}
    claims_in_last_draft = 0
    for raw in trace.get("grounding_outputs", []):
        try:
            output = json.loads(raw)
        except (TypeError, ValueError):
            continue
        if "supported_claims" in output:
            flags = output.get("supported_claims") or []
            if len(flags) != claims_in_last_draft:
                facts["verdict_count_mismatch"] += 1
            facts["audit_rejections"] += sum(flag is False for flag in flags)
            facts["audit_issues"].extend(str(issue)[:200] for issue in output.get("issues", []))
        elif "claims" in output:
            claims, calculations = validated_candidates({**output, "answerable": True}, sources, record["question"])
            facts["exact_drops"] += len(output.get("claims", [])) + len(output.get("calculations", [])) - len(claims) - len(calculations)
            claims_in_last_draft = len(claims)
    return facts


def failure_modes(facts):
    modes = []
    if facts["status"] == "needs_clarification":
        modes.append("routing: asked to clarify a complete question")
    if facts["status"] in {"reasoning_unavailable", "TimeoutError", "error"}:
        modes.append("capacity: model call failed or timed out")
    if facts["exact_drops"]:
        modes.append("drafting: claim failed exact quote/number checks")
    if facts["verdict_count_mismatch"]:
        modes.append("audit: verdict count did not match claims")
    if facts["audit_rejections"]:
        modes.append("audit: claim judged unsupported")
    if facts["status"] == "partial":
        modes.append("answer: partial (" + ", ".join(sorted(facts["missing"])) + ")")
    if facts["status"] in {"answered", "partial"} and not facts["lead_shown"]:
        modes.append("answer: no direct answer shown")
    return modes


def main(paths):
    records = []
    for pattern in paths or [str(ARTIFACTS / "nano-*" / "results.json")]:
        for path in sorted(glob.glob(pattern)):
            run = Path(path).parent.name
            records.extend({**record, "run": run} for record in json.loads(Path(path).read_text(encoding="utf-8")))
    counts, rows = Counter(), []
    for record in records:
        facts = pipeline_facts(record)
        modes = failure_modes(facts)
        counts.update(modes)
        rows.append({"run": record["run"], "case_id": record["case_id"], "question": record["question"],
                     "expected": record.get("expected", ""), "answer": record.get("result", {}).get("answer", ""),
                     "status": facts["status"], "automatic_modes": "; ".join(modes),
                     "audit_issues": " | ".join(facts["audit_issues"][:4]), "pass": "", "notes": ""})
    out = ARTIFACTS / f"review-{datetime.now():%Y%m%d-%H%M%S}.csv"
    with out.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    print(f"{len(rows)} answers from {len({r['run'] for r in rows})} run(s) -> {out}")
    for mode, count in counts.most_common():
        print(f"{count:4d}  {mode}")


if __name__ == "__main__":
    main(sys.argv[1:])
