# Regulatory ingestion fixture sources

Reconnaissance started: 2026-09-17. Status updated: 2026-09-18.

Crawler identity approved by the maintainer on 2026-09-18:
`IrokoAI-RegulatoryIngest/1.0 (+mailto:ingest@irokoai.site)`.
All fetches below used that User-Agent with TLS verification on, a 2-second
per-host delay, and `robots.txt` checked first.

## CBN — fetched fixtures

| Fixture | Requested URL | Fetched (UTC) | Status | Bytes | SHA-256 (12) |
|---|---|---|---|---|---|
| `cbn/2026-09-18-01-robots.txt` | `https://www.cbn.gov.ng/robots.txt` | 2026-09-18T11:35:19 | 200 | 194 | `a28e1810a23c` |
| `cbn/2026-09-18-02-documents-index.html` | `https://www.cbn.gov.ng/documents/` | 2026-09-18T11:35:20 | 200 | 15,299 | `2edd050bf1f1` |
| `cbn/2026-09-18-03-ofid-other-financial-institution-supervision.html` | `…/documents/ofidcirculars.html` | 2026-09-18T11:49:51 | 200 | 7,486 | `4d1cd0abeedd` |
| `cbn/2026-09-18-04-bsd-banking-supervision-new.html` | `…/documents/BSDCircularsNEW.html` | 2026-09-18T11:49:53 | 200 | 7,354 | `50a263d07cf1` |
| `cbn/2026-09-18-05-compliance.html` | `…/documents/ComplianceCirculars.html` | 2026-09-18T11:49:55 | 200 | 7,257 | `5c7d586b47b3` |
| `cbn/2026-09-18-06-bod-payments-system.html` | `…/documents/BODcirculars.html` | 2026-09-18T11:49:58 | 200 | 7,302 | `a7c7fbf94981` |
| `cbn/2026-09-18-07-fpr-financial-policy-and-regulation.html` | `…/documents/FPRCircularsNotices.html` | 2026-09-18T11:50:02 | 200 | 7,472 | `5a2007e737f8` |
| `cbn/2026-09-18-08-aml-cft.html` | `…/documents/AML-CFT.html` | 2026-09-18T11:50:02 | 200 | 7,523 | `d373263ae1db` |
| `cbn/2026-09-18-09-all-cbn-circulars.html` | `…/documents/circulars.html` | 2026-09-18T11:50:04 | 200 | 7,348 | `981a10c2d38e` |
| `cbn/2026-09-18-10-api-ofis.json` | `https://www.cbn.gov.ng/api/GetOFISCirculars` | 2026-09-18T11:52:58 | 200 | 40,680 | `276e2558cb26` |
| `cbn/2026-09-18-11-api-all.json` | `https://www.cbn.gov.ng/api/GetAllCirculars` | 2026-09-18T11:53:01 | 200 | 1,177,729 | `0fac90541443` |

Selection reason: the documents index was the brief's seed; the seven category
pages are the brief's priority categories plus AML/CFT and All CBN Circulars,
with every href taken verbatim from the index fixture. The two `.json` fixtures
are the Kendo grid data endpoints discovered inside the category pages — the
listings are not present in the category HTML.

### Full capture: not committed

`cbn/2026-09-18-11-api-all.json` is **gitignored** (1.15 MB, re-fetchable).

| | |
|---|---|
| Source URL | `https://www.cbn.gov.ng/api/GetAllCirculars` |
| Fetched (UTC) | 2026-09-18T11:53:01 |
| Records | 2,629 |
| Bytes | 1,177,729 |
| SHA-256 | `0fac90541443f27b5e996ff2bb106e9b5e4ef0781b9e9d5e9bfde04b83613147` |

Re-fetch (Phase 1 onward, once the CLI exists):

```
python -m ingestion recon https://www.cbn.gov.ng/api/GetAllCirculars \
    --save backend/tests/ingestion/fixtures/cbn/$(date -u +%Y-%m-%d)-api-all.json
```

The hash above pins what CBN advertised on that date. A different hash on
re-fetch is expected — the catalogue grows — and is not a failure.

