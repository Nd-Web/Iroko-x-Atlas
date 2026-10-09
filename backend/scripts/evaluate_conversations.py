"""Multi-turn conversation evaluation: realistic chats, checked turn by turn.

The single-question suite names the document in every question; real users do not. These
scenarios (tests/evals/conversation_scenarios.json) cover natural and vague phrasing,
follow-ups, topic switches, the document library, questions the documents cannot answer,
out-of-scope requests, implications, comparisons and Pidgin. Each turn is sent through the
real chat API with the conversation id of the turn before, exactly as the UI does.

Checks are deterministic (code beats a model judge when a rule can decide):
  intent_in       the router's intent must be one of these
  must_match      every regex must appear in the answer (case-insensitive)
  must_not_match  no regex may appear (e.g. an invented naira figure)
  must_cite       at least one citation title must contain one of these strings

A failed conversation reports its FIRST failing turn: errors compound, so the earliest
failure is the one to fix. Run from backend:
  python scripts/evaluate_conversations.py run [--scenario ID] [--concurrency 2]
Writes .dist/rag-evaluation/conversations-<time>.json. Nothing touches production data.
"""

import argparse
import asyncio
import json
import logging
import re
import sys
import tempfile
import time
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).resolve().parent))
import evaluate_document_answers as harness  # noqa: E402  (shared isolated setup)

SCENARIOS = harness.BACKEND / "tests" / "evals" / "conversation_scenarios.json"


def check_turn(spec, result):
    """Failed check descriptions for one turn; an empty list means the turn passed."""
    # Check text as users see it: literal Markdown escaping is not a missing name.
    answer = re.sub(r"\\([\\`*_{}\[\]<>#+.!|~-])", r"\1", result.get("answer", ""))
    steps = result.get("agent_trace", [])
    intent = next((s.get("intent") for s in steps if s.get("tool") == "intent"), None)
    titles = [c.get("document_title", "") for c in result.get("citations", [])]
    failures = []
    if spec.get("intent_in") and intent not in spec["intent_in"]:
        failures.append(f"intent was {intent}, expected {'/'.join(spec['intent_in'])}")
    for pattern in spec.get("must_match", []):
        if not re.search(pattern, answer, re.I):
            failures.append(f"answer lacks /{pattern}/")
    for pattern in spec.get("must_not_match", []):
        if re.search(pattern, answer, re.I):
            failures.append(f"answer contains forbidden /{pattern}/")
    if spec.get("must_cite") and not any(want.lower() in title.lower() for want in spec["must_cite"] for title in titles):
        failures.append(f"no citation from {' or '.join(spec['must_cite'])}")
    if spec.get("no_citations") and titles:
        failures.append("unexpected citations")
    if spec.get("status_in") and result.get("answer_status") not in spec["status_in"]:
        failures.append(f"unexpected status: {result.get('answer_status')}")
    if spec.get("max_words") and len(answer.split()) > spec["max_words"]:
        failures.append("answer exceeds word limit")
    if not answer.strip():
        failures.append("empty answer")
    if result.get("answer_status") in {"reasoning_unavailable", "validation_failed"}:
        failures.append("answer could not be completed")
    return failures, intent


