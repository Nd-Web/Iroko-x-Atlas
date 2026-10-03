# CBN manual import - 30 September 2026

This supersedes the unresolved-download status in [the earlier recovery report](cbn-recovery-2026-09-30.md), which remains an historical record.

## Completed

- All 18 PDFs matched expected filenames and CBN catalogue file sizes and parsed successfully.
- All 18 originals preserved privately in Azure Blob Storage and registered in production Postgres.
- 92 page records and 68 text chunks extracted; all 18 documents indexed.
- Together with the two previously indexed documents, the initial 20-document batch is now ingested.
- Original Blob hashes match the supplied files. All 68 chunks match their saved page offsets and hashes, and Azure Search content matches Postgres.
- No extra documents or recurring sources enabled. Original downloads were not modified or deleted.
- The earlier third-party gazette candidate was not used or indexed.

## Metadata review

Catalogue values are retained separately from printed dates and references.

| Item | Catalogue date | Printed document date |
| --- | --- | --- |
| 7116: 47-bank gazette | 2023-05-23 | 2023-05-22 |
| 6034: 2019 AFS extension | 2020-05-29 | 2020-04-30 |
| 5701: MFB inclusion targets | 2019-07-01 | 2019-06-20 |
| 5017: BVN enrolment | 2017-04-24 | 2017-04-21 |

published_date uses the printed issue date with date_basis recorded. Catalogue dates remain separately stored; differences do not necessarily mean that website posting dates are erroneous.

Printed references were recorded separately from catalogue references. The gazettes use distinct statutory-instrument identifiers.

Sparse second pages in both gazettes were visually confirmed as page-number-only pages, not missing OCR; originals remain intact.

The MFB targets letter states 64 customers per month and 774 per year. The source contains this arithmetic inconsistency. Text was preserved unchanged and a provenance warning was added.

Technical review covered page completeness, quality flags, first-page identity, dates/references, exact chunk integrity, original hashes and all indexed chunks. This is not a full legal/content audit or confirmation of present-day applicability. End-to-end answer/citation evaluation and current-regulation coverage remain separate rollout checks.

## Evidence

- Import/OCR: iroko-ingestion-manual-k9ce1e0
- Review/index: iroko-ingestion-manual-6xfflhp
- Private audit in iroko-documents: manual-import/2026-09-30/cbn/final-5635564aef8a225d5f2469f84f20acd711516636bdc4eeeb8220f24cf18324b1.json
- [Document IDs, checksums and metadata](cbn-manual-import-2026-09-30.json)
