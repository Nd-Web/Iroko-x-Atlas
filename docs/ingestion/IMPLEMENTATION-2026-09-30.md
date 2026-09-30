# Iroko document pipeline implementation

The September 30 request authorizes implementation of the MineScreen-inspired
improvements. The September 18 brief remains historical reconnaissance; its
phase approval stops do not describe this new implementation request.

## Plan

1. Preserve originals before accepting uploads; persist processing jobs in the
   existing application database. Use an isolated `ingestion` schema on Postgres.
2. Extract pages locally first, use Azure Document Intelligence for scans and
   tables, retain raw/normalized text, and chunk with real source offsets.
3. Persist hashes, versions, extraction issues and regulatory evidence. Hold
   incomplete or suspect extraction for human review before indexing.
4. Run resumable workers with leases, retries and bounded OCR spending. Keep
   Azure AI Search, with Postgres as the source for rebuilding its chunks.
5. Add a conservative official-source collector: CBN JSON discovery and
   configurable official HTML listing pages. Preserve access failures and
   require source configuration rather than inventing regulator endpoints.
6. Connect upload, connector import, review and retrieval to the pipeline;
   expose progress and review actions in the document library.
7. Test failures, duplicate uploads, leases, review, provenance, crawling and
   indexing. Document deployment separately from local verification.

## Decisions

- Adapt patterns; no MineScreen code, data, credentials or database is copied.
- No second vector database. Existing Azure embeddings remain 3072 dimensions.
- Postgres queue avoids another paid Redis service. A separate worker polls it.
- New tables have their own metadata/migration ownership. The application
  Document remains the library record, referenced by ID without cross-schema DDL.
- SQLite schema translation is only a local development/test convenience.
  Production uses the application's Postgres connection: atomic acceptance of
  Document + revision + job requires the same database. A separate ingestion
  database override is therefore intentionally unsupported in this implementation.
- Version changes mean changed source bytes, not a legal conclusion that one
  regulation supersedes another. A new version requires review before replacing
  the current searchable version.
- Regulatory extraction records candidate obligations as exact quotations.
  It does not manufacture dates, penalties or legal interpretations.
- Crawling is opt-in. No live downloads, cloud migrations, paid OCR or production
  deployment are run as part of local implementation/testing.

See README.md for operation and verification results.

## Completion and verification

Implemented the seven steps above as a locally tested, opt-in pipeline. See
[OPERATIONS.md](OPERATIONS.md) for exact feature boundaries and rollout.

- 32 tests passed together, including real isolated Postgres migration and worker
  concurrency checks. A further source-run persistence/deduplication test passed
  with the four recovery tests: 33 distinct passing tests in total.
- Ingestion Ruff checks, Python compilation, TypeScript checking and targeted
  frontend ESLint checks passed. The full Next.js production build passed.
- No production migrations, deployment, live regulatory collection or paid Azure
  processing were run. Cloud adapters are mocked in the local pipeline tests.
- Existing `.dist/` output was left untouched. MineScreen files were read only.
