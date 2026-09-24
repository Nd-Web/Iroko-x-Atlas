# Regulatory document ingestion: Phase 0 plan

Initial reconnaissance: 2026-09-17. Revised for user review: 2026-09-18
(local timezone: Africa/Lagos, UTC+1). The updated specification is [BRIEF.md](BRIEF.md).

**Status: Phase 0 is incomplete; production implementation has not started.**
The contact email is now approved: `ingest@irokoai.site`, with User-Agent
`IrokoAI-RegulatoryIngest/1.0 (+mailto:ingest@irokoai.site)`. The user will set the
real local dotenv value. This turn is limited to database investigation and
documentation/template changes, followed by a stop for review.

Fresh inspection still finds `DATABASE_URL=sqlite:///./atlas.db` in backend/.env
and no ingestion override. PostgreSQL target identity, comparison to the other
project, extension namespace and role privileges remain unverified. The intended
target has not been inferred from the example template or the local server port.
See [the database investigation](DATABASE-REVIEW-2026-09-18.md).

The build brief requires tests, lint, type checks, a change summary, assumptions,
and an approval stop after every phase. Do not begin Phase 1 until the remaining
Phase 0 evidence has been gathered, this plan updated, and the user approves it.

> **Section 0 below supersedes anything later in this document that contradicts
> it.** Sections 3, 5, 6 and 7 were written before CBN reconnaissance completed
> and before the 2026-09-18 decisions; treat them as historical.

## 0. Decisions and evidence, 2026-09-18

### Access constraints (CBN)

Discovery works. Downloading originals does not.

| Path | Result |
|---|---|
| `/robots.txt`, `/documents/`, the 7 category pages | HTTP 200 |
| `/api/GetAllCirculars`, `/api/GetOFISCirculars` | HTTP 200, JSON |
| Circular PDFs under `/Out/`, `/out/circulars/` | **HTTP 403, Cloudflare challenge** |

The 403 body is a Cloudflare `Just a moment...` interstitial with a `cf-ray`
header. `robots.txt` permits these paths, so this is an access control applied
above robots, not a crawl-policy refusal.

**Retested with ordinary HTTP hygiene only (decision 1a).** Six combinations —
HTTP/1.1 and HTTP/2, with and without standard `Accept`/`Accept-Language`, with
and without a `Referer` set to the circular's own listing page — all returned
403. Our real User-Agent was used throughout. No variant changed the outcome, so
the block does not come from missing request headers.

**Egress is already residential Nigerian (decision 1b).** Requests originate
from `AS29465 MTN Nigeria Communication Limited`, Lagos, NG — a consumer ISP,
not a cloud or datacentre host. Retrying from a local Lagos connection will not
help, because that is the connection already in use.

**Bright Data Web Unlocker is not approved for cbn.gov.ng** and must not be
used. No browser-identity spoofing and no challenge solving.

**Consequences.** Phases 4 and 5 must run from local fixture files in
`backend/tests/ingestion/fixtures/pdfs/`, placed there manually, so extraction
and chunking are never blocked on downloads. Phase 2's download path can be
built and tested against fixtures and a local HTTP mock, but cannot be
demonstrated end to end against live CBN PDFs until access is resolved. Brief
definition-of-done item 1 is therefore blocked on either an allowlist or manual
files. A draft allowlist request is in
[cbn-allowlist-request.md](cbn-allowlist-request.md) — **not sent**, pending a
confirmed recipient address.

### robots.txt: `urllib.robotparser` is unsafe here

The brief's section 7 mandates `urllib.robotparser`. Against CBN's actual
`robots.txt` it permits **every** path, including the two CBN explicitly
disallows. Two independent defects, both reproduced:

1. **No wildcard or `$` support.** `Disallow: /*.asp$` is treated as a literal
   prefix and matches nothing, so `/foo.asp` is reported allowed.
2. **First-match, not longest-match.** CBN's file opens with `Allow: /`, which
   short-circuits every later `Disallow`, so even `/museum/` is reported allowed.

Confirmed `/api/` paths are allowed under any reading (decision 1c), so the JSON
endpoints stay. But a correct matcher — longest-match wins, with `*` and `$`
support per the Google robots specification — must replace `urllib.robotparser`
in Phase 1. This is a brief correction, not an optional refinement.

### Retrieval: Azure AI Search, not pgvector (decision 2)

pgvector is dropped. Postgres remains the system of record; Azure AI Search is
the retrieval index, fully rebuildable from Postgres. The `embedding` column,
HNSW index and `search_tsv` generated column leave the schema;
`text_sha256`, character offsets and page ranges stay.

