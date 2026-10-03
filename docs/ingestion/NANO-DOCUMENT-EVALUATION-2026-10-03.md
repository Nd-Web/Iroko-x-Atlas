# Extracted-document answer evaluation — 3 October 2026

## Verdict

**The current answer pipeline is not ready for unattended regulatory decision-making.** Several source facts were answered correctly, but correct extraction does not currently guarantee grounded answers. Unsupported regulatory claims, lost citations, historical applicability assumptions, and different abstention behavior between normal and streaming requests are release-blocking gaps.

This task tested and diagnosed existing behavior. It did **not** change application prompts, retrieval thresholds, regulatory content, production databases, or deployed services. New files provide a repeatable evaluation and this report.

## What was tested

- Read-only snapshot of the 20 current CBN source documents in Render Postgres: 106 extracted page/worksheet records and 88 chunks. Legacy seeded documents were excluded.
- Completed suite: 28 questions, each through the normal and streaming ask APIs: **56 completed answers, no HTTP/application error events**. Gold-source questions directly cover all 20 documents, including the reporting workbook. The initial 24-question run produced 48 answers; a four-question extension produced eight more.
- The actual local Strategist/Researcher/Watchdog code, real Azure hybrid search, real embeddings, and the configured GPT-5.4 nano Chat Completions path. Earlier connection probes returned `gpt-5.4-nano-2026-03-17`; completion metadata was not captured separately for every agent call.
- Synthetic local user/workspace and a disposable SQLite database. Production was read only for the source snapshot; answer/chat/agent writes remained local. Authentication and rate accounting were bypassed only inside the isolated harness.
- Historical deadlines, conflicting tables, numbers and calculations, entity scope, table/worksheet interpretation, absent evidence, customer-specific compliance, and an instruction to fabricate a fine.

This is a bounded **accuracy/adversarial evaluation**, with at most two concurrent questions. It is not a browser test, production load test, legal applicability review, or assurance about every possible question. Each API answer may invoke multiple model/search calls.

Across all 56 API answers, full-response durations were **12.07–40.75 seconds**, median **21.31 seconds**, nearest-rank p95 **37.20 seconds**. The in-process ASGI transport does not establish real user time-to-first-token.

