# Bright Data discovery for Iroko chat

## Configuration

Set these in the backend environment (local `backend/.env`, or the Render web
service's Environment settings), then restart/redeploy the backend:

```dotenv
BRIGHTDATA_API_KEY=<your Bright Data API key>
BRIGHTDATA_SERP_ZONE=serp_api1
BRIGHTDATA_REGULATORY_SEARCH_ENABLED=true
```

Keep the key out of Git and frontend/public environment variables. Rotate any key
shared in a conversation. Direct SERP access needs no proxy customer ID/password.
It uses Bright Data's fixed HTTPS `/request` API endpoint. The existing proxy,
browser and scraper products are not enabled by this chat integration.

The feature defaults off. Set `BRIGHTDATA_REGULATORY_SEARCH_ENABLED=false` to turn
it off; direct official-catalogue research still works. Configure account/zone
spending controls in Bright Data before enabling at production scale. This code
bounds requests per research pass; it is not a cross-instance monthly quota.

## What happens

1. Existing chat routing decides whether public regulatory research is needed.
   Uploaded/attached-document questions stay within their source boundary.
2. The research service selects at most three regulators. For each, it searches
   once using an official domain, fixed public topic labels and `filetype:pdf`.
   Raw prompts, customer names, account identifiers and private document content
   are never sent to this search provider by this path. Catalogue discovery runs
   alongside search and can still find official HTML notices.
3. Search candidates are restricted to existing approved regulator HTTPS hosts.
   Search snippets and AI-generated search summaries are discarded. Website
   housekeeping pages are excluded; substantive instruments are prioritised.
4. At most two candidate documents per regulator are read through `OfficialClient`.
   Existing DNS/private-address, redirect, robots and download limits remain in
   force. No browser challenge/login bypass is attempted. Original fetched text
   and provenance go through the existing grounded-answer checks.
5. The agent activity includes a `web_search` step with discovery success counts.
   Actual official-page availability is recorded in the existing source checks.

Discovery uses one attempt per regulator, a 12-second HTTP timeout and a 13-second
overall provider-call deadline, inside the existing 28-second research budget.
Successful public-topic results are cached in-process for 10 minutes; failures for
30 seconds. The cache is bounded and not shared across instances. A provider
failure falls back to catalogue discovery, not fabricated results. HTTP 200
wrappers containing upstream errors are treated as failures, not empty searches.
Query-mismatch responses are rejected. A nonempty search response containing no
approved official URLs is recorded as `NoOfficialResults`, not successful coverage.

This does not replace Azure AI Search or run bulk ingestion. Public content is
temporarily parsed/cached, not automatically saved to the shared document library.
Scans requiring OCR, oversized PDFs, unavailable sites, and superseded regulations
remain possible gaps. Discovery is not proof a rule is current or applicable.

## Verification

From `backend`, with the backend Python environment active:

```powershell
python scripts/check_regulatory_search.py
python scripts/check_regulatory_search.py --fetch
python -m pytest tests/ingestion/test_regulatory_discovery.py tests/ingestion/test_regulatory_research.py
```

The live check makes a fixed public NDPC search. `--fetch` also exercises actual
official-source extraction, and fails if none of the discovered sources yield
usable evidence. It makes no model calls, database writes or email sends, and
prints no credentials. Live requests can consume the provider's allowance.

### Local verification, 8 October 2026

- 561 selected search, grounding, conversation, routing and streaming regression
  tests passed. These deterministic tests are separate from live provider checks.
- Live SERP calls returned official CBN and NDPC PDF links. A separate live fetch
  of the discovered NDPC registration guidance parsed five pages and produced four
  usable evidence passages with a source hash.
- Live results were mixed: other requests timed out, returned an upstream 502,
  or returned off-domain results. The strict combined `--fetch` check did not
  consistently pass. Failed/off-domain results were rejected, not used as evidence.
- No model-answer quality claim follows from these connectivity/extraction checks.
  No production deployment, bulk ingestion, or production database writes were made.

API integration follows the [Bright Data SERP documentation](https://docs.brightdata.com/products/serp-api/introduction)
and [parsed-result schema](https://docs.brightdata.com/products/serp-api/parsed-json-results).