`search_regulatory_chunks` keeps its signature and `RegulatoryCitation` return
type, backed by Azure AI Search. The `ingestion` schema, separate Alembic
version table and `regulatory_*` / `ingestion_*` prefixes all still stand.

**Tier finding.** The service reports `indexesCount.quota = 15`,
`storageSize.quota = 15 GB`, `vectorIndexSize.quota = 5 GB` — that is **Basic
tier, not Free**. Current usage is 71 documents, 3.23 MB storage, 880 KB vector.
Measured per chunk: 12,288 bytes of vector (3072 dims × 4 bytes, exactly) and
~45 KB total storage. At a pessimistic 30 chunks per document, 2,629 CBN
documents give ~79,000 chunks ≈ 969 MB vector and ~3.6 GB storage — inside both
quotas. **No tier upgrade is required**, and the free-tier concern does not
apply.

**Dimensions: use 3072, not 1536.** The 1536 proposal existed only to respect
pgvector's 2,000-dimension HNSW ceiling. With pgvector gone that constraint
disappears, Azure AI Search supports 3072, and the existing `iroko-chunks` index
already uses 3072 with `text-embedding-3-large`. Matching it avoids a second
embedding configuration. `INGESTION_EMBEDDING_DIMENSIONS` should become 3072.

### Data model changes accepted

- **Spreadsheets kept, not parsed (decision 4).** `media_type` extends to
  `application/vnd.ms-excel` and
  `application/vnd.openxmlformats-officedocument.spreadsheetml.sheet`. Download
  and store originals with full metadata so Watchdog sees them, set status
  `stored_unparsed`, skip extraction. Never silently drop a regulatory artifact.
- **Reference numbers (decision 5).** `reference_number` stays verbatim. Add
  indexed `reference_number_normalized` — trimmed, internal whitespace
  collapsed, uppercased — for lookup and the exact-match search boost. The 21
  whitespace-padded values in the capture are the regression corpus.
- **Dates (decision 7).** CBN is **DD/MM/YYYY**; the brief's MM/DD/YYYY
  assumption was wrong. Evidence: 1,586 rows have a first component > 12, zero
  rows have a second > 12, all 2,629 parse under `%d/%m/%Y`. Parse with that
  explicit format and fail loudly if a future capture contains a row that parses
  only as MM/DD/YYYY.

### Discovery strategy (decision 8)

There is no server-side paging: `pageSize` is 10 and paging is client-side over
a complete payload, so one request returns the whole catalogue. Incremental mode
fetches the full JSON each run and diffs against the database by normalised link
and `refNo`. Each run's raw API response is stored in blob storage with its hash,
so the audit trail can prove what CBN advertised on any given day.

Backfill priority: (1) the 78 OFIS records, (2) everything from the last five
years, (3) the remainder. 2,629 documents is a large first bite for storage,
extraction budget and any manual-download workaround.

`/api/GetAllCirculars` is a confirmed superset — all 78 OFIS ids appear among
the 2,629 — so it drives discovery and the category endpoints only tag
`category`.

### Tooling (decision 9)

`pytest`, `pytest-asyncio`, `respx` and `ruff` are approved and installed, with
config in `backend/pytest.ini` and `backend/ruff.toml`, pinned in
`backend/requirements-dev.txt`. `make` is not installed on the development
machine and the repo has no Makefile, so `backend/tasks.py` is the equivalent:
`python tasks.py test | lint | fmt | check`. **mypy is deferred**; the per-phase
checklist covers tests and lint only, and the README says so.

Both are scoped to the ingestion subsystem. The pre-existing `backend/tests/`
suite has failures and the wider backend has roughly 48 lint findings that
predate this work; including them would bury new problems in old noise.

## 1. Work performed and boundaries

- Read the complete supplied build brief and both repository `AGENTS.md` files.
- Inspected tracked backend code, configuration, deployment files, integrations,
  tests, dependency declarations, and installed local tools.
- Checked local database/cache/storage listeners without writing application data.
- Prepared `docs/ingestion/recon.py`, a standalone sequential snapshot helper.
  It imports only the standard library and the already-declared `httpx` dependency.
- Ran the existing safe baseline checks; detailed results are recorded in
  `validation-phase-0.txt` alongside this plan.
- Created the fixture acquisition ledger in
  `backend/tests/ingestion/fixtures/SOURCES.md`. It contains no invented fixtures.