### Committed sample

`cbn/api-all-sample.json` — **52 records, 26,521 bytes**, derived from the full
capture above. Deliberately chosen so that every quirk in `LANDMINES.md` has at
least one example: all 4 raw-HTML links, both empty links, 6 spreadsheets, 6
whitespace-padded `refNo` values, all three `/Out/` `/OUT/` `/out/` case
variants, links containing spaces, dates with day > 12, the oldest (2002–2009)
and newest (2025–2026) years, and ordinary control rows. Parser tests run
against this file, not the full capture.

## CBN — blocked requests (not fixtures)

Three circular PDFs selected from `2026-09-18-10-api-ofis.json` were requested
and refused. No bypass was attempted.

| Requested URL | Attempted (UTC) | Result |
|---|---|---|
| `…/Out/2019/OFISD/Letter to all MFBs on the Revised National Financial Inclusion Targets.pdf` | 2026-09-18 | HTTP 403 |
| `…/out/circulars/ofid/2009/ofid-01-2009.pdf` | 2026-09-18 | HTTP 403 |
| `…/Out/2013/OFISD/Extension of Compliance Deadline for MFBs.pdf` | 2026-09-18 | HTTP 403 |

A single diagnostic request to the second URL returned `server: cloudflare`, a
`cf-ray` header and a `Just a moment...` interstitial: a Cloudflare anti-bot
challenge. `robots.txt` permits these paths, so this is an access control
applied above robots, not a crawl-policy refusal. No CBN PDF fixture exists yet
and none of the three responses is stored as a publication fixture.

## SEC — fetched fixtures

Captured 2026-09-18 by the earlier Phase 0 helper, stored as raw
`*.response.bin` with `*.source.json` sidecars and per-attempt `*-attempt.json`
manifests. Sidecars for these predate the `requested_url` field; the URLs are
recorded in the attempt manifests.

| Fixture | Fetched (UTC) | Status | Bytes |
|---|---|---|---|
| `sec/20260918T113545Z-01-home-sec-gov-ng.response.bin` | 2026-09-18T11:35:47 | 404 | 25 |
| `sec/20260918T113545Z-02-home-sec-gov-ng.response.bin` | 2026-09-18T11:35:51 | 200 | 49,181 |
| `sec/20260918T113545Z-03-sec-gov-ng.response.bin` | 2026-09-18T11:35:53 | 404 | 25 |
| `sec/20260918T113545Z-04-sec-gov-ng.response.bin` | 2026-09-18T11:35:54 | 301 | 0 |
| `sec/20260918T113545Z-05-sec-gov-ng.response.bin` | 2026-09-18T11:35:57 | 200 | 103,966 |
| `sec/20260918T113712Z-01-sec-gov-ng.response.bin` | 2026-09-18T11:37:13 | 404 | 25 |
| `sec/20260918T113712Z-02-sec-gov-ng.response.bin` | 2026-09-18T11:37:17 | 200 | 287,113 |

`sec.gov.ng/robots.txt` returned 404, which the brief treats as "allowed".

## Still outstanding

- Three CBN circular PDFs — blocked by the Cloudflare challenge above.
- A second CBN pagination page — not applicable: the grid endpoints return the
  complete dataset in one response and paginate client-side.
- SEC circulars RSS feed, three linked circular pages (HTML-only and
  PDF-attachment examples), and the rules-and-regulations page, each recorded
  with its requested URL.
- Synthetic derivatives (banner-variant HTML, generated scanned PDF) are created
  in later phases and must be labelled as derivatives of a named real fixture.

## Record format after each successful fetch

Record fixture path, requested URL, final URL, fetch timestamp in UTC, media type,
exact byte count, SHA-256, and the reason it was selected. The Phase 0 helper
writes a matching `.source.json` sidecar. Preserve raw bytes and path case.

Record failed or disallowed requests separately with URL, attempt date and reason;
never label an access-denied/challenge/error body as a publication fixture. Mark
generated banner variants and later generated scanned PDFs as synthetic derivatives,
with a reference to their real source fixture. Do not overwrite existing snapshots.
