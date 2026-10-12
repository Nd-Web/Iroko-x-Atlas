"""Live acceptance baseline, with read-only public corpus snapshot and isolated chat DB.

Run from backend: python scripts/evaluate_mfb_pilot.py
No production database writes, ingestion, emails or customer chat creation. Existing model
and official-search configuration are preserved. Scores require source-text review.
"""
import argparse
import asyncio
import hashlib
import json
import logging
import os
import subprocess
import tempfile
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import httpx
from dotenv import load_dotenv
from fastapi import FastAPI
from sqlalchemy import create_engine, text

from evaluate_document_answers import (
    ARTIFACTS, BACKEND, case_trace, install_observers, save, setup_local,
)


def public_snapshot():
    """Filter in SQL before loading any content; never export customer documents."""
    engine = create_engine(os.environ['DATABASE_URL'], connect_args={'connect_timeout': 15})
    eligible = """SELECT r.id FROM ingestion.regulatory_documents r
        JOIN ingestion.document_access a ON a.document_id=r.id
        JOIN documents d ON d.id=r.id
        WHERE r.is_current=true AND a.shared_regulatory=true AND d.status='indexed'"""
    result = {'captured_at': datetime.now(timezone.utc).isoformat()}
    try:
        with engine.connect() as conn:
            conn.execute(text('SET TRANSACTION READ ONLY'))
            result['source_migration'] = conn.execute(text(
                'SELECT version_num FROM ingestion.alembic_version_ingestion')).scalar()
            for name, table, id_column in [
                ('documents', 'documents', 'id'),
                ('revisions', 'ingestion.regulatory_documents', 'id'),
                ('pages', 'ingestion.regulatory_document_pages', 'document_id'),
                ('chunks', 'ingestion.regulatory_chunks', 'document_id'),
            ]:
                result[name] = [dict(row) for row in conn.execute(text(
                    f'SELECT * FROM {table} WHERE {id_column} IN ({eligible})')).mappings()]
            conn.rollback()
    finally:
        engine.dispose()
    for doc in result['documents']:
        doc.update(uploaded_by_id='evaluation-owner', blob_url=None, extra_metadata={})
    for revision in result['revisions']:
        revision['reviewed_by'] = None
    if not result['documents']:
        raise RuntimeError('No eligible shared regulatory corpus; evaluation stopped')
    return result


def code_manifest():
    root = BACKEND.parent
    digest = hashlib.sha256()
    for path in sorted(BACKEND.rglob('*.py')):
        if any(part in {'.venv', '__pycache__', '.dist'} for part in path.parts):
            continue
        digest.update(str(path.relative_to(root)).encode())
        digest.update(path.read_bytes())
    return {'head': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=root, text=True).strip(),
            'status': subprocess.check_output(['git', 'status', '--short'], cwd=root, text=True),
            'python_source_sha256': digest.hexdigest()}


def existing_factory(directory):
    """Resume only the isolated database; never reconnect application writes to prod."""
    database = directory / 'evaluation.db'
    if not database.is_file():
        raise ValueError('Missing isolated evaluation database')
    os.environ['DATABASE_URL'] = 'sqlite:///' + database.resolve().as_posix()
    os.environ['DOCUMENT_PIPELINE_ENABLED'] = 'true'
    os.environ['SEED_DEMO_DATA'] = 'false'
    import models.workflow  # noqa: F401
    import models.compliance_graph  # noqa: F401
    import models.filing  # noqa: F401
    from ingestion.db import pipeline_bind
    from models.database import SessionLocal, engine
    SessionLocal.configure(bind=pipeline_bind(engine))
    return SessionLocal


