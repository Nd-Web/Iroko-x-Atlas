# Frontend performance pass — 2026-10-09

Status: implemented locally; not pushed or deployed.

## Changes

- Moved authentication, query caching and toast providers out of the root layout into the app/auth route groups. Homepage and pilot booking no longer fetch `/api/auth/me` or start session polling. Protected routes retain their providers and existing server-side authorization.
- Converted the homepage's static content to a Server Component, with a small interactive mobile-header component. Layout, copy, illustrations and FAQ behavior remain unchanged.
- Disabled automatic login-route prefetch in the public header, so it does not pull app/auth bundles into the public page's initial load. Pilot CTA prefetch remains enabled.
- Sidebar destinations prefetch on hover, keyboard focus or touch instead of preloading every visible destination. Links still use Next.js client-side navigation.
- Split inactive dashboard compliance/audit tabs into on-demand chunks. Audit-chain verification is requested when the audit tab is opened, not on every dashboard visit. Verification itself has not been removed.
- Reused one WAT date formatter for booking slot grouping and avoided repeatedly copying each day's slot array. Availability stays uncached and submit-time conflict handling is unchanged.
- Preserved unchanged chat-message identities with a per-workspace WeakMap, memoized message rendering, and replaced repeated history scans with one linear question lookup. This avoids re-parsing old Markdown answers during another answer's updates. Citations, feedback, interruption flags and export question context remain intact.

## Measured result and limitations

Measured using a local production build (`next build` / `next start`), headless Edge, a fresh browser context for each route and a 390 × 844 viewport. Browser API requests were mocked; no actual bookings, emails or model calls were made by the smoke flows.

| Chat page initial-load measurement | Before | After |
| --- | ---: | ---: |
| Compressed script bytes | 423,979 | 231,425 |
| Decoded script bytes | 1,397,294 | 794,627 |
| Script requests | 27 | 11 |
| Resource requests | 97 | 20 |

This is about 45% fewer compressed script bytes in the sampled local chat-page load, including scripts fetched speculatively. It is not a 45% improvement in response time, an AI inference benchmark, or a production Core Web Vitals result. Automatic prefetch timing can affect measurements; public-page totals varied across runs. First-paint timings were not used to claim an improvement.

Behavioral checks also confirm zero initial auth API requests on the homepage/booking page and no audit-trail request on the inactive dashboard tab.

## Verification

- Production build and TypeScript checking passed.
- All 80 frontend Node tests passed, including 11 new performance regressions.
- Targeted lint: no errors; the existing unused `onClose` warning in Sidebar remains.
- Mobile (390px) and desktop (1440px) browser smoke flows passed: homepage navigation and FAQ, homepage-to-pilot navigation, date/time selection, mocked booking conflict/refresh then success, mocked login-to-dashboard transition, lazy audit/compliance tabs, two chat turns and expansion of earlier messages. No browser runtime errors were observed.

## Repeat the checks

From `frontend`:

```powershell
node --test tests/*.test.cjs
npm run build
npm run start -- --port 3377
```

In another terminal, with Playwright installed locally (or `IROKO_PLAYWRIGHT_MODULE` pointing at an existing installation):

```powershell
$env:IROKO_BROWSER_CHANNEL = 'msedge'
node scripts/measure-frontend.cjs
$env:IROKO_PERF_WIDTH = '1440'
node scripts/measure-frontend.cjs
```

The script only accepts localhost and mocks browser API calls. Use a test backend configuration when testing additional server-rendered routes. Set `IROKO_PERF_ASSERT_OPTIMIZED=0` when measuring an older baseline that still makes the removed requests.

## Remaining production considerations

This pass does not alter backend hosting, database queries, availability-provider latency, model inference or evidence checks. Backend cold starts or slow upstream services can still delay data and AI answers. Validate production performance after deployment before choosing further infrastructure or backend changes.
