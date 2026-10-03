"""Bounded live Q&A evaluation; source DB is read-only, application writes are isolated.

Run from backend: python scripts/evaluate_document_answers.py snapshot
Then: python scripts/evaluate_document_answers.py run --limit 2
Generated evidence stays under ignored .dist/rag-evaluation, never in customer chats.
Assertions are conservative triage signals, not a semantic accuracy certification.
"""

import argparse
import asyncio
import json
import logging
import os
import re
import sys
import tempfile
import time
from contextvars import ContextVar
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import create_engine, text

BACKEND = Path(__file__).resolve().parents[1]
ROOT = BACKEND.parent
ARTIFACTS = ROOT / ".dist" / "rag-evaluation"
sys.path.insert(0, str(BACKEND))
case_trace = ContextVar("evaluation_trace", default=None)


def save(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, default=str), encoding="utf-8")


def snapshot():
    """Read public regulator evidence only; no customer/users/secrets are exported."""
    engine = create_engine(os.environ["DATABASE_URL"], connect_args={"connect_timeout": 15})
    with engine.connect() as conn:
        conn.execute(text("SET TRANSACTION READ ONLY"))
        version = conn.execute(
            text("SELECT version_num FROM ingestion.alembic_version_ingestion")
        ).scalar()
        revisions = [
            dict(r)
            for r in conn.execute(
                text("SELECT * FROM ingestion.regulatory_documents WHERE is_current=true")
            ).mappings()
            if r["provenance"].get("regulator") == "CBN"
        ]
        ids = {r["id"] for r in revisions}
        docs = [
            dict(r)
            for r in conn.execute(text("SELECT * FROM documents")).mappings()
            if r["id"] in ids
        ]
        pages = [
            dict(r)
            for r in conn.execute(
                text("SELECT * FROM ingestion.regulatory_document_pages ORDER BY position")
            ).mappings()
            if r["document_id"] in ids
        ]
        chunks = [
            dict(r)
            for r in conn.execute(text("SELECT * FROM ingestion.regulatory_chunks")).mappings()
            if r["document_id"] in ids
        ]
        conn.rollback()
    engine.dispose()
    if not ids:
        raise RuntimeError("No current CBN pipeline documents found")
    # Original owner identities and blob URLs are not needed for Q&A testing.
    for doc in docs:
        doc["uploaded_by_id"] = "evaluation-owner"
        doc["blob_url"] = None
        doc["extra_metadata"] = {}
    result = {
        "captured_at": datetime.now().isoformat(),
        "source_migration": version,
        "documents": docs,
        "revisions": revisions,
        "pages": pages,
        "chunks": chunks,
    }
    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    save(ARTIFACTS / "corpus.json", result)
    print(
        json.dumps(
            {
                "documents": len(docs),
                "pages": len(pages),
                "chunks": len(chunks),
                "source_migration": version,
            }
        )
    )


def hydrate(model, row):
    from sqlalchemy import DateTime

    values = dict(row)
    for column in model.__table__.columns:
        if isinstance(column.type, DateTime) and isinstance(values.get(column.name), str):
            values[column.name] = datetime.fromisoformat(values[column.name])
    return model(**values)


def setup_local(corpus, run_dir):
    # Override BEFORE importing either application session factory.
    os.environ["DATABASE_URL"] = "sqlite:///" + (run_dir / "evaluation.db").as_posix()
    os.environ["DOCUMENT_PIPELINE_ENABLED"] = "true"
    os.environ["SEED_DEMO_DATA"] = "false"
    import models.workflow  # noqa: F401 -- register derived-record tables
    from ingestion.db import pipeline_bind
    from ingestion.models import (
        Chunk,
        DocumentAccess,
        Membership,
        Page,
        PipelineBase,
        Revision,
        Workspace,
    )
    from models.database import Base, Document, SessionLocal, User, engine

    bind = pipeline_bind(engine)
    Base.metadata.create_all(bind)
    PipelineBase.metadata.create_all(bind)
    # Existing app session paths also need schema translation on this isolated SQLite DB.
    SessionLocal.configure(bind=bind)
    with SessionLocal() as db:
        db.add(
            User(
                id="evaluation-owner",
                email="evaluation@example.invalid",
                full_name="Evaluation",
                role="admin",
                hashed_password="unused",
            )
        )
        db.add(Workspace(id="evaluation", name="Isolated evaluation"))
        db.add(Membership(user_id="evaluation-owner", workspace_id="evaluation"))
        for row in corpus["documents"]:
            db.add(hydrate(Document, row))
            db.add(
                DocumentAccess(
                    document_id=row["id"], workspace_id="evaluation", shared_regulatory=False
                )
            )
        for model, key in [(Revision, "revisions"), (Page, "pages"), (Chunk, "chunks")]:
            for row in corpus[key]:
                db.add(hydrate(model, row))
        db.commit()
    return SessionLocal