The 2026-09-18 revision adds a repo-local full updated brief, database investigation
and README, revises this plan and the fixture ledger, and adds the approved contact,
optional database/deployment overrides and proposed dimensions to `.env.example`.
No runtime code, local backend/.env, existing tables, agent prompts, audit logic,
dependencies, services, secrets, or Azure resources have been changed. No regulator
request, migration, extension/role creation or Docker command was run in this review.

## 2. Repository conventions and reuse

| Area | Observed implementation | Ingestion approach / decision |
|---|---|---|
| Layout | Backend runs with `backend/` as the import root: `main.py`, `core/`, `models/`, `services/`, `routes/`, `agents/`. There is no implemented `app` package. | Prefer `backend/ingestion/`, tests under `backend/tests/ingestion/`, and CLI `python -m ingestion` from `backend/`. Keep documentation at root `docs/ingestion/`. This is a path adaptation, not a second application. |
| Dependencies | `backend/requirements.txt`; pip/venv instructions and Docker installs. No backend Poetry/uv lockfile or `pyproject.toml`. Frontend uses npm and `package-lock.json`. | Continue requirements.txt/pip. Install no dependencies during Phase 0. A package installed globally is not a declared project dependency. |
| Settings | `core/config.py:Settings` is an import-friendly Pydantic settings singleton. `services/settings.py:AppSettings` performs stricter application startup validation. Both use case-sensitive `.env` settings. `main.py` loads dotenv then Key Vault. | Extend the existing settings mechanism for optional ingestion settings; use a subsystem view rather than a third independently loaded settings hierarchy. Document every new setting in root `.env.example`. CLI imports must not start the app, bootstrap users, seed data, or call Key Vault. |
| SQLAlchemy | Declared and installed version 2.0.35. `models/database.py` provides sync `engine`, `SessionLocal`, `Base`, UUID strings and the active users/audit models. `services/database.py` provides an async factory already bound to the application URL and a different Base. | User's isolation requirement supersedes the earlier shared-metadata proposal: define ingestion-only `MetaData(schema="ingestion")` on its declarative base. Reuse driver/session conventions with a factory bound to the effective ingestion URL; do not mutate or reuse an already-bound application engine when the override differs. Keep existing bases untouched; preserve UUID strings and timezone-aware new timestamps. |
| DB configuration | Actual local backend dotenv uses SQLite. `.env.example` contains an illustrative PostgreSQL URL, which is not an active connection. Sync models read the environment; async services derive a driver from settings. | Nonblank `INGESTION_DATABASE_URL` overrides the existing `DATABASE_URL` for ingestion only. Blank/unset falls back. PostgreSQL is required for ingestion; no SQLite vector substitute. Existing audit/auth connections remain on the application database. |
| Migrations | `backend/alembic.ini` is a comment-only placeholder. No usable migration environment is tracked. Existing startup calls `create_all` and ad hoc `ALTER TABLE`; Alembic is not declared. | User now explicitly requests an independent ingestion Alembic environment/history. Plan `backend/ingestion/alembic.ini`, ingestion-only metadata and scripts. Implement/add the dependency only after Phase 1 approval; never call application `init_db`, reuse another repository's config/history, or stamp its version table. |
| Jobs | `services/connector_sync.py` has an in-memory APScheduler `AsyncIOScheduler`. `main.py` starts connector jobs and regulatory/OMCR polling. Other scheduler modules exist but are not started there. | Reuse the current scheduler where appropriate. APScheduler is not an existing durable task queue. Propose an ARQ worker using the reachable local Redis after deployment/service ownership is confirmed; ARQ itself is preapproved. Preserve existing jobs. |
| Logging | Standard Python logging; `core/logging.py:get_logger` supplies a plain-text formatter. | Use the existing factory and attach regulator/run/document/stage fields. A `LoggerAdapter` can include the fields in message text as well as `extra`, because the current formatter does not render arbitrary extras. Do not introduce a second logging stack. |
| Admin authentication | `services/auth_utils.py:require_admin` accepts `admin` and `superadmin`; `routes/users.py` demonstrates `Depends(require_admin)`. | Reuse that dependency for every ingestion admin route, including the original-download URL. No new admin role is necessary. |
| Agent tools | `agents/kernel.py` registers plugin objects using `kernel.add_plugin`. `agents/researcher.py` uses the compatibility `@kernel_function` decorator and JSON results. | Create a thin ingestion-owned wrapper over the Python search service. Registering it into agents/kernel is a separately gated agent-code change. |
| Agent roster | Registered agents are Researcher, Analyst, Watchdog, **Scribe**, Strategist. No active Sentinel was found. | Follow the actual registration conventions; do not add or rename an agent. |
| Existing regulatory sources | `services/cbn_regulations.py` and `services/regulatory_service.py` contain hand-maintained material. `services/ncc_live_rules.py` uses web intelligence paths. | They are not verified source fixtures or a reusable lawful, verbatim ingestion pipeline. Do not use stored URLs as proof of current page layout or reuse paid crawling/unlocking behavior. Existing agent behavior stays outside this task until approved. |
| Existing document text processing | `services/document_processor.py:clean_text` rewrites currency forms, strips characters and collapses spaces; existing chunking estimates tokens from character count. | These operations cannot implement the brief's verbatim normalization and token/offset invariant unchanged. Add narrowly scoped ingestion normalization/chunking while preserving customer-document behavior. |

