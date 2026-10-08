"""Build/review/evaluate Iroko candidates. No database, search, or training-job calls.

From backend:
  python scripts/chat_dataset.py build
  python scripts/chat_dataset.py validate
  python scripts/chat_dataset.py evaluate --limit 40
  python scripts/chat_dataset.py evaluate --live --limit 12
  python scripts/chat_dataset.py export --reviews path/to/reviews.json --output path/to/train.jsonl
"""
import argparse
import asyncio
from collections import Counter, defaultdict, deque
from datetime import datetime, timezone
import hashlib
import json
import logging
from pathlib import Path
import sys
import time

BACKEND = Path(__file__).resolve().parents[1]
ROOT = BACKEND.parent
sys.path.insert(0, str(BACKEND))
from evaluation.chat_dataset import build, check_result, export_approved, read_cases, review_page, validate, write_dataset

DEFAULT_FOLDER = ROOT / ".dist" / "chat-dataset" / "v1"


def select_cases(rows, split, limit, families):
    """Sample categories and families before their phrasing variants."""
    buckets = defaultdict(lambda: defaultdict(deque))
    for row in rows:
        if row["split"] == split and (not families or row["family"] in families):
            buckets[row["category"]][row["family"]].append(row)
    selected = []
    while len(selected) < limit:
        # Complete one family round before sampling another phrasing. Otherwise a
        # small category repeats variants while larger categories remain untested.
        ordered = {category: deque(groups[family].popleft() for family in sorted(groups) if groups[family])
                   for category, groups in sorted(buckets.items())}
        if not any(ordered.values()):
            break
        while any(ordered.values()) and len(selected) < limit:
            for values in ordered.values():
                if values and len(selected) < limit:
                    selected.append(values.popleft())
    return selected


async def evaluate_case(case, complete=None):
    # Imports are deliberately delayed until after the offline-only build/validate path.
    from services.chat_conversation import recall_answer, social_answer
    from services.chat_intent import conversational_reply
    from services.chat_router import route_question
    from services.grounded_answers import answer

    question, history = case["messages"][-1]["content"], case["history"]
    task = case["task"]
    if task == "grounding":
        # This stage receives an already selected passage; routing without that
        # selection would incorrectly judge 'this document' as an unknown referent.
        if complete is None:
            return {"reason": "Model execution was not requested"}, "needs_model", True
        return await answer(question, {"sources": case["evidence"], "knowledge_gap": not case["evidence"]},
                            complete, answer_mode="helpful"), "provided_evidence_answering", False
    if task in {"unavailable", "empty", "access_check_failed"}:
        return await answer(question, {"sources": [], "knowledge_gap": True, "retrieval_status": task},
                            complete, answer_mode="helpful"), "availability", False
    route = await route_question(question, history, complete)
    if task == "routing":
        return route, "routing", False
    if task != "grounding":
        if route["intent"] == "greeting":
            result = conversational_reply(route["conversational_kind"], question=question)
            return {**result, "answer_status": "conversational"}, "conversation", False
        if route["intent"] == "conversation_recall":
            return recall_answer(question, history), "memory", False
        if route["intent"] == "clarification":
            return {"answer": route["clarification"], "answer_status": "needs_clarification", "citations": []}, "routing", False
        if route["intent"] == "social" and complete:
            result = await social_answer(question, history, complete)
            if result is not None:
                return result, "conversation", False
    if complete is None:
        return {"intent": route["intent"], "reason": "Model execution was not requested"}, "needs_model", True
    context = {"sources": case["evidence"], "knowledge_gap": not case["evidence"]}
    result = await answer(route.get("query") or question, context, complete, answer_mode="helpful",
                          conversation_context=route.get("conversation_context"))
    return result, "provided_evidence_answering", False