async def run(args):
    import httpx
    from fastapi import FastAPI

    corpus = json.loads((harness.ARTIFACTS / "corpus.json").read_text(encoding="utf-8"))
    scenarios = json.loads(args.scenarios.read_text(encoding="utf-8"))
    if args.scenario:
        scenarios = [s for s in scenarios if s["id"] in args.scenario]
    if not scenarios:
        raise ValueError("No matching scenarios")
    if sum(len(s["turns"]) for s in scenarios) > args.max_turns:
        raise ValueError("Selected scenarios exceed the explicit turn budget")
    run_dir = Path(tempfile.mkdtemp(prefix="conversations-", dir=harness.ARTIFACTS))
    SessionLocal = harness.setup_local(corpus, run_dir)
    from models.database import engine
    assert engine.url.get_backend_name() == "sqlite", "Stress tests require isolated SQLite"
    from agents import kernel
    original_complete = kernel.llm_complete
    model_calls = 0

    async def bounded_complete(*pos, **kw):
        nonlocal model_calls
        if model_calls >= args.max_model_calls:
            raise RuntimeError("Evaluation model-call budget exhausted")
        model_calls += 1
        return await original_complete(*pos, **kw)

    kernel.llm_complete = bounded_complete
    from ingestion.access import as_user
    from models.database import User, get_db
    from routes import ask as ask_route
    from services.auth_utils import get_current_user

    harness.install_observers()
    app = FastAPI()
    app.include_router(ask_route.router)

    def db_dependency():
        with SessionLocal() as db:
            yield db

    async def user_dependency():
        with SessionLocal() as db:
            user = db.get(User, "evaluation-owner")
            with as_user(user):
                yield user

    app.dependency_overrides[get_db] = db_dependency
    app.dependency_overrides[get_current_user] = user_dependency
    ask_route._check_rate_limit = lambda user_id: True
    semaphore = asyncio.Semaphore(args.concurrency)
    records = []

    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://evaluation.local") as client:

        async def one(scenario):
            async with semaphore:
                conversation_id, turns = None, []
                for index, spec in enumerate(scenario["turns"]):
                    trace = {}
                    token = harness.case_trace.set(trace)
                    started = time.monotonic()
                    try:
                        response = await asyncio.wait_for(client.post(
                            "/api/atlas/ask/stream-http" if args.stream else "/api/atlas/ask",
                            json={"query": spec["user"], "conversation_id": conversation_id}), timeout=150)
                        if args.stream and response.status_code == 200:
                            events = [json.loads(line[6:]) for line in response.text.splitlines()
                                      if line.startswith("data: ") and line[6:] != "[DONE]"]
                            result = next((event for event in reversed(events) if event.get("type") == "complete"), {"error": "MissingStreamCompletion"})
                            if any(event.get("type") == "error" for event in events):
                                result = {"error": "StreamError"}
                            elif "error" not in result and "".join(e.get("content", "") for e in events if e.get("type") == "token") != result.get("answer"):
                                result = {"error": "StreamTokenMismatch"}
                        else:
                            result = response.json() if response.status_code == 200 else {"error": f"HTTP {response.status_code}"}
                    except Exception as exc:  # Never record exception text: it can include configuration.
                        result = {"error": type(exc).__name__}
                    finally:
                        harness.case_trace.reset(token)
                    conversation_id = result.get("conversation_id", conversation_id)
                    failures, intent = check_turn(spec, result) if "error" not in result else ([result["error"]], None)
                    turns.append({"turn": index + 1, "user": spec["user"], "intent": intent,
                                  "resolved_question": next((s.get("resolved_question") for s in result.get("agent_trace", [])
                                                             if s.get("tool") == "conversation_context"), None),
                                  "status": result.get("answer_status"), "seconds": round(time.monotonic() - started, 1),
                                  "failures": failures, "answer": result.get("answer", ""),
                                  "citations": [c.get("document_title") for c in result.get("citations", [])],
                                  "agent_trace": result.get("agent_trace", []),
                                  "source_checks": result.get("source_checks", []),
                                  "trace": trace})
                    print(json.dumps({"scenario": scenario["id"], "turn": index + 1, "failures": failures}), flush=True)
                if conversation_id:
                    saved = await client.get(f"/api/atlas/conversations/{conversation_id}/messages")
                    persisted = saved.json().get("messages", []) if saved.status_code == 200 else []
                    if len(persisted) != len(turns) * 2:
                        turns[-1]["failures"].append("conversation history persistence mismatch")
                first = next((t for t in turns if t["failures"]), None)
                records.append({"id": scenario["id"], "category": scenario["category"], "passed": first is None,
                                "first_failure": {k: first[k] for k in ("turn", "user", "failures")} if first else None,
                                "turns": turns})
                print(json.dumps({"scenario": scenario["id"], "passed": first is None,
                                  "first_failure": first["failures"] if first else None}), flush=True)

        await asyncio.gather(*(one(s) for s in scenarios))
    records.sort(key=lambda r: r["id"])
    by_category = defaultdict(Counter)
    for record in records:
        by_category[record["category"]]["passed" if record["passed"] else "failed"] += 1
    turns = [t for r in records for t in r["turns"]]
    latencies = sorted(t["seconds"] for t in turns)
    report = {
        "captured_at": datetime.now().isoformat(),
        "model_calls": model_calls,
        "transport": "sse" if args.stream else "json",
        "latency_seconds": {"median": latencies[len(latencies) // 2], "max": max(latencies)},
        "scope": "Real local chat API, isolated SQLite, live configured model/search; not production load certification.",
        "conversations_passed": f"{sum(r['passed'] for r in records)}/{len(records)}",
        "turns_passed": f"{sum(not t['failures'] for t in turns)}/{len(turns)}",
        "by_category": {k: dict(v) for k, v in sorted(by_category.items())},
        "first_failures": [{"id": r["id"], **r["first_failure"]} for r in records if not r["passed"]],
        "records": records,
    }
    out = harness.ARTIFACTS / f"conversations-{datetime.now():%Y%m%d-%H%M%S}.json"
    harness.save(out, report)
    print(json.dumps({k: report[k] for k in ("conversations_passed", "turns_passed", "by_category")}, indent=1))
    print(json.dumps({"report": str(out)}))
    return 1 if any(t["failures"] for t in turns) else 0


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("command", choices=["run"])
    parser.add_argument("--scenario", action="append", default=[], help="Run only these scenario ids")
    parser.add_argument("--concurrency", type=int, choices=[1, 2, 3], default=2)
    parser.add_argument("--scenarios", type=Path, default=SCENARIOS)
    parser.add_argument("--configured-model", action="store_true", help="Explicitly test the locally configured model (API usage)")
    parser.add_argument("--stream", action="store_true", help="Exercise the UI's SSE endpoint and verify token/completion consistency")
    parser.add_argument("--max-turns", type=int, default=100)
    parser.add_argument("--max-model-calls", type=int, default=180)
    args = parser.parse_args()
    load_dotenv(harness.BACKEND / ".env", override=True)
    logging.disable(logging.CRITICAL)
    import os
    if not 1 <= args.max_turns <= 200 or not 1 <= args.max_model_calls <= 500:
        parser.error("max-turns must be 1..200; max-model-calls must be 1..500")
    if not args.configured_model and (os.getenv("AZURE_OPENAI_DEPLOYMENT") != "gpt-5.4-nano" or os.getenv("AZURE_OPENAI_RESPONSES_ENDPOINT")):
        parser.error("Evaluations run on the configured nano Chat Completions test model, never production's model")
    sys.exit(asyncio.run(run(args)))


if __name__ == "__main__":
    main()
