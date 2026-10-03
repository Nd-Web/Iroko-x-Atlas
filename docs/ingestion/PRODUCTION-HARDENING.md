# Document pipeline production hardening

## Implementation plan

1. Explicit, server-managed workspaces; default legacy accounts to isolated personal workspaces. Never infer membership from profile organisation names. Share only explicitly approved public regulatory documents.
2. Enforce the same access policy on listings, analytics, originals, evidence, mutations, search and AI document retrieval; prevent shared answer caches and graph enrichment from bypassing it.
3. Validate file signatures and bounded archive contents before storage; enforce workspace upload and OCR budgets under database locks.
4. Add a bounded automatic queue runner that exits successfully when idle and does not schedule regulator crawls. Keep manual collection separate.
5. Test cross-workspace access, malformed inputs, quotas, retries and upload-to-search with isolated adapters; test PostgreSQL migrations/concurrency in a disposable database.
6. Deploy only after migration/worker/API compatibility checks, then run a synthetic end-to-end production smoke test. Record unfinished rollout prerequisites explicitly.

## Scope

Document boundaries are not a claim that all legacy operational modules have been converted into a multi-tenant product. Unscoped enrichment must not enter customer document answers. Existing customer grouping requires explicit administrator assignment; no guessed grouping or deletion of originals.

## What changed

Documents now belong to an explicit workspace. Migration defaults each existing user to an isolated workspace, assigns owned documents there and quarantines records without a known owner. Profile organisation names never grant access. Team membership is assigned explicitly by a platform administrator; users with existing workspace documents cannot be moved without a separate reviewed migration.

The same policy protects lists, document analytics, originals, extraction evidence, mutations and AI search. Postgres supplies an access filter before Azure retrieval, then canonical indexed chunks are verified again before entering model context. The previous global answer cache, legacy graph enrichment and hard-coded organisation memory are excluded from document answers. Empty search reports a knowledge gap.

Document-derived alerts, tasks, queries, traces, audit entries and organisation memory have separate workspace ownership in `ingestion.record_access`. ORM queries, counts and bulk mutations enforce that ownership for authenticated requests. New records are assigned transactionally; unattributable older records remain quarantined. Worker-created regulator alerts and document audit entries inherit the document workspace. The graph only includes accessible documents and scoped alert/task data; legacy vendor enrichment is excluded in pipeline mode.

Public regulator documents require an explicit platform-admin sharing action, a current indexed revision and official-source provenance. Previously imported documents are not silently shared. Their private alerts and audit notes are not made public by sharing the document. Revised files require another review and sharing decision.

Uploads retain private immutable originals, checksums, exact page text, canonical chunks, version lineage, review decisions and durable jobs. Transactions and blocking database locks run off the async API event loop, allowing overlapping uploads to finish. Failed indexing reuses extraction checkpoints.

Input checks reject renamed HTML/binary files, malformed PDFs, unsafe Office archives, macros, embedded binaries and oversized expansion. Native extraction runs in a subprocess with a wall-clock timeout; Linux additionally applies CPU, address-space and output-file limits. This does not replace malware scanning. Both HTTP layers cap multipart bodies, and the client gives useful retry guidance for outages and quota errors. Session changes clear cached document data.

## Default controls

| Setting | Default |
| --- | --- |
| Document size / multipart body | 50 MiB / 51 MiB including overhead |
| Native PDF pages | 250 (`DOCUMENT_MAX_PAGES`) |
| Parser timeout / Linux address space | 150 seconds / 768 MiB (`EXTRACTION_TIMEOUT_SECONDS`, `EXTRACTION_MEMORY_MB`) |
| Workspace uploads per UTC day | 50 (`WORKSPACE_DAILY_UPLOAD_LIMIT`) |
| Workspace bytes per UTC day | 250 MiB (`WORKSPACE_DAILY_UPLOAD_BYTES`) |
| Workspace queued/retry/running documents | 25 (`WORKSPACE_PENDING_DOCUMENT_LIMIT`) |
| Workspace OCR pages per UTC day | 200 (`WORKSPACE_DAILY_OCR_PAGES`) |
| Global OCR pages per UTC day / per document | 500 / 50 (existing `DOCINTEL_*` controls) |

Exact duplicate acceptance does not spend another upload allowance. OCR reservations include failed calls. PostgreSQL locks serialize concurrent reservations. Set overrides consistently on API and worker; the HTTP size caps must stay aligned with `DOCUMENT_MAX_BYTES`.

## Deployment order

This release has not yet been deployed. Follow this order:

