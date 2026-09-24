# Regulatory ingestion: database and configuration review

Updated 2026-09-18. **Phase 1 has not started.** This is the reviewed design and
operating contract, not a claim that the subsystem or migration files exist.
See [BRIEF.md](BRIEF.md), [PLAN.md](PLAN.md), and the
[database investigation](DATABASE-REVIEW-2026-09-18.md).

## Which database and schema

The actual backend/.env currently resolves to `sqlite:///./atlas.db`, normally
`backend/atlas.db` when launched from `backend/`. SQLite has no host/port. It is
the current application database and is **not a supported ingestion target**.
The intended PostgreSQL host/port/database and its relationship to the other
repository are not yet identified. Do not take the PostgreSQL example in
`.env.example` as an active connection, or assume the local PostgreSQL listener
belongs to ingestion.

All ingestion-owned tables will reside in PostgreSQL schema **`ingestion`**,
including its independent version table **`ingestion.alembic_version_ingestion`**.
Keep the existing `regulatory_*` and `ingestion_*` table prefixes. Models inherit
an ingestion-only `MetaData(schema="ingestion")`; the application metadata is
not changed. New schema objects, indexes, constraints and types must also stay
within the ownership boundary. Existing application and other-project objects
are never included in ingestion migration metadata.

## Configuration and precedence

Set these in backend/.env or the deployment's environment. The template contains
the approved non-secret contact value and blank optional overrides:

```dotenv
INGESTION_CONTACT_EMAIL=ingest@irokoai.site
INGESTION_USER_AGENT=IrokoAI-RegulatoryIngest/1.0 (+mailto:ingest@irokoai.site)
INGESTION_DATABASE_URL=
INGESTION_EMBEDDING_DEPLOYMENT=
INGESTION_EMBEDDING_DIMENSIONS=1536
```

These new settings are documented now; runtime support belongs to Phase 1.
The user will populate backend/.env. This review did not edit it.

Database selection is deterministic:

1. Use a **nonblank `INGESTION_DATABASE_URL`** if configured.
2. Otherwise use the backend's existing **`DATABASE_URL`**.
3. Require PostgreSQL. Missing/invalid/non-PostgreSQL targets fail clearly; do not
   silently create a SQLite database, pick another database or switch services.

The selection happens after loading settings through the existing backend
mechanism. Current application startup loads dotenv with `override=True` and then
fills missing secrets from Key Vault; direct Pydantic settings imports can behave
differently. Phase 1 entry points must explicitly initialize local configuration
consistently before importing global settings, without importing `main` or
triggering cloud/bootstrap jobs. In deployment without a local dotenv file,
the supplied process environment is authoritative.

The ingestion engine/session factory must be bound to the selected URL, using the
repo's existing sync-to-async driver conventions. The application's already-bound
engine is not reused when it points elsewhere. Do not mutate global DATABASE_URL:
auth and the existing audit chain continue using the application connection.

To move ingestion to a separate database later, provision/identify a PostgreSQL
database and suitable role, then set only **`INGESTION_DATABASE_URL`** to that
connection in backend/.env or deployment secrets. Inspect its catalogs and vector
namespace before running the scoped migration command. Changing this setting
selects a target; it does not copy existing ingestion data or audit history.
Never place a credential-bearing URL in a committed ini file or CLI argument.

## Independent migration environment

Planned config: **`backend/ingestion/alembic.ini`**.
Planned script directory: **`backend/ingestion/migrations/`**.
Both are new ingestion-owned resources to implement after approval; do not reuse
the comment-only backend/alembic.ini or the other repository's config/revisions.

The exact future upgrade command, run from the repository root, is:

```powershell
.\backend\.venv\Scripts\python.exe -m alembic -c backend/ingestion/alembic.ini upgrade head
```

The equivalent command from `backend/` is:

```powershell
.\.venv\Scripts\python.exe -m alembic -c ingestion/alembic.ini upgrade head
```

**Do not run these yet:** the config/revisions are not implemented and Phase 1
approval has not been given. Their env.py must resolve paths relative to the
config, load the intended backend settings, and use only ingestion metadata.

Required Alembic configuration:

```text
version_table="alembic_version_ingestion"
version_table_schema="ingestion"
include_schemas=True
target_metadata=<ingestion-only metadata with schema="ingestion">
include_object=<exclude every object outside the owned ingestion schema>
include_name=<exclude other schemas before reflection>
```

