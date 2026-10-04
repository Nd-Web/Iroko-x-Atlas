# Iroko document pipeline: implementation and operation

This is the September 30 implementation. The earlier BRIEF/PLAN files contain
historical source reconnaissance, not the deployment instructions for this code.

## Running it (updated 4 October 2026)

The pipeline needs **two processes** against the same database, both with
`DOCUMENT_PIPELINE_ENABLED=true`: the API (accepts uploads, serves evidence and
the source controls) and a **worker** (extracts, OCRs, chunks, embeds, indexes and
collects from regulator sources). Without a worker, uploads stay queued and the
Regulatory sources panel warns after 10 minutes.

- Local: `run.bat` starts the backend, the worker (`python -m ingestion worker`)
  and the frontend. The local `backend/.env` points at the production Render
  Postgres, Blob container and Search index, so local uploads and collections are
  production writes, private to the uploader's workspace.
- Production: the Render API needs `DOCUMENT_PIPELINE_ENABLED=true`, and a worker
  must run: the scheduled Azure job in `backend/deploy/ingestion-worker.bicep`
  (every 5 minutes, `scheduled-drain`) built from the same commit as the API.

Behaviour added on 4 October:

- **Recurring collection works.** A scheduled drain queues enabled sources whose
  schedule (6 hours to weekly, set in the panel) is due. Manual sources
  (interval 0) are still only collected by **Collect now**. Download problems are
  shown on the source; only newly exhausted jobs fail a scheduled execution.
- **Access challenges.** If a site answers with a bot challenge
  (`cf-mitigated: challenge`, as cbn.gov.ng does for every PDF), the run stops
  after that file with status **blocked**. Iroko does not retry around or bypass it.
- **Not yet collected list.** Each run keeps the newest 50 listed items that are
  not in Iroko. For a blocked site, an administrator opens the official link,
  downloads the file in a browser and uses **Import file**. The import is accepted
  only for an item in the latest listing, under the crawler's source key and
  catalogue metadata; when the catalogue states a size (CBN), the bytes must match.
- **Budget goes to new documents.** Never-collected items are tried before 30-day
  re-verification; files imported without a crawl count as verified when they
  were accepted. Broken links back off for 1, 2, 4 … 30 days instead of using
  the batch every run.
- **Titles** from generic listing pages drop "Download the full … here · 415 KB"
  boilerplate and fall back to a tidied file name.
- **Review.** Generic pages carry no publication date, so their documents enter
  review with `publication_date_missing`. The reviewer can enter the date printed
  on the document when approving; it is stored as `date_basis: reviewer_confirmed`
  and indexed. Short text, Word and sheet records are no longer sent to review as
  "little or no text" (that check applies to PDF pages only).
- **Failures.** Validation, checksum and parser errors fail at once with the reason
  shown on the document; outages are still retried with backoff.
- **Sharing.** Platform administrators can share an indexed official regulator
  document with every workspace from its evidence panel (an audit note is required).

Official listing pages verified on 4 October with the collector's identified
client: SEC rules and regulations, SEC guidelines, FCCPC regulations and
guidelines, NDIC publications and the NDPC homepage (attachments downloaded);
CBN `GetAllCirculars` (2,629 items, newest August 2026) and `GetOFISCirculars`
(78 items, newest May 2023) list circulars but challenge every file download.
nfiu.gov.ng timed out.

## Azure Search connection checked September 30

The locally configured endpoint is now `https://irokoai.search.windows.net`.
The existing local Search key authenticated against it, and `iroko-chunks` was
created with the 3072-dimensional vector field and `iroko-semantic` configuration.
The index was read back successfully and currently contains zero chunks.
`backend/create_index.py` now checks an existing index and never deletes or
overwrites it. This only establishes Search connectivity in the local environment;
the production Render environment must set its own endpoint and key.

