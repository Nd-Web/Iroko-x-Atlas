"""Retrieval-only evaluation: synthetic questions per passage, measured with recall@k and MRR.

Answer quality and retrieval fail for different reasons, so they are measured separately.
For each extracted passage of the public CBN snapshot the model writes two questions the
passage answers: a "specific" one naming the document, and a "natural" one phrased the way a
compliance officer asks without knowing which document holds the answer. The real search
path (hybrid keyword + vector search, semantic reranking, permission checks) then has to
find that passage.

Run from backend:
  python scripts/evaluate_retrieval.py generate   # writes tests/evals/cbn_retrieval_questions.json
  python scripts/evaluate_retrieval.py run        # writes .dist/rag-evaluation/retrieval-*.json

Review generated questions before trusting them: a question its passage does not answer
measures nothing. Searches read the production index; every database read and write goes to
an isolated SQLite copy of the snapshot, exactly like evaluate_document_answers.py.
"""

import argparse
import asyncio
import json
import logging
import os
import sys
import tempfile
import time
from collections import defaultdict
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).resolve().parent))
import evaluate_document_answers as harness  # noqa: E402  (shared isolated setup)

QUESTIONS = harness.BACKEND / "tests" / "evals" / "cbn_retrieval_questions.json"
CUTOFFS = (1, 3, 5, 12, 20)

GENERATOR_PROMPT = """You write retrieval test questions for a compliance assistant used by
Nigerian microfinance banks and other financial institutions. You get ONE passage from a
regulatory document, plus the document's title and date for context. Write two questions
that THIS passage answers:
- specific: names the document, its date or its subject, as a user who knows the document would.
- natural: how a busy compliance officer would type it without knowing which document holds the
  answer. It must NOT mention any date, title, reference number, circular, letter or issuer, and
  must not start with a persona such as "As a compliance officer".
Each question must ask for a fact the passage actually states (a requirement, deadline,
recipient, amount, definition, scope or consequence) and must be answerable from this passage
alone. Never put the answer or candidate answers in the question (no "e.g." lists). Never copy
more than six consecutive words from the passage, never mention "the passage" or "this text",
and keep each question under 30 words. If the passage is boilerplate (addresses,
signatures, salutations, page headers, distribution lists) or states no answerable fact, set
skip to true and return no questions."""

GENERATOR_SCHEMA = {
    "type": "object",
    "properties": {
        "skip": {"type": "boolean"},
        "specific": {"type": "string"},
        "natural": {"type": "string"},
    },
    "required": ["skip", "specific", "natural"],
    "additionalProperties": False,
}


def load_corpus():
    return json.loads((harness.ARTIFACTS / "corpus.json").read_text(encoding="utf-8"))