def install_observers():
    """Observe existing application behaviour without replacing retrieval or model calls."""
    from agents.researcher import ResearcherAgent
    from agents.strategist import StrategistAgent
    import agents.strategist as strategist_module
    from services import azure_search
    from services.boardroom_formatter import BoardroomFormatter

    original_context = StrategistAgent._retrieve_context
    original_search = ResearcherAgent.search_documents
    original_format = BoardroomFormatter.format_executive_summary
    original_hybrid = azure_search.hybrid_search
    original_complete = strategist_module.llm_complete

    async def complete(*args, **kwargs):
        value = await original_complete(*args, **kwargs)
        if case_trace.get() is not None and kwargs.get("json_schema"):
            case_trace.get().setdefault("grounding_outputs", []).append(value)
        return value

    async def context(self, *args, **kwargs):
        value = await original_context(self, *args, **kwargs)
        if case_trace.get() is not None:
            case_trace.get().setdefault("contexts", []).append(value)
        return value

    async def search(self, *args, **kwargs):
        value = await original_search(self, *args, **kwargs)
        if case_trace.get() is not None:
            case_trace.get().setdefault("researcher", []).append(json.loads(value))
        return value

    async def hybrid(*args, **kwargs):
        value = await original_hybrid(*args, **kwargs)
        if case_trace.get() is not None:
            case_trace.get().setdefault("raw_search", []).append(
                {"query": kwargs.get("query"), "results": value}
            )
        return value

    async def formatter(self, raw_result, *args, **kwargs):
        if case_trace.get() is not None:
            case_trace.get()["before_formatter"] = raw_result.get("answer")
        value = await original_format(self, raw_result, *args, **kwargs)
        return value

    StrategistAgent._retrieve_context = context
    strategist_module.llm_complete = complete
    ResearcherAgent.search_documents = search
    BoardroomFormatter.format_executive_summary = formatter
    # Researcher/Watchdog import the same function by name, so observe those aliases too.
    azure_search.hybrid_search = hybrid
    import agents.researcher
    import agents.watchdog

    agents.researcher.hybrid_search = hybrid
    if hasattr(agents.watchdog, "hybrid_search"):
        agents.watchdog.hybrid_search = hybrid


def assertions(case, result):
    answer = result.get("answer", "")
    text_checks = {
        pattern: bool(re.search(pattern, answer, re.I | re.S))
        for pattern in case.get("required_patterns", [])
    }
    citations = result.get("citations", [])
    cited = {c.get("document_id") for c in citations if isinstance(c, dict)}
    sources = {p["document_id"] for p in case.get("sources", [])}
    return {
        "text_checks": text_checks,
        "source_citation_present": bool(cited & sources) if sources else None,
        "triage": "review"
        if not all(text_checks.values()) or (sources and not cited & sources)
        else "candidate_pass",
    }


