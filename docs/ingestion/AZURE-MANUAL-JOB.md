# Azure on-demand worker for the first manual pull

Use an Azure Container Apps **manual Job**, not an always-on Container App, for
the initial 20-document regulator batch. The API's **Collect now** action queues
a source job in the shared Render Postgres database. A manually started Azure
execution then runs `python -m ingestion drain --max-seconds 5400`, processing
that source and the document jobs it creates. The command never schedules
recurring sources. It exits nonzero on a timed-out queue, newly failed document
job, or a source run with a failed/suspect result or attachment errors.

## Before creating Azure resources

1. Deploy the ingestion-enabled backend and frontend code. The Render web API
   and Azure job must use the same version of the pipeline and the same Postgres
   database. Confirm `ingestion.alembic_version_ingestion` is at
   `20260930_pipeline` (already applied to this project's Render database).
2. Rotate the Render Postgres password shared during setup. The Azure job runs
   **outside Render** and therefore needs the Render **external** Postgres URL
   with `?sslmode=require`, not the internal URL used by the Render web service.
   Restrict Render external database access to known Azure egress addresses if
   static egress is configured; do not put a database URL in the image or Git.
3. Create a private Azure Container Registry and a Container Apps environment
   on the Consumption plan. Prefer Central US for proximity to Iroko's Azure
   Blob and Search services, subject to regional availability and pricing.
4. Build from `backend/` using `Dockerfile.ingestion-job` and push a versioned
   image to the private registry. The separate worker requirements avoid the
   API, browser-download, and frontend runtimes.

## Manual Job settings

| Setting | Value |
| --- | --- |
| Trigger | Manual |
| Image | Versioned `iroko-ingestion` image from the private registry |
| Command | Image default: `python -m ingestion drain --max-seconds 5400` |
| Parallelism | 1 |
| Replica completion count | 1 |
| Replica retry limit | 0; the Postgres queue has its own bounded retries |
| Replica timeout | 7200 seconds (the process has a shorter 5400-second limit) |
| Initial size | 0.5 vCPU / 1 GiB; increase if large PDFs require more memory |
| Ingress | None |

Use Container Apps **secrets** referenced by environment variables for
`DATABASE_URL`, `AZURE_STORAGE_CONNECTION_STRING`, `AZURE_SEARCH_API_KEY`,
`AZURE_OPENAI_EMBEDDING_API_KEY`, and `AZURE_DOCUMENT_INTELLIGENCE_KEY`.
The job also needs:

```dotenv
DOCUMENT_PIPELINE_ENABLED=true
AZURE_STORAGE_CONTAINER=iroko-documents
AZURE_SEARCH_ENDPOINT=https://irokoai.search.windows.net
AZURE_SEARCH_INDEX_NAME=iroko-chunks
AZURE_SEARCH_SEMANTIC_CONFIG=iroko-semantic
AZURE_OPENAI_EMBEDDING_ENDPOINT=https://favourpeters6rt-4278-resource.services.ai.azure.com
AZURE_OPENAI_EMBEDDING_API_VERSION=2025-01-01-preview
AZURE_OPENAI_EMBEDDING_DEPLOYMENT=text-embedding-3-large
AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT=https://irokoai.cognitiveservices.azure.com/
DOCINTEL_MAX_PAGES_PER_DOCUMENT=50
DOCINTEL_DAILY_PAGE_BUDGET=500
```

The Render web service uses its **internal** `DATABASE_URL` and needs
`DOCUMENT_PIPELINE_ENABLED=true` when the job is ready. Keep each source's
`interval_hours=0` for manual-only collection. Do not start more than one
manual execution at a time for the first batch.

## First run

1. In the document library, create and enable the approved CBN OFIS source with
   `max_documents=20`, `interval_hours=0`. Verify the URL and source owner.
2. Click **Collect now**. Confirm the API returns `queued` before starting the
   Azure Job from the portal (or `az containerapp job start`).
3. Watch the execution logs and Iroko's ingestion **Runs**, **Reviews**, and
   **Stats**. A successful execution means queue work completed without an
   attachment error; it does **not** mean every document was indexed. Review
   extracted text, source dates, original downloads, and citations before
   approving any item requiring review.
4. If the Azure execution fails or times out, inspect job errors and source
   results in Postgres/UI before starting a second execution. Jobs and leases
   are durable; a later run can resume eligible work after its lease expires.

Jobs consume compute only while executing, but the registry, logging, cross-
cloud traffic, OCR, embeddings, and Azure Search can have separate charges.
This job is manually triggered; new uploads after it exits will remain queued
until another execution is started. An event trigger or always-on worker is a
separate future deployment decision.
