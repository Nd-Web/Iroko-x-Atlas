# Iroko AI: Regulatory Document Ingestion Pipeline, Build Brief

You are implementing a new subsystem inside the existing Iroko AI codebase. Read this entire brief before writing any code.

**Revised 2026-09-18 (Africa/Lagos). Status: documentation/configuration-template review only; Phase 1 is not approved.**

This is the full repository-local revision of the user-supplied build brief at
`C:/Users/HomePC/.codex/attachments/57ea794a-ff32-4a9d-bd43-53af24d421bc/pasted-text-1.txt`.
The source attachment is preserved unchanged. This revision incorporates the
2026-09-18 instructions for crawler identity, isolated ingestion metadata and
Alembic ownership, database selection, safe pgvector reuse, and the proposed
1,536-dimensional ingestion embeddings. Original requirements remain in effect
except where explicitly revised here. Repository findings, remaining design
questions, and incomplete reconnaissance are tracked in [PLAN.md](PLAN.md).

---

## AMENDMENTS — 2026-09-18 (supersede everything below that conflicts)

Approved after CBN reconnaissance completed. Where this block contradicts a
later section, **this block wins**. Evidence for each is in
[PLAN.md §0](PLAN.md).

1. **pgvector is dropped entirely.** Every pgvector, `halfvec`, HNSW-on-Postgres
   and extension-namespace requirement below is void, including the section 3
   dependency row, the section 5 dimension discussion, the "pgvector availability
   and namespace" section, and the integration-test requirement for pgvector.
   Postgres remains the system of record. **Azure AI Search is the retrieval
   index**, rebuildable from Postgres — the repo already runs hybrid search there
   and a second vector stack must not be built. Proposed index definition:
   [azure-search-index.md](azure-search-index.md).

2. **Embedding dimensions are 3072**, not 1536. The 1536 figure existed only to
   respect pgvector's 2,000-dimension ceiling, which no longer applies. This
   matches the existing `iroko-chunks` index and `text-embedding-3-large`.

3. **CBN dates are `DD/MM/YYYY`.** The "month/day/year, e.g. Published
   10/30/2018" assumption in the CBN section is wrong. Proven across all 2,629
   records: 1,586 have a first component > 12, none have a second > 12. Parse
   with an explicit `%d/%m/%Y`, and fail loudly if a future capture contains a
   row that parses only as MM/DD/YYYY.

4. **`urllib.robotparser` must not be used.** Against CBN's real `robots.txt` it
   permits every path, including the two CBN disallows: it has no `*`/`$`
   support, and its first-match precedence lets the leading `Allow: /`
   short-circuit every `Disallow`. Phase 1 needs a matcher with longest-match
   precedence and wildcard support per the Google robots specification.

5. **CBN listings are JavaScript-rendered, but Playwright is NOT needed.** The
   category pages carry no rows; a Kendo grid loads them from JSON endpoints
   (`/api/GetAllCirculars` and per-category equivalents), which `robots.txt`
   allows. There is no server-side paging — one request returns the full
   catalogue — so no pagination handling is required.

6. **CBN PDFs are blocked by Cloudflare (HTTP 403).** No bypass is permitted:
   Bright Data Web Unlocker is not approved for cbn.gov.ng, and browser-identity
   spoofing and challenge solving are forbidden. Phases 4 and 5 must work from
   local fixture files placed manually in
   `backend/tests/ingestion/fixtures/pdfs/`.

7. **`media_type` extends to spreadsheets**: `application/vnd.ms-excel` and
   `application/vnd.openxmlformats-officedocument.spreadsheetml.sheet`. Store
   the originals with full metadata, set status `stored_unparsed`, skip
   extraction. Never silently drop a regulatory artifact.

8. **Add `reference_number_normalized`** (trimmed, internal whitespace
   collapsed, uppercased, indexed) alongside the verbatim `reference_number`,
   used for lookup and the exact-match search boost.

9. **Tooling**: `pytest`, `pytest-asyncio`, `respx`, `ruff` are approved and
   installed. **mypy is deferred** — the per-phase checklist is tests and lint
   only. `make` is unavailable, so `backend/tasks.py` is the equivalent.

The current task authorizes changes to documentation and configuration templates
only, followed by a review stop. Do not create production models, settings code,
migrations, tests, or services; install dependencies; run database DDL; or begin
Phase 1 during this review. All implementation and phase approval gates below
remain in force. An observed PostgreSQL service or installed extension file does
not establish the intended database, its extension namespace, permissions, or
whether another repository uses the same database. Record verified facts and
leave those relationships unknown until checked.

## 0. How to work

Work in the phases listed in section 17. At the end of every phase:

1. Run the test suite, linter and type checker the repo already uses.
2. Summarise what you changed, which files you touched, and why.
3. List open questions and any assumptions you made.
4. **Stop and wait for my approval** before starting the next phase.

Ground rules:

- **Explore before you write.** Reuse the repo's existing conventions except for the explicit ingestion isolation requirements in this revision. Before Phase 1, find out how the project handles package layout, settings, async DB access (SQLAlchemy version, sync or async), migrations, background jobs, logging, auth for admin routes, dependency management (Poetry, uv or pip), and the existing hash-chained audit trail. Ingestion must have its own SQLAlchemy metadata/base and scoped Alembic environment as specified in section 6; do not attach ingestion tables to shared application metadata or repurpose the existing placeholder Alembic configuration. Reuse existing services and conventions wherever that ownership boundary permits.
- **Never invent URLs, CSS selectors, table structures or date formats.** Fetch the real page, save it as a test fixture, and derive parsers from what you actually see. If a page cannot be fetched, stop and tell me.
- **Ask before** adding a new infrastructure service, changing existing tables, modifying the audit trail's core logic, changing agent prompts or agent code, or adding any dependency not listed in section 3.
- **Licences:** only MIT, BSD or Apache-2.0 dependencies. Do not use PyMuPDF (AGPL). Ask before adding anything GPL, AGPL or commercially licensed.
- **Polite, lawful crawling only.** Respect robots.txt, rate limits and any access controls. Never bypass captchas, logins, paywalls or blocks. If a site blocks us, log it and tell me.
- **Verbatim rule.** Stored regulatory text must be the regulator's exact words. No LLM rewriting, summarising or "cleaning" of stored text. Only the deterministic whitespace normalisation described in section 10 is allowed.
- **Originals are immutable.** The app never overwrites or deletes a stored original.
- **No secrets in code.** Everything sensitive comes from environment variables. Keep `.env.example` updated.
- **Local development must not require Docker.** Detect the OS. Check pgvector availability and installation in the effective ingestion database, not merely the server's extension files. Reuse an already-installed `vector` extension in its actual namespace; never reinstall or relocate it. If absent from the database but available on the server, creation in the owned `ingestion` schema is a future Phase 1 operation under section 6. If unavailable on the server, or creation fails for lack of privileges, stop and give me options rather than working around it. Do not run DDL during the current documentation review.
- **Database ownership is explicit.** Ingestion-owned objects live only in schema `ingestion`. No ingestion migration may issue `CREATE`, `ALTER`, or `DROP` against objects outside that schema. Keep the existing table prefixes as additional protection. Never downgrade a shared database without explicit approval, and never alter another repository's configuration, migrations, schemas, or tables.