The updated Azure OpenAI embedding settings returned a 3072-dimensional vector.
The local Blob connection string now targets the `irokoai` storage account;
`iroko-documents` was created as a private container and read back successfully.
The credential remains only in the ignored local `backend/.env`, not this guide.
The local Document Intelligence endpoint is
`https://irokoai.cognitiveservices.azure.com/`. With its key in the same ignored
environment file, a one-page synthetic PDF was processed successfully by the
pipeline's `prebuilt-layout` extraction function: one page returned, expected text
recognized, and method recorded as `azure_layout`. The test file was removed.
The local database URL uses SQLite and the pipeline flag is unset. On September
30, the local application database was migrated to Render Postgres: all 22
tables and 1,719 rows matched after transfer, and the isolated ingestion
migration reached version `20260930_pipeline`. A live backend connection to
that Postgres database was observed after Render settings were updated. No
live regulatory document pull or Azure worker deployment has run.

## What happens to a document

1. An upload, connected drive import or enabled regulator source supplies a file.
2. Iroko computes SHA-256, checks for a duplicate within that source, and preserves
   the original in its existing private Azure Blob container. Storage failure
   rejects the upload; it never claims the file was accepted.
3. One database transaction creates the existing library Document, a revision,
   an audit event, and a processing job. The API returns without waiting for OCR,
   embeddings or indexing.
4. A separate worker claims a job. It reads and verifies the original, extracts
   pages, and preserves both raw and normalized text. PDF page numbers are real;
   Word/text/Excel records use body/sheet locators instead of invented pages.
5. Digital PDF text is extracted locally. Pages with little text, damaged text or
   tables go to Azure Document Intelligence `prebuilt-layout`. Only those page
   numbers are submitted. OCR expenditure is reserved in a daily database budget.
6. Chunks are exact substrings of the normalized text, with bounded token counts,
   character offsets, actual page ranges, headings and hashes. Postgres retains
   these chunks; Azure Search can be rebuilt without repeating extraction.
7. Incomplete OCR, weak extraction, missing regulatory publication dates and new
   versions enter review. Administrators can compare extracted text with the
   original. Incomplete OCR cannot be approved. Empty documents cannot be approved.
8. Approved/good-quality text receives the existing 3072-dimensional Azure
   embeddings and is batch-indexed into the existing Azure Search index. Missing
   embeddings or partial indexing fail the job and trigger retry.
9. A revision becomes current only after successful indexing. Search checks
   Postgres before using managed chunks: partial uploads, archived, unreviewed,
   rejected, altered and old versions cannot reach the answer through the shared
   retrieval path. Citation provenance travels to Researcher and context callers.

The index schema does not change. Provenance is attached from Postgres by chunk
ID. This avoids a destructive Azure index recreation or a second vector database.

## Where information lives

| Data | Location |
| --- | --- |
| Original files | Existing private Azure Blob container, immutable `<document-id>/<filename>` objects |
| Library record | Existing application `documents` table |
| Version identity and review | `ingestion.regulatory_documents` |
| Raw/normalized pages | `ingestion.regulatory_document_pages` |
| Exact chunks and citation offsets | `ingestion.regulatory_chunks` |
| Jobs, attempts and leases | `ingestion.ingestion_jobs` |
| Configured sources and crawl history | `ingestion.ingestion_sources`, `ingestion.ingestion_crawl_runs` |
| OCR budget reservations | `ingestion.ingestion_ocr_budget` |
| Operational audit events | Existing `audit_logs` table |

The `regulatory_*` names preserve the earlier schema convention; these tables
also hold uploaded company documents. Existing application metadata is unchanged.
This implementation writes operational audit records. It does **not** claim that
new ingestion events have been integrated into the separate compliance hash chain.

Version identity is source + byte hash. An unchanged upload is reused. Different
bytes at the same source create a new revision, retain the old original and require
review. This does not infer legal supersession or which regulation applies to a bank.

## Production rollout

Use the same application `DATABASE_URL` for the web API and worker. It must be
Postgres in production. The former proposed `INGESTION_DATABASE_URL` override is
not used because acceptance spans application and ingestion tables atomically.
Do not point this setup at another project's database.

1. Install `backend/requirements.txt`. Back up the application database.
2. With `backend/` as the working directory and production environment loaded,
   run `python -m alembic -c ingestion/alembic.ini upgrade head`.
   The migration creates only the `ingestion` schema and its tables. Use a
   migration connection allowed to create this schema; application/worker roles
   require CRUD access. Do not grant extra permissions to unrelated databases.