1. Review and commit the intended code. Existing staged PDFs and `.dist` artifacts require their own inspection before a push; do not include populated environment files or deployment parameters. Take and verify a production Postgres backup.
2. Pause document writes and allow current executions to finish. Build a new versioned worker image from the repository root:

   ```powershell
   az acr build --registry IrokoAI --image iroko-ingestion:<release-tag> --file backend/Dockerfile.ingestion-job backend
   ```

3. From the new release's `backend/`, with the intended Postgres URL injected securely, run:

   ```powershell
   python -m alembic -c ingestion/alembic.ini upgrade head
   python -m ingestion check
   ```

   Expected version: `20261003_retire_demo`. Workspace tables are created/backfilled, and the eight legacy demo document identities without a real extraction revision, original Blob, or source connector are recoverably archived. Their original rows are retained, their status becomes archived, and demo access is revoked; real uploaded/extracted content is untouched. Destructive downgrade is refused. Azure requires Render's external URL with TLS; Render's API may use its internal URL. `init-local` is SQLite-only.
4. Deploy matching API and frontend code; update the manual job to the new image. Schema preflight must pass before workers or the enabled API start. Production should use `SEED_DEMO_DATA=false` and a configured signing secret.
5. Assign team workspaces and review which of the existing 20 regulatory documents should be shared. Platform-admin APIs are `POST /api/ingestion/workspaces`, `POST /api/ingestion/workspaces/{id}/members`, and `PUT /api/ingestion/documents/{id}/sharing`. The bodies respectively contain `name`, `user_id`, and `shared_regulatory` plus a review `note`. Existing invitations do not automatically grant membership.
6. Deploy the separate scheduled worker from `backend/deploy/ingestion-worker.bicep`, using the existing East US 2 environment, ACR pull identity and the new image. Supply `databaseUrl`, `storageConnectionString`, `searchKey`, `embeddingKey` and `documentIntelligenceKey` securely at deployment time; never check actual credentials into a parameter file. The identity needs registry pull permission. This retains the manual job.
7. Run the live acceptance checks below, then re-enable customer uploads.

The scheduled worker uses a five-minute cadence and `python -m ingestion scheduled-drain --max-seconds 240`. Azure supports scheduled container jobs; see [Microsoft's job documentation](https://learn.microsoft.com/en-us/azure/container-apps/jobs). Idle executions succeed. Delayed retries remain queued for the next run. The runner stops claiming work at its time budget; the current document may finish beyond it, bounded by the container timeout. Database leases fence concurrent workers. Overlapping scheduled executions still need cost/capacity monitoring.

No new regulator crawl is scheduled by this command. Collection remains explicit, with regulator sources at `interval_hours=0`. The five-minute cadence adds queue/startup delay; processing is not instant. Compute, registry, logging, traffic, OCR, embeddings, database and search have separate costs.

## Verification and operations

Local commands use fake cloud adapters and a disposable Postgres cluster, never the configured production database:

```powershell
# backend/
.\.venv\Scripts\python.exe -m pytest tests/ingestion -q -o addopts='' --disable-warnings
.\.venv\Scripts\python.exe -m ruff check ingestion tests/ingestion
# frontend/
node --test tests/document-upload-proxy.test.cjs
node_modules\.bin\tsc.cmd --noEmit
```

Live acceptance: upload a harmless unique test file in workspace A; verify preserved bytes, automatic processing and searchable exact text. In workspace B, verify list/search/graph exclusion and 404 for A's original, evidence, alert/task mutations. Test sharing and revocation separately. Verify malformed-file/quota responses and duplicate idempotency. Archive synthetic evidence through the API after inspection while retaining audit history.

Local verification on 2026-10-03: 65 backend ingestion tests passed, including disposable-Postgres migration and concurrency tests; all 7 frontend upload-proxy tests passed. TypeScript, focused frontend ESLint, backend ingestion Ruff and Azure worker Bicep compilation passed. These checks do not substitute for the live acceptance test or certify the production deployment.

Monitor failed executions, oldest pending/retry age, exhausted attempts, review backlog, OCR budget and storage growth. Alert when a document remains queued beyond two schedule intervals plus observed processing time. An idle successful execution is not proof that old failed jobs have been resolved.

If rollout fails, stop the new worker and disable document ingress while investigating. Retain originals, extraction checkpoints, ownership and audits. Do not revert to an API with unscoped retrieval or drop access tables as an emergency fix.

Outstanding production gates: backup, migration, image build, API/frontend deployment, explicit membership/public-document assignments, scheduler activation and live smoke test. Full application-wide tenancy, malware scanning, load testing and Linux resource-limit validation remain separate requirements. Windows tests do not certify Linux kernel enforcement.
