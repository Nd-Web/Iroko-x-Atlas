"""Reproducible, provenance-bearing candidates and leakage checks. No database access."""
from collections import Counter, defaultdict
import hashlib
import html
import json
from pathlib import Path
import re
from urllib.parse import urlsplit

from evaluation.chat_seeds import seeds

VERSION = "iroko-chat-v1"


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def family_group(title):
    name = title.casefold()
    for term in ("bank verification number", "anti-money laundering", "revocation of operating"):
        if term in name:
            return term
    return re.sub(r"\W+", " ", name).strip()


def case_record(family, index, question, evidence=None):
    evidence = evidence if evidence is not None else family["evidence"]
    messages = []
    for turn in family["history"]:
        messages.append({"role": "user", "content": turn["question"]})
        if turn.get("answer_summary"):
            messages.append({"role": "assistant", "content": turn["answer_summary"]})
    messages.append({"role": "user", "content": question})
    row = {"id": f"{family['family']}:{index:02}", "version": VERSION,
        "family": family["family"], "split_group": family.get("split_group", family["family"]),
        "split": family["split"], "category": family["category"], "task": family["task"],
        "origin": family["origin"], "history": family["history"], "messages": messages,
        "evidence": evidence, "reference_answer": family["reference_answer"], "checks": family["checks"],
        "rubric": ["Answer the actual current request and use conversation context correctly.",
            "Use readable, proportionate language; keep factual scope and uncertainty explicit.",
            "Every regulatory or business assertion must be supported by the provided evidence.",
            "A prior assistant answer, template, fetch date or missing search hit is not proof of compliance or current law."],
        "review": {"status": "candidate", "reviewer": None, "training_rights": "not_reviewed"}}
    row["case_sha256"] = digest(row)
    return row


def build(corpus, questions):
    families = seeds()
    assert len(families) == 40
    rows = [case_record(family, i, q) for family in families for i, q in enumerate(family["questions"])]
    documents = {d["id"]: d for d in corpus["documents"]}
    revisions = {r["id"]: r for r in corpus["revisions"]}
    chunks = {c["id"]: c for c in corpus["chunks"]}
    by_doc = defaultdict(list)
    for question in questions:
        chunk = chunks.get(question["chunk_id"])
        if chunk and chunk["document_id"] == question["document_id"] and question["document_id"] in documents:
            by_doc[question["document_id"]].append(question)
    if len(by_doc) != 20:
        raise ValueError("v1 expects the existing 20-document public CBN snapshot; update the version before changing corpus size")
    groups = defaultdict(list)
    for doc_id in by_doc:
        groups[family_group(documents[doc_id]["title"])].append(doc_id)
    # Related BVN/AML/revocation documents stay together. Four singleton document
    # groups plus six behavioural families supply 100 held-out variants.
    holdout_groups = set(sorted((g for g, ids in groups.items() if len(ids) == 1), key=digest)[:4])
    prefixes = ["", "Please answer from the cited document: ", "In plain language, ",
        "Using only the supplied source, ", "Help me understand: ", "According to this document, ",
        "Explain briefly: ", "Check the source and tell me: ", "I am reading this circular. ", "For a source-based summary: "]
    for doc_id, candidates in sorted(by_doc.items()):
        doc, revision = documents[doc_id], revisions[doc_id]
        provenance = revision.get("provenance", {})
        url = provenance.get("source_url", "")
        host = urlsplit(url).hostname or ""
        if provenance.get("classification") != "public" or provenance.get("regulator") != "CBN" or not (host == "cbn.gov.ng" or host.endswith(".cbn.gov.ng")):
            raise ValueError("Only verified-public CBN source records are allowed in this dataset")
        group = family_group(doc["title"])
        family = {"family": f"cbn-{doc_id}", "split_group": "document:" + group,
            "split": "holdout" if group in holdout_groups else "development", "category": "regulatory_reading",
            "task": "grounding", "history": [], "evidence": [], "reference_answer": None,
            "origin": "existing_generated_question_and_public_extracted_evidence",
            "checks": {"citations": "required", "cite_document": doc_id}}
        natural = [q for q in candidates if q.get("style") == "natural"] or candidates
        for i in range(10):
            question = natural[i % len(natural)]
            chunk = chunks[question["chunk_id"]]
            source = {"document_id": doc_id, "chunk_id": chunk["id"], "title": doc["title"], "content": chunk["content"],
                "provenance": {"source_url": url, "regulator": "CBN", "classification": "public",
                    "published_date": provenance.get("published_date"), "source_kind": "public_snapshot",
                    "legal_applicability_status": "not_assessed", "content_sha256": hashlib.sha256(chunk["content"].encode()).hexdigest()}}
            rows.append(case_record(family, i, prefixes[i] + question["question"], [source]))
    validate(rows)
    return rows


