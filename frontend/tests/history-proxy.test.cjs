const { test } = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");
const ts = require("typescript");

function load(file, dependencies, extras = {}) {
  const module = { exports: {} };
  const source = ts.transpileModule(fs.readFileSync(path.join(__dirname, "..", file), "utf8"), {
    compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 },
  }).outputText;
  vm.runInNewContext(source, { module, exports: module.exports, Response, Error, ...extras, require: name => {
    if (!(name in dependencies)) throw new Error(`Unexpected module: ${name}`);
    return dependencies[name];
  } });
  return module.exports;
}

for (const [file, expectedPath] of [
  ["app/api/atlas/conversations/route.ts", "/api/atlas/conversations"],
  ["app/api/atlas/conversations/[id]/messages/route.ts", "/api/atlas/conversations/saved%20id/messages"],
]) {
  test(`${file}: private history gets a cold-start budget and preserves auth failures`, async () => {
    let result = { data: { messages: [] }, error: null, status: 200 };
    const calls = [];
    const route = load(file, { "@/lib/api-client": { apiRequest: async (...args) => { calls.push(args); return result; } } });
    const response = await route.GET(new Request("http://localhost"), { params: Promise.resolve({ id: "saved id" }) });
    assert.equal(calls[0][0], expectedPath);
    assert.equal(calls[0][1].timeoutMs, 45000);
    assert.equal(response.headers.get("cache-control"), "private, no-store");
    assert.equal(route.maxDuration, 60);
    result = { data: null, error: "Session expired", status: 401 };
    const expired = await route.GET(new Request("http://localhost"), { params: Promise.resolve({ id: "saved id" }) });
    assert.equal(expired.status, 401);
    assert.equal((await expired.json()).error, "Session expired");
  });
}

test("API helper forwards cookie auth and timeout overrides without leaking helper options", async () => {
  let request;
  const helper = load("lib/api-client.ts", {
    "next/headers": { cookies: async () => ({ get: () => ({ value: "fixture-only" }) }) },
    "./config": { API_BASE: "https://backend.example.test", COOKIE_NAME: "iroko_token" },
  }, {
    AbortSignal: { timeout: milliseconds => ({ milliseconds }) },
    fetch: async (url, options) => { request = { url, options }; return Response.json({ conversations: [] }); },
  });
  const result = await helper.apiRequest("/api/atlas/conversations", { timeoutMs: 45000 });
  assert.equal(result.status, 200);
  assert.equal(request.options.signal.milliseconds, 45000);
  assert.equal(request.options.headers.Authorization, "Bearer fixture-only");
  assert.equal(request.options.cache, "no-store");
  assert.equal("timeoutMs" in request.options, false);
  assert.equal("bearerToken" in request.options, false);
});

test("a backend timeout is a retryable gateway timeout, not a successful empty history", async () => {
  const helper = load("lib/api-client.ts", {
    "next/headers": { cookies: async () => ({ get: () => undefined }) },
    "./config": { API_BASE: "https://backend.example.test", COOKIE_NAME: "iroko_token" },
  }, { AbortSignal, fetch: async () => { const error = new Error("timeout"); error.name = "TimeoutError"; throw error; } });
  const result = await helper.apiRequest("/api/atlas/conversations", { timeoutMs: 45000 });
  assert.equal(result.status, 504);
  assert.equal(result.data, null);
  assert.match(result.error, /taking too long/);
});