Both AGENTS.md files contain Next.js documentation instructions. Phase 0 makes
no frontend implementation changes. The frontend is checked only for baseline
validation.

## 3. Local environment evidence

- OS: Windows 11, build 22621; Python 3.13.7 (system and backend `.venv`).
- PostgreSQL Windows service `postgresql-x64-18` is running; localhost:5432 accepts
  connections. `C:/Program Files/PostgreSQL/18/share/extension/vector.control`
  exists and declares default version **0.8.6**. This proves extension files are
  present, not that this server can load them or that a database enabled them.
- On 2026-09-18, no PostgreSQL DSN was found in the relevant process/backend dotenv
  configuration. The local URL is `sqlite:///./atlas.db`, normally resolving to
  `backend/atlas.db`. Host and port are not applicable. Read-only catalog inspection
  found schema `main`, 21 existing tables and no Alembic version table; the full
  list is in the [database review](DATABASE-REVIEW-2026-09-18.md).
- On 2026-09-17, attempted a read-only connection to local PostgreSQL with the conventional
  administrative database/user and no supplied password. It failed with
  `OperationalError: no password supplied`. No credential guessing followed.
  Consequently this required query **has not executed**:

  ```sql
  SELECT * FROM pg_available_extensions WHERE name = 'vector';
  ```

- Redis on localhost:6379 responded successfully to a read-only `PING`. No Redis
  runtime integration or dependency is declared in the application. A successful
  PING does not establish production Redis deployment, persistence, or ownership.
- Azurite was not found on PATH and localhost:10000 did not accept a connection.
  Phase 1 storage integration testing needs it installed/running; no installation
  was attempted in Phase 0. The brief authorizes a Docker-free local setup.
- The backend virtual environment has SQLAlchemy 2.0.35, httpx 0.27.0,
  APScheduler 3.11.3, and azure-ai-documentintelligence 1.0.0. It lacks several
  ingestion/test tools including pytest, Alembic, pgvector, Redis, and ARQ.
  Some are installed in system Python; that does not make them project dependencies.

The email is resolved. Remaining database evidence needs the intended PostgreSQL
connection and the other project's repo path or non-secret server/database identity.
Case A/B/C cannot be assigned from the current SQLite configuration. Use B for a
shared database, C for the same instance with different databases, and A for a
separate database on a different instance. Do not infer identity from host strings
alone when aliases/proxies are possible. Never print passwords or full URLs.

### Required database isolation contract

These rules apply in all three deployment cases and supersede earlier shared-base
or shared-migration suggestions:

1. All ingestion tables use `MetaData(schema="ingestion")` on an ingestion-only
   declarative base. Keep `regulatory_*` and `ingestion_*` names. Do not set the
   schema separately on every model or change either existing application Base.
   Explicitly keep foreign keys, sequences and any enum types in the owned schema.
2. Use only `backend/ingestion/alembic.ini` and its own script directory/history.
   Set `version_table="alembic_version_ingestion"`,
   `version_table_schema="ingestion"`, `include_schemas=True`, and ingestion-only
   `target_metadata`. Our migration environment must bootstrap its owned schema
   before Alembic creates that schema's version table. An initial revision alone
   may run too late for this prerequisite. No bootstrap/migration is written now.
3. `include_object` excludes every non-ingestion object on both reflected and model
   sides; resolve column/index/constraint ownership via their parent table. Unknown
   ownership fails closed. `include_name` additionally filters schemas before
   reflection and avoids proposing drops for unowned tables. Test the connection's
   default-schema/`None` reflection behavior rather than treating `None` as owned.
   Maintain an explicit ownership boundary even if unrelated tables are found
   within an existing ingestion schema. Autogenerate filters do not constrain
   handwritten SQL; generated/handwritten migrations must also be reviewed.