## 1. Context

Iroko AI is an autonomous compliance intelligence platform for Nigerian microfinance banks (MFBs) and fintechs. It uses five agents: Researcher, Watchdog, Analyst, Sentinel and Strategist. Watchdog monitors regulatory changes. Analyst and Sentinel reason over regulations and must cite the exact clause they rely on. The stack is FastAPI, Postgres, Redis, Azure OpenAI, Semantic Kernel and Next.js, with a hash-chained audit trail and a NetworkX knowledge graph.

This subsystem discovers new publications from Nigerian regulators, downloads the originals, stores them immutably, extracts text page by page, chunks it verbatim, embeds it, makes it searchable with precise citations, notifies the agents, and records every step in the audit trail.

```
crawl → download → dedupe/version → store original → extract pages
      → chunk (verbatim) → embed → index → notify Watchdog
```

Every stage is a separate, idempotent, resumable job.

## 2. Scope

**In scope**

- Regulators in this order: CBN and SEC first; NDIC, NFIU, NDPC and FCCPC in a later phase.
- Publications delivered as PDFs, and publications that exist only as HTML pages (SEC circulars are often HTML).
- Backfill (historical) and incremental (new items only) crawling.
- A search service the agents can call, returning verbatim chunks with citations.
- An admin CLI, admin API endpoints and basic monitoring.

**Out of scope for now** (design so these can be added later)

- Customer-uploaded documents. Keep the storage module generic enough to add a separate per-tenant container later.
- Inferring regulatory supersession (e.g. "circular A replaces circular B"). File-level versioning is in scope; legal supersession is not.
- LLM summaries, frontend UI, and knowledge-graph integration.

## 3. Approved dependencies

