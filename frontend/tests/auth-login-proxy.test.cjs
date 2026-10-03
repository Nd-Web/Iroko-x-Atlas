const { test } = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");
const ts = require("typescript");

function compile(file) {
  return ts.transpileModule(fs.readFileSync(path.join(__dirname, "..", file), "utf8"), {
    compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 },
  }).outputText;
}
const helper = compile("lib/auth-login-proxy.ts");
const route = compile("app/api/auth/login/route.ts");
const credentials = { email: "owner@example.com", password: "test-only-password" };
const user = { id: "test-user", email: credentials.email, role: "admin" };
const success = () => Response.json({ access_token: "test-only-token", user });

function proxy(fetch) {
  const sandboxModule = { exports: {} };
  vm.runInNewContext(helper, {
    module: sandboxModule, exports: sandboxModule.exports, Response, AbortSignal, fetch,
    require(name) {
      if (name === "@/lib/config") return { API_BASE: "https://backend.invalid" };
      throw new Error(`Unexpected dependency: ${name}`);
    },
  });
  return sandboxModule.exports.loginToBackend;
}

test("missing credentials are rejected before contacting the backend", async () => {
  const response = await proxy(() => assert.fail("Unexpected fetch"))({});
  assert.equal(response.status, 400);
});

test("HTML gateway failure is retried once and can recover", async () => {
  let calls = 0;
  const result = await proxy(async () => ++calls === 1
    ? new Response("<h1>Gateway unavailable</h1>", { status: 502 }) : success())(credentials);
  assert.equal(result.ok, true);
  assert.equal(calls, 2);
});

test("gateway outage stays a bounded error and never returns upstream HTML", async () => {
  let calls = 0;
  const result = await proxy(async () => {
    calls++;
    return new Response("<h1>private upstream details</h1>", { status: 503 });
  })(credentials);
  assert.equal(result.ok, false);
  assert.equal(result.status, 503);
  assert.equal(calls, 2);
  assert.doesNotMatch(result.error, /private|<h1>/);
});

test("bad credentials are not retried or mislabelled as a backend outage", async () => {
  let calls = 0;
  const result = await proxy(async () => {
    calls++;
    return Response.json({ detail: "Invalid email or password" }, { status: 401 });
  })(credentials);
  assert.equal(calls, 1);
  assert.equal(result.status, 401);
  assert.equal(result.error, "Invalid email or password");
});

test("deactivated accounts and rate limits are never retried", async () => {
  for (const status of [403, 429]) {
    let calls = 0;
    const result = await proxy(async () => {
      calls++;
      return Response.json({ detail: "Access denied" }, { status });
    })(credentials);
    assert.equal(result.status, status);
    assert.equal(calls, 1);
  }
});

test("invalid backend JSON cannot create a successful auth result", async () => {
  const result = await proxy(async () => new Response("{invalid", {
    status: 200, headers: { "content-type": "application/json" },
  }))(credentials);
  assert.equal(result.ok, false);
  assert.equal(result.status, 502);
});

test("a token without a valid user cannot create a successful auth result", async () => {
  const result = await proxy(async () => Response.json({ access_token: "not-a-session", user: null }))(credentials);
  assert.equal(result.ok, false);
  assert.equal(result.status, 502);
});

test("network timeouts stop after two attempts", async () => {
  let calls = 0;
  const result = await proxy(async () => { calls++; throw new Error("timeout"); })(credentials);
  assert.equal(calls, 2);
  assert.equal(result.ok, false);
  assert.equal(result.status, 503);
});

test("a temporary connection error can recover without changing credentials", async () => {
  let calls = 0;
  const result = await proxy(async (url, options) => {
    assert.equal(url, "https://backend.invalid/api/auth/login");
    assert.equal(options.cache, "no-store");
    assert.equal(options.redirect, "error");
    assert.equal(JSON.parse(options.body).password, credentials.password);
    if (++calls === 1) throw new Error("connection reset");
    return success();
  })(credentials);
  assert.equal(result.ok, true);
  assert.equal(calls, 2);
});

test("field validation errors are not presented as wrong credentials", async () => {
  const result = await proxy(async () => Response.json({ detail: [{ msg: "Invalid email" }] }, { status: 422 }))(credentials);
  assert.equal(result.status, 422);
  assert.match(result.error, /fields/);
});

function handler(result, writes) {
  const sandboxModule = { exports: {} };
  vm.runInNewContext(route, {
    module: sandboxModule, exports: sandboxModule.exports, Response, process: { env: { NODE_ENV: "production" } },
    require(name) {
      if (name === "next/headers") return { cookies: async () => ({ set: (...args) => writes.push(args) }) };
      if (name === "@/lib/config") return { COOKIE_NAME: "iroko_token", COOKIE_MAX_AGE: 86400 };
      if (name === "@/lib/auth-login-proxy") return { loginToBackend: async () => result };
      throw new Error(`Unexpected dependency: ${name}`);
    },
  });
  return sandboxModule.exports.POST;
}

test("successful route sets only a secure httpOnly session and never returns its token", async () => {
  const writes = [];
  const response = await handler({ ok: true, data: { access_token: "test-only-token", user } }, writes)(
    new Request("https://site.invalid/api/auth/login", { method: "POST", body: JSON.stringify(credentials) }));
  assert.equal(response.status, 200);
  assert.equal(writes.length, 1);
  assert.equal(writes[0][2].httpOnly, true);
  assert.equal(writes[0][2].secure, true);
  assert.equal(response.headers.get("cache-control"), "private, no-store");
  assert.deepEqual(await response.json(), { user });
});

test("failed route never writes a cookie and includes safe retry guidance", async () => {
  const writes = [];
  const response = await handler({ ok: false, status: 503, error: "Temporary outage" }, writes)(
    new Request("https://site.invalid/api/auth/login", { method: "POST", body: JSON.stringify(credentials) }));
  assert.equal(response.status, 503);
  assert.equal(writes.length, 0);
  assert.equal(response.headers.get("retry-after"), "5");
});