3. Ensure the existing private Blob container exists. Configure
   `AZURE_STORAGE_CONNECTION_STRING` and, if nondefault, `AZURE_STORAGE_CONTAINER`.
   Original uploads now fail if storage is unavailable. A container is never
   silently provisioned by the application.
4. Set `AZURE_SEARCH_ENDPOINT=https://irokoai.search.windows.net` and reuse the
   configured `AZURE_SEARCH_API_KEY`, `AZURE_SEARCH_INDEX_NAME=iroko-chunks`,
   semantic configuration and Azure OpenAI embedding settings. The index
   provisioning script now creates an absent index and checks an existing one
   without deleting or overwriting it: run `python create_index.py` from
   `backend/` after verifying the endpoint and key. The local key was confirmed
   to list indexes on this service on September 30; production environment
   values must be configured independently.
5. For OCR set `AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT` and
   `AZURE_DOCUMENT_INTELLIGENCE_KEY`. Set `DOCINTEL_MAX_PAGES_PER_DOCUMENT=50`
   and `DOCINTEL_DAILY_PAGE_BUDGET=500`, or smaller explicit budgets.
6. Start a Render background worker with root directory `backend`, build command
   `pip install -r requirements.txt`, and start command `python -m ingestion worker`.
   Set `DOCUMENT_PIPELINE_ENABLED=true` on both web and worker. A background
   worker is required: the web request does not launch an unreliable in-memory job.
   Check hosting plan availability/cost before adding the worker.
7. Keep `ALLOW_DEMO_SEARCH=false` and `SEED_DEMO_DATA=false` for real customer
   use. Existing demo/index records are not removed by this migration; audit and
   remove demo content separately before serving a customer corpus.
8. Upload a known PDF, verify its original/download, page text and final indexed
   status, then ask questions whose answers can be checked against it. Stop the
   worker mid-job in staging and confirm it resumes after its lease expires.

The flag defaults to false for staged rollout. When false the original upload
path remains available, but the fabricated extraction/search fallbacks have been
removed (search demos now require explicit `ALLOW_DEMO_SEARCH=true`). This code
does not automatically alter production environment variables, run cloud OCR,
configure Azure retention, or deploy itself. The database migration described
above was performed separately.

For local SQLite only, `python -m ingestion init-local` creates the extra tables
using schema translation. It does not create application tables. Run the existing
API setup first. SQLite is a development convenience, not the production queue.

The tokenizer downloads its public encoding on first worker use. For restricted
egress deployments, prewarm `tiktoken.get_encoding('cl100k_base')` during the image
build and set `TIKTOKEN_CACHE_DIR` to a persistent readable path.

## Source collection

Administrators use **Document library → Regulatory sources** to register a URL,
select its listing format, then enable or manually collect it. Each source has a
bounded batch (default 20 attachment attempts). New sources are manual-only
(`interval_hours=0`): enabling permits **Collect now**, but does not schedule a run.
Recurring collection requires an explicit interval of 6 to 720 hours. Collection
runs in the same durable worker. API controls also exist under `/api/ingestion`.

The initial pilot is one manual CBN OFIS batch of up to 20 documents total, not
20 per regulator. Leave other sources paused and do not queue another batch until
the initial evidence and answers have been checked. A download failure can leave
fewer than 20 accepted documents; report the shortfall instead of silently
expanding collection. Existing registered sources keep their stored settings:
set their interval to 0 and batch size to 20 explicitly before using this plan.

Before relying on this first batch for customer answers, verify each accepted
document's source URL, title, reference and publication date against the original.
Compare extracted amounts, percentages, deadlines and tables with the PDF; inspect
all flagged pages. Then test representative questions with known answers and
check that each citation opens the correct document version and page. Include
questions the 20 documents cannot answer and check that the response acknowledges
missing evidence. These are rollout acceptance checks, not completed live tests
or a guarantee that extraction heuristics catch every error. Publication dates
alone do not establish effective dates or legal applicability.

