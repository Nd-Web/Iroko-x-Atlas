"""Export users' answer feedback for review: the data flywheel's intake.

Each thumbs-down with a reason is a candidate evaluation case. A reviewer (one domain
expert who owns the quality bar) reads it, writes what the answer should have said, and
moves good cases into tests/evals/. Thumbs-up answers are kept as candidate examples.

Run from backend, against the database you mean to read:
  python scripts/export_answer_feedback.py [--since 2026-10-01]

Reads only. Output contains customer questions and answers, so it is written under the
git-ignored .dist/feedback/ directory; handle it like any other customer record.
"""

import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))
OUT = BACKEND.parent / ".dist" / "feedback"


def collect(db, since=None):
    """Feedback rows joined with the answer, the question it answered and nearby context."""
    from models.database import AnswerFeedback, Message

    query = db.query(AnswerFeedback).order_by(AnswerFeedback.updated_at)
    if since:
        query = query.filter(AnswerFeedback.updated_at >= since)
    rows = []
    for feedback in query:
        answer = db.get(Message, feedback.message_id)
        if answer is None:
            continue
        earlier = (db.query(Message).filter(Message.conversation_id == answer.conversation_id,
                                            Message.created_at <= answer.created_at, Message.id != answer.id)
                   .order_by(Message.created_at.desc()).limit(5).all())
        question = next((m.content for m in earlier if m.role == "user"), "")
        trace = answer.agent_trace or []
        resolved = next((s.get("resolved_question") for s in trace
                         if isinstance(s, dict) and s.get("tool") == "conversation_context"), None)
        outcome = next((s for s in trace if isinstance(s, dict) and s.get("tool") == "answer_outcome"), {})
        rows.append({
            "message_id": answer.id, "conversation_id": answer.conversation_id,
            "helpful": feedback.helpful, "reason": feedback.reason, "comment": feedback.comment,
            "rated_at": feedback.updated_at.isoformat() if feedback.updated_at else None,
            "question": question, "resolved_question": resolved,
            "earlier_turns": [{"role": m.role, "content": m.content[:600]} for m in reversed(earlier[1:])],
            "answer": answer.content, "answer_status": outcome.get("answer_status"),
            "cited_documents": sorted({c.get("document_title") or c.get("document_id") or "" for c in (answer.citations or [])
                                       if isinstance(c, dict)} - {""}),
        })
    return rows


def eval_candidates(rows):
    """Thumbs-down answers in the evaluation-case shape, with blanks for the reviewer."""
    return [{
        "id": f"feedback_{row['message_id'][:12]}",
        "question": row["resolved_question"] or row["question"],
        "expected": row["comment"] or "",
        "required_patterns": [],
        "sources": [],
        "feedback_reason": row["reason"],
        "observed_answer": row["answer"],
        "review_status": "needs_review",
    } for row in rows if row["helpful"] is False]


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--since", type=datetime.fromisoformat, default=None)
    args = parser.parse_args()
    from dotenv import load_dotenv
    load_dotenv(BACKEND / ".env")
    from sqlalchemy import text
    from models.database import SessionLocal

    with SessionLocal() as db:
        if db.get_bind().dialect.name == "postgresql":
            db.execute(text("SET TRANSACTION READ ONLY"))
        rows = collect(db, args.since)
        db.rollback()
    OUT.mkdir(parents=True, exist_ok=True)
    stamp = f"{datetime.now():%Y%m%d-%H%M%S}"
    (OUT / f"feedback-{stamp}.jsonl").write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows),
                                                  encoding="utf-8")
    candidates = eval_candidates(rows)
    (OUT / f"eval-candidates-{stamp}.json").write_text(json.dumps(candidates, ensure_ascii=False, indent=1),
                                                       encoding="utf-8")
    helpful = sum(r["helpful"] for r in rows)
    print(json.dumps({"feedback": len(rows), "helpful": helpful, "not_helpful": len(rows) - helpful,
                      "eval_candidates": len(candidates), "output": str(OUT),
                      "database": os.environ.get("DATABASE_URL", "").split("@")[-1][:60]}))


if __name__ == "__main__":
    main()