4. Never issue CREATE, ALTER or DROP against `public` or another unowned schema.
   Never perform a shared-database downgrade without asking the user. Never use
   `DROP SCHEMA ... CASCADE` or drop the vector extension in a downgrade.
5. Resolve a nonblank `INGESTION_DATABASE_URL` first, then existing `DATABASE_URL`.
   Keep app settings/database unchanged. Future CLI/migration setup must load
   configuration before importing global settings; do not import `main`/Key Vault
   to obtain it. The [README](README.md) records the precedence and exact commands.
6. Inspect `pg_extension` for vector and its namespace in the selected database.
   Reuse an existing extension wherever installed; do not reinstall, relocate or
   upgrade it. Resolve the vector type, operator class and driver codec with the
   discovered qualified namespace, or a carefully scoped session search_path.
   Resolving a type in `public` never authorizes DDL there.
7. If vector is absent, after the owned schema bootstrap use
   `CREATE EXTENSION IF NOT EXISTS vector WITH SCHEMA ingestion`. Stop on missing
   server files or insufficient privileges. This is a future migration/bootstrap
   requirement; the current request stops after read-only investigation/docs.
8. Prefer an ingestion-specific role with USAGE and CREATE only on the ingestion
   schema, with ownership of its migration-managed objects. Initial schema/extension
   provisioning may need a privileged operator; do not grant broad permanent rights
   to work around this. Runtime DML rights can be narrower. If roles cannot be
   provisioned, state the actual privilege failure and shared-role risk. Role
   capabilities are currently unknown because no PostgreSQL target is configured.
9. Phase 1 tests must import all ingestion models, assert a nonempty expected table
   set and assert every table resolves to schema `ingestion`. Add ownership/filter,
   version-table, override precedence, extension namespace reuse and foreign-table
   preservation integration checks. No vacuous model test is added before models.