async def generate(args):
    from agents.kernel import llm_complete

    corpus = load_corpus()
    titles = {d["id"]: d["title"] for d in corpus["documents"]}
    dates = {r["id"]: r["provenance"].get("published_date") for r in corpus["revisions"]}
    chunks = sorted(corpus["chunks"], key=lambda c: (c["document_id"], c["chunk_index"]))
    if args.limit:
        chunks = chunks[: args.limit]
    semaphore = asyncio.Semaphore(args.concurrency)
    questions, skipped, failed = [], [], []

    async def one(chunk):
        async with semaphore:
            payload = {"document_title": titles.get(chunk["document_id"], ""),
                       "published_date": dates.get(chunk["document_id"]), "passage": chunk["content"]}
            try:
                raw = await llm_complete(json.dumps(payload, ensure_ascii=False), system_prompt=GENERATOR_PROMPT,
                                         json_schema=GENERATOR_SCHEMA, max_tokens=300, service_id="nano")
                result = json.loads(raw)
            except Exception as exc:  # A failed generation is reported, never silently dropped.
                failed.append({"chunk_id": chunk["id"], "error_type": type(exc).__name__})
                return
            if result.get("skip"):
                skipped.append(chunk["id"])
                return
            for style in ("specific", "natural"):
                text = " ".join(str(result.get(style, "")).split())
                if 10 <= len(text) <= 300:
                    questions.append({"id": f"{chunk['id']}:{style}", "chunk_id": chunk["id"],
                                      "document_id": chunk["document_id"], "style": style, "question": text})

    await asyncio.gather(*(one(chunk) for chunk in chunks))
    questions.sort(key=lambda q: q["id"])
    QUESTIONS.write_text(json.dumps(questions, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(json.dumps({"passages": len(chunks), "questions": len(questions), "skipped_boilerplate": len(skipped),
                      "failed": len(failed), "written_to": str(QUESTIONS)}))


def rank_of(target, ranked):
    return ranked.index(target) + 1 if target in ranked else None


def summarise(rows):
    """Recall@k (did the target appear in the top k) and MRR, by passage and by document."""
    total = len(rows)
    summary = {"questions": total}
    for level in ("chunk", "document"):
        ranks = [row[f"{level}_rank"] for row in rows]
        summary[level] = {f"recall@{k}": round(sum(r is not None and r <= k for r in ranks) / total, 3) for k in CUTOFFS}
        summary[level]["mrr"] = round(sum(1 / r for r in ranks if r) / total, 3)
    return summary


async def run(args):
    corpus = load_corpus()
    questions = json.loads(QUESTIONS.read_text(encoding="utf-8"))
    if args.limit:
        questions = questions[: args.limit]
    run_dir = Path(tempfile.mkdtemp(prefix="retrieval-", dir=harness.ARTIFACTS))
    harness.setup_local(corpus, run_dir)
    from agents.researcher import ResearcherAgent
    from ingestion.access import Principal, as_user

    owner = Principal("evaluation-owner", "admin")  # A plain value, never a detached ORM row.
    semaphore = asyncio.Semaphore(args.concurrency)
    rows = []

    async def one(question):
        async with semaphore:
            started = time.monotonic()
            with as_user(owner):
                found = json.loads(await ResearcherAgent().search_documents(query=question["question"], top_k=max(CUTOFFS)))
            results = found.get("results", [])
            chunks = [r["chunk_id"] for r in results]
            documents = list(dict.fromkeys(r["document_id"] for r in results))
            rows.append({**question, "status": found.get("retrieval_status"),
                         "chunk_rank": rank_of(question["chunk_id"], chunks),
                         "document_rank": rank_of(question["document_id"], documents),
                         "top_titles": [r.get("title") for r in results[:3]],
                         "seconds": round(time.monotonic() - started, 2)})

    await asyncio.gather(*(one(q) for q in questions))
    rows.sort(key=lambda r: r["id"])
    by_style = defaultdict(list)
    for row in rows:
        by_style[row["style"]].append(row)
    report = {
        "captured_at": datetime.now().isoformat(),
        "search_unavailable": sum(row["status"] != "ok" for row in rows),
        "overall": summarise(rows),
        "by_style": {style: summarise(items) for style, items in sorted(by_style.items())},
        "document_misses_at_12": [
            {k: row[k] for k in ("id", "question", "document_rank", "top_titles")}
            for row in rows if not row["document_rank"] or row["document_rank"] > 12
        ],
        "rows": rows,
    }
    out = harness.ARTIFACTS / f"retrieval-{datetime.now():%Y%m%d-%H%M%S}.json"
    harness.save(out, report)
    print(json.dumps({k: report[k] for k in ("search_unavailable", "overall", "by_style")}, indent=1))
    print(json.dumps({"document_misses_at_12": len(report["document_misses_at_12"]), "report": str(out)}))


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("command", choices=["generate", "run"])
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--concurrency", type=int, choices=[1, 2, 3, 4], default=3)
    args = parser.parse_args()
    load_dotenv(harness.BACKEND / ".env", override=True)
    logging.disable(logging.CRITICAL)
    if args.command == "generate":
        # Generation reads only the snapshot file; it never opens a database session.
        os.environ["DATABASE_URL"] = "sqlite://"
        asyncio.run(generate(args))
    else:
        asyncio.run(run(args))


if __name__ == "__main__":
    main()