async def run(args):
    import httpx
    from fastapi import FastAPI

    corpus = json.loads((ARTIFACTS / "corpus.json").read_text(encoding="utf-8"))
    cases = json.loads(
        (BACKEND / "tests" / "evals" / "cbn_document_questions.json").read_text(encoding="utf-8")
    )
    if args.case_id:
        cases = [case for case in cases if case["id"] in args.case_id]
        if len(cases) != len(set(args.case_id)):
            raise ValueError("Unknown or duplicate case selection")
    if args.limit:
        cases = cases[: args.limit]
    run_dir = Path(tempfile.mkdtemp(prefix="nano-", dir=ARTIFACTS))
    SessionLocal = setup_local(corpus, run_dir)
    from agents.strategist import StrategistAgent
    from ingestion.access import as_user
    from models.database import User, get_db
    from routes import ask as ask_route
    from services.auth_utils import get_current_user

    install_observers()
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
    # Do not let unrelated auth settings or customer rate accounting affect this isolated run.
    ask_route._check_rate_limit = lambda user_id: True
    results = []
    semaphore = asyncio.Semaphore(args.concurrency)
    modes = args.modes.split(",")
    page_map = {(p["document_id"], p["page_number"]): p for p in corpus["pages"]}
    locator_map = {(p["document_id"], p.get("locator")): p for p in corpus["pages"]}
    doc_map = {d["id"]: d for d in corpus["documents"]}

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://evaluation.local"
    ) as client:

        async def one(case, mode):
            async with semaphore:
                trace = {}
                token = case_trace.set(trace)
                started = time.monotonic()
                result = {}
                try:
                    if mode == "oracle":
                        # Diagnostic: give the existing answer prompt complete gold pages,
                        # bypassing ONLY retrieval/classification, clearly labelled in output.
                        chunks, citations = [], []
                        for source in case.get("sources", []):
                            for page_no in source["pages"]:
                                page = page_map[(source["document_id"], page_no)]
                                chunks.append(
                                    f"[Document {source['document_id']}, physical page {page_no}]\n{page['text']}"
                                )
                            for locator in source.get("locators", []):
                                page = locator_map[(source["document_id"], locator)]
                                chunks.append(
                                    f"[Document {source['document_id']}, worksheet {locator}]\n{page['text']}"
                                )
                            citations.append(
                                {
                                    "document_id": source["document_id"],
                                    "document_title": doc_map[source["document_id"]]["title"],
                                    "excerpt": "",
                                }
                            )
                        strategist = StrategistAgent()
                        context = {
                            "chunks": chunks,
                            "citations": citations,
                            "confidence": "medium",
                            "knowledge_gap": False,
                        }
                        from agents.kernel import llm_complete

                        answer = await llm_complete(
                            strategist._build_answer_prompt(case["question"], context, False),
                            system_prompt=strategist._ANSWER_SYSTEM_PROMPT,
                            max_tokens=2400,
                        )
                        try:
                            result = json.loads(
                                answer.strip().replace("```json", "").replace("```", "")
                            )
                        except json.JSONDecodeError:
                            result = {"answer": answer, "citations": []}
                    else:
                        endpoint = (
                            "/api/atlas/ask" if mode == "normal" else "/api/atlas/ask/stream-http"
                        )
                        response = await asyncio.wait_for(
                            client.post(endpoint, json={"query": case["question"]}), timeout=120
                        )
                        if response.status_code != 200:
                            result = {"error": f"HTTP {response.status_code}"}
                        elif mode == "normal":
                            result = response.json()
                        else:
                            events = [
                                json.loads(line[6:])
                                for line in response.text.splitlines()
                                if line.startswith("data: ") and line[6:].strip() != "[DONE]"
                            ]
                            trace["stream_errors"] = [e for e in events if e.get("type") == "error"]
                            result = next(
                                (e for e in reversed(events) if e.get("type") == "complete"),
                                {"error": "No complete SSE event"},
                            )
                            trace["streamed_answer"] = "".join(
                                e.get("content", "") for e in events if e.get("type") == "token"
                            )
                    record = {
                        "case_id": case["id"],
                        "mode": mode,
                        "question": case["question"],
                        "expected": case["expected"],
                        "sources": case.get("sources", []),
                        "seconds": round(time.monotonic() - started, 2),
                        "result": result,
                        "trace": trace,
                    }
                    record["assertions"] = assertions(case, result)
                except Exception as exc:
                    # No exception text/SQL parameters: those can include configuration secrets.
                    record = {
                        "case_id": case["id"],
                        "mode": mode,
                        "question": case["question"],
                        "error_type": type(exc).__name__,
                        "seconds": round(time.monotonic() - started, 2),
                    }
                finally:
                    case_trace.reset(token)
                results.append(record)
                save(run_dir / "results.json", results)
                print(
                    json.dumps(
                        {
                            "case": case["id"],
                            "mode": mode,
                            "seconds": record["seconds"],
                            "triage": record.get("assertions", {}).get("triage", "error"),
                        }
                    ),
                    flush=True,
                )

        await asyncio.gather(*(one(case, mode) for case in cases for mode in modes))
    save(
        run_dir / "manifest.json",
        {
            "model": os.getenv("AZURE_OPENAI_DEPLOYMENT"),
            "cases": len(cases),
            "modes": modes,
            "concurrency": args.concurrency,
            "corpus_documents": len(corpus["documents"]),
            "source_migration": corpus["source_migration"],
            "production_writes": False,
            "limitations": "Isolated ASGI API evaluation, not browser/production deployment or load certification. Oracle bypasses retrieval and classification; candidate_pass still requires semantic review.",
        },
    )
    print(json.dumps({"output_directory": str(run_dir), "completed": len(results)}))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["snapshot", "run"])
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--concurrency", type=int, choices=[1, 2, 3], default=2)
    parser.add_argument("--modes", default="normal,stream")
    parser.add_argument("--case-id", action="append", default=[], help="Run only selected case IDs")
    args = parser.parse_args()
    if not set(args.modes.split(",")) <= {"normal", "stream", "oracle"}:
        parser.error("Modes must be normal,stream,oracle")
    load_dotenv(BACKEND / ".env", override=True)
    logging.disable(logging.CRITICAL)
    if os.getenv("AZURE_OPENAI_DEPLOYMENT") != "gpt-5.4-nano" or os.getenv(
        "AZURE_OPENAI_RESPONSES_ENDPOINT"
    ):
        parser.error(
            "This bounded suite requires the explicitly configured nano Chat Completions path"
        )
    if args.command == "snapshot":
        snapshot()
    else:
        asyncio.run(run(args))


if __name__ == "__main__":
    main()