async def evaluate(args, rows):
    complete = None
    calls, output_allowance = 0, 0
    if args.live:
        # Environment values stay local. No environment file is changed or exported.
        from dotenv import load_dotenv
        load_dotenv(BACKEND / ".env", override=True)
        from agents.kernel import llm_complete

        async def bounded_complete(*pos, **kw):
            nonlocal calls, output_allowance
            if calls >= args.max_model_calls:
                raise RuntimeError("Evaluation model-call budget exhausted")
            calls += 1
            output_allowance += kw.get("max_tokens", 1000)
            return await llm_complete(*pos, **kw)
        complete = bounded_complete
    selected = select_cases(rows, args.split, args.limit, args.family)
    if not selected:
        raise ValueError("No cases matched the requested split/families")
    records = []
    for case in selected:
        if args.live and calls >= args.max_model_calls:
            records.append({"id": case["id"], "category": case["category"], "skipped": True, "failures": [], "stage": "budget_exhausted"})
            continue
        started = time.monotonic()
        try:
            result, stage, skipped = await asyncio.wait_for(evaluate_case(case, complete), timeout=100)
        except Exception as exc:
            result, stage, skipped = {"error": type(exc).__name__}, "execution_error", False
        failures = [] if skipped else check_result(case, result)
        record = {"id": case["id"], "case_sha256": case["case_sha256"], "category": case["category"],
            "stage": stage, "skipped": skipped, "failures": failures,
            "seconds": round(time.monotonic() - started, 2), "question": case["messages"][-1]["content"],
            "answer": result.get("answer", ""), "answer_status": result.get("answer_status"),
            "citations": result.get("citations", []), "missing_information": result.get("missing_information", []),
            "human_review": "pending"}
        records.append(record)
        if args.live or failures:
            print(json.dumps({"id": case["id"], "stage": stage, "skipped": skipped, "failures": failures}), flush=True)
    measured = [r for r in records if not r["skipped"]]
    report = {"created_at": datetime.now(timezone.utc).isoformat(), "split": args.split, "live": args.live,
        "selected": len(records), "mechanically_passed": sum(not r["failures"] for r in measured),
        "measured": len(measured), "skipped": len(records) - len(measured), "model_calls": calls,
        "requested_output_token_allowance": output_allowance,
        "scope": "Component checks with supplied evidence; not production retrieval, latency, or expert accuracy certification.",
        "failure_categories": dict(Counter(r["category"] for r in measured if r["failures"])), "records": records}
    path = args.folder / f"evaluation-{'live' if args.live else 'offline'}-{datetime.now(timezone.utc):%Y%m%d-%H%M%S}.json"
    path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({**{k: report[k] for k in ("selected", "mechanically_passed", "measured", "skipped", "model_calls", "failure_categories")}, "report": str(path)}))
    return 1 if any(r["failures"] for r in measured) else 0


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("command", choices=["build", "validate", "review", "evaluate", "export"])
    parser.add_argument("--folder", type=Path, default=DEFAULT_FOLDER)
    parser.add_argument("--corpus", type=Path, default=ROOT / ".dist/rag-evaluation/corpus.json")
    parser.add_argument("--questions", type=Path, default=BACKEND / "tests/evals/cbn_retrieval_questions.json")
    parser.add_argument("--split", choices=["development", "holdout"], default="development")
    parser.add_argument("--limit", type=int, default=40)
    parser.add_argument("--family", action="append", default=[])
    parser.add_argument("--live", action="store_true", help="Use the locally configured model; incurs API usage")
    parser.add_argument("--max-model-calls", type=int, default=40)
    parser.add_argument("--reviews", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if not 1 <= args.limit <= 600 or not 1 <= args.max_model_calls <= 200:
        parser.error("limit must be 1..600 and model calls 1..200")
    logging.disable(logging.CRITICAL)
    try:
        if args.command == "build":
            raw = args.corpus.read_bytes()
            rows = build(json.loads(raw), json.loads(args.questions.read_text(encoding="utf-8")))
            if dict(Counter(r["split"] for r in rows)) != {"development": 500, "holdout": 100}:
                raise ValueError("Unexpected split counts")
            manifest = write_dataset(args.folder, rows, hashlib.sha256(raw).hexdigest())
            review_page(rows, args.folder / "review.html")
            print(json.dumps(manifest, indent=2))
            return 0
        rows = read_cases(args.folder)
        summary = validate(rows)
        if args.command == "validate":
            print(json.dumps(summary, indent=2))
        elif args.command == "review":
            review_page(rows, args.folder / "review.html")
            print(str(args.folder / "review.html"))
        elif args.command == "evaluate":
            return asyncio.run(evaluate(args, rows))
        else:
            if not args.reviews or not args.output:
                parser.error("export requires --reviews and --output")
            approved = export_approved(rows, json.loads(args.reviews.read_text(encoding="utf-8")))
            if not approved:
                raise ValueError("No approved training examples; review candidates first")
            # Never overwrite a prior export silently.
            with args.output.open("x", encoding="utf-8") as handle:
                handle.write("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in approved))
            print(json.dumps({"exported": len(approved), "path": str(args.output), "training_job_started": False}))
        return 0
    except (OSError, ValueError, KeyError) as exc:
        parser.exit(2, f"Dataset operation failed ({type(exc).__name__}): {exc}\n")


if __name__ == "__main__":
    raise SystemExit(main())