- CBN: JSON catalogue parser is tested with the saved CBN fixture. It handles
  `DD/MM/YYYY`, verbatim reference numbers, normalized references and case-sensitive
  paths. For an MFB pilot, start with the previously discovered OFIS catalogue:
  `https://www.cbn.gov.ng/api/GetOFISCirculars`. The full catalogue is
  `https://www.cbn.gov.ng/api/GetAllCirculars`. Revalidate live availability before
  enabling; past reconnaissance found that PDF downloads can return HTTP 403.
- Other official domains: generic HTML listing parser collects direct PDF/DOCX/XLSX
  links from a supplied listing page. Register the verified official URL yourself.
  Domain allowlisting is not proof that a site's layout has been validated.
- SEC HTML-only circular bodies, RSS, JavaScript-only archives, and bespoke
  NDIC/NFIU/NDPC/FCCPC discovery are **not implemented site integrations** here.
  The generic attachment collector is usable where the official HTML provides
  those links. Add captured fixtures and a parser before claiming wider coverage.

The collector identifies itself, enforces HTTPS/official domains, checks robots
rules including wildcards/longest match, limits response bytes, delays requests,
retries transient failures, and rejects redirects to unrelated domains. It does
not bypass access challenges. Sources start paused. A zero-result page or a high
failure rate is marked suspect. Listing snapshots are retained in Blob Storage;
each run preserves its result/error record. Known versions are rechecked after
30 days. No paid crawling service was added.

## Review and retrieval

Open a document from the library to inspect its evidence. Admins/superadmins can
approve or reject with a note, or retry extraction. A retry clears the failed
extraction checkpoint, then processes the preserved original again. It can incur
new OCR charges. Reindexing from saved chunks is available separately through
`POST /api/ingestion/documents/{id}/reindex` and does not repeat OCR.

Structured regulatory output contains candidate `must`/`shall` obligations as
exact quotations, with page/locator evidence. Publication metadata comes from the
source listing. Effective dates, applicability, penalty interpretations and
institution-specific legal conclusions are not guessed. A reviewer still needs
to establish these facts. This is extraction quality control, not a guarantee of
legally correct model answers.

The existing app uses a shared document library. This change does not turn its
existing department filters into bank-by-bank tenant authorization. Deploy a
separate customer workspace until tenant ACLs are implemented across all agents,
search endpoints and document access paths.

## Recovery and cost controls

- Five attempts with exponential delays; a five-minute lease is renewed every
  30 seconds. Expired work can be claimed by another worker. Old lease tokens
  cannot commit publication. Exhausted jobs are visible as failed.
- Preserved extraction/chunks are checkpoints: a search outage does not repeat
  paid OCR. Blob writes are immutable. Original retrieval verifies its checksum.
- OCR reservations count attempted calls, including failures, to avoid a retry
  storm exceeding the budget. The UTC date defines the daily budget.
- If some pages exceed OCR limits, the document stays in review. Retry after
  changing the limit/budget or providing a readable document. Automatically
  resuming only the remaining OCR pages is a future optimization.
- `python -m ingestion stats` prints job counts; `/api/ingestion/stats`, `/runs`
  and `/sources` expose operations to administrators.
- Soft delete/versioning/WORM settings remain manual Azure decisions. Archiving
  an indexed managed document preserves originals and audit evidence while
  excluding it from retrieval. No destructive retention policy is configured.

## Verification

From `backend/`: `python -m pytest tests/ingestion --disable-warnings` and
`python -m ruff check ingestion tests/ingestion`.

Tests use synthetic documents, saved listings, mocked cloud adapters, and isolated
SQLite databases. Optional Postgres integration tests create and stop a disposable
local cluster if the configured binaries exist (`INGESTION_TEST_PG_BIN`); they
never use the application's configured database. They verify scoped migrations
and concurrent job claims. `npx tsc --noEmit` checks the frontend.

Live Azure Blob/Search/OCR and actual government-site access still require the
staging smoke test described above. Benchmark answer correctness on representative
MFB/fintech questions before making accuracy claims.

Local verification completed: 33 distinct ingestion tests passed (including
isolated Postgres migration/concurrency and source collection/deduplication),
ingestion lint and Python compilation passed, and frontend TypeScript, targeted
ESLint and the Next.js production build passed. Existing `datetime.utcnow()`
conventions generate deprecation warnings in the Python 3.13 test environment.
