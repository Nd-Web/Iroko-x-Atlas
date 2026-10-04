"""Live model + official-source smoke test; all application writes go to isolated SQLite.

Requires the public corpus snapshot from evaluate_document_answers.py snapshot.
Usage: python scripts/evaluate_regulatory_answers.py --question "latest compliance risk and cost"
Results stay in ignored .dist/rag-evaluation. A successful run is not a legal accuracy certification.
"""
import argparse
import asyncio
import json
import tempfile
import time
from pathlib import Path

import httpx
from dotenv import load_dotenv
from fastapi import FastAPI

from evaluate_document_answers import ARTIFACTS, BACKEND, case_trace, install_observers, save, setup_local


async def run(question, mode, require_findings=False):
    load_dotenv(BACKEND / ".env", override=True)
    corpus = json.loads((ARTIFACTS / "corpus.json").read_text(encoding="utf-8"))
    directory = Path(tempfile.mkdtemp(prefix="official-research-", dir=ARTIFACTS))
    factory = setup_local(corpus, directory)
    from ingestion.access import as_user
    from models.database import Message, User, get_db
    from routes import ask
    from services.auth_utils import get_current_user

    app = FastAPI()
    app.include_router(ask.router)
    install_observers()

    def database():
        with factory() as db:
            yield db

    async def user():
        with factory() as db:
            with as_user(db.get(User, "evaluation-owner")):
                yield db.get(User, "evaluation-owner")

    app.dependency_overrides[get_db] = database
    app.dependency_overrides[get_current_user] = user
    ask._check_rate_limit = lambda _user: True
    trace = {}
    token = case_trace.set(trace)
    started = time.monotonic()
    try:
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url="http://evaluation.local") as client:
            path = "/api/atlas/ask/stream-http" if mode == "stream" else "/api/atlas/ask"
            response = await asyncio.wait_for(client.post(path, json={"query": question}), timeout=130)
            response.raise_for_status()
            events = [json.loads(line[6:]) for line in response.text.splitlines()
                      if line.startswith("data: ") and line != "data: [DONE]"] if mode == "stream" else []
            result = next((event for event in reversed(events) if event.get("type") == "complete"), {}) if events else response.json()
            if mode == "stream" and (not result or any(event.get("type") == "error" for event in events)):
                raise RuntimeError("Evaluation stream did not complete successfully")
            with factory() as db:
                persisted = db.get(Message, result["message_id"])
                assert persisted and persisted.content == result["answer"]
                # Pydantic adds optional/default fields on the normal endpoint;
                # compare evidence identity/content, not presentation-only defaults.
                citation_keys = ("document_id", "document_title", "chunk_id", "excerpt", "provenance", "source_url")
                canonical = lambda citations: [{k: c.get(k) for k in citation_keys} for c in citations]
                assert canonical(persisted.citations) == canonical(result["citations"])
            assert result.get("research_checked_at"), "No official-source check was reported"
            save(directory / "result.json", {"question": question, "mode": mode, "result": result,
                                               "events": events, "trace": trace, "seconds": time.monotonic() - started})
            if require_findings:
                assert result["answer"].startswith("Verified source findings:") and result["citations"], (
                    f"No approved findings; inspect {directory / 'result.json'}"
                )
            print(json.dumps({"path": str(directory / "result.json"), "seconds": round(time.monotonic() - started, 2),
                              "answer": result["answer"], "citations": [{"title": c["document_title"],
                              "source_url": c.get("source_url"), "excerpt": c["excerpt"]} for c in result["citations"]]}, indent=2))
    finally:
        case_trace.reset(token)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--question", required=True)
    parser.add_argument("--mode", choices=["normal", "stream"], default="stream")
    parser.add_argument("--require-findings", action="store_true", help="Fail if only a gap/source-review fallback is returned; preserve diagnostics first")
    args = parser.parse_args()
    asyncio.run(run(args.question, args.mode, args.require_findings))
