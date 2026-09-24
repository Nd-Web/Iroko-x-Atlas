# CBN User-Agent allowlist request — DRAFT, NOT SENT

**Status:** awaiting maintainer approval and a confirmed recipient address.
**From:** ingest@irokoai.site

## Which address to use

I could not verify a contact address from a fetched CBN page — the documents
index fixture does not expose one, and I will not guess an address for outbound
mail. Please confirm the recipient before this is sent. Candidates to verify on
cbn.gov.ng directly:

- The webmaster / IT contact on the CBN "Contact Us" page.
- The Corporate Communications Department, which handles general external
  correspondence.
- The Other Financial Institutions Supervision Department (OFISD), which owns
  the circulars most relevant to us — useful as a CC, since they benefit from
  accurate downstream distribution of their circulars.

Sending to an unverified address risks the request being ignored, so it is worth
confirming rather than guessing.

## Draft

> **Subject:** Request to allowlist a documented compliance crawler (IrokoAI-RegulatoryIngest)
>
> Dear Sir/Madam,
>
> I am writing to request that a clearly identified automated client be
> permitted to download circulars published on cbn.gov.ng.
>
> **Who we are.** Iroko AI is a Nigerian regulatory-compliance platform used by
> microfinance banks and fintechs to track their obligations under CBN
> regulation. We maintain an internal library of CBN circulars so that our users
> are advised against the exact published wording rather than a paraphrase.
>
> **What we fetch.** Only PDF and HTML documents linked from CBN's own public
> listing pages, discovered through `https://www.cbn.gov.ng/documents/` and the
> circular listing endpoints it uses. We do not attempt to access any
> non-public, authenticated or restricted area of the site.
>
> **How often.** A single incremental check each day at approximately 06:00 WAT,
> which downloads only documents that are new or have changed since our last
> check. A one-time historical backfill would be spread over several days.
>
> **Our rate limits.** One request at a time per host, with a minimum two-second
> delay between requests, giving a ceiling of roughly 30 requests per minute and
> in practice far fewer. We honour `robots.txt`, follow `Retry-After`, and use
> conditional requests (`If-None-Match` / `If-Modified-Since`) so unchanged
> documents are not re-downloaded.
>
> **How to identify us.** Every request carries this User-Agent:
>
> `IrokoAI-RegulatoryIngest/1.0 (+mailto:ingest@irokoai.site)`
>
> **The problem.** Requests for the HTML listing pages succeed, but requests for
> the PDF files themselves (for example under `/Out/` and `/out/circulars/`)
> return HTTP 403 from Cloudflare with a browser challenge. We have not
> attempted to circumvent this in any way, and we will not do so. We are asking
> instead for the above User-Agent to be allowlisted in your Cloudflare
> configuration for public document paths.
>
> We are happy to supply a fixed source IP range, reduce our request rate
> further, or restrict our fetching to a specific window that suits your
> operations.
>
> If this request should be directed to a different department, I would be
> grateful if you could point me to the right contact.
>
> Thank you for your time.
>
> Yours faithfully,
>
> *[name, role]*
> Iroko AI
> ingest@irokoai.site

## Before sending

- Confirm the recipient address (see above).
- Replace the signature placeholder with a real name and role; an anonymous
  request is unlikely to be actioned.
- Decide whether to offer a fixed egress IP. Current egress is a residential
  MTN Nigeria connection in Lagos (AS29465), which is dynamic — a stable IP
  would make allowlisting easier for CBN and may be worth arranging first.
