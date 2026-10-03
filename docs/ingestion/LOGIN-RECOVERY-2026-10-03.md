# Login / backend availability recovery

The frontend's “Backend unavailable” response occurs when its authentication upstream returns non-JSON. On inspection, both the public backend and login proxy were reachable, but the production database was still at `20260930_pipeline`; release `662f428` requires `20261003_retire_demo`.

The imported ingestion routes install global audit ownership hooks. A successful login writes an audit entry, which now queries workspace tables. Thus an unmigrated deployment can pass shallow health checks and reject nonexistent credentials correctly but fail an actual successful login. An enabled document pipeline instead rejects the schema during startup. The deployment sequence was incomplete.

## Production repair performed

- Created a private custom-format PostgreSQL backup in ignored `.dist/production-recovery/`; verified its archive table-data listing before changing production.
- Applied both reviewed pending migrations with Alembic in one transaction.
- Confirmed head `20261003_retire_demo`, preserved all five user identities, all 28 document rows, all 20 real revision identities/checksums and all 88 chunks. Demo rows are recoverably archived, not physically deleted.
- Ran the production schema preflight in a read-only transaction. No real credentials, tokens, database URLs or backup contents are committed or printed.

## Code protections

Postgres API startup now checks the required audit/workspace schema even when document processing is disabled. It does not disable access controls or automatically migrate a production database on a web request.

Login transport permits only one retry for gateway 502/503/504 responses or connection failures, with ten seconds per attempt and a thirty-second handler budget. Credential/account/rate-limit errors are not retried. Invalid JSON or malformed success payloads cannot create a cookie. Session cookies remain secure and httpOnly; tokens never appear in the frontend response. Error responses are no-store and outage responses include retry guidance. A retry is not a cure for a persistent service or schema outage.

Regression coverage includes the successful-login scoped-audit write, invalid-password behavior, disabled-pipeline Postgres preflight, gateway recovery, retry bounds, malformed payloads and session cookie handling. Local tests do not constitute a real-user production login: the live diagnostic used a nonexistent account, correctly receiving 401. The user should retry their own login after rollout.

Final checks: 104 backend tests and 19 frontend proxy tests passed, plus TypeScript and focused frontend/backend lint. The two corrupt local development-generated type files were preserved under ignored `.dist/next-type-recovery/`, then route types regenerated using the installed Next.js generator. No downloaded PDF or production backup is included in this release.

## Prevent recurrence

Before future API releases that change schema, verify a backup and run from the release's `backend/` against the intended production database:

```powershell
python -m alembic -c ingestion/alembic.ini upgrade head
python -m ingestion check
```

Use a controlled release/pre-deploy step rather than starting new API/worker code against an older schema. Keep API and worker release versions compatible. Never resolve a schema error by disabling workspace filters or reverting to demo evidence.
