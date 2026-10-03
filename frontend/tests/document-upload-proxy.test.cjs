const { test } = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");
const ts = require("typescript");

const source = fs.readFileSync(path.join(__dirname, "../lib/document-upload-proxy.ts"), "utf8");
const compiled = ts.transpileModule(source, { compilerOptions: {
  module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022,
} }).outputText;

function proxy(token, fetch) {
  const sandboxModule = { exports: {} };
  vm.runInNewContext(compiled, {
    module: sandboxModule, exports: sandboxModule.exports, Response, Request, TransformStream, AbortSignal, URL,
    fetch, require(name) {
      if (name === "next/headers") return { cookies: async () => ({ get: () => token ? { value: token } : undefined }) };
      if (name === "@/lib/config") return { API_BASE: "https://backend.invalid", COOKIE_NAME: "session" };
      throw new Error(`Unexpected dependency: ${name}`);
    },
  });
  return sandboxModule.exports.proxyDocumentUpload;
}

function request(extra = {}) {
  return new Request("https://iroko.invalid/api/documents", { method: "POST",
    headers: { "content-type": "multipart/form-data; boundary=test" }, body: "sample", ...extra });
}

test("unauthenticated upload never reaches backend", async () => {
  const response = await proxy(null, () => assert.fail("Unexpected fetch"))(request());
  assert.equal(response.status, 401);
});

test("streamed upload preserves authenticated acceptance and no-store", async () => {
  const response = await proxy("test-token", async (url, options) => {
    assert.equal(url, "https://backend.invalid/api/documents");
    assert.equal(options.headers.Authorization, "Bearer test-token");
    assert.equal(options.cache, "no-store");
    assert.equal(await new Response(options.body).text(), "sample");
    return Response.json({ id: "doc-1", status: "pending" });
  })(request());
  assert.equal(response.status, 200);
  assert.equal((await response.json()).status, "pending");
  assert.equal(response.headers.get("cache-control"), "private, no-store");
});

test("HTML upstream outage becomes a helpful JSON error", async () => {
  const response = await proxy("token", async () => new Response("<h1>Offline</h1>", {
    status: 503, headers: { "content-type": "text/html" },
  }))(request());
  assert.equal(response.status, 502);
  assert.match((await response.json()).error, /Check your document list/);
});

test("quota response retains status and retry guidance", async () => {
  const response = await proxy("token", async () => Response.json({ detail: "Quota reached" }, {
    status: 429, headers: { "retry-after": "3600" },
  }))(request());
  assert.equal(response.status, 429);
  assert.equal(response.headers.get("retry-after"), "3600");
});

test("declared oversized requests are rejected before fetch", async () => {
  const response = await proxy("token", () => assert.fail("Unexpected fetch"))(request({
    headers: { "content-type": "multipart/form-data; boundary=test", "content-length": String(60 * 1024 * 1024) },
  }));
  assert.equal(response.status, 413);
});

test("unknown-length streams cannot bypass the body limit", async () => {
  let chunks = 0;
  const body = new ReadableStream({ pull(controller) {
    if (chunks++ < 53) controller.enqueue(new Uint8Array(1024 * 1024));
    else controller.close();
  } });
  const response = await proxy("token", async (_, options) => {
    for await (const chunk of options.body) assert.ok(chunk.byteLength);
    return Response.json({});
  })(request({ body, duplex: "half" }));
  assert.equal(response.status, 413);
});

test("connection failure never falsely claims the document was rejected", async () => {
  const response = await proxy("token", async () => { throw new Error("offline"); })(request());
  assert.equal(response.status, 503);
  assert.match((await response.json()).detail, /Check your document list/);
});
