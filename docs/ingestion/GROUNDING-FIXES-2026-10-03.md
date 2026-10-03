# Document grounding and demo retirement

## Implemented

- Document and regulatory questions retrieve only accessible, current, indexed canonical extraction revisions. Empty retrieval fails closed; relevance ranking is not a probability of correctness.
- Strict structured drafts carry atomic claims, exact contiguous quotations and canonical chunk identities. Multi-document comparisons explicitly cite each supporting passage. Server-side validation rejects invented coordinates, quotations and unsupported numbers.
- A separate semantic audit checks support, attribution, historical scope and question coverage. At most one repaired draft is allowed. Calculations use validated operands and server-side Decimal arithmetic.
- Normal and streaming APIs share validation before displaying prose. The API preserves the knowledge-gap flag. Streaming therefore waits for the validated answer rather than leaking unchecked draft tokens.
- Source citations are assembled from database identities and provenance. Document answers bypass executive rewriting, static regulatory context, synthetic relevance-statistic analysis and organisation-memory injections.
- Retired startup seeding, canned scenarios, seed command contents, mock extracted text, both static regulatory corpora, sample fraud/Watchdog alerts, fabricated news/SERP/scraping results and synthetic briefing fallback facts. Empty compatibility interfaces remain for existing importers. These interfaces are not live monitoring integrations.
- Eight legacy demo identities without an extraction revision, original Blob or source connector are excluded from access. Migration `20261003_retire_demo` retains original records in an ingestion-owned recovery archive, marks their application rows archived and revokes demo access. It does not delete real uploads, extracted regulator records, PDFs or users. Destructive downgrade is refused.

The OpenAI Docs skill informed strict schema use in both Chat Completions and Responses, following the official [Structured Outputs documentation](https://developers.openai.com/api/docs/guides/structured-outputs). Schema adherence is not proof of semantic correctness.

## Verification and known limitations

The final automated grounding/ingestion suite passed locally: 100 tests, including the disposable-PostgreSQL retirement migration, schema preflight, canonical-source access and replacement demo-fallback assertions. Focused grounding/migration lint checks also passed. Tests never used the configured production database.

The critical live retest used the configured `gpt-5.4-nano` deployment and genuine extracted CBN evidence in an isolated local ASGI application/database, with no production writes. Run artifacts remain local and ignored under `.dist/rag-evaluation/nano-5osqqlwe/`.

Eight answers were checked across normal and streaming modes: BVN timeline, conflicting FTR tables, uninsured-entity fine, and workbook new-customer definition. BVN dates and FTR attribution were correct in both modes; neither selected a historically conflicting table as current law. The workbook no longer invented a “new to the bank” criterion, but the normal answer omitted the savings/credit categories requested. Both fine questions conservatively refused instead of confirming that the full letter states no fine; they invented no fine amount. Five answers passed the automated triage checks, which do not certify accuracy.

Nano's semantic auditor can still approve incomplete answers or refuse supported ones. This is an observed remaining gap, not a production-ready accuracy guarantee. Exact-source validation reduces fabrication but cannot prove every paraphrase or legal interpretation. The complete 56-answer suite has not been rerun against this final release. Production deployment/load/browser tests also remain outstanding.

## Rollout

Follow `PRODUCTION-HARDENING.md`: verified database backup, pause document writes, migrate to `20261003_retire_demo`, update matching worker/API/frontend versions, check schema readiness, explicitly assign workspaces/share approved regulator revisions, and run production smoke tests before reopening uploads. No production migration is run merely by committing this code. The startup demo seed flag can no longer re-enable fabricated evidence.

Downloaded `CBN PDF/`, local `.dist/` artifacts and populated `.env` files are excluded from the commit. Originals are preserved locally. Sample expectations in test fixtures are not application evidence.