Alembic distinguishes schema-name filtering before reflection from object filtering
on both reflected and model metadata; both are useful here.
([Official autogenerate documentation](https://alembic.sqlalchemy.org/en/latest/autogenerate.html))

## 4. Audit integration and its limitations

The existing chain is `audit_trail`, defined in `models/audit_trail.py`.
`services/audit_service.py:AuditService.log_decision` is an async method accepting
a **synchronous** SQLAlchemy session, `agent_name`, `action_type`,
`decision_summary`, source/reference fields, and optional workspace metadata.
It commits and refreshes the supplied session itself.

Proposed representation: exact event name in `action_type`, an ingestion stage
identifier in `agent_name`, and canonical JSON for the permitted event payload in
the existing unrestricted Text `decision_summary`. This avoids another chain or
table change. Interpret section 13's payload table as authoritative: metadata,
IDs, hashes and counts are permitted; full regulatory text is prohibited.

The existing API does not provide event idempotency or an atomic join to a new
async document transaction. A separate audit session alone cannot guarantee
exactly-once delivery. A persisted outbox/reconciliation proposal is needed before
claiming resumable audit behavior; its schema belongs in the approved design.
Any new outbox table is owned by `ingestion`. Existing audit/admin-auth sessions
remain bound to the application database even if ingestion uses its URL override.
Do not migrate/copy the audit chain, widen ingestion-role rights to application
tables, or claim an atomic transaction across separate databases.

The read-only audit review also found pre-existing correctness issues:

1. Appends select the global latest entry by timestamp with no serialization;
   concurrent writers can use the same predecessor.
2. `verify_chain_integrity` verifies link/hash fields but does **not** recompute
   `entry_hash` from stored event contents. A changed decision summary can escape
   detection. Passing this function alone is limited evidence of integrity.
3. Appending is global but workspace-filtered verification starts its subset at
   genesis, which can reject a valid subset of the global chain.
4. Hash creation uses aware timestamps while persistence uses naive UTC; any
   approved verifier repair must reproduce the historical serialization exactly.

**Approval decision:** canonical-JSON adapter alone with the above acknowledged
limits, or a separately specified repair to the existing audit core (with
concurrency, payload-tamper, historical-hash and workspace tests). The brief
forbids changing that core without asking. No repair or second chain was created.

## 5. Azure services and integration choices

- `services/azure_openai.py` already owns a lazy shared embedding client and public
  single-input `get_embedding`. Extend that service for batch/dimensions support
  rather than create another Azure client. Preserve current callers and add 5xx
  retry handling for ingestion. The alternate `services/embeddings.py` helper
  creates clients, truncates strings and swallows failures; do not reuse those
  behaviors for authoritative chunks.
- Current embedding/search code uses **3,072 dimensions** and the existing Azure
  Search index expects that size. The plan for this review is to request
  **1,536 dimensions** from the reused `text-embedding-3-large` deployment for both
  ingestion chunks and ingestion search queries, then store `vector(1536)` with
  HNSW cosine indexing. Use `INGESTION_EMBEDDING_DIMENSIONS=1536`; a blank
  `INGESTION_EMBEDDING_DEPLOYMENT` reuses the existing configured deployment.
  Preserve the existing Azure Search dimension configuration. Validate returned
  vector lengths; never silently truncate or mix spaces. No live embedding call
  was made, so this deployment's acceptance of reduced dimensions is not yet
  verified. OpenAI documents the dimensions parameter, and pgvector documents a
  2,000-dimension limit for HNSW on vector.
  ([OpenAI embeddings](https://developers.openai.com/api/docs/guides/embeddings),
  [pgvector HNSW](https://github.com/pgvector/pgvector#hnsw))
- `services/blob_storage.py` uses a synchronous client, overwrite-enabled uploads
  and deletion. Extend the shared storage service with an async client factory
  and explicitly immutable operations used by an ingestion wrapper. Do not call
  the current mutable-upload/delete operations for regulatory originals.
- The installed Document Intelligence SDK is **1.0.0**, matching requirements.txt.
  Local signature inspection confirms `begin_analyze_document(model_id, body, *,
  pages=..., output_content_format=..., ...)`. Phase 4 will use prebuilt-layout,
  flagged page selection, markdown, and page-number mapping with fixture tests.
  No live Azure request was made for this inspection.
- Production managed identity, development Azurite, private regulatory container,
  read-only SAS and upload-without-overwrite remain the intended design. No code
  will configure or lock WORM policies. README will describe manual Azure setup.

## 6. Regulator reconnaissance: evidence still required

**No site structure, pagination, date format, main-content selector, feed contents,
category URL, circular URL, or PDF has been verified yet.** The URLs immediately
below come from the user's brief and are seeds, not observed findings.

| Regulator | Brief-provided seed | Planned evidence |
|---|---|---|
| CBN | `https://www.cbn.gov.ng/documents/` | Raw index HTML, robots evidence, discovered category links and labels |
| SEC | `https://home.sec.gov.ng/feeds/circulars.rss` | Raw RSS, robots evidence, actual item URLs and dates |
| SEC | `https://sec.gov.ng/our-mandate/regulation/rules-and-regulations` | Raw rules page, observed attachment/archive links |

The email has been supplied. After the user reviews this documentation update,
remaining Phase 0 source reconnaissance can use that approved identity:

1. Use the sequential Phase 0 helper with the configured User-Agent and verified
   TLS. It checks robots before publication requests, spaces requests per host,
   honors robots delay/rate directives, checks every redirect within the regulator
   domain family, rejects unexpected compressed transfer content, and never
   overwrites a saved fixture. Its explicit errors stop reconnaissance for review;
   it is not the later async/retrying production client.
2. Fetch/save the CBN index and every listed circular category discovered there,
   prioritizing Other Financial Institution Supervision, Banking Supervision,
   Compliance, Payments System, and Financial Policy and Regulation. Include
   All CBN Circulars, CBN Policy, and Trade and Exchange if present. Record the
   printed category names rather than assuming the brief's labels remain current.
3. Save a second pagination page wherever pagination exists. Establish actual
   table columns, date representations, next-page mechanics, and live old/new
   listing paths. Do not infer newest-first ordering or a single date format.
4. Compare category listings against All CBN Circulars. Samples can disprove a
   superset; they cannot establish complete historical coverage. If coverage is
   uncertain, propose crawling category sources with content/URL dedupe instead
   of claiming All Circulars is complete.
5. Download three real CBN circular PDFs via links in saved official listings;
   include a digital circular and one containing a table if available. Check
   `%PDF-`, size, page count and actual text before choosing heading fixtures.
6. Fetch SEC feed and three circular pages discovered from it/the official archive.
   Include HTML-only and PDF-attached publications if available. Save the rules
   page and observed archive pagination. Compare actual page containers to choose
   a main-content selector that excludes navigation, footer and announcements.
7. Inspect feed links and any WordPress/sitemap references. Any authorized discovery
   probes must pass the same robots/domain checks; the helper currently only
   reports observed links and does not probe guessed paths automatically.
8. Add source URLs, UTC fetch timestamps, hashes, purpose, and each saved fixture
   path to SOURCES.md. Keep exact downloaded bytes. Generated banner-only variants
   must be clearly marked as synthetic derivatives of a named saved fixture.

If any required page is inaccessible, robots-disallowed, challenged, or has broken
TLS, record the URL/status and stop to tell the user. Do not bypass it with an
alternate identity, proxy, scraper service, browser, or TLS disabling. Do not add
Playwright merely because it is already declared for unrelated repo features.

## 7. Design conflicts to resolve before dependent implementation

These are open proposals, not silently accepted deviations.

| Issue | Concrete conflict | Proposed decision |
|---|---|---|
| Repeated table headers | Repeating an earlier header before later rows means `chunk.text` is no longer a contiguous source substring. | Keep the exact-substring invariant. Put repeatable header context in separate display/embedding metadata, or approve a richer multiple-span citation model. Do not insert invented characters into stored chunk text. |
| Oversized atomic units | One sentence or table row can exceed CHUNK_MAX_TOKENS while the brief prohibits splitting it. | Raise an explicit chunking error and flag the document until the user permits an oversized atomic chunk or splitting. Never silently violate either rule. |
| Version rollback | URL u serves A, then B, then A again. Literal dedupe case 1 recognizes A but leaves B latest. | Define current publication/URL heads separately from immutable content reuse before finalizing models. |
| Divergent aliases | u1 and u2 share A; u1 changes to B, globally demoting A. Later u2 changes to C and no longer finds a latest predecessor A. | Decide whether aliases must share a lineage or may evolve independently. Independent URL observations/publication lineage may need additional new tables. |
| Cross-regulator identical content | Global unique content hash retains only the first row's regulator/title when another regulator publishes the same bytes. | Decide whether global artifact dedupe and regulator-specific publication metadata need separate records. Do not silently narrow uniqueness. |
| Concurrent versions | Unique content hash handles equal-content races, but different hashes for one URL can create multiple heads. | Serialize URL/lineage resolution, re-read the head, and enforce the approved head invariant; order observations so a slower stale response cannot replace a newer head. |
| Old silent amendments | Incremental discovery stopping after 15 known URLs can leave older URLs forever unchecked. | Add an independent throttled sweep of URLs overdue for re-verification. |
| HTML phase ordering | Phase 3 content hashes need canonical HTML extraction/normalization currently listed under Phase 4. | Introduce the shared HTML-to-text/normalization functions in Phase 3; Phase 4 adds complete page persistence and PDF routing. Use the same canonical HTML text for identity and page text. |
| OCR partial state | A pending page can have provisional text-layer output. Extraction method alone does not say whether that output is accepted. | Persist pending-page state in documented page quality/status metadata; keep good pages, but defer that document's chunk/embed/notify until all pages are resolved. Other documents continue. |
| OCR document limit | A permanent 50-page cap leaves documents with more flagged pages pending forever. | Confirm whether 50 means per attempt or lifetime per document; propose resumable batches with atomic daily budget reservations. |
| Atomicity across systems | Blob, DB, audit, queue and notification do not share one transaction. | Approve an explicit stage/outbox reconciliation design. Permit immutable unreferenced blobs after interrupted uploads; reuse by hash on retry. Do not claim exactly-once audit/notification from status checks alone. |
| Crawl completion | Discovery can finish before downloads, but counts and the 20% failure rule depend on downloads. | Track per-run work outcomes and finalize the run after downloads settle; extraction may continue later. Persist per-listing productivity for layout-change detection. |

For verbatim storage, distinguish exact original bytes from extracted text. PDF
text extraction/OCR and deterministic HTML rendering produce the canonical page
text; only the brief's whitespace normalization may then change that text.
Chunks must be exact contiguous slices of the joined canonical page text, with
document/page/offset provenance. No LLM rewriting, heading rewriting, spelling
correction, de-hyphenation, or sentence reflow is proposed.

## 8. Phased implementation after approval

| Phase | Planned deliverable and gate |
|---|---|
| 0 | Complete required snapshots, source-derived parser/heading findings, authenticated pgvector check and baseline record; update this plan; stop for approval. |
| 1 | Existing-settings integration and optional DB override, ingestion-only metadata and schema tests, independent Alembic environment/history with ownership filters, approved additive migrations, vector namespace reuse, HTTP/URL/storage foundations and the approved audit adapter. Review target database/role and remaining audit/design decisions first. Stop. |
| 2 | CBN pure fixture parsers, discovery, download/versioning/storage and CLI dry-run. Run ten-document backfill twice and show DB/blob/audit evidence for no duplicates. Use callable sequential services before Phase 6 queue wrappers. Stop. |
| 3 | SEC RSS/backfill and PDF-vs-HTML resolution, canonical HTML extraction and hash identity. Test that banner-only changes do not change content identity. Stop. |
| 4 | PDF text layer, deterministic normalization, quality metrics/router, Document Intelligence protocol/adapter, pending OCR and atomic budgets. Show routes for all three CBN PDFs plus a generated scan; mock cloud calls by default. Stop. |
| 5 | Approved chunk boundary/table policy and strict offsets, embedding client extension, vector/full-text indexes and RRF search, CLI and unregistered SK wrapper. Show actual headings for three fixture PDFs and three verifiable searches. Stop. |
| 6 | Approved durable worker/stage chaining, UTC schedules, admin routes/auth, stats/stuck monitoring, run finalization and approved outbox/notification design. Stop before agent activation unless explicitly authorized. |
| 7 | Recon NDIC/NFIU/NDPC/FCCPC from official homepages; stop for approach approval, then implement one regulator at a time with fixtures/tests and its own gate. |

The table intentionally preserves all approval gates. It does not authorize
implementing later phases merely because Phase 0 is accepted.

## 9. Notification and operations proposal

No durable event bus was found. Watchdog currently exposes `run_all_checks` and is
invoked directly by existing code. Propose Redis Stream
`iroko:regulatory:documents` only after the existing Redis/worker deployment is
confirmed. Use persisted publication intent, stable event identity, acknowledgments
and consumer retry/reclaim. Notify only after embedding is complete. Activation
in Watchdog is an explicit future approval because it changes agent code.

All ingestion schedules use explicit UTC: CBN/SEC 05:00 daily; pending OCR 06:00
daily; remaining regulators Monday 05:30 after their implementation. Select the
independent overdue-URL verification schedule as part of Phase 6 review. Do not
start another copy of each cron in every API worker.

## 10. Validation and current limitations

See `validation-phase-0.txt` for the original checks and
`validation-review-2026-09-18.txt` for the unchanged results rerun for this review.
The inspected offline backend subset returned **64 passed, 6 failed, 41
deselected** (111 tests collected). Frontend ESLint returned **48 errors and
22 warnings** across 195 files. Frontend TypeScript checking passed. These are
baseline results; no application fixes were made in Phase 0.

The backend has no configured lint/typecheck command. Frontend provides ESLint
and TypeScript. Several existing backend files named `test_*` perform live Azure,
Key Vault or other external work at import, so unrestricted collection is not an
offline unit suite. The inspected safe subset must be labeled as a subset, and
live/integration checks reported separately rather than claimed as passing.

The new Phase 0 helper passed targeted Ruff/Mypy and eight offline HTTP smoke
checks using the already-installed system tools. These are helper checks, not a
new repo-wide testing standard or dependency installation. Its `--help` is safe
without application secrets; fetch requires the explicit contact email.

Remaining limitations: no source fixtures yet, no target PostgreSQL connection
or other-project identity and therefore no installed-vector/namespace result,
no Azurite round trip, no actual parser evidence, no production migration or
pipeline behavior tested. Phase 0 cannot be called complete while these required
reconnaissance inputs/evidence remain outstanding.

## 11. Review checklist for the next approval boundary

This documentation update stops for user review as requested. The email is
resolved; the PostgreSQL connection/other-project comparison still need evidence.
After those inputs and source reconnaissance, present a completed Phase 0 plan with:

- observed site structures, pagination/date/selectors, fixture ledger and access failures;
- exact baseline check results and any remaining environment blocker;
- confirmed isolated Alembic/schema ownership design and remaining outbox scope;
- acceptance of the proposed 1,536-dimensional ingestion embeddings;
- existing audit adapter limitations versus an explicitly approved core repair;
- table/header and atomic-unit policies, version/publication semantics and OCR limits;
- confirmed local/production Redis worker plan, with agent activation deferred.

Pending decisions do not authorize changes to existing tables, audit core,
infrastructure, or agents. No secrets belong in this document or source control.