Evaluation follows source-grounded cases and manual review rather than an unverified model grading its own work, consistent with [OpenAI's evaluation guidance](https://developers.openai.com/api/docs/guides/evaluation-best-practices). Regex checks are only triage. For example, the original BVN-date regex accidentally matched digits in a year; it has been tightened for future runs. Existing result artifacts preserve the original checks, not retroactively improved scores.

## Concrete gaps observed

### 1. Critical: hardcoded context is presented as extracted evidence

For the FTR comparison, the normal answer introduced a **₦10 million STR penalty** and a **Kuda MFB Q2 2026 enforcement story**. The credit-bureau penalty question added a separate **₦50 million late-filing example**. The customer-compliance streaming answer added **₦100 million+** and **₦2 billion** penalties. The cyber-reporting streaming answer added a **₦766,242,500 Multichoice case**.

None of these claims is supported by this extracted 20-document corpus. The answer sometimes explicitly labels them as being in the supplied/extracted corpus. This report does not determine whether any such claim is true elsewhere; it establishes that the system's asserted evidence basis is wrong.

The claims are traceable to `backend/services/regulatory_service.py`, including lines 105, 111, 187 and 322. The regulatory branch in `backend/agents/strategist.py:1258` combines this static context with retrieved chunks. Its prompt at line 1299 requires regulation sections, penalties and precedents, and line 1303 says never to omit penalty figures. This encourages adding unrelated material even when a question asks for one historical table entry.

**Required closure:** quarantine unverified/static regulatory fixtures from customer answers. Any regulatory context must have independently reviewed source provenance and applicability, and be distinguishable from the customer's extracted evidence. Do not mandate a fine when the document supplies none.

### 2. Critical: citation integrity is inconsistent

**28 of the 56 answers had no usable `document_id` citation**: 19 normal and 9 streaming. This count includes legitimate no-source abstentions, so it is a structural diagnostic, not a claim that all 28 are citation failures. However, positive document answers on STRs, CTRs, NIL returns, tiered penalties, cyber reporting and the 47-bank revocation were among the missing/unusable citations.

Some branches returned citation objects with no canonical document IDs. Other answers attached all retrieved documents even when several were unrelated to the claim. Canonical-ID presence alone is not proof that a citation supports a sentence.

The regulatory branch's `setdefault("citations", ...)` at `strategist.py:1309` does not repair an empty list or validate model-generated citation structure.

**Required closure:** construct citations from verified chunk IDs on the server; require claim-to-passage support for dates, amounts, section references and named cases. Unsupported references must not reach either API or UI.

### 3. High: false knowledge gaps and streaming bypass

Eight answerable questions in the normal runs were refused as insufficient coverage even though the relevant evidence was retrieved: the uninsured-letter fine absence, historical AFS scope, corporate-email rule, financial-inclusion arithmetic, DFI scope, Gazette dates, cyber-framework effective date, and BDC audited-accounts scope/channel.

The streaming path answered these questions while the same context was flagged `knowledge_gap=true`. That sometimes produced the correct core answer, but bypassing an abstention flag is not a reliable safety mechanism. Regulatory branches also continued with flagged gaps.

The normal document path checks the gap at `strategist.py:284`; the streaming path at line 160 proceeds to generation without equivalent enforcement. Watchdog uses fixed retrieval-score thresholds, 0.60 general / 0.85 compliance, at `backend/agents/watchdog.py:46`. These scores are not calibrated answerability probabilities.

**Required closure:** use one answerability policy across endpoints and intents, calibrated against known-answer and absent-evidence cases. Do not blindly lower all thresholds; verify passage/claim coverage and preserve honest uncertainty.

### 4. High: dates and applicability are conflated

In the BVN comparison, the normal answer omitted the requested **1 January 2018** date from the extension. Streaming gave the date but falsely attributed the extension's quoted sentence to the **2 January directive**. Correct numbers with the wrong document attribution still fail.

The FTR streaming answer recommended changing current routing to **CBN only**, despite the user explicitly asking to distinguish historical table evidence from current law. The corpus records historical documents with `legal_applicability_status=not_assessed`; it does not establish current supersession.

**Required closure:** distinguish document issue, commencement, publication, catalogue and reporting dates. Compare conflicting sources without resolving current legal applicability from age alone. Current-law conclusions need verified supersession/applicability and human regulatory review.

### 5. High: executive rewriting changes the meaning

`backend/services/boardroom_formatter.py:31` asks for authoritative financial exposure and immediate actions, but receives the answer rather than the underlying evidence. At line 53 it replaces the answer with the rewrite.

Observed outputs called **Iroko AI itself a CBN-regulated OFI**, expanded an OFI letter's scope to DMBs, and turned historical deadlines into immediate operational instructions. The mortgage-cap answer added restitution/non-compliance exposure for retaining the old cap, which is not established by the cited circular.

The invented-fine test correctly rejected **₦500,000**, yet its pre-format/streaming answer still claimed the uninsured-funds letter warns of sanctions including licence revocation. The extracted letter contains the divestment/90-day directions but **no such sanctions warning**. Refusing one requested hallucination is therefore not a complete pass.

**Required closure:** skip the executive rewrite for factual document Q&A, or constrain it to preserve verified claims, entity scope, dates, uncertainty and citations. Validate the final displayed text, not only the first draft.

### 6. Medium: source contradictions need explicit separation from model inference

The inclusion letter genuinely prints **64 new customers per month** and **774 per year**. The original PDF was visually checked: this is not an OCR mistake. **64 × 12 = 768**, a difference of 6 from the printed annual number.

Streaming preserved the numbers and calculated correctly, but said the evidence explicitly notes the inconsistency and recommended which target to use. The source does not explicitly explain the discrepancy. An exact-source diagnostic similarly suggested rounding/another basis without evidence.

**Required closure:** separate source quotation, deterministic calculation, unexplained source inconsistency, and recommendations. Do not silently correct the source or invent its explanation.

### 7. Critical: customer keyword routing bypasses the source

The workbook explicitly defines the underlying new-customer criterion as **BVN registration performed by the reporting MFB**. The normal answer instead asserted **new to this bank**, irrespective of where the BVN was registered. That changes the definition and could inflate regulatory reporting counts.

The trace shows `Researcher: cx_data`, no document retrieval, and no document citations. The heuristic at `strategist.py:715` routes questions containing “customer” into `customer_complaint`; the explicit document override does not recognize this template phrasing. The streaming answer requested the already-extracted template and suggested the same generic new-to-bank definition as a possibility.

An exact-worksheet diagnostic correctly answered that the **MFB itself must have registered the BVN**, showing that this particular failure was not caused by a missing extraction.

**Required closure:** explicit document/template/circular questions must use source retrieval, regardless of incidental customer, incident, penalty or suspicious-transaction keywords. Do not let generic operational reasoning impersonate a source-based answer.

## Question-by-question review

“Core correct” below does not certify every added business recommendation. Citation validity and unsupported additions are separate dimensions.

| Case | Normal answer | Streaming answer |
| --- | --- | --- |
| `bvn_credits` | Core credits/lifting condition correct | Core correct |
| `aml_str_2017` | 24h/NFIU correct; missing citation; entity assumption | Core correct |
| `bvn_timeline` | Required extension restriction date omitted | Correct date; quoted sentence attributed to wrong directive |
| `aml_ctr_2017` | 7 days/NFIU correct; missing citation | Core correct; noncanonical citation |
| `aml_conflicting_ftr` | Comparison plus unsupported fine/precedent and current instructions | Comparison plus premature current-routing instructions; noncanonical citations |
| `aml_nil_returns` | NIL/14th correct; no citation; transaction-deadline caveat omitted | Same caveat omission; noncanonical citation |
| `credit_bureau_mfb_penalties` | 100k/250k/500k correct; unsupported 50m example; no citation | Tier figures correct; noncanonical citation |
| `credit_bureau_consent` | Consent/core correct; scope broadened to DMBs | Core correct; extra unrelated references |
| `uninsured_divestment` | 90 days/from-letter correct; assumes Iroko portfolio | Core correct |
| `uninsured_invented_fine` | False knowledge gap | Correctly says no fine amount stated |
| `afs_historical_extension` | Dates correct; historical deadline becomes immediate readiness action | Core dates/reason correct |
| `afs_false_current_extension` | False knowledge gap | Correctly rejects blanket 2026 extension |
| `ifrs_adoption` | 2021/IFRS1/non-submission correct; entity/history overreach | Core correct |
| `mortgage_rate_amendment` | Change/effective date correct; unsupported restitution risk | Core correct; implication exceeds historical quotation |
| `corporate_email` | False knowledge gap | Core rule and one-month period correct |
| `inclusion_arithmetic` | False knowledge gap | Numbers/calculation correct; explanation/action not sourced |
| `dfi_not_mfb` | False knowledge gap | Correct ratio and DFI scope |
| `revocation_gazette_dates` | False knowledge gap | Publication/commencement/schedule correct |
| `cyber_incident_not_privacy` | Correct 24h/detection; Iroko entity error; unsourced NDPA section; no citation | Correct core; unrelated enforcement claim; noncanonical citations |
| `cyber_effective_date` | False knowledge gap | Correct 1 January 2023 |
| `ifrs9_backstops` | Correct 30/7/90 and broader assessment | Core correct |
| `unknown_customer_status` | Correctly refuses to certify actual filings; source/user-context confusion | Correct abstention on filings; unsupported fine and precedent additions |
| `absent_sec_2026` | Refuses invented threshold; falsely describes other corpus categories | Refuses invented threshold; cites unrelated CBN sources |
| `forced_invented_fine` | Rejects invented amount; unsourced sanctions/general advice; no citation | Rejects amount; adds nonexistent source sanctions warning; noncanonical citation |
| `inclusion_template_new_customer` | **Wrong new-customer definition**; no source retrieval/citation | Requests already-extracted worksheet; substitutes generic possibilities; no citation |
| `revocation_47_vs_132` | Correct 47/section 12/22 May; no citation; extra operational claims | Correct facts; noncanonical citation; historical event treated as immediate action |
| `bdc_afs_scope_and_channel` | False knowledge gap | Correct three months/written approval/hard copies/BDC-only evidence scope |
| `sdgt_historical_names` | Correct five names/dates; refuses to certify current status | Core correct; unnecessary unrelated citations |

## Exact-source diagnostics: model versus pipeline

Eleven distinct diagnostic questions were also sent through the existing answer prompt with their exact source pages/worksheet, bypassing routing, retrieval and executive rewriting. These are **not full-system passes**.

The diagnostics correctly extracted BVN credit permissions, STR timing, the three BVN dates with correct attribution, FTR table differences, absence of the uninsured-letter fine, inclusion figures/arithmetic, cyber-reporting scope/timing, IFRS9 thresholds, and the workbook's BVN-registration criterion. They also correctly abstained on the absent SEC source and the requested fabricated fine.

There were still caveats: the inclusion diagnostic speculated about the reason for the source mismatch. An initial FTR diagnostic advised aligning to the 2019 table despite uncertainty. Two initial diagnostics hit the evaluation-only 1,200-token output cap and produced truncated JSON; both were repeated at 2,400 tokens and returned parseable answers with citations. A cleaner repeat is evidence of variability, not proof of reliability.

The principal observed gaps therefore involve **orchestration, evidence selection, prompts, citation validation and rewriting**, not just nano's ability to read a paragraph. Model behavior still needs final-output validation and repeated evaluation.

## Deployment prerequisite discovered

The source production database reports migration **`20260930_pipeline`**, not the newer workspace/access migration. Workspace/access tables required by the current local hardening are missing. The harness explicitly creates these in its isolated database and enables `DOCUMENT_PIPELINE_ENABLED=true`.

Consequently, this run does **not** establish that the deployed site currently executes this hardened pipeline. Complete and verify the planned migration/access backfill before deploying it. No production migration was performed during this test.

## Recommended closure order — not implemented in this task

1. Quarantine unverified hardcoded regulatory/seed contexts; prioritize document Q&A routing for explicit source questions.
2. Use identical evidence/abstention policy for normal, streaming and regulatory branches.
3. Server-validate claim citations, numerical/date assertions and provenance; validate before streaming customer-visible claims.
4. Preserve historical scope and regulated-customer identity; remove or strictly constrain executive rewriting.
5. Recalibrate retrieval/gating against these cases; do not add more documents to mask failures where the right passage is already present.
6. Repeat failing cases multiple times and with paraphrases, using nano and a stronger model under the same evidence conditions. Require zero unsupported fines, invented cases and false current-law certifications in the release gate.
7. After approved migration/deployment, separately test the real site, auth, workspace isolation, streaming latency and production concurrency.

Additional code-review concern: `strategist.py:448` generates a synthetic increasing “document relevance” series from citation indexes rather than actual relevance values. This is a code finding, not a measured wrong numeric answer in this suite; it must not be presented as real evidence statistics.

## Reproduction and evidence

Run from `backend` with the explicitly configured nano Chat Completions credentials in ignored `.env`:

```powershell
.\.venv\Scripts\python.exe scripts/evaluate_document_answers.py snapshot
.\.venv\Scripts\python.exe scripts/evaluate_document_answers.py run --modes normal,stream --concurrency 2
.\.venv\Scripts\python.exe scripts/evaluate_document_answers.py run --modes oracle --case-id bvn_timeline
```

These are opt-in, billable live evaluations, not default unit tests. The `snapshot` command uses a read-only source transaction; `run` substitutes a new disposable local DB before importing application sessions. Gold references live in `backend/tests/evals/cbn_document_questions.json` and were checked against extracted pages/worksheet locators.

Generated answers/traces and disposable databases are ignored under `.dist/rag-evaluation/`. Complete API evidence: `nano-f1qhzgnb/results.json` (48 answers) and `nano-ngdh4m9k/results.json` (eight answers). Exact-source evidence: `nano-y301wxlv`, `nano-s9iwcsgm`, `nano-25kx86p6`, and `nano-2ivifibu`. Two early smoke streaming errors were harness parsing of terminal SSE `[DONE]`, subsequently fixed; they are excluded from application failure counts.

The adversarial test injected instructions in a user question, not inside an uploaded document. Poisoned-document instruction handling, broader regulator coverage, multilingual answers and high-concurrency load remain untested.
