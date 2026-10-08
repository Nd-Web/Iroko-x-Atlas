# Iroko chat dataset v1

This is a local candidate dataset and evaluation workflow, not a trained model.
It contains **500 development variants and 100 held-out variants across 60 families**:
40 authored behavioural families and 20 document families from the existing public
CBN extraction snapshot. Each family has ten phrasings. They are not 600 independent
regulatory questions. No customer chats or private institution records are imported.

The initial coverage includes social conversation, capabilities, transcript recall,
follow-ups, requested formatting, topic switches, missing documents, source attribution,
unsupported fines, historical applicability, prompt injection in sources, template versus
actual records, source conflicts, Pidgin, and search/access failures.

## Files and commands

Run from `backend/` with its virtual environment:

```powershell
.venv/Scripts/python.exe scripts/chat_dataset.py build
.venv/Scripts/python.exe scripts/chat_dataset.py validate
.venv/Scripts/python.exe scripts/chat_dataset.py evaluate --limit 500
.venv/Scripts/python.exe scripts/chat_dataset.py evaluate --live --limit 12 --max-model-calls 24
```

`build` reads the existing `.dist/rag-evaluation/corpus.json` and
`backend/tests/evals/cbn_retrieval_questions.json`. It never connects to Postgres or
Azure Search. It accepts only public CBN source records and preserves source URLs,
publication metadata and content hashes. It does not copy PDFs.

Outputs live in `.dist/chat-dataset/v1/`, excluded from Git:

- `development.jsonl`: 500 development candidates.
- `holdout.jsonl`: 100 candidates reserved for subsequent evaluation.
- `manifest.json`: version, hashes, counts and limitations.
- `review.html`: standalone development-set review page.
- `evaluation-*.json`: observed answers, failures, skipped cases, timing and call counts.

Scripts and seed definitions are version-controlled; regenerating source-derived
artifacts requires the local corpus snapshot. Rebuilding is deterministic for the
same inputs and code. Content changes invalidate prior per-case reviews.

## What the evaluations measure

The offline run tests deterministic conversational replies, recall, clarification,
availability messages and routing assertions. Cases that need a model are explicitly
**skipped**, never counted as passes.

`--live` uses the locally configured model and incurs API usage. Calls are sequential,
bounded by `--limit`, `--max-model-calls` and a per-case timeout. The call limit counts
logical completions; the provider wrapper may retry a completion. The report records
requested output-token allowances, not actual billed tokens or a dollar estimate.

The live runner tests conversation components and answer generation with supplied
evidence. It does not measure production retrieval recall, end-to-end request latency,
database persistence or email delivery. Continue using the existing API conversation
and retrieval suites for those chat layers. Mechanical pass/fail checks are triage;
they do not establish legal correctness or human-rated naturalness.

The synthetic evidence tests a fictional process, not Nigerian law. Public CBN targets
do not contain pre-approved reference answers: a reviewer must check both the generated
question and an answer against its source. Historical passages do not establish current law.

## Separation and review

All phrasing variants of a family share a split. Related BVN, AML and licence-revocation
documents stay together, so their versions cannot appear on opposite sides. No public
document crosses the two sets. Synthetic fixtures intentionally recur across tasks:
this evaluates different behaviours, not unseen vocabulary. The historical CBN corpus
was already used in earlier project evaluation; this is a new held-out split for future
dataset changes, not a claim of an untouched external benchmark.

Develop using the 500 examples. The review page excludes the held-out set. Only run
`evaluate --split holdout --live ...` after freezing a candidate change, and do not
tune that candidate to individual held-out answers. Record failures for the next dataset
version with fresh holdout groups.

Open `review.html`, enter the reviewer's name, inspect the evidence, edit the proposed
answer, and approve or reject each candidate. The public document cases start with a
blank answer, to avoid presenting unreviewed legal answers as gold labels. Review decisions
remain in the current tab until **Download reviews** is used; export regularly.

To prepare reviewed development examples for a future supported fine-tuning workflow:

```powershell
.venv/Scripts/python.exe scripts/chat_dataset.py export --reviews PATH/iroko-dataset-reviews.json --output PATH/iroko-reviewed-training.jsonl
```

The exporter rejects held-out cases, routing-only checks, stale hashes, duplicate
approvals, missing answers, unnamed reviewers and unconfirmed source reuse rights.
Source-dependent examples include their evidence; availability examples include the
retrieval outcome. No model is trained or uploaded by this command. Applicability and
reuse rights require human review; automated validation cannot provide that approval.

The current generated set contains **zero human-approved training examples**. The next
step is reviewing a diverse development sample, correcting the largest observed failure
groups, and measuring again. Training is justified only if these measurements show that
prompt/context/routing improvements are insufficient.

This workflow follows the [official OpenAI evaluation guidance](https://developers.openai.com/api/docs/guides/evaluation-best-practices)
on task-specific datasets, representative edge cases and human calibration.

## Initial development baseline — 7 October 2026

- 58 selected dataset, grounded-answer and answer-lead regression tests passed.
- Offline development run: 162 measured checks passed; 338 model-dependent cases
  explicitly skipped. This is not a 500-answer accuracy score.
- Initial live sample: 11/12 mechanical passes. Inspection found a false-positive
  certification regex and an irrelevant licence clarification for checklist completion.
  The regex now distinguishes a direct certification from a qualified denial; the
  answer prompt asks for completion records for this kind of checklist question.
- Targeted live rerun: 4/4 mechanical passes for completion evidence, historical
  currentness, source-injected instructions and unsupported fines (9 logical model calls).
- Browser checks verified development-only review content, approval metadata and
  preservation of an approved answer when navigating away and back. No real human
  approval was created by those tests.
- No held-out live evaluation or model training was performed.

Known qualitative gaps remain: the historical-currentness and unsupported-fine
answers sometimes ask the user to identify a document already supplied. Some answers
repeat the lead in their evidence bullets or include overly broad missing-information
boilerplate. Mechanical passes do not catch all of these issues. Human reviewers should
flag irrelevant follow-up questions and repetition before approving target answers.
The live sample is small and uses supplied evidence, not the production retrieval path.

## Response-quality iteration — 7 October 2026

- Writer and reviewer now share precise missing-information definitions. The reviewer
  can explicitly reject irrelevant draft gap labels; those corrections cannot erase
  exact quote/number validation failures or the reviewer's own unresolved findings.
  Existing claim approval and fail-closed paths remain in place.
- Exact repeated introductions are omitted. One-fact answers use the cited claim alone
  unless a direct yes/no lead is useful. Historical/currentness warnings are consolidated
  for display without dropping their machine-readable gap metadata.
- Development checks now flag unnecessary document-identification questions for supplied
  historical-policy and penalty questions. Sampling covers all selected families before
  repeating variants, and reports include missing-information labels.
- Prompt-only changes still failed one live supplied-policy question. With explicit
  reviewer corrections, the eight-family development sample passed 8/8 mechanical checks
  (15 logical model calls). Offline checks remained 162/162, with 338 model cases skipped.
- 250 focused regression tests passed across grounding, conversation memory, routing,
  presentation, evidence validation and dataset tooling. The final one-fact rendering
  change was verified by deterministic tests after the live sample.

Qualitative inspection still found repetitive paraphrasing in a longer multi-claim answer
and generic wording in the unsupported latest-rule case. These remain review targets;
8/8 is not an expert legal-accuracy score. No held-out evaluation, training job, deployment,
or production database operation was performed in this iteration.