async def run(args):
    load_dotenv(BACKEND / '.env', override=True)
    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    directory = args.resume.resolve() if args.resume else Path(tempfile.mkdtemp(prefix='mfb-pilot-', dir=ARTIFACTS))
    suite = json.loads((BACKEND / 'tests/evals/mfb_pilot_questions.json').read_text(encoding='utf-8'))
    known_ids = {c['id'] for c in suite['cases']}
    if args.case_ids and (len(set(args.case_ids)) != len(args.case_ids) or not set(args.case_ids) <= known_ids):
        raise ValueError('Case selection contains an unknown or duplicate question ID')
    if args.case_ids and 14 in args.case_ids and (1 not in args.case_ids or args.case_ids.index(1) > args.case_ids.index(14)):
        raise ValueError('Q14 requires Q1 earlier in the same run')
    previous = None
    if args.resume:
        previous = json.loads((directory / 'manifest.json').read_text(encoding='utf-8'))
        if previous.get('finished_at'):
            raise ValueError('Completed evaluation cannot be resumed or overwritten')
        corpus = json.loads((directory / 'corpus.json').read_text(encoding='utf-8'))
        if hashlib.sha256((directory / 'corpus.json').read_bytes()).hexdigest() != previous['corpus']['sha256']:
            raise ValueError('Snapshot changed since original run')
        if suite != previous['suite']:
            raise ValueError('Question suite changed since original run')
        factory = existing_factory(directory)
    else:
        corpus = public_snapshot()
        save(directory / 'corpus.json', corpus)
        factory = setup_local(corpus, directory)
    from ingestion.access import as_user
    from models.database import AgentRun, AuditLog, Message, User, get_db
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
            actor = db.get(User, 'evaluation-owner')
            with as_user(actor):
                yield actor

    app.dependency_overrides[get_db] = database
    app.dependency_overrides[get_current_user] = user
    ask._check_rate_limit = lambda _user: True
    manifest = {
        'started_at': datetime.now(timezone.utc).isoformat(), 'code': code_manifest(),
        'model_configuration': {k: v for k, v in os.environ.items()
                                if k.startswith(('AZURE_OPENAI_', 'OPENAI_'))
                                and any(t in k for t in ('DEPLOYMENT', 'MODEL', 'API_VERSION'))
                                and not any(t in k for t in ('KEY', 'SECRET', 'TOKEN', 'ENDPOINT'))},
        'scope': 'Local working tree; live configured models, Azure Search and bounded official research; isolated HTTP/SSE chat, persistence and audit. Not a deployed-production test.',
        'isolation_limits': 'Only currently indexed, shared-regulatory documents copied. No private institution records, filing profiles or production knowledge graph. Local SQLite replaces Postgres for chat writes. Authentication is injected as a synthetic evaluation user.',
        'corpus': {'documents': len(corpus['documents']), 'chunks': len(corpus['chunks']),
                   'regulators': dict(Counter(r['provenance'].get('regulator', 'unknown') for r in corpus['revisions'])),
                   'sha256': hashlib.sha256((directory / 'corpus.json').read_bytes()).hexdigest()},
        'suite': suite, 'runs': [],
    }
    if previous:
        if previous['model_configuration'] != manifest['model_configuration']:
            raise ValueError('Model configuration changed; start a separately versioned evaluation')
        previous.setdefault('resumptions', []).append({
            'at': datetime.now(timezone.utc).isoformat(), 'code': manifest['code'],
            'note': 'Continued only unfinished cases after session interruption. Same saved public corpus and synthetic database; live web/time may differ.'})
        manifest = previous
    save(directory / 'manifest.json', manifest)
    print(json.dumps({'directory': str(directory), 'corpus': manifest['corpus']}), flush=True)
    cases = {c['id']: c for c in suite['cases']}
    order = args.case_ids or suite['priority_order']
    schedule = [(i, 1) for i in order] + ([(1, 2), (1, 3)] if args.repeat_capital and 1 in order else [])
    completed = {(r['id'], r['repeat']) for r in manifest['runs']}
    schedule = [(i, repeat) for i, repeat in schedule if (i, repeat) not in completed]
    conversations = {}
    for prior in manifest['runs']:
        if prior['repeat'] == 1:
            record = json.loads((directory / prior['file']).read_text(encoding='utf-8'))
            conversation = record.get('result', {}).get('conversation_id')
            if conversation:
                conversations[prior['id']] = conversation
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url='http://evaluation.local') as client:
        for case_id, repeat in schedule:
            case = cases[case_id]
            record = {'id': case_id, 'repeat': repeat, 'question': case['question'],
                      'started_at': datetime.now(timezone.utc).isoformat(), 'review_status': 'unscored'}
            trace = {}
            token = case_trace.set(trace)
            started = time.monotonic()
            print(json.dumps({'starting': case_id, 'repeat': repeat}), flush=True)
            try:
                body = {'query': case['question']}
                if case.get('conversation_from'):
                    body['conversation_id'] = conversations[case['conversation_from']]
                response = await asyncio.wait_for(client.post('/api/atlas/ask/stream-http', json=body), timeout=145)
                response.raise_for_status()
                events = [json.loads(line[6:]) for line in response.text.splitlines()
                          if line.startswith('data: ') and line != 'data: [DONE]']
                result = next((e for e in reversed(events) if e.get('type') == 'complete'), {})
                record.update(result=result, events=events)
                if result.get('conversation_id') and repeat == 1:
                    conversations[case_id] = result['conversation_id']
                with factory() as db:
                    message = db.get(Message, result.get('message_id', ''))
                    record['persistence'] = {
                        'answer_matches': bool(message and message.content == result.get('answer')),
                        'citations_match': bool(message and message.citations == result.get('citations')),
                        'trace_matches': bool(message and message.agent_trace == result.get('agent_trace')),
                    }
                    if message:
                        record['saved_agent_trace'] = message.agent_trace
                        record['agent_runs'] = [
                            {c.name: getattr(row, c.name) for c in AgentRun.__table__.columns}
                            for row in db.query(AgentRun).filter(AgentRun.conversation_id == message.conversation_id)]
                    record['audit_log_count_after'] = db.query(AuditLog).count()
                record['transport_ok'] = bool(result) and not any(e.get('type') == 'error' for e in events)
            except Exception as exc:
                # Avoid serialising connection strings/headers from third-party exception messages.
                record.update(transport_ok=False, error_type=type(exc).__name__)
            finally:
                record['seconds'] = round(time.monotonic() - started, 3)
                record['trace'] = trace
                case_trace.reset(token)
                filename = f'q{case_id:02d}-run{repeat}.json'
                save(directory / filename, record)
                manifest['runs'].append({'id': case_id, 'repeat': repeat, 'file': filename,
                                         'transport_ok': record['transport_ok'], 'seconds': record['seconds']})
                save(directory / 'manifest.json', manifest)
                print(json.dumps({'finished': case_id, 'repeat': repeat, 'transport_ok': record['transport_ok'],
                                  'seconds': record['seconds'], 'file': filename}), flush=True)
    manifest['finished_at'] = datetime.now(timezone.utc).isoformat()
    save(directory / 'manifest.json', manifest)
    print(json.dumps({'complete': str(directory)}), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--case-ids', type=int, nargs='+')
    parser.add_argument('--repeat-capital', action='store_true')
    parser.add_argument('--resume', type=Path, help='Continue unfinished cases against the same isolated snapshot/database')
    arguments = parser.parse_args()
    logging.basicConfig(level=logging.ERROR)
    asyncio.run(run(arguments))