| Purpose | Library | Licence |
|---|---|---|
| HTTP | httpx | BSD-3 |
| HTML parsing | selectolax (BeautifulSoup only if selectolax can't handle a page) | MIT |
| RSS | feedparser (parse text we fetched ourselves; don't let it fetch) | BSD-2 |
| Retries | tenacity | Apache-2.0 |
| JS-rendered sites | playwright (**ask me before adding**; only if a site truly needs it) | Apache-2.0 |
| PDF text layer | pypdfium2 | Apache-2.0 / BSD-3 |
| PDF tables and layout checks | pdfplumber | MIT |
| OCR and table fallback | azure-ai-documentintelligence | MIT |
| Blob storage | azure-storage-blob (async `aio` client), azure-identity | MIT |
| ~~Vectors~~ | ~~pgvector~~ **REMOVED (amendment 1)** — retrieval is Azure AI Search via the existing `azure-search-documents` dependency | — |
| Ingestion migrations | Alembic (explicitly requested in the 2026-09-18 revision; add during approved Phase 1 only) | MIT |
| Token counting | tiktoken | MIT |
| Jobs | ARQ, **unless the repo already uses Celery or another queue**, in which case use that | MIT |
| Test HTTP mocking | respx | BSD-3 |
| Test images for scanned-PDF fixtures | Pillow | HPND (permissive) |

Alembic's dependency and isolated environment design are now explicitly requested; this does not authorize installing or implementing them before Phase 1 approval. The explicitly listed PostgreSQL and HPND licences above remain approved exceptions to the general MIT/BSD/Apache-2.0 rule.

Do not add Scrapy, LangChain, LlamaIndex, Unstructured, or paid crawling or scraping APIs.

## 4. Module layout

Use the repository's `backend/` import root. The planned subsystem is `backend/ingestion/`, with `python -m ingestion` run from `backend/`. The following paths are a design for later approved phases; creating them is not authorized by this review:

```
backend/ingestion/
  __init__.py
  __main__.py            # CLI entry point
  config.py              # pydantic settings for this subsystem
  models.py              # ingestion-owned base/MetaData(schema="ingestion") and models
  alembic.ini            # dedicated config; never use the shared placeholder
  migrations/
    env.py               # ingestion-only metadata, filters and version table
    versions/            # revisions own schema ingestion only
  schemas.py             # pydantic DTOs (DocumentListing, Citation, ...)
  enums.py               # Regulator, DocumentStatus, DocType, ExtractionMethod ...
  http.py                # shared polite HTTP client
  urls.py                # URL normalisation, domain allow-lists
  crawlers/
    base.py
    cbn.py
    sec.py
    ndic.py nfiu.py ndpc.py fccpc.py   # later phase
    registry.py          # Regulator -> crawler class
  download.py            # streaming download, validation, hashing
  versioning.py          # dedupe and version-lineage logic
  storage.py             # Azure Blob wrapper
  extraction/
    router.py            # decides text layer vs Document Intelligence per page
    text_layer.py        # pypdfium2 + pdfplumber
    quality.py           # per-page quality heuristics
    doc_intelligence.py  # Azure Document Intelligence fallback
    html.py              # main-content extraction for HTML publications
    normalise.py         # deterministic whitespace normalisation
  chunking.py
  embeddings.py
  search.py              # hybrid retrieval for agents
  audit.py               # thin adapter over the EXISTING audit trail
  notify.py              # tells Watchdog about new documents
  jobs.py                # queue job functions and cron schedule
  api.py                 # admin FastAPI router
backend/tests/ingestion/
  fixtures/cbn/ fixtures/sec/ fixtures/pdfs/ ...
  test_*.py
docs/ingestion/
  BRIEF.md               # this revised full brief
  PLAN.md                # written in Phase 0
  README.md              # written by the end
```

## 5. Configuration

All settings go through the repo's settings mechanism with an `INGESTION_` prefix (or match the repo's convention). Add every variable to `.env.example` with a comment.

- `INGESTION_CONTACT_EMAIL`: `ingest@irokoai.site`, supplied by the user on 2026-09-18.
- `INGESTION_USER_AGENT`: exact configured value `IrokoAI-RegulatoryIngest/1.0 (+mailto:ingest@irokoai.site)`.
- `INGESTION_DATABASE_URL`: optional ingestion-specific database connection. Use it only when nonblank after whitespace checking; otherwise reuse the existing `DATABASE_URL`. Use this same effective database for ingestion runtime sessions, migrations and extension probes. Tests use the same URL-resolution rules with explicitly isolated test targets; never use a configured application/shared database as the default test target. Never replace or mutate the application's existing `DATABASE_URL` to implement this override. Keep credentials in local environment/secrets only. Ingestion requires PostgreSQL: if the effective URL selects SQLite or another unsupported backend, fail clearly and request a PostgreSQL connection; do not silently create a new database or substitute a vector backend. This override does not establish that the database is distinct from, or shared with, another repository.
- `INGESTION_REQUEST_DELAY_SECONDS` (default 2.0), `INGESTION_MAX_CONCURRENCY_PER_HOST` (default 1).
- `INGESTION_CONNECT_TIMEOUT` (10), `INGESTION_READ_TIMEOUT` (60), `INGESTION_MAX_RETRIES` (4).
- `INGESTION_MAX_DOWNLOAD_BYTES` (default 100 MB), `INGESTION_TEMP_DIR`.
- `INGESTION_REVERIFY_AFTER_DAYS` (default 30): how often an already-known URL is re-downloaded to detect silent amendments.
- `AZURE_STORAGE_ACCOUNT_URL` for production (managed identity via `DefaultAzureCredential`).
- `AZURE_STORAGE_CONNECTION_STRING` for local development only (Azurite: `UseDevelopmentStorage=true`).
- `INGESTION_BLOB_CONTAINER` (default `regulatory`).
- `DOCINTEL_ENDPOINT`, `DOCINTEL_KEY` (optional; if unset, flagged pages go to `pending_ocr` and the pipeline continues).
- `DOCINTEL_MAX_PAGES_PER_DOCUMENT` (50), `DOCINTEL_DAILY_PAGE_BUDGET` (500).
- `QUALITY_MIN_CHARS_PER_PAGE` (80), `QUALITY_MAX_BAD_CHAR_RATIO` (0.05), `QUALITY_ROUTE_TABLE_PAGES` (true).
- `CHUNK_TARGET_TOKENS` (600), `CHUNK_MAX_TOKENS` (1000), `CHUNK_OVERLAP_TOKENS` (60).
- `INGESTION_EMBEDDING_DEPLOYMENT`: reuse the existing Azure OpenAI embedding deployment when this optional value is blank/unset; reuse the existing client. Do not create a second deployment/client or change current callers by default.
- `INGESTION_EMBEDDING_DIMENSIONS`: proposed value `1536` for ingestion only, using an explicit dimensions request to the existing deployment. This is the plan presented for user review, not permission to implement it in this turn. Both ingestion chunk and query embeddings must use the same approved dimensions. Verify deployment support before implementation; fail clearly on a dimension mismatch. Existing Azure Search vectors/index definitions remain at **3072** dimensions. Do not change a shared embedding dimension default to implement ingestion. pgvector HNSW indexes on `vector` support at most 2,000 dimensions; a different model/size or use of `halfvec` requires an updated proposal and approval.

## 6. Data model

Create these tables only during approved Phase 1 using the dedicated ingestion Alembic environment below. Timestamps are UTC (`timestamptz`). Use UUID primary keys unless the repo uses something else.

### Schema and metadata ownership

- Every ingestion model belongs to one subsystem-owned declarative base whose metadata is `MetaData(schema="ingestion")`. All ingestion model tables must resolve to schema `ingestion` through that metadata default. Do not set schema separately on each model, and do not modify the existing shared/global metadata or declarative bases.
- Keep the exact table prefixes/names below. The qualified names are `ingestion.ingestion_crawl_runs`, `ingestion.regulatory_documents`, `ingestion.regulatory_document_urls`, `ingestion.regulatory_document_pages`, and `ingestion.regulatory_chunks`. Any later approved ingestion support tables, sequences, enum types and indexes also belong to the owned schema. Foreign keys between ingestion tables must resolve within this metadata/schema.
- Prefer a dedicated database role whose ownership and DDL privileges are limited to `ingestion`; grant only the minimum access needed for existing extension types/operators and explicitly approved service integration. Do not broaden privileges or change roles for other applications as an automatic setup step. A dedicated role/schema must not be represented as a confirmed deployment fact until verified.

### Dedicated Alembic environment and migration safeguards

- Proposed config: `backend/ingestion/alembic.ini`; script location: `backend/ingestion/migrations/`. Reuse the repository's dependency and logging conventions while keeping this environment independent of other migration histories. Do not repurpose `backend/alembic.ini`, stamp an existing application history, or import shared metadata into `target_metadata`.
- Use only the ingestion-owned metadata as `target_metadata`. Set `include_schemas=True`, `version_table="alembic_version_ingestion"`, and `version_table_schema="ingestion"`. Bootstrap schema `ingestion` before Alembic needs to create its version table, during an approved migration/setup step only. Schema bootstrap is never an application import or startup side effect.
- `include_object` must ignore **every** object outside the owned schema, whether reflected or metadata-defined. For tables, resolve their schema directly; for columns, indexes and constraints, resolve the owning parent table's schema. Reject objects whose owning schema cannot be resolved, including unqualified/unknown ownership; never fall back to accepting them. Apply the same ownership rule when examining comparison objects. The metadata default alone is not an ownership filter.
- Add `include_name` as defense in depth: permit reflection of the owned `ingestion` schema only and filter child reflected names by their parent schema. Inspect the connection's actual default schema: it is not necessarily `public`. Resolve reflected schema `None` only against that verified default (or enforce a migration connection where ingestion is not the default); never blindly treat `None` as ingestion. Test ingestion-as-default reflection and exclusion of public/other schemas. Do not rely on `include_name` alone, because it does not cover every metadata-side or explicitly authored operation.
- Review generated and handwritten revisions for explicit schema ownership. Autogeneration filters do not authorize arbitrary DDL: no ingestion migration may create, alter or drop an object outside `ingestion`, and no migration may silently modify existing application tables. Keep the table prefixes even with these filters.
- Never run a downgrade against a shared database without separate explicit approval. No downgrade may drop the `vector` extension, wherever installed, or touch another application's objects. Do not use cascade deletion to evade these boundaries.
- Proposed scoped migration command, run from the repository root **only after Phase 1 approval and configuration of the effective PostgreSQL URL**: `backend/.venv/Scripts/python.exe -m alembic -c backend/ingestion/alembic.ini upgrade head`. The config must make its paths resolve correctly for this exact invocation. Document the corresponding command for other supported operating systems. Neither this command nor any DDL is to be run during the current review.

### pgvector availability and namespace

Inspect installation in the **effective ingestion database** using read-only catalog queries. Server files or a successful probe in a different database do not establish installation here:

```sql
SELECT extname, extnamespace::regnamespace FROM pg_extension WHERE extname = 'vector';

SELECT e.extversion, n.nspname AS extension_schema
FROM pg_catalog.pg_extension AS e
JOIN pg_catalog.pg_namespace AS n ON n.oid = e.extnamespace
WHERE e.extname = 'vector';

SELECT name, default_version, installed_version
FROM pg_catalog.pg_available_extensions
WHERE name = 'vector';
```

- If `vector` is installed, reuse it in the namespace reported by `pg_extension`, even when that namespace is outside `ingestion`. Do not reinstall, relocate, upgrade or drop the existing extension as part of ingestion migrations.
- Ensure ORM types, migration DDL, HNSW operator classes and vector query operators resolve in the discovered namespace. Use safely quoted schema-qualified names, including operators where needed, or an explicitly configured safe session/transaction search path restricted to trusted schemas. Do not alter the database/role-wide search path or rely on an uncontrolled default search path.
- If `vector` is not installed but server availability is confirmed, the later approved setup may execute `CREATE EXTENSION IF NOT EXISTS vector WITH SCHEMA ingestion` only after bootstrapping the owned schema. Reinspect the actual extension namespace afterward, including a concurrent-install case, and reuse that actual namespace. Do not assume `IF NOT EXISTS` moves an existing extension.
- If extension files are unavailable, stop and present Docker-free options. If extension creation fails for insufficient privileges, fail clearly and report it; do not auto-elevate, change other roles, install into another schema, or silently fall back. **No extension/schema creation or other DDL is authorized in this documentation-review turn.**
- Downgrades never drop the extension, including an extension originally created for ingestion, because other database objects may later depend on it.

### Tables

**`ingestion_crawl_runs`**
`id`, `regulator`, `mode` (`incremental` | `backfill`), `status` (`running` | `succeeded` | `failed` | `suspect`), `triggered_by` (`cron` | `cli` | `api:{user_id}`), `started_at`, `finished_at`, `listings_found`, `documents_new`, `versions_new`, `errors_count`, `error_samples` (jsonb, capped at 20 entries).

**`regulatory_documents`**
- `id`, `regulator`, `doc_type` (`circular` | `guideline` | `regulation` | `framework` | `exposure_draft` | `act` | `press_release` | `other`; infer conservatively from the title, default `other`, never block on it), `category` (the regulator's own category label, nullable), `reference_number` (nullable), `title`, `published_date` (nullable date).
- `media_type` (`application/pdf` | `text/html` | `application/vnd.ms-excel` | `application/vnd.openxmlformats-officedocument.spreadsheetml.sheet`) — see amendment 7.
- `raw_sha256`: SHA-256 of the exact downloaded bytes.
- `content_sha256` (**unique**): the identity used for dedupe and versioning. For PDFs it equals `raw_sha256`. For HTML it is the hash of the extracted main-content text (see section 9 for why).
- `blob_path`, `size_bytes`, `page_count`.
- `previous_version_id` (FK to self, nullable), `is_latest` (bool).
- `status` (`stored` | `extracted` | `pending_ocr` | `chunked` | `embedded` | `failed`), `status_detail`, `retry_count`.
- `first_crawl_run_id` (FK), `fetched_at`, `created_at`, `updated_at`.
- Indexes: `(regulator, published_date)`, `reference_number`, `status`.

**`regulatory_document_urls`**
`id`, `document_id` (FK), `url` (normalised), `listing_url`, `first_seen_at`, `last_seen_at`, `last_verified_at`, `etag`, `last_modified`. Unique `(url, document_id)`, index on `url`.

**`regulatory_document_pages`**
`id`, `document_id`, `page_number` (1-based), `extraction_method` (`text_layer` | `document_intelligence` | `html`), `route_reason` (nullable text, e.g. `low_char_count`, `bad_chars`, `table_detected`), `raw_text`, `text` (normalised), `char_count`, `quality` (jsonb with the metrics the router used), `created_at`. Unique `(document_id, page_number)`.

**`regulatory_chunks`**
- `id`, `document_id`, `chunk_index`, `section_heading` (nullable).
- `context_header`: e.g. `CBN | Circular | {reference_number} | {title} | {published_date} | {section_heading}`. Used as embedding input only; never merged into `text`.
- `text`: verbatim.
- `token_count`, `page_start`, `page_end`, `char_start`, `char_end` (offsets into the document's joined normalised text).
- `text_sha256`, `embedding` (proposed `vector(1536)`, nullable until embedded, subject to the embedding plan review in section 5), `embedding_model`. Resolve the vector type from the installed extension namespace described above.
- ~~`search_tsv`~~ **REMOVED (amendment 1)** — full-text search lives in Azure AI Search, not Postgres.
- `created_at`.
- Unique `(document_id, chunk_index)`. HNSW index on `embedding` with `vector_cosine_ops` resolved from the installed extension namespace, GIN index on `search_tsv`, btree on `document_id`. All three indexes belong to their ingestion-owned table/schema.

## 7. Shared HTTP client (`http.py`)

- One `httpx.AsyncClient` per process, with the configured User-Agent, timeouts, HTTP/1.1, and redirects followed up to 5 hops.
- **Per-host throttling** enforced in this layer, not only in the queue: an async lock or semaphore per host plus the configured delay between requests to the same host.
- **Retries with tenacity**: exponential backoff with jitter on connection errors, timeouts, HTTP 429 and 5xx. Honour `Retry-After`. Do not retry other 4xx.
- **robots.txt**: fetch and cache per host (24h) with `urllib.robotparser`. If a URL is disallowed, skip it, log a warning and count it in the run's errors. If robots.txt itself returns 404, treat it as allowed; if it errors, retry later instead of assuming.
- **Domain allow-list** per crawler. After redirects, the final URL's host must still be allowed or the response is rejected.
- **TLS verification stays on.** If a government site has a broken certificate, fail, log it clearly and tell me. Never disable verification globally.
- Support conditional requests (`If-None-Match`, `If-Modified-Since`) using the stored `etag` and `last_modified`.

URL normalisation (`urls.py`): `urljoin` against the page URL, strip fragments, lowercase scheme and host, percent-encode spaces and unsafe characters, and **keep path case unchanged**. Unit-test this with real-looking messy links from the fixtures (relative paths, spaces, mixed-case folders).

## 8. Crawlers

### 8.1 Base interface

Separate I/O from parsing so parsers are pure functions tested against saved fixtures.

```python
@dataclass(frozen=True)
class DocumentListing:
    regulator: Regulator
    title: str
    document_url: str          # PDF link, or the HTML page itself for HTML-only publications
    listing_url: str
    media_type_hint: str | None
    category: str | None = None
    reference_number: str | None = None
    published_date: date | None = None

class BaseCrawler(ABC):
    regulator: ClassVar[Regulator]
    allowed_domains: ClassVar[frozenset[str]]

    @abstractmethod
    async def discover(self, mode: CrawlMode, limit: int | None) -> AsyncIterator[DocumentListing]: ...

    # Pure parsing helpers live in the subclass, e.g.
    # def parse_listing_page(html: str, page_url: str) -> ParsedListingPage
```

Behaviour shared by all crawlers:

- **Incremental mode** walks listing pages newest-first and stops after `N` consecutive already-known URLs (default 15) or when pagination ends.
- **Backfill mode** walks everything, respecting `--limit` and `--since`.
- **Layout-change detection:** if a listing page that yielded items on the previous successful run now yields zero, mark the run `suspect`, log at error level, and do not treat it as "no new documents".
- One bad listing or document never aborts the run. Record the error and continue.

### 8.2 CBN (`cbn.py`)

- Allowed domains: `cbn.gov.ng`, `www.cbn.gov.ng`.
- Start from the documents index at `https://www.cbn.gov.ng/documents/`. It lists circular categories including All CBN Circulars, Other Financial Institution Supervision, Banking Supervision, Compliance, Payments System, Financial Policy and Regulation, CBN Policy, and Trade and Exchange.
- **Phase 0 reconnaissance:** fetch the index and each category page, save them as fixtures, and determine:
  - whether "All CBN Circulars" is a true superset (if so, crawl it for discovery and use category pages only to tag `category`);
  - pagination mechanics;
  - the columns available (reference, title, published date, file size, PDF link);
  - whether older `.asp` listing pages and newer pages coexist, and which ones are live.
- Priority categories for MFB compliance: Other Financial Institution Supervision, then Banking Supervision, Compliance, Payments System, and Financial Policy and Regulation.
- Dates: **`DD/MM/YYYY`, proven from fixtures (amendment 3)** — 1,586 of 2,629 rows have a first component > 12 and none have a second > 12. Parse with an explicit `%d/%m/%Y`; fail loudly if a future capture contains a row that parses only as MM/DD/YYYY.
- Reference numbers look like `FMD/DIR/PUB/CIR/001/009` or `BPS/DIR/GEN/CIR/04/007`. Capture them exactly as printed.
- Link paths use inconsistent case (e.g. `/Out/2021/...`). Normalise per section 7 without lowercasing paths.
- Only ingest from CBN's own domain. Fake CBN circulars circulate on social media.

### 8.3 SEC Nigeria (`sec.py`)

- Allowed domains: `sec.gov.ng`, `home.sec.gov.ng`, `www.sec.gov.ng`.
- **Incremental:** fetch the circulars RSS feed at `https://home.sec.gov.ng/feeds/circulars.rss` with our HTTP client, then parse the text with feedparser. For each item, fetch the linked circular page.
- **Circular pages** (under `/for-investors/keep-track-of-circulars/<slug>/`) are often HTML-only. If a page links a PDF attachment, treat the PDF as the document and keep the page URL as `listing_url`. If it has no PDF, the HTML page itself is the document.
- **Backfill:** crawl `https://sec.gov.ng/our-mandate/regulation/rules-and-regulations`, which lists consolidated rules with "Download Full Document" links, plus the circular archive listing pages found during reconnaissance.
- The same content may appear on both `sec.gov.ng` and `home.sec.gov.ng`. Content hashing handles dedupe; record both URLs in `regulatory_document_urls`.
- Main-content selectors must exclude the site-wide scrolling announcement banner, navigation and footer (see section 9).

### 8.4 NDIC, NFIU, NDPC, FCCPC (later phase)

Do not write these crawlers until reconnaissance is done and I've approved the approach. For each regulator:

1. Find the official domain and the pages that list regulations, guidelines, circulars or notices. Use only links discovered from the official homepage, never guessed paths.
2. Check for, in order of preference: an RSS or Atom feed, a WordPress REST API (`/wp-json/wp/v2/...`), `sitemap.xml`, then server-rendered HTML listings.
3. Check whether listings are present in the raw HTML. If they only appear after JavaScript runs, propose Playwright for that site and wait for approval.
4. Save fixtures and write a short findings section in `docs/ingestion/PLAN.md`.

## 9. Download, dedupe, versioning and storage

### Download (`download.py`)

- Stream to a temp file while computing SHA-256. Enforce `INGESTION_MAX_DOWNLOAD_BYTES`.
- Validate the type by content, not the extension: PDFs must start with `%PDF-`. HTML must be `text/html`. Reject anything else with a recorded error.
- Always delete temp files, including on failure.

### HTML identity problem

Regulator web pages contain changing banners, menus and session junk. Hashing raw HTML would create fake "new versions" constantly. For HTML documents:

- `raw_sha256` is the hash of the raw bytes (used for the blob path).
- Extract the main content using a per-site selector defined in the crawler, normalise it (section 10), and hash that for `content_sha256`.
- Write a test proving that two fixture pages differing only in banner text produce the same `content_sha256`.

### Versioning (`versioning.py`)

Run this in a single transaction. For a downloaded listing with normalised URL `u` and content hash `h`:

1. **A document with `content_sha256 = h` already exists:** upsert the `regulatory_document_urls` row for `(u, document)` and update `last_seen_at` and `last_verified_at`. No new blob, no new document.
2. **Otherwise, if `u` is already linked to a document `d_old` with `is_latest = true`:** create a new document with `previous_version_id = d_old.id`, set `d_old.is_latest = false`, and emit a `document_version_detected` audit event. The old version is kept forever.
3. **Otherwise:** create a new document with `is_latest = true`.

Handle unique-constraint races on `content_sha256` by re-reading and falling into case 1.

Skipping known URLs in incremental mode: if `u` is known and `last_verified_at` is newer than `INGESTION_REVERIFY_AFTER_DAYS`, skip the download. Otherwise use a conditional GET, and if the server reports "not modified", just update `last_verified_at`.

### Storage (`storage.py`)

- Async Azure Blob client. Use `DefaultAzureCredential` when `AZURE_STORAGE_ACCOUNT_URL` is set; otherwise use the connection string (Azurite locally).
- Private container `INGESTION_BLOB_CONTAINER`, created at startup if missing in development only.
- Blob path: `{regulator_lower}/{raw_sha256}.{pdf|html}`.
- Upload with overwrite disabled. "Already exists" counts as success, since content-addressed paths make this idempotent.
- Set content type, and blob metadata for `source_url` and `fetched_at`.
- Provide `get_download_url(blob_path, ttl_minutes=15)` returning a short-lived, read-only SAS URL (user-delegation SAS when using managed identity), and `open_stream(blob_path)`.
- The app must tolerate delete and overwrite being impossible. **Do not write code or scripts that configure or lock immutability policies**, since locked policies are irreversible. Instead, document the manual Azure setup in the README: container versioning, soft delete, and a time-based retention (WORM) policy.

Local development: document installing Azurite with `npm install -g azurite` and running `azurite --silent --location .azurite`. Add `.azurite/` to `.gitignore`.

## 10. Extraction

### Normalisation (`normalise.py`)

Deterministic and minimal: convert line endings to `\n`, strip trailing spaces on each line, collapse runs of 3+ newlines to 2, and replace non-breaking spaces with spaces. **No de-hyphenation, spelling fixes or reflowing.** Store both `raw_text` and normalised `text` for every page.

### Router (`router.py`, `quality.py`)

For each PDF page:

1. Extract the text layer with pypdfium2.
2. Compute quality metrics:
   - non-whitespace character count;
   - bad-character ratio (U+FFFD, `(cid:NNN)` patterns, control characters);
   - whether the page is mostly image (pdfplumber `page.images` area versus page area);
   - whether pdfplumber detects tables (only if `QUALITY_ROUTE_TABLE_PAGES`).
3. Route to Document Intelligence if the character count is below the minimum, the bad-character ratio is above the maximum, the page is image-dominant with low text, or it contains a table and table routing is on. Record `route_reason` and the metrics in `quality`.
4. Otherwise keep the text-layer result (`extraction_method = text_layer`).

Log a per-document summary: pages via text layer, pages via Document Intelligence, pages pending OCR.

### Document Intelligence fallback (`doc_intelligence.py`)

- Use the `prebuilt-layout` model with markdown output. Send **only the flagged pages** using the SDK's pages option. Confirm exact parameter names against the installed SDK version rather than from memory.
- Map results back to page numbers. Tables arrive as markdown tables; keep them intact.
- Enforce `DOCINTEL_MAX_PAGES_PER_DOCUMENT` and `DOCINTEL_DAILY_PAGE_BUDGET` (tracked in Redis or a table). When a budget is exhausted, or Document Intelligence isn't configured, set the document to `pending_ocr`, keep the text-layer output for unflagged pages, and retry on a later run.
- Define a `PageExtractor` protocol so a different fallback (e.g. a vision model) can be added later without touching the router. Implement only Document Intelligence now.

### HTML (`html.py`)

Use the crawler's main-content selector, convert headings, lists and tables to plain text or markdown-like text, and store it as a single page (`page_number = 1`, `extraction_method = html`).

## 11. Chunking (`chunking.py`)

- **Input:** ordered normalised page texts. Join pages with `\n\n`, tracking each page's character offsets so every chunk gets `page_start`, `page_end`, `char_start` and `char_end`.
- **Section detection:** build heading patterns from real fixture documents, not assumptions. Likely candidates: numbered headings (`1.0`, `2.1`, `3.2.4` followed by a title), `PART`, `SECTION`, `CHAPTER`, `SCHEDULE` or `APPENDIX` with a number or roman numeral, and short all-caps title lines. Lettered sub-clauses like `(a)`, `(b)`, `(i)` are **not** split points; keep them with their parent section. In the Phase 5 summary, show me the detected headings for 3 real CBN documents so I can verify them.
- **Sizing:** aim for `CHUNK_TARGET_TOKENS` and never exceed `CHUNK_MAX_TOKENS` (count with tiktoken). Split oversized sections on paragraph boundaries, then sentence boundaries, never mid-sentence. Apply `CHUNK_OVERLAP_TOKENS` only between chunks of the same section. Never chunk across documents.
- **Tables:** never split mid-row. If a table exceeds the maximum, split by rows and repeat the header row in each piece.
- **Invariant test:** every `chunk.text` must be an exact substring of the joined document text at `[char_start:char_end]`. Enforce this in code (raise on violation) and in tests.
- `text_sha256` is the hash of the exact stored `text`.
- Re-chunking a document replaces its chunks inside one transaction.

## 12. Embeddings and search

### Embeddings (`embeddings.py`)

- Reuse the repo's Azure OpenAI client and existing embedding deployment. The input is `context_header + "\n\n" + text`.
- Proposed ingestion-only size is **1536** dimensions for both indexed chunks and search queries, requested explicitly and validated against the stored vector size. Keep existing Azure Search embeddings/indexes at **3072** dimensions. Any shared-client enhancement must preserve current callers' default behavior. This proposal is for review; implementation belongs to approved Phase 5 work after the Phase 1 schema decision.
- Batch requests, retry on 429 and 5xx with backoff, and store `embedding_model`.
- Only embed chunks where `embedding IS NULL` unless forced.

### Search service (`search.py`)

```python
async def search_regulatory_chunks(
    query: str,
    *,
    regulators: list[Regulator] | None = None,
    doc_types: list[DocType] | None = None,
    published_after: date | None = None,
    published_before: date | None = None,
    include_old_versions: bool = False,
    top_k: int = 10,
) -> list[RegulatoryCitation]: ...
```

- **Hybrid retrieval (amendment 1):** vector cosine plus keyword search **in Azure AI Search**, merged with reciprocal rank fusion (k = 60), following `services/azure_search.hybrid_search`. Not Postgres.
- If the query contains something that looks like a reference number, run an exact `reference_number` lookup first and rank those results at the top.
- By default return only chunks from documents where `is_latest = true`.
- `RegulatoryCitation` contains: chunk text (verbatim), section heading, page range, character offsets, document title, regulator, doc type, reference number, published date, source URL (most recently seen), `text_sha256`, the document's `content_sha256`, and the document ID.
- Expose this as a plain Python service first. Then add a thin Semantic Kernel plugin wrapper following the pattern the existing agents use to register tools. Do not change agent prompts or behaviour without asking.

## 13. Audit trail integration (`audit.py`)

Find the existing hash-chained audit trail and write through it. Do not create a second chain. Events and payloads (IDs and hashes only, never full text):

| Event | Payload |
|---|---|
| `crawl_run_started` / `crawl_run_finished` | run ID, regulator, mode, counts, status |
| `document_stored` | document ID, regulator, reference number, title, source URL, `raw_sha256`, `content_sha256`, blob path, size |
| `document_version_detected` | new document ID, previous document ID, URL, both content hashes |
| `document_extracted` | document ID, page count, pages per extraction method, route reasons summary |
| `document_chunked` | document ID, chunk count, SHA-256 over the ordered list of chunk `text_sha256` values |
| `document_embedded` | document ID, embedding model, chunk count |
| `document_failed` | document ID or URL, stage, error class, short message |

If the existing audit API can't express this cleanly, stop and propose a change rather than modifying its core.

## 14. Notifying Watchdog (`notify.py`)

When a document reaches `embedded`, publish an event with document ID, regulator, title, reference number, published date, and whether it's a new document or a new version. First check whether the repo already has an event or messaging pattern and use it. If not, propose a Redis Stream (e.g. `iroko:regulatory:documents`), since streams persist messages unlike pub/sub, and wait for my approval before wiring it into Watchdog.

## 15. Jobs, scheduling, CLI and admin API

### Jobs (`jobs.py`)

Jobs: `crawl_regulator(regulator, mode, limit)`, `download_listing(listing)`, `extract_document(document_id)`, `chunk_document(document_id)`, `embed_document(document_id)`, `retry_pending_ocr()`.

- Each job is idempotent, checks the current status before acting, and enqueues the next stage on success.
- Deduplicate job IDs (e.g. `download:{sha256(url)}`).
- Failures set `status = failed` with `status_detail`, increment `retry_count`, and allow a capped automatic retry.

Schedule, with all times stored and configured in UTC (Nigeria is WAT, UTC+1, no daylight saving):

- CBN and SEC incremental: daily at 05:00 UTC (06:00 WAT).
- Other regulators: weekly on Monday at 05:30 UTC, once implemented.
- `retry_pending_ocr`: daily at 06:00 UTC.

### CLI (`python -m ingestion ...`, from `backend/`)

- `recon <url> --save <fixture_path>`: fetch politely, save the HTML, and print a summary (title, PDF links found, tables found, RSS/Atom links, whether `/wp-json/` and `sitemap.xml` respond).
- `crawl <regulator> --mode incremental|backfill [--limit N] [--since YYYY-MM-DD] [--dry-run]`. Dry-run prints parsed listings without downloading or writing to the database.
- `process <document_id> [--from-stage extract|chunk|embed] [--force]`
- `reprocess --status failed|pending_ocr [--regulator X]`
- `search "<query>" [--regulator CBN] [--top-k 5]`: prints citations with page ranges.
- `stats`: document counts by regulator and status, stuck documents, last run per regulator, Document Intelligence budget used today.

### Admin API (`api.py`)

Protect every route with the repo's existing admin auth. If no admin role exists, ask me.

- `POST /admin/ingestion/crawl` with body `{regulator, mode, limit}`: enqueues a run and returns the run ID.
- `GET /admin/ingestion/runs?regulator=&status=`
- `GET /admin/ingestion/documents?regulator=&status=&doc_type=&q=` (paginated)
- `GET /admin/ingestion/documents/{id}`: metadata, URLs, version lineage, per-page extraction method and route reason, chunk count.
- `GET /admin/ingestion/documents/{id}/original`: returns a short-lived read-only SAS URL.
- `POST /admin/ingestion/documents/{id}/reprocess` with body `{from_stage}`.

## 16. Monitoring

- Mark a crawl run `suspect` when a previously productive listing page yields zero items, or when more than 20% of downloads in a run fail.
- `stats` and the API surface documents stuck in a non-terminal status for over 24 hours.
- Use structured logs through the repo's logger with `regulator`, `crawl_run_id`, `document_id` and `stage` fields.

## 17. Phases

**Phase 0: Reconnaissance and plan (no production code)**
- Explore the repo and document its conventions (section 0).
- Build only the `recon` helper, or use a throwaway script, to fetch and save fixtures for the CBN documents index, each priority CBN category page (including a second pagination page if one exists), 3 real CBN circular PDFs, the SEC RSS feed, 3 SEC circular pages (with and without PDF attachments if possible), and the SEC rules and regulations page.
- Check pgvector availability and installed namespace in the effective ingestion database using read-only queries, the task queue in use, and the audit trail API. Record whether the actual database/role and any relationship to another repository have been verified; do not infer them from a local service or extension file.
- Write `docs/ingestion/PLAN.md`: repo findings, site findings (structure, pagination, date formats, selectors), deviations from this brief and why, and open questions.
- Preserve this revised full brief at `docs/ingestion/BRIEF.md`. The 2026-09-18 documentation/config-template update ends at a review stop and does not itself complete missing reconnaissance or authorize implementation.
- **Stop and wait for approval.**

**Phase 1: Foundations**
Only after explicit Phase 1 approval: config, enums, ingestion-owned `MetaData(schema="ingestion")`/base/models, dedicated Alembic dependency/config/environment and scoped migrations, HTTP client, URL normalisation, storage module (tested against Azurite), audit adapter. Implement effective database-URL selection and per-database vector namespace discovery/reuse under sections 5 and 6. Tests for HTTP retries, robots handling, the domain allow-list, the size cap and URL normalisation; add a test asserting every ingestion model table resolves to schema `ingestion`, and migration ownership/filter/extension-reuse tests described in section 18. Preserve shared application metadata, existing tables and Azure Search's 3072 dimensions. No shared-database downgrade without separate explicit approval. **Stop.**

**Phase 2: CBN end to end to storage**
CBN crawler, download, versioning, CLI `crawl` with `--dry-run`. Parser tests against fixtures. Demonstrate `crawl cbn --mode backfill --limit 10` storing originals in Azurite with correct database rows and audit events, then re-run it to show zero duplicates. **Stop.**

**Phase 3: SEC**
RSS incremental crawling, backfill, HTML documents with content hashing. Include the banner-change test. **Stop.**

**Phase 4: Extraction**
Normalisation, quality router, text layer, Document Intelligence fallback (mocked in tests; one live test skipped unless `DOCINTEL_*` is set), HTML extraction, `pending_ocr` flow, and budgets. Show the routing summary for the 3 CBN fixture PDFs plus a generated scanned PDF. **Stop.**

**Phase 5: Chunking, embeddings and search**
Chunker with the invariant enforced, approved ingestion-only embedding dimensions (currently proposed at 1536), indexes with installed-namespace vector type/operator resolution, hybrid search, CLI `search`, Semantic Kernel wrapper. Preserve existing Azure Search at 3072 dimensions. Show detected headings for 3 CBN documents and 3 example searches with citations. **Stop.**

**Phase 6: Orchestration and operations**
Job chaining, cron schedule, admin API, `stats`, monitoring rules, notification proposal or implementation. **Stop.**

**Phase 7: Remaining regulators**
Reconnaissance for NDIC, NFIU, NDPC and FCCPC, update `PLAN.md`, **stop for approval**, then implement one regulator at a time with fixtures and tests.

## 18. Testing requirements

These are implementation requirements for the appropriate approved phase, not authorization to add test code or run DDL during the current documentation review.

- **Phase 1 ownership:** explicitly import all ingestion models and assert their metadata contains the nonempty expected table set before checking that every ingestion model table resolves to schema `ingestion` and uses the subsystem metadata rather than shared metadata. An empty metadata collection must fail instead of passing the schema assertion vacuously. Test `include_object` with owned and non-owned tables, columns, indexes and constraints; unresolved ownership fails closed. Test `include_name` excludes other/default schemas and that Alembic's version table is `ingestion.alembic_version_ingestion`.
- **Database selection:** test a nonblank `INGESTION_DATABASE_URL` override and blank/unset fallback to existing `DATABASE_URL`; runtime/migrations/probes must agree. Unsupported effective backends fail clearly without creating an alternate database.
- **Migration isolation:** use an authorized disposable PostgreSQL test database with unrelated objects in another schema; prove autogeneration includes no create/alter/drop for those objects and scoped migrations leave them untouched. Test reuse of an existing vector extension in a different namespace without reinstall/relocation, absent-extension creation only in `ingestion`, clear privilege failure, and absence of extension drops in downgrade operations. Never exercise a downgrade on a shared database without explicit approval.
- **Embedding isolation:** verify proposed ingestion vectors and queries have the approved 1536 dimensions while existing Azure Search callers/index expectations remain 3072.

- **Unit:** every parser against saved fixtures, date parsing (including rejection of ambiguous dates), URL normalisation, versioning cases 1–3 and the race condition, HTML content hashing, quality metrics and routing decisions, normalisation, the chunker (heading detection, size limits, table splitting with repeated header, the substring invariant, page and offset mapping), and reciprocal rank fusion.
- **HTTP (respx):** retries and backoff, `Retry-After`, no retry on 404, robots disallow, redirects to a non-allowed domain, oversize downloads, non-PDF bytes served as `.pdf`, conditional GET handling.
- **Integration** (`@pytest.mark.integration`): Azurite round trip, real Postgres with pgvector in a test database, and a full pipeline on fixture PDFs:
  - one real digital CBN circular;
  - one scanned PDF generated at test time by rasterising a fixture page with pypdfium2 and saving the image as a PDF with Pillow;
  - one document with a table.
- **Live** (`@pytest.mark.live`, excluded by default and never in CI): `crawl cbn --dry-run --limit 5` and `crawl sec --dry-run --limit 5`.
- Keep fixtures small, and record in `backend/tests/ingestion/fixtures/SOURCES.md` the URL and fetch date of every fixture.

## 19. Definition of done

1. `crawl cbn --mode backfill --limit 20` followed by `search "minimum capital requirement microfinance bank"` returns verbatim chunks whose page ranges I can verify against the original PDFs.
2. Re-running any crawl creates zero duplicate documents or blobs.
3. A modified file served at a known URL produces a new version linked to the old one, and both remain retrievable.
4. The existing audit-chain verification passes after a full pipeline run.
5. All unit and integration tests pass, and lint and type checks pass.
6. `docs/ingestion/README.md` covers: local setup (Azurite, pgvector, env vars), running the CLI and workers, how to add a new regulator (crawler, fixtures, tests), the manual Azure setup steps for blob versioning, soft delete and WORM retention, and the Document Intelligence budget settings. It also states the effective database selection (`INGESTION_DATABASE_URL` when nonblank, otherwise existing `DATABASE_URL`), the owned `ingestion` schema, dedicated-role preference, vector installation/namespace inspection and reuse, and the exact scoped Alembic command from section 6 with its working directory and prerequisites. Document how to use the override without changing another repository or the main application database, and the prohibition on unapproved shared-database downgrades. Include the ingestion-only 1536-dimensional proposal/approved setting and unchanged Azure Search 3072-dimensional behavior.
7. Every ingestion table resolves through subsystem-owned `MetaData(schema="ingestion")`; migration ownership tests pass; the Alembic version table is `ingestion.alembic_version_ingestion`; no ingestion migration changes objects outside the owned schema or drops the vector extension.

## 20. Review status and unresolved original design questions

This revised brief is a review artifact. The 2026-09-18 additions establish the
required isolation design and crawler identity; they do not authorize Phase 1,
DDL, runtime settings changes, dependency installation or work in another
repository. The 1536-dimensional embedding approach is the proposal for review.

Other conflicts identified in Phase 0 remain recorded in [PLAN.md](PLAN.md),
including table-header repetition versus exact substring offsets, oversized
sentences/rows, publication/version heads and rollback/concurrency, incomplete
OCR and its cap, durable audit/job/notification delivery, and HTML extraction
phase ordering. Their original requirements above are preserved pending explicit
resolution before dependent implementation; this revision does not silently
approve the proposed alternatives. Stop for user review after the authorized
documentation/configuration-template update.
