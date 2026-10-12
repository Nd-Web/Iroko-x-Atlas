"""Evaluation safeguards; no network/model calls or production database writes."""
import importlib
import json
from pathlib import Path
from types import SimpleNamespace

import pytest


@pytest.fixture
def modules(monkeypatch):
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[1] / 'scripts'))
    return importlib.import_module('evaluate_mfb_pilot'), importlib.import_module('render_mfb_evaluation')


def test_suite_priority_and_fictional_fixture():
    suite = json.loads((Path(__file__).parent / 'evals/mfb_pilot_questions.json').read_text(encoding='utf-8'))
    assert suite['priority_order'][:4] == [1, 3, 7, 11]
    assert sorted(suite['priority_order']) == list(range(1, 15))
    cases = {c['id']: c for c in suite['cases']}
    assert cases[14]['conversation_from'] == 1
    assert 'entirely fictional' in cases[8]['question']
    assert 'no report should be submitted' in cases[8]['question']
    assert 'BSD/DIR/2025/099' in cases[11]['question']


def test_resume_never_creates_an_empty_replacement_database(modules, tmp_path):
    evaluate, _ = modules
    with pytest.raises(ValueError, match='Missing isolated evaluation database'):
        evaluate.existing_factory(tmp_path)
    assert not (tmp_path / 'evaluation.db').exists()


def test_snapshot_selects_only_shared_indexed_current_documents(modules, monkeypatch):
    evaluate, _ = modules
    statements = []
    state = {'rolled_back': False, 'disposed': False}

    class Connection:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def execute(self, statement):
            sql = str(statement)
            statements.append(sql)
            if 'alembic_version' in sql:
                return SimpleNamespace(scalar=lambda: 'test-version')
            rows = []
            if sql.startswith('SELECT * FROM documents '):
                rows = [{'id': 'public-doc', 'uploaded_by_id': 'real-owner', 'blob_url': 'private-url', 'extra_metadata': {'owner': 'private'}}]
            if sql.startswith('SELECT * FROM ingestion.regulatory_documents '):
                rows = [{'id': 'public-doc', 'reviewed_by': 'real-reviewer'}]
            return SimpleNamespace(mappings=lambda: rows)

        def rollback(self):
            state['rolled_back'] = True

    class Engine:
        def connect(self):
            return Connection()

        def dispose(self):
            state['disposed'] = True

    monkeypatch.setenv('DATABASE_URL', 'postgresql://unused.invalid/evaluation')
    monkeypatch.setattr(evaluate, 'create_engine', lambda *args, **kwargs: Engine())
    corpus = evaluate.public_snapshot()
    assert statements[0] == 'SET TRANSACTION READ ONLY'
    for query in statements[2:]:
        assert 'a.shared_regulatory=true' in query
        assert 'r.is_current=true' in query
        assert "d.status='indexed'" in query
        assert query.startswith('SELECT')
    assert corpus['documents'][0]['uploaded_by_id'] == 'evaluation-owner'
    assert corpus['documents'][0]['blob_url'] is None
    assert corpus['documents'][0]['extra_metadata'] == {}
    assert corpus['revisions'][0]['reviewed_by'] is None
    assert all(state.values())


@pytest.mark.parametrize('finished,corpus,reviewed,expected', [
    (False, 'same', [], 'not finished'),
    (True, 'different', [], 'corpus snapshot'),
    (True, 'same', [], 'explicit reviewed score'),
])
def test_renderer_requires_completed_matching_review(modules, tmp_path, finished, corpus, reviewed, expected):
    _, renderer = modules
    (tmp_path / 'manifest.json').write_text(json.dumps({
        'finished_at': '2026-10-11' if finished else None, 'corpus': {'sha256': 'same'},
        'runs': [{'file': 'q01-run1.json'}],
    }), encoding='utf-8')
    (tmp_path / 'q01-run1.json').write_text(json.dumps({'id': 1, 'repeat': 1}), encoding='utf-8')
    review = tmp_path / 'review.json'
    review.write_text(json.dumps({'corpus_sha256': corpus, 'scores': reviewed}), encoding='utf-8')
    with pytest.raises(ValueError, match=expected):
        renderer.render(tmp_path, review, tmp_path / 'report.md')
    assert not (tmp_path / 'report.md').exists()
