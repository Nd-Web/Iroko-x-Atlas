# CBN listing data quirks

Every quirk below was observed in the full 2,629-record capture of
`https://www.cbn.gov.ng/api/GetAllCirculars` taken 2026-09-18
(sha256 `0fac90541443f27b5e996ff2bb106e9b5e4ef0781b9e9d5e9bfde04b83613147`).

`api-all-sample.json` (52 records) is committed and deliberately contains at
least one example of each. Parser tests should run against that sample.

| # | Quirk | Count in full capture | Example |
|---|---|---|---|
| 1 | `link` contains spaces | 1,510 / 2,629 | `/Out/2026/FMD/Review of Discount Window Circular.pdf` |
| 2 | `link` path case varies | `/Out/`, `/OUT/`, `/out/`, `/OUT/C`, `/out/c` | `/out/circulars/ofid/2009/ofid-01-2009.pdf` |
| 3 | `link` contains raw HTML, not a path | 4 | `<A TITLE="If clicking fails, right click…" HREF="../OUT/CIRCULARS/TED/200…` |
| 4 | `link` has a trailing anchor fragment | included in #3 | `/Out/2012/circulars/fpr/Additional KYC Requirement.pdf">Download</a>` |
| 5 | `link` empty | 2 | `""` |
| 6 | Non-PDF artifacts | 13 | `.xls`, `.xlsx`, plus truncated values such as `/fmd/`, `2009/`, `00.08` |
| 7 | `refNo` padded with whitespace | 21 | `"FMD/DIR/PUB/CIR/001/031 "` (trailing space) |
| 8 | `filesize` is a **string**, never an int | 2,629 / 2,629 | `"399862"` |
| 9 | `documentDate` is **DD/MM/YYYY** | 2,629 / 2,629 | `23/05/2023` |

## Notes per quirk

**1–2 — URL normalisation.** Percent-encode spaces and unsafe characters, and
**never lowercase the path**. Resolve relative links with `urljoin` against the
listing page URL. Some links begin `../`, so resolution must handle traversal.

**3–5 — defensive link parsing.** 6 of 2,629 rows (0.23%) do not yield a usable
URL directly. Extract an `href` when the value contains markup, strip any
trailing anchor text, and record a `document_failed` audit event with the raw
value when no URL can be recovered. Never crash the run on these.

**6 — spreadsheets.** Per the maintainer's decision, download and store these
with full metadata, set status `stored_unparsed`, and skip extraction. Never
silently drop a regulatory artifact. Truncated values such as `/fmd/` cannot be
fetched and should be recorded as failures.

**7 — reference numbers.** Store `reference_number` verbatim, exactly as
published. Populate `reference_number_normalized` (trimmed, internal whitespace
collapsed, uppercased, indexed) for lookup and the exact-match search boost.
The 21 padded values are the regression corpus for this.

**8 — filesize.** Coerce to int defensively; treat non-numeric as unknown. This
is the listing's claim, not a verified size — the real size comes from the
download.

**9 — dates.** DD/MM/YYYY is proven, not assumed: 1,586 rows have a first
component greater than 12, and **zero** rows have a second component greater
than 12. All 2,629 values parse under `%d/%m/%Y`. Parse with that explicit
format. A test must fail loudly if a future capture contains a row that parses
only as MM/DD/YYYY, which would indicate CBN changed format.