The ownership filter applies to both model and reflected objects, resolving
columns/indexes/constraints through their parent table. Unknown schemas fail
closed; `None` is never blindly treated as ingestion. Explicitly test reflection
with the configured default schema/search_path. Omit unrelated tables even if
someone has placed them in ingestion. These hooks limit autogeneration, not
arbitrary SQL in a revision. Review every migration and enforce narrow database
privileges. [Alembic documents both filtering hooks](https://alembic.sqlalchemy.org/en/latest/autogenerate.html).

Our own migration environment must create the owned ingestion schema **before**
Alembic tries to create its version table there. A first revision that runs after
version-table setup is insufficient. Use an explicit, narrowly scoped initial
bootstrap in that environment, with ownership checks if the schema already exists.
No external migration history is stamped, merged, renamed, updated or dropped.

Never issue CREATE, ALTER or DROP against `public` or another schema we do not own.
Never run a downgrade on a shared database without asking the user. Do not use
`DROP SCHEMA ... CASCADE`; vector is never dropped by downgrade. Do not call the
application's `init_db`/global `create_all` from ingestion entry points.

## Existing vector extension and namespace resolution

The extension is installed per database. First run the read-only query in the
selected PostgreSQL database:

```sql
SELECT extname, extnamespace::regnamespace
FROM pg_extension
WHERE extname = 'vector';
```

If present, reuse its discovered namespace; never reinstall, relocate or upgrade
it. Resolve vector types, cosine operators/operator classes and driver codec
registration using qualified names where supported, or a session search_path
that exposes the existing extension. All ingestion object names remain explicitly
schema-qualified. Resolving an extension in `public` permits no DDL there, and
the runtime/migration role must have no CREATE privilege there.

If absent, after the owned-schema bootstrap, the scoped migration/bootstrap uses:

```sql
CREATE EXTENSION IF NOT EXISTS vector WITH SCHEMA ingestion;
```

This is the requested conditional creation with an explicit target namespace to
avoid accidental public objects. Stop if vector server files are unavailable or
the role lacks installation privileges; tell the user instead of changing roles
or installing elsewhere. The extension is retained on every downgrade. PostgreSQL
requires the target schema to exist before installation and keeps extension names
unique database-wide. [PostgreSQL CREATE EXTENSION](https://www.postgresql.org/docs/current/sql-createextension.html)

Current evidence is limited to local extension files declaring version 0.8.6.
**Installed vector availability/namespace in the intended database is unverified**;
the configured SQLite connection cannot execute the query above.

## Role boundaries

Prefer a dedicated migration role with USAGE and CREATE on ingestion only and
ownership of its managed objects. A runtime role can have only the needed DML
and sequence permissions within ingestion. Reading a vector type in an existing
extension namespace may need USAGE on that namespace, without CREATE or object
ownership there. That is the minimum type-resolution exception, not permission
to migrate the other project's objects.

Initial schema creation or extension installation may require a privileged
operator because a schema-limited role cannot bootstrap a nonexistent schema.
Do not grant broad permanent database privileges or revoke another project's
grants. No role was created during this review; PostgreSQL role privileges cannot
be determined until its target is configured. If a dedicated role cannot be
created, report the actual restriction and that a broad shared role can execute
handwritten SQL beyond the autogenerate filters.

## Embedding dimensions planned for review

Use **1,536 dimensions** for ingestion documents and search queries, requested
through the existing Azure OpenAI embedding client/deployment, then validate the
returned length and store `vector(1536)` with HNSW cosine indexing. A blank
INGESTION_EMBEDDING_DEPLOYMENT falls back to AZURE_OPENAI_EMBEDDING_DEPLOYMENT;
the repository's current model default is text-embedding-3-large.

The model supports reduced dimensions via the API; 1,536 fits below pgvector's
2,000-dimension HNSW limit for vector. The configured Azure deployment still
requires later live validation. Do not truncate returned vectors or mix dimensions.
Existing Azure AI Search embeddings remain at their existing 3,072 dimensions.
([OpenAI embeddings](https://developers.openai.com/api/docs/guides/embeddings),
[pgvector HNSW](https://github.com/pgvector/pgvector#hnsw))

## Verification required in Phase 1

- Import every ingestion model and assert the complete, nonempty expected table
  set has `table.schema == "ingestion"` and the required prefixes. Metadata itself
  must have schema ingestion; the assertion must not pass with no models imported.
- Verify the version table name/schema and override/fallback behavior.
- Exercise autogenerate against unrelated public/other-schema tables and version
  history; assert it emits no operations for them. Include default-schema `None`
  and table-child filter cases, and compare catalogs before/after migration.
- Test reuse of vector installed in another schema, no duplicate installation,
  absent-extension installation limited to ingestion and privilege failure behavior.
- Test that audit/auth remain on their original database when the ingestion
  override points elsewhere, without creating another audit chain.

No model/schema test is implemented now because there are no ingestion models
and the user explicitly prohibited starting Phase 1. A test over an empty metadata
collection would provide no evidence. The existing baseline results are in
[the dated validation report](validation-review-2026-09-18.txt).

This README will grow into the operational guide during later approved phases:
Azurite, workers, crawler/processing/search commands, per-regulator fixtures,
manual Azure retention setup and OCR budgets remain future implementation work.
