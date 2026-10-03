# CBN attachment recovery — 30 September 2026

## Result

- Original 20-document batch: 2 already indexed, 18 attachment downloads failed.
- This recovery attempt: 1 third-party PDF candidate preserved, 17 still unrecovered.
- No new documents were added to Postgres or Azure AI Search.
- The recovered candidate is in a private Blob recovery prefix, separate from normal indexed document paths.

## Recovered candidate

CBN catalogue item 7117, **Revocation of Operating Licenses**, dated 23 May 2023.

Downloaded from [SabiLaw's public PDF copy](https://sabilaw.org/wp-content/uploads/2023/06/Revocation-of-Operating-Licence-original-1.pdf).
The PDF opens and has 10 pages. Its front page identifies Gazette No. 94, Vol. 110, Government Notice No. 57 and S.I. No. 23. Printed pagination is B459–B468.

SHA-256: `b2e8f7d5c4969cd9a2b20e1e3a409888f9f85c8e2eab2c609e697e8b2a983e7e`

The downloaded file has 469,098 bytes; the CBN catalogue lists 399,862 bytes. This difference does not prove alteration, but byte identity and full equivalence cannot be verified while the official original is unavailable. It remains **unverified and excluded from search**.

Private storage: `irokoai / iroko-documents / recovery/2026-09-30/cbn-7117/b2e8f7d5c4969cd9a2b20e1e3a409888f9f85c8e2eab2c609e697e8b2a983e7e/revocation-gazette-94.pdf`

## Remaining work

The [manifest](cbn-recovery-2026-09-30.json) lists all 18 exact canonical links, catalogue dates/references and recovery status. Catalogue metadata may differ from the printed instrument and must be checked against the original.

Official alternative links checked still returned access challenges. Association archives generally linked back to CBN, while other results were summaries or sign-in restricted. No challenge pages were ingested.

The next practical route is to download the originals through a normal authorized browser session, or obtain them directly from CBN. Preserve the original bytes and canonical URLs. Before indexing, verify title/reference/date, all pages and tables, extraction quality and historical applicability. Do not automatically mark historical circulars as currently applicable.

No CBN outreach was sent and no recurring retry schedule was enabled.