def validate(rows):
    errors, ids, groups, documents = [], set(), defaultdict(set), defaultdict(set)
    for row in rows:
        if row["id"] in ids:
            errors.append("Duplicate id: " + row["id"])
        ids.add(row["id"])
        if row["split"] not in {"development", "holdout"}:
            errors.append("Invalid split: " + row["id"])
        groups[row["split_group"]].add(row["split"])
        if digest({k: v for k, v in row.items() if k != "case_sha256"}) != row["case_sha256"]:
            errors.append("Changed case/hash: " + row["id"])
        if not row["messages"] or row["messages"][-1]["role"] != "user":
            errors.append("Missing final user request: " + row["id"])
        for source in row["evidence"]:
            if source.get("provenance", {}).get("source_kind") == "public_snapshot":
                documents[source["document_id"]].add(row["split"])
                if hashlib.sha256(source["content"].encode()).hexdigest() != source["provenance"]["content_sha256"]:
                    errors.append("Changed evidence: " + row["id"])
        for pattern in [*row["checks"].get("required", []), *row["checks"].get("forbidden", []), *row["checks"].get("query_forbidden", [])]:
            re.compile(pattern)
    if any(len(splits) > 1 for splits in groups.values()):
        errors.append("A scenario family crosses development/holdout")
    if any(len(splits) > 1 for splits in documents.values()):
        errors.append("A public source document crosses development/holdout")
    if errors:
        raise ValueError("; ".join(errors))
    return {"cases": len(rows), "families": len({r["family"] for r in rows}),
            "splits": dict(Counter(r["split"] for r in rows)), "categories": dict(Counter(r["category"] for r in rows)),
            "review_status": dict(Counter(r["review"]["status"] for r in rows))}


