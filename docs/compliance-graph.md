# Compliance knowledge graph: rollout and operation

The graph links each regulatory **requirement** to the workspace's own **controls** and to the
**records** that evidence them, with a quote and a review history for every link. It powers the
Knowledge Graph page, the "how does X relate to Y" step in chat, the compliance-records answers
(gaps, owners, due dates, what changed) and the audit pack export.

## What a reader of the graph can rely on

- Every link is **stated in source** (a verified quote with an explicit cue such as "hereby
  amends"), **suggested by Iroko** (the model's reading), or **entered by a person**. Separately,
  it is proposed, confirmed, rejected or needs re-review. Nothing is auto-confirmed and no
  confidence score is shown.
- Quotes are always cut from the document's own text. The model only points at numbered sentences.
- A gap is shown as "Not established in Iroko's records", never as non-compliance.
- A licence revocation is not an instrument revocation, "(as amended)" is not an amendment, a
  shared subject is not a relationship, and a reference number carried by two documents is only a
  suggestion.
- Effective dates come from the instrument's own words. A date that belongs to one requirement
  ("Effective August 1, 2017, customers without BVN shall not …") stays on that requirement.
  A date quoted from an earlier letter is never used.
- Review is split by layer. The Iroko team (superadmins) confirms shared regulation facts.
  Each workspace's admins confirm their own controls, evidence, applicability and mappings.
- All graph data is isolated per workspace. Shared library facts are visible to every workspace
  that can see the documents.

## Settings

| Where | Setting | Value |
|---|---|---|
| Render API | `COMPLIANCE_GRAPH_ENABLED` | `true` (the page and endpoints return 503 while false) |
| Render API | `DOCUMENT_PIPELINE_ENABLED` | `true` (still outstanding from the pipeline rollout) |
| Azure worker | `complianceGraphEnabled` (Bicep parameter) | `true` (default) |
| Azure worker | `responsesEndpoint`, `responsesApiKey`, `responsesDeployment` | the production Responses model (`gpt-6.1-sol-1`) |
| Azure worker | `LLM_FALLBACK` | `false`, set by the template: an outage defers jobs instead of downgrading to a test model |
| Both | `GRAPH_DAILY_TOKEN_BUDGET` / `GRAPH_WORKSPACE_DAILY_TOKEN_BUDGET` / `GRAPH_TOKENS_PER_MINUTE` | 2,000,000 / 1,000,000 / 30,000 by default |
| Local only | `IROKO_LOAD_DOTENV=false`, `IROKO_LOAD_KEYVAULT=false` | Stop `main.py` from loading the production `backend/.env` and Key Vault, for isolated runs |

The tables (`cg_*`) are created by the API at startup (`init_db`). No migration is needed. The
worker defers graph jobs (it doesn't fail them) until the tables exist.

## Rollout order

Each production step needs the owner's go-ahead.

1. **Upload the core rulebooks now, in parallel.** The library lacks, among others:
   - MFB: the prudential guidelines, the AML/CFT/CPF Regulations 2022, the MLPPA 2022 and the NDPA 2023.
   - Payments: the PSP licensing framework and the mobile money, agent banking, consumer
     protection and cybersecurity guidelines.

   Upload them as shared regulator documents.
2. **Create the pilot workspace and assign every customer user to it before anyone uploads.**
   New users otherwise land in private `user:<id>` workspaces, and moving a user who already has
   documents is refused. Put all Iroko staff in one library workspace.
3. **Ship the backend with `COMPLIANCE_GRAPH_ENABLED=false`.** Render deploys automatically and
   the tables are created on startup.
4. **Rebuild the worker image from the same commit and redeploy
   `backend/deploy/ingestion-worker.bicep`** with the new parameters (`responsesEndpoint`,
   `responsesApiKey`, optional budgets). Use the clean-worktree procedure in
   [ingestion/OPERATIONS.md](ingestion/OPERATIONS.md).
5. **In the Render dashboard**, set `COMPLIANCE_GRAPH_ENABLED=true` and
   `DOCUMENT_PIPELINE_ENABLED=true`.
6. **Deploy the frontend.**
7. **Queue extraction for the existing library.** Either:
   - as a superadmin on the Knowledge Graph page, call `POST /api/compliance-graph/admin/backfill`; or
   - from `backend/` with production settings:
     `python -m ingestion graph-backfill --production`, optionally with `--document <id>`,
     `--workspace <id>` or `--force`.

   The CLI refuses a non-SQLite database without `--production`. The scheduled worker then works
   through the queue in five-minute drains.
8. **Review.**
   - A superadmin works through Review → Regulation facts (addressees, references, effective dates).
   - The customer's admin confirms the licence categories (the top-right button), uploads
     policies, procedures and records with the right role, then reviews Iroko's control
     mappings and evidence links.

## Day-to-day operation

- **Health.**
  - The Overview tab shows extraction backlog and failures.
  - `python -m ingestion stats` counts jobs by kind and state.
  - `GET /api/compliance-graph/admin/runs` lists recent stages and estimated tokens. Other
    workspaces' private documents appear as counts only.
- **Deferred jobs are normal.** A job waits, without using a retry, in four situations:
  - a long document continues in the next slice after the 150-second time box;
  - the daily budget is spent, so it resumes after midnight Lagos time;
  - the model is unavailable, so it retries every 15 minutes and fails visibly after 24 hours;
  - the worker has the flag off or the tables don't exist yet.
- **Graph jobs never block document processing.** Batch drains count only document and source
  jobs.
- **Re-running a document:** `python -m ingestion graph-backfill --production --document <id> --force`.
  - Reviewed rows are never overwritten: newer machine output for a confirmed or rejected item is
    kept as a proposal for the reviewer to accept.
  - A new version of a document keeps owners, decisions and confirmations through each
    requirement's lineage. Reworded requirements raise a change impact instead.
- **Change tracking.**
  - Stated (or confirmed) amendments, revocations, supersessions and deadline extensions become
    library change events.
  - Each workspace sees only the impact on its own links, with a task routed to Compliance.

## Evaluations

Run these from `backend/`. All of them use isolated SQLite and never touch production data.

| Command | Checks | Cost |
|---|---|---|
| `python -m pytest tests/compliance_graph` | 77 tests: rules, jobs, workspace sync, permissions, isolation, chat, verdicts | none |
| `python scripts/evaluate_graph_extraction.py --offline` | The deterministic gold-set facts on the 20 CBN documents plus synthetic letters: references, letter dates, addressees, applicability per licence, relationships and their traps, effective dates, change events | none |
| `python scripts/evaluate_graph_extraction.py --model nano` | Also the model-dependent requirement checks: hand-labelled recall, kinds, computed deadlines, history and title traps | nano test deployment |
| `python scripts/evaluate_graph_extraction.py --model sol --mapping` | All of the above on the production model. Then a pilot MFB workspace (`tests/evals/graph_fixtures`): controls found, suggested mappings, evidence links, and related-sounding clauses that must map to nothing | production model tokens |

The gold set is `tests/evals/graph_gold.json`. Every expectation was read from the document's
own text and carries a short reason. Reports are written to
`.dist/rag-evaluation/graph-extraction-<time>.json` and list each extracted requirement and each
suggestion in words for review. The latest results are in the next section.

## Latest evaluation results

Both runs were made on 9 October 2026 on the 20 CBN corpus documents, plus 4 synthetic letters and the pilot-workspace fixtures.

| Check | gpt-6.1 sol (production model) | gpt-5.4 nano (test model) |
|---|---|---|
| Deterministic facts (references, dates, addressees, applicability, relationships and traps, effective dates, change events) | 125 / 125 | 125 / 125 |
| Model-dependent requirement checks | 44 / 44 | 41 / 44 |
| Hand-labelled requirement recall | 100% | 96.7% |
| Precision traps avoided (history restated from earlier letters, definitions, titles, the regulator's own actions) | 8 / 8 | 6 / 8 |
| Pilot-workspace mapping (controls found, mappings, evidence links, no mapping for related-sounding clauses) | 18 / 18 | 14 / 18 |
| Chat: the five pilot questions plus a graph outage | 6 / 6 | 5 / 6 |

Sol's run took 12 minutes and an estimated 160,000 tokens. The nano run started before the mapping judge was given document context, which is the fix that took Sol from 17 to 18 mapping checks.

The CBN texts exposed these issues, and the gold set now guards each of them:

- **Effective dates.**
  - A date stated for one requirement was being taken as the instrument's date.
  - A date reported from an earlier letter was being taken as this letter's date.
  - The "Commencement" note of a statutory instrument was missed.
- **Letterhead.** Department-name headings above the Ref line hid the own reference and the letter date. A letter could then cite itself.
- **List items.** Items under "all OFIs are required to:" were missed. Items under "… were required to:" restate an earlier letter.
- **Deadlines from the letter date.** "Within 90 days of the date of this letter" now becomes a date.
- **Addressees.** A misspelt "MICROFINACE BANKS" was read as commercial banks.
- **Shared reference numbers.** Resolution depended on the order documents were processed.
- **Changes before review.** An amendment older than a confirmation flagged that confirmation for re-review.
- **Mapping without context.** The judge compared "this policy" without knowing which policy it was.

## Decisions waiting for the owner

- **Addressee terms and licence categories** (`services/compliance_graph/taxonomy.py`). For
  example, a bare "banks" counts only as a suggestion of DMB/PSB, and OFI includes MFBs but not
  payment licences.
- **Returns beyond MFBs.** Applicability for NFIU STR/CTR, the NDPC audit and NDIC returns is
  listed as `PROPOSED_WIDER_RETURN_GROUPS` and is not applied until signed off. Until then, those
  returns apply to MFB licences only.

## Known limits

- References are resolved by reference number only. A citation by title ("the Guide to Charges")
  never links on its own.
- Statutory-instrument numbers ("S.I. No. 22 of 2023") are not yet normalised as references.
- Without the rulebooks above, requirements about data protection or the AML/CFT regulations
  can't be mapped. The graph shows such controls as unmapped rather than guessing.
- A fully local end-to-end run would need local stand-ins for Blob storage and Azure Search,
  which upload and indexing require. The eval harness covers the graph on the existing corpus
  instead.
