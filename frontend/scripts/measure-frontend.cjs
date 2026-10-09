/* eslint-disable @typescript-eslint/no-require-imports -- Standalone Node diagnostic. */
// Run against `next start`, never production. Browser API calls are mocked, so this
// measures frontend overhead without sending email, booking, or model requests.
// Set IROKO_PLAYWRIGHT_MODULE to an installed Playwright module if not local.
const assert = require("node:assert/strict");
const { chromium } = require(process.env.IROKO_PLAYWRIGHT_MODULE || "playwright");
const base = process.env.IROKO_PERF_URL || "http://127.0.0.1:3377";
const width = Number(process.env.IROKO_PERF_WIDTH || 390);
const assertOptimized = process.env.IROKO_PERF_ASSERT_OPTIMIZED !== "0";
if (!["localhost", "127.0.0.1"].includes(new URL(base).hostname)) {
  throw new Error("Use an isolated local production build, not a deployed site.");
}

async function main() {
  const browser = await chromium.launch({ headless: true, channel: process.env.IROKO_BROWSER_CHANNEL });
  try {
    for (const pathname of ["/", "/request-demo", "/login", "/dashboard", "/chat"]) {
      const protectedPage = ["/dashboard", "/chat"].includes(pathname);
      const context = await browser.newContext({ viewport: { width, height: 844 }, serviceWorkers: "block" });
      if (protectedPage) await context.addCookies([{ name: "iroko_token", value: "local-performance-fixture", url: base }]);
      const apiCalls = [];
      let signedIn = protectedPage;
      let bookings = 0;
      let chatTurns = 0;
      await context.route("**/api/**", async route => {
        const url = new URL(route.request().url());
        apiCalls.push(url.pathname);
        let status = 200;
        let body = {};
        if (url.pathname === "/api/auth/me") {
          status = signedIn ? 200 : 401;
          body = signedIn ? { id: "perf-user", full_name: "Performance Test", role: "admin", email: "test@example.test" } : { detail: "Not signed in" };
        } else if (url.pathname === "/api/auth/login") {
          signedIn = true;
          await context.addCookies([{ name: "iroko_token", value: "local-performance-fixture", url: base }]);
        } else if (url.pathname === "/api/pilot/requests") {
          bookings++;
          status = bookings === 1 ? 409 : 201;
          body = bookings === 1 ? { detail: { message: "That time was just booked. Please choose another." } }
            : { id: "mock-booking", slot_start: route.request().postDataJSON().slot_start, slot_end: "2026-10-13T08:30:00Z", timezone: "Africa/Lagos" };
        } else if (url.pathname === "/api/atlas/ask/stream") {
          chatTurns++;
          const complete = { type: "complete", conversation_id: "test-conversation", answer: `Verified test answer ${chatTurns}.`, agent_trace: [],
            citations: [{ document_id: "test-document", source: "Test policy", excerpt: "A test clause.", source_url: "https://example.test/policy" }],
          };
          await route.fulfill({ contentType: "text/event-stream", body: `data: ${JSON.stringify(complete)}\n\n` });
          return;
        } else if (url.pathname === "/api/pilot/availability") {
          body = { timezone: "Africa/Lagos", slot_minutes: 30, business_hours: "09:00–17:00 WAT", slots: ["2026-10-12T08:00:00Z", "2026-10-12T08:30:00Z", "2026-10-13T08:00:00Z"] };
        } else if (url.pathname.endsWith("/signals")) {
          body = { regulatory: [], competitor: [], vendor_risk: [], fraud: [], market: [] };
        } else if (url.pathname.endsWith("/audit-trail")) {
          body = { entries: [], total: 0, chain_valid: true };
        } else if (url.pathname === "/api/atlas/conversations") {
          body = { conversations: [] };
        } else if (url.pathname === "/api/documents") {
          body = { total: 0, documents: [] };
        } else if (url.pathname === "/api/alerts") {
          body = { total: 0, alerts: [] };
        }
        await route.fulfill({ status, contentType: "application/json", body: JSON.stringify(body) });
      });
      const page = await context.newPage();
      const errors = [];
      page.on("pageerror", error => errors.push(error.message));
      const response = await page.goto(base + pathname, { waitUntil: "networkidle" });
      assert.equal(response.status(), 200, pathname);
      await page.locator("h1").first().waitFor();
      const metrics = await page.evaluate(() => {
        const resources = performance.getEntriesByType("resource");
        const scripts = resources.filter(entry => entry.initiatorType === "script");
        return {
          scriptRequests: scripts.length,
          scriptDecodedBytes: scripts.reduce((sum, entry) => sum + entry.decodedBodySize, 0),
          scriptEncodedBytes: scripts.reduce((sum, entry) => sum + entry.encodedBodySize, 0),
          resourceRequests: resources.length,
          // Local lab timings, not a production Core Web Vitals score.
          fcpMs: Math.round(performance.getEntriesByName("first-contentful-paint")[0]?.startTime || 0),
        };
      });
      const initialApiCalls = [...apiCalls];
      if (assertOptimized && ["/", "/request-demo"].includes(pathname)) {
        assert.equal(initialApiCalls.includes("/api/auth/me"), false, "public pages must not check app sessions");
      }
      if (assertOptimized && pathname === "/dashboard") {
        assert.equal(initialApiCalls.some(path => path.endsWith("/audit-trail")), false, "inactive audit tab must not fetch");
      }
      if (pathname === "/") {
        if (width < 900) {
          await page.getByRole("button", { name: "Open navigation" }).click();
          await page.getByRole("navigation", { name: "Mobile navigation" }).getByText("Platform", { exact: true }).click();
          assert.equal(await page.getByRole("button", { name: "Open navigation" }).getAttribute("aria-expanded"), "false");
        }
        await page.locator("summary").first().click();
        assert.equal(await page.locator("details").first().getAttribute("open"), "");
        await page.getByRole("link", { name: /Request Free 30-Day Pilot/ }).first().click();
        await page.locator('[aria-label="Available dates"] button').first().waitFor();
        assert.equal(new URL(page.url()).pathname, "/request-demo");
      } else if (pathname === "/request-demo") {
        const dates = page.locator('[aria-label="Available dates"] button');
        assert.equal(await dates.count(), 2);
        await dates.last().click();
        assert.equal(await page.locator('[aria-label="Available times"] button').count(), 1);
        await page.locator('[aria-label="Available times"] button').click();
        assert.equal(await page.getByRole("button", { name: "Request free 30-day pilot" }).isEnabled(), true);
        await page.locator('[name="full_name"]').fill("Local Test");
        await page.locator('[name="work_email"]').fill("test@example.test");
        await page.locator('[name="phone"]').fill("8012345678");
        await page.locator('[name="job_title"]').fill("Compliance Officer");
        await page.locator('[name="company_name"]').fill("Local Test Company");
        await page.locator('[name="company_type"]').selectOption({ label: "Microfinance Bank" });
        await page.locator('[name="country"]').fill("Nigeria");
        await page.locator('[name="consent_to_contact"]').check();
        await page.getByRole("button", { name: "Request free 30-day pilot" }).click();
        await page.getByRole("alert").filter({ hasText: "That time was just booked" }).waitFor();
        await page.locator('[aria-label="Available times"] button').first().click();
        await page.getByRole("button", { name: "Request free 30-day pilot" }).click();
        await page.getByRole("heading", { name: "You're booked." }).waitFor();
        assert.equal(bookings, 2);
      } else if (pathname === "/login") {
        await page.locator("#email").fill("test@example.test");
        await page.locator("#password").fill("Local-mock-only-password");
        await page.getByRole("button", { name: "Sign in", exact: true }).click();
        await page.locator("#main-content").getByRole("heading", { name: "Web Intelligence", exact: true }).waitFor();
        assert.equal(new URL(page.url()).pathname, "/dashboard");
      } else if (pathname === "/dashboard") {
        const auditResponse = initialApiCalls.some(path => path.endsWith("/audit-trail"))
          ? Promise.resolve()
          : page.waitForResponse(response => response.url().includes("/audit-trail"));
        await page.getByRole("tab", { name: /Audit Trail/ }).click();
        await auditResponse;
        await page.getByRole("tab", { name: "Verdict & Compliance" }).click();
        await page.getByPlaceholder(/Describe a decision/).fill("Test action");
      } else if (pathname === "/chat") {
        for (let i = 1; i <= 2; i++) {
          await page.locator("textarea").fill(`Test question ${i}`);
          await page.locator("textarea").press("Enter");
          await page.getByLabel("Iroko answer", { exact: true }).filter({ hasText: `Verified test answer ${i}.` }).waitFor();
        }
        await page.getByRole("button", { name: /Show earlier messages/ }).click();
        assert.equal(await page.getByLabel("Iroko answer", { exact: true }).count(), 2);
        assert.equal(chatTurns, 2);
      }
      assert.deepEqual(errors, [], `${pathname}: browser errors`);
      console.log(JSON.stringify({ pathname, width, ...metrics, initialApiCalls, smoke: "passed" }));
      await context.close();
    }
  } finally {
    await browser.close();
  }
}
main().catch(error => { console.error(error); process.exitCode = 1; });
