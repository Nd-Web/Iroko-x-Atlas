"""Known-answer check of the compliance engine (POST /api/v1/compliance/check).

Runs on the isolated SQLite copy of the CBN snapshot made by
`python scripts/evaluate_document_answers.py snapshot`; the shared search index is
only read and nothing reaches the production database.

Run from backend: python scripts/evaluate_compliance_verdicts.py [--case-id ID ...]

Each case states the real-world answer ("truth") and whether the governing rule is
in the snapshot ("covered"). Grades:
  correct      verdict is acceptable for the truth
  unverified   the engine said it could not verify (safe; the rule is missing from the library)
  UNSAFE       a violation was cleared with GO
  FALSE ALARM  a permitted action was blocked with NO-GO
  cautious     a permitted action got MONITOR
"""

import argparse
import asyncio
import json
import logging
import os
import sys
import tempfile
from pathlib import Path

from dotenv import load_dotenv

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))
sys.path.insert(0, str(BACKEND / "scripts"))
CASES = BACKEND / "tests" / "evals" / "compliance_verdict_cases.json"


def grade(case, response):
    verdict = response.get("verdict")
    accept = case.get("accept") or [case["truth"]]
    unverified = verdict == "MONITOR" and "Not covered by Iroko's regulation library" in response.get("flags", [])
    if unverified:
        return "unverified" if case["truth"] != "GO" else "cautious"
    if verdict in accept:
        return "correct"
    if verdict == "GO":
        return "UNSAFE"
    if case["truth"] == "GO":
        return "FALSE ALARM" if verdict == "NO-GO" else "cautious"
    return "wrong"


async def run(case_ids):
    import evaluate_document_answers as harness

    cases = json.loads(CASES.read_text(encoding="utf-8"))
    if case_ids:
        cases = [c for c in cases if c["id"] in case_ids]
    corpus = json.loads((harness.ARTIFACTS / "corpus.json").read_text(encoding="utf-8"))
    run_dir = Path(tempfile.mkdtemp(prefix="verdicts-", dir=harness.ARTIFACTS))
    SessionLocal = harness.setup_local(corpus, run_dir)

    import httpx
    from fastapi import FastAPI

    from models.database import User, engine, get_db
    from routes import compliance_api

    if not str(engine.url).startswith("sqlite"):
        raise RuntimeError("Refusing to run: the application database is not the isolated SQLite copy")

    # Observe which passages each check retrieved (for error analysis); behaviour is unchanged.
    from agents.watchdog import WatchdogAgent

    retrieved = []
    assessed = {}
    search, assess = WatchdogAgent._search_documents, WatchdogAgent.assess_proposed_action

    async def observed_search(self, query, doc_type=None, top_k=8):
        results = await search(self, query, doc_type=doc_type, top_k=top_k)
        retrieved[:] = [r.get("title", "") for r in results or []]
        return results

    async def observed_assess(self, *args, **kwargs):
        result = await assess(self, *args, **kwargs)
        assessed.clear()
        assessed.update({k: result.get(k) for k in ("assessment", "unverified_rule", "basis")})
        return result

    WatchdogAgent._search_documents = observed_search
    WatchdogAgent.assess_proposed_action = observed_assess

    app = FastAPI()
    app.include_router(compliance_api.router, prefix="/api/v1")

    def db_dependency():
        with SessionLocal() as db:
            yield db

    def user_dependency():
        with SessionLocal() as db:
            return db.get(User, "evaluation-owner")

    app.dependency_overrides[get_db] = db_dependency
    app.dependency_overrides[compliance_api._optional_jwt_user] = user_dependency

    rows = []
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://eval", timeout=180) as client:
        for case in cases:
            retrieved.clear()
            response = await client.post("/api/v1/compliance/check", json={"text": case["text"], "sector": "financial"})
            body = response.json()
            result = grade(case, body) if response.status_code == 200 else f"error {response.status_code}"
            rows.append({**case, "grade": result, "response": body, "retrieved": list(retrieved),
                         "assessment": dict(assessed)})
            why = "quote not found" if assessed.get("unverified_rule") else assessed.get("assessment", "")
            print(f"{result:12} truth {case['truth']:5} got {body.get('verdict', '-'):7} {case['id']:26} {why}", flush=True)

    totals = {}
    for row in rows:
        totals[row["grade"]] = totals.get(row["grade"], 0) + 1
    print(json.dumps(totals))
    out = run_dir / "verdicts.json"
    out.write_text(json.dumps(rows, indent=1, ensure_ascii=False), encoding="utf-8")
    print("trace:", out)


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--case-id", action="append", default=[])
    args = parser.parse_args()
    load_dotenv(BACKEND / ".env", override=True)
    logging.disable(logging.CRITICAL)
    # Evaluations run on the nano Chat Completions test deployment, not the primary model.
    os.environ["AZURE_OPENAI_RESPONSES_ENDPOINT"] = ""
    if os.getenv("AZURE_OPENAI_DEPLOYMENT") != "gpt-5.4-nano":
        parser.error("This suite requires AZURE_OPENAI_DEPLOYMENT=gpt-5.4-nano")
    asyncio.run(run(args.case_id))


if __name__ == "__main__":
    main()
