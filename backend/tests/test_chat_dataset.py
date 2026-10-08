"""Dataset boundaries and grading regressions, using synthetic evidence only."""
from copy import deepcopy
import importlib.util
from pathlib import Path

import pytest

from evaluation.chat_dataset import build, case_record, check_result, digest, export_approved, read_cases, review_page, validate, write_dataset
from evaluation.chat_seeds import seeds


@pytest.fixture
def rows():
    corpus = {"documents": [], "revisions": [], "chunks": []}
    questions = []
    for i in range(20):
        doc_id, chunk_id = f"doc-{i}", f"chunk-{i}"
        corpus["documents"].append({"id": doc_id, "title": f"Synthetic document {i}"})
        corpus["revisions"].append({"id": doc_id, "provenance": {"classification": "public", "regulator": "CBN", "source_url": f"https://www.cbn.gov.ng/synthetic/{i}"}})
        corpus["chunks"].append({"id": chunk_id, "document_id": doc_id, "content": "Fictional review evidence."})
        questions.append({"document_id": doc_id, "chunk_id": chunk_id, "question": f"What does synthetic document {i} say?", "style": "natural"})
    return build(corpus, questions)


def approve(case, **changes):
    return {"id": case["id"], "case_sha256": case["case_sha256"], "decision": "approve", "reviewer": "Test reviewer",
            "answer": "Reviewed answer", "training_rights_confirmed": True, "evidence_verified": True, **changes}


def test_600_variants_have_disjoint_families_and_public_sources(rows, tmp_path):
    result = validate(rows)
    assert result["cases"] == 600 and result["families"] == 60
    assert result["splits"] == {"development": 500, "holdout": 100}
    assert result["review_status"] == {"candidate": 600}
    manifest = write_dataset(tmp_path, rows, "fixture-corpus-hash")
    assert manifest["training_ready"] is False
    assert read_cases(tmp_path) == [r for split in ("development", "holdout") for r in rows if r["split"] == split]


def test_source_tampering_and_family_leakage_are_rejected(rows):
    changed = deepcopy(rows)
    changed[-1]["evidence"][0]["content"] = "Tampered"
    with pytest.raises(ValueError, match="Changed"):
        validate(changed)
    changed = deepcopy(rows)
    changed[1]["split"] = "holdout"
    changed[1]["case_sha256"] = digest({k: v for k, v in changed[1].items() if k != "case_sha256"})
    with pytest.raises(ValueError, match="family crosses"):
        validate(changed)


def test_candidate_data_cannot_silently_become_training(rows):
    assert export_approved(rows, []) == []
    case = rows[0]
    for change in ({"reviewer": ""}, {"training_rights_confirmed": False}, {"answer": ""}, {"case_sha256": "stale"}):
        with pytest.raises(ValueError):
            export_approved(rows, [approve(case, **change)])
    result = export_approved(rows, [approve(case)])
    assert len(result) == 1
    assert result[0]["messages"][-1] == {"role": "assistant", "content": "Reviewed answer"}


def test_holdout_never_enters_training_even_with_approval(rows):
    heldout = next(r for r in rows if r["split"] == "holdout")
    with pytest.raises(ValueError, match="holdout"):
        export_approved(rows, [approve(heldout)])


def test_evidence_review_and_training_context_are_required(rows):
    case = next(r for r in rows if r["evidence"] and r["split"] == "development")
    with pytest.raises(ValueError, match="verify"):
        export_approved(rows, [approve(case, evidence_verified=False)])
    result = export_approved(rows, [approve(case)])
    assert case["evidence"][0]["content"] in result[0]["messages"][1]["content"]
    unavailable = next(r for r in rows if r["task"] == "unavailable")
    assert '"retrieval_status": "unavailable"' in export_approved(rows, [approve(unavailable)])[0]["messages"][1]["content"]


def test_review_html_escapes_sources_and_excludes_holdout(rows, tmp_path):
    rows[0]["reference_answer"] = "</script><script>alert(1)</script>"
    path = tmp_path / "review.html"
    review_page(rows, path)
    html = path.read_text(encoding="utf-8")
    assert "</script><script>alert(1)" not in html
    assert next(r for r in rows if r["split"] == "holdout")["id"] not in html


def test_mechanical_checks_do_not_certify_a_wrong_document(rows):
    case = next(r for r in rows if r["category"] == "regulatory_reading")
    failures = check_result(case, {"answer": "An answer", "citations": [{"document_id": "wrong"}]})
    assert "wrong_source_document" in failures
    assert check_result(rows[0], {"error": "RuntimeError"}) == ["generation_error"]


@pytest.mark.asyncio
async def test_offline_evaluator_never_calls_a_model():
    path = Path(__file__).resolve().parents[1] / "scripts/chat_dataset.py"
    spec = importlib.util.spec_from_file_location("dataset_cli", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    families = seeds()
    hello = next(f for f in families if f["family"] == "hello")
    result, stage, skipped = await module.evaluate_case(case_record(hello, 0, "hello"))
    assert not skipped and stage == "conversation" and "Hi" in result["answer"]
    factual = next(f for f in families if f["family"] == "exact_interval")
    result, stage, skipped = await module.evaluate_case(case_record(factual, 0, factual["questions"][0]))
    assert skipped and stage == "needs_model"


def test_compliance_grader_distinguishes_denial_from_direct_certification():
    family = next(f for f in seeds() if f["family"] == "compliance_certification")
    case = case_record(family, 0, family["questions"][0])
    assert not check_result(case, {"answer": "The evidence does not establish whether you are compliant. Provide completion records."})
    assert any(f.startswith("forbidden:") for f in check_result(case, {"answer": "Yes, you are compliant. No further records needed."}))


def test_sampler_covers_families_before_repeating_variants(rows):
    path = Path(__file__).resolve().parents[1] / "scripts/chat_dataset.py"
    spec = importlib.util.spec_from_file_location("dataset_sampling_cli", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    selected = module.select_cases(rows, "development", 50, [])
    assert len({r["family"] for r in selected}) == 50
    assert len(module.select_cases(rows, "development", 500, [])) == 500