def read_cases(folder):
    return [json.loads(line) for split in ("development", "holdout")
            for line in (Path(folder) / f"{split}.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]


def write_dataset(folder, rows, corpus_hash):
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    for split in ("development", "holdout"):
        (folder / f"{split}.jsonl").write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows if r["split"] == split), encoding="utf-8")
    manifest = {"version": VERSION, **validate(rows), "corpus_sha256": corpus_hash,
        "dataset_sha256": digest(rows), "training_ready": False,
        "limitations": ["600 variants represent 60 underlying families, not 600 independent scenarios.",
            "All cases are candidates; automatic checks are not expert approval.",
            "Public regulatory documents require applicability and reuse-rights review before training.",
            "Held-out groups are separated within this dataset; the historical corpus was used in earlier project evaluations.",
            "Synthetic fixture topics intentionally overlap across splits; holdout tests new tasks, not unseen vocabulary.",
            "Component evaluations with supplied evidence do not measure production retrieval or storage reliability."]}
    (folder / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest


def check_result(case, result):
    """Mechanical triage only. A passing result still needs semantic review."""
    failures, spec = [], case["checks"]
    answer = result.get("answer", "")
    if result.get("error"):
        return ["generation_error"]
    if case["task"] != "routing" and not answer.strip():
        failures.append("empty_answer")
    for key, value in (("intent", result.get("intent")), ("status", result.get("answer_status"))):
        if spec.get(key) and value not in spec[key]:
            failures.append(f"{key}:{value}")
    for pattern in spec.get("required", []):
        if not re.search(pattern, answer, re.I):
            failures.append("missing:" + pattern)
    for pattern in spec.get("forbidden", []):
        if re.search(pattern, answer, re.I):
            failures.append("forbidden:" + pattern)
    for pattern in spec.get("query_forbidden", []):
        if re.search(pattern, result.get("query", ""), re.I):
            failures.append("wrong_topic:" + pattern)
    citations = result.get("citations", [])
    if spec.get("citations") == "none" and citations:
        failures.append("unexpected_citation")
    if spec.get("citations") == "required" and not citations:
        failures.append("missing_citation")
    if spec.get("cite_document") and not any(c.get("document_id") == spec["cite_document"] for c in citations):
        failures.append("wrong_source_document")
    if spec.get("max_words") and len(answer.split()) > spec["max_words"]:
        failures.append("too_long")
    return failures


def export_approved(rows, reviews):
    """Return only explicitly reviewed development examples, never holdout/eval outputs."""
    validate(rows)
    by_id, output = {row["id"]: row for row in rows}, []
    seen = set()
    for review in reviews:
        if review.get("decision") != "approve":
            continue
        case = by_id.get(review.get("id"))
        if not case or case["id"] in seen or case["split"] != "development" or case["task"] == "routing":
            raise ValueError("Unknown, duplicate, holdout or routing-only case cannot enter training")
        seen.add(case["id"])
        if review.get("case_sha256") != case["case_sha256"]:
            raise ValueError("Review is stale; the case changed")
        if not str(review.get("reviewer", "")).strip() or review.get("training_rights_confirmed") is not True:
            raise ValueError("A named reviewer and confirmed reuse rights are required")
        if case["evidence"] and review.get("evidence_verified") is not True:
            raise ValueError("The reviewer must verify the answer against its evidence")
        answer = review.get("answer")
        if not isinstance(answer, str) or not answer.strip():
            raise ValueError("Approved cases need an actual reviewed target answer")
        # Include evidence and history in training inputs; never teach source-dependent
        # facts as unconditional answers from model memory.
        context = {"history": case["history"], "evidence": case["evidence"], "question": case["messages"][-1]["content"],
            "retrieval_status": case["task"] if case["task"] in {"empty", "unavailable", "access_check_failed"} else "not_run"}
        output.append({"messages": [{"role": "system", "content": "You are Iroko AI. Answer naturally. Conversation history is context; use supplied evidence for factual claims and cite it. State unresolved facts accurately."},
            {"role": "user", "content": json.dumps(context, ensure_ascii=False)}, {"role": "assistant", "content": answer.strip()}]})
    return output


def review_page(rows, path):
    # Review development only. Do not leak held-out targets into prompt tuning.
    payload = json.dumps([r for r in rows if r["split"] == "development"], ensure_ascii=True).replace("<", "\\u003c")
    page = '''<!doctype html><meta charset="utf-8"><title>Iroko dataset review</title>
<style>body{font:16px/1.6 system-ui;max-width:1050px;margin:40px auto;padding:0 20px;color:#152c24}pre{white-space:pre-wrap;background:#eef8f3;padding:20px}textarea{width:100%;min-height:130px;font:inherit}button,input{font:inherit;padding:8px;margin:4px}small{display:block}details{margin:16px 0}</style>
<h1>Iroko conversation dataset review</h1><p>Candidate examples, not approved legal guidance. Export a review file regularly; edits are held in this tab only.</p>
<label>Your name <input id="reviewer"></label><button id="prev">Previous</button><button id="next">Next</button><button id="download">Download reviews</button>
<h2 id="title"></h2><small id="meta"></small><pre id="chat"></pre><details><summary>Source evidence and rubric</summary><pre id="sources"></pre></details>
<label>Reviewed target answer<textarea id="answer"></textarea></label><label><input type="checkbox" id="verified">I verified factual claims against the evidence</label><br>
<label><input type="checkbox" id="rights">Reuse rights for the intended training use are confirmed</label><br><label>Review notes<textarea id="notes"></textarea></label>
<button id="approve">Approve</button><button id="reject">Reject</button><span id="status"></span>
<script>const cases=PAYLOAD;let index=0;const reviews={};const el=id=>document.getElementById(id);
function show(){const c=cases[index],r=reviews[c.id]||{};el('title').textContent=`${index+1}/${cases.length}: ${c.id}`;el('meta').textContent=`${c.category} — ${c.family} — candidate`;
el('chat').textContent=c.messages.map(m=>m.role+': '+m.content).join('\\n\\n');el('sources').textContent=JSON.stringify({evidence:c.evidence,rubric:c.rubric},null,2);el('answer').value=r.answer||c.reference_answer||'';el('notes').value=r.notes||'';el('verified').checked=!!r.evidence_verified;el('rights').checked=!!r.training_rights_confirmed;el('status').textContent=r.decision||'Awaiting review';}
function save(decision){const c=cases[index];if(!el('reviewer').value.trim()){alert('Enter your name');return;}reviews[c.id]={id:c.id,case_sha256:c.case_sha256,reviewer:el('reviewer').value.trim(),decision,answer:el('answer').value,notes:el('notes').value,evidence_verified:el('verified').checked,training_rights_confirmed:el('rights').checked};el('status').textContent=decision;}
el('approve').onclick=()=>save('approve');el('reject').onclick=()=>save('reject');el('prev').onclick=()=>{index=Math.max(0,index-1);show()};el('next').onclick=()=>{index=Math.min(cases.length-1,index+1);show()};
el('download').onclick=()=>{const url=URL.createObjectURL(new Blob([JSON.stringify(Object.values(reviews),null,2)],{type:'application/json'}));const a=document.createElement('a');a.href=url;a.download='iroko-dataset-reviews.json';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000)};show();</script>'''
    Path(path).write_text(page.replace("PAYLOAD", payload), encoding="utf-8")
