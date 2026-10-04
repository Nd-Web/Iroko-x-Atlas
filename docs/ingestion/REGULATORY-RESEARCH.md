# Evidence-first regulatory research

Chat can now attempt bounded official research for a regulatory question when stored
evidence cannot answer it, or immediately when the user asks for latest/current findings.
Precise uploaded-document, letter and spreadsheet questions stay source-scoped.

For public freshness questions, the official check runs first. If it returns usable
evidence, an unnecessary embedding/index lookup is skipped. Institution-specific status,
filing, record and risk-exposure questions still retrieve authorized internal evidence.

The research path reads official CBN, SEC, NDPC, NDIC, NFIU or FCCPC discovery pages.
It selects up to three regulators and two linked documents per regulator, using local
keyword ranking. It is not an exhaustive web search or a continuous monitoring service.
All URLs, redirects and DNS addresses pass the ingestion client's HTTPS/domain/public-IP
checks and robots policy. No full customer prompt or uploaded document is sent to a
search provider. The existing configured reasoning model still receives permitted
retrieved evidence, as in ordinary document chat.

Budgets: 28-second overall research deadline, six-second HTTP request timeout, no retries,
3 MB per fetched response, PDF native extraction limited to 50 pages/eight seconds,
and nine evidence passages. OCR is not automatically charged from chat. Public-page
text is cached in process for ten minutes, at most 24 pages. Answers and customer
documents are never stored in that shared cache. Page text is untrusted data.

Each passage has a canonical source ID, URL, content hash, fetch timestamp and physical
page/text offset. Fetch time is not publication time. This lookup does not bulk ingest
documents into the permanent regulatory corpus; ingestion remains a separate workflow.
Validated source excerpts and official URLs survive persisted chat citations.

Partial findings still require exact source quotes, server-owned citation coordinates,
numeric checks and an independent model evidence audit. These checks are per claim:
one rejected quote or unsupported fact cannot erase other independently approved
findings. An empty first draft gets one bounded repair attempt. Precise source-reading
questions retain their all-or-nothing completeness requirements. Unsupported fines, fees
misrepresented as penalties, assumed customer compliance, and unsupported claims of
current applicability are not approved merely because other facts are supported.
The response separates verified findings from missing penalty, scope, customer status,
supersession or freshness information. A recent announcement is not the customer's
highest risk, and a bounded lookup cannot certify it found the absolute latest rule.
If automated validation fails despite finding sources, source links/excerpts remain
available explicitly for review, not as approved compliance conclusions. A reasoning
outage is distinguished from missing source material. Diagnostic logs contain only
validation stages and candidate counts, not customer questions, documents or model prose.

No new credentials or database migration are needed for this path. Existing chat-model,
embedding/search, database and outbound HTTPS configuration must still work. Official
sites may be blocked, unavailable or scanned; failures are reported as incomplete
coverage rather than interpreted as absence of obligations or penalties.

Run deterministic checks from backend:
`python -m pytest tests/ingestion tests/test_grounded_answers.py`

For an explicitly authorized live smoke test, first create the public-only snapshot
with `scripts/evaluate_document_answers.py snapshot`, then run
`python scripts/evaluate_regulatory_answers.py --question "latest compliance risk and cost"`.
The latter uses the real configured model and public websites, but isolates all chat
writes in SQLite under ignored `.dist/rag-evaluation`. Review results, not just exit status:
the model audit and smoke test do not guarantee legal correctness.
Use `--require-findings` for a regression case expected to produce approved findings;
this fails on a generic/source-review fallback rather than counting any HTTP 200 as success.
