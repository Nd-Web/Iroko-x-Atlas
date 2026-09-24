# Database isolation investigation — 2026-09-18

Scope: read-only configuration and catalog inspection. No migration, role,
schema, table or extension was created, altered or dropped. No password, full
credential-bearing URL or application row data was printed.

## Actual configured target

| Item | Observed result |
|---|---|
| Configuration source | `backend/.env` |
| Existing `DATABASE_URL` | `sqlite:///./atlas.db` (contains no credentials) |
| `INGESTION_DATABASE_URL` | Not set |
| Process overrides for these two variables | Neither set |
| Database engine | SQLite |
| Host / port | Not applicable: a local SQLite file |
| Database name/path | `./atlas.db`, relative to the backend process working directory |
| Normal launcher resolution | `backend/atlas.db`; `run.bat` starts the backend from `backend/` |
| Other project's location/connection | Not supplied; comparison cannot be verified |
| PostgreSQL relationship A/B/C | **Unclassified**: no intended PostgreSQL target or comparison endpoint is identified |

For a backend started from another working directory, the relative SQLite path
can resolve to a different file. The inspection used the documented `backend/`
working directory, opened the existing file with SQLite URI `mode=ro`, and enabled
`PRAGMA query_only`. No application module or startup hook was imported.

The approved contact email is `ingest@irokoai.site`; its absence from local dotenv
is expected because the user will set it. It is no longer an unanswered input.

## Schemas, tables and migration history actually observed

`PRAGMA database_list` returned SQLite schema `main`. The catalog query was:

```sql
SELECT name FROM sqlite_schema WHERE type = 'table' ORDER BY name;
```

All 21 observed tables are in `main`:

```text
agent_runs
alerts
audit_logs
audit_trail
complaint_tickets
connectors
conversations
documents
knowledge_gaps
messages
network_incidents
network_kpis
network_sites
org_memory
password_reset_tokens
regulatory_memory
signal_nodes
user_invitations
users
vendor_contracts
workflow_tasks
```

There is no table named `alembic_version` or beginning with `alembic_version` in
that inspected SQLite database. This does not establish what exists in the other
project's PostgreSQL database.

## pgvector and role findings

The local PostgreSQL 18 installation has a `vector.control` file declaring
version `0.8.6` at `C:/Program Files/PostgreSQL/18/share/extension/vector.control`.
`C:/Program Files/PostgreSQL/18/lib/vector.dll` also exists.
Extension files alone do not prove that the intended database has an installed
or usable vector extension.

The requested query has **not executed**, because the configured target is SQLite:

```sql
SELECT extname, extnamespace::regnamespace
FROM pg_extension
WHERE extname = 'vector';
```

No claim is made that PostgreSQL lacks vector or that installation is needed.
Likewise, the intended PostgreSQL role's privileges and ability to create roles
cannot yet be assessed. No role creation was attempted. Reusing a broad role
would leave handwritten SQL capable of reaching objects outside the ingestion
schema; autogenerate filtering does not remove that risk.

## Pending PostgreSQL inspection

The user has been asked to configure the intended target securely in
`backend/.env`, and identify the other repository or provide its non-secret
host/port/database details. No credential should be posted in chat.

With a target available, open a read-only transaction using the resolved URL;
report only non-secret connection identity and catalog metadata. Do not import
`main`, run `init_db`, invoke Alembic, or initialize a worker during inspection.

```sql
SELECT current_database(), inet_server_addr(), inet_server_port(),
       current_user, current_schema(), current_setting('search_path');

SELECT nspname, pg_get_userbyid(nspowner) AS owner
FROM pg_namespace
ORDER BY nspname;

-- Application relations across all non-system schemas, with ownership.
SELECT n.nspname AS schema_name, c.relname AS table_name,
       c.relkind, pg_get_userbyid(c.relowner) AS owner
FROM pg_class AS c
JOIN pg_namespace AS n ON n.oid = c.relnamespace
WHERE c.relkind IN ('r', 'p', 'f')
  AND n.nspname <> 'information_schema'
  AND n.nspname !~ '^pg_'
ORDER BY n.nspname, c.relname;

SELECT n.nspname AS schema_name, c.relname AS version_table
FROM pg_class AS c
JOIN pg_namespace AS n ON n.oid = c.relnamespace
WHERE c.relkind IN ('r', 'p')
  AND (c.relname = 'alembic_version'
       OR left(c.relname, 16) = 'alembic_version_')
ORDER BY n.nspname, c.relname;

SELECT extname, extnamespace::regnamespace
FROM pg_extension WHERE extname = 'vector';

SELECT name, default_version, installed_version
FROM pg_available_extensions WHERE name = 'vector';

SELECT rolname, rolsuper, rolcreatedb, rolcreaterole
FROM pg_roles WHERE rolname = current_user;

SELECT has_database_privilege(current_user, current_database(), 'CONNECT') AS can_connect,
       has_database_privilege(current_user, current_database(), 'CREATE') AS can_create_schema;

SELECT nspname,
       has_schema_privilege(current_user, oid, 'USAGE') AS can_use,
       has_schema_privilege(current_user, oid, 'CREATE') AS can_create
FROM pg_namespace
WHERE nspname IN ('ingestion', 'public')
   OR oid IN (SELECT extnamespace FROM pg_extension WHERE extname = 'vector');
```

If access to a catalog or schema is denied, report the limitation; do not infer
that an unseen object is absent. Compare actual server/database identities with
the other project, allowing for hostname aliases/proxies. Do not classify solely
from repository names or a port listener.

Use **B** when both projects share the same database, **C** when they use the same
PostgreSQL instance but different databases, and **A** for a separate database on
a separate instance. This distinguishes C from the otherwise overlapping phrase
"separate database." Until identities are established, keep the result unclassified.

All three cases use `ingestion` schema, the separate migration history, preserved
table prefixes and the ownership rules documented in [README.md](README.md).
