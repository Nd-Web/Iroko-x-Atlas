const { test } = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");
const ts = require("typescript");

function load(file, overrides = {}) {
  const module = { exports: {} };
  const source = ts.transpileModule(fs.readFileSync(path.join(__dirname, "..", file), "utf8"), {
    compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 },
  }).outputText;
  vm.runInNewContext(source, {
    module, exports: module.exports, Response, AbortSignal, AbortController, ReadableStream,
    TextEncoder, TextDecoder, setTimeout, clearTimeout, ...overrides,
    require(name) {
      if (name === "./stream") return load("lib/stream.ts");
      if (name === "@/lib/config") return { API_BASE: "https://backend.invalid" };
      throw new Error(`Unexpected dependency ${name}`);
    },
  });
  return module.exports;
}
const { readStream } = load("lib/stream.ts");
const sse = (body) => new Response(body, { headers: { "content-type": "text/event-stream" } });
const collect = async (response) => {
  const events = [];
  for await (const event of readStream(response)) events.push(event);
  return events;
};

test("SSE comments and empty data do not terminate the stream", async () => {
  const events = await collect(sse(': keep-alive\n\ndata:\n\ndata:{"type":"complete","answer":"OK"}\n\n'));
  assert.equal(events.length, 1);
  assert.equal(events[0].answer, "OK");
});
test("final SSE event without a newline is retained", async () => {
  const events = await collect(sse('data: {"type":"complete","answer":"OK"}'));
  assert.equal(events[0].type, "complete");
});
test("multiline data, CRLF, fragmented UTF-8, and NDJSON are supported", async () => {
  const bytes = new TextEncoder().encode(': ping\r\ndata: {"type":"token",\r\ndata: "content":"₦500"}\r\n\r\n{"type":"complete","answer":"₦500"}');
  let index = 0;
  const events = await collect(new Response(new ReadableStream({
    pull(controller) {
      if (index < bytes.length) controller.enqueue(bytes.slice(index, ++index));
      else controller.close();
    },
  })));
  assert.equal(events[0].content, "₦500");
  assert.equal(events[1].answer, "₦500");
});
test("DONE cancels the reader and malformed data is not silently ignored", async () => {
  let cancelled = false;
  const response = sse(new ReadableStream({
    start(c) { c.enqueue(new TextEncoder().encode('data: [DONE]\n\n')); },
    cancel() { cancelled = true; },
  }));
  assert.equal((await collect(response)).length, 0);
  assert.equal(cancelled, true);
  await assert.rejects(() => collect(sse("data: {broken}\n\n")), /unreadable/);
});

function client(fetch) { return load("lib/chat-stream.ts", { fetch }).streamChat; }
const signal = () => new AbortController().signal;
test("one submission makes one request and returns the saved conversation", async () => {
  let calls = 0;
  const events = [];
  const result = await client(async (_, options) => {
    calls++;
    assert.equal(JSON.parse(options.body).conversation_id, "conversation-1");
    return sse('data: {"type":"complete","answer":"OK","conversation_id":"conversation-1"}\n\n');
  })({ query: "Question", conversation_id: "conversation-1" }, signal(), e => events.push(e));
  assert.equal(calls, 1);
  assert.equal(result.conversation_id, "conversation-1");
  assert.equal(events.length, 1);
});
test("model failures and truncated streams become visible errors", async () => {
  await assert.rejects(() => client(async () => sse('data: {"type":"error","message":"Model unavailable"}\n\n'))(
    { query: "Question" }, signal(), () => {}), /Model unavailable/);
  await assert.rejects(() => client(async () => sse('data: {"type":"token","content":"partial"}\n\n'))(
    { query: "Question" }, signal(), () => {}), /before the answer was complete/);
});
test("HTTP failures are not retried and never display HTML", async () => {
  let calls = 0;
  await assert.rejects(() => client(async () => {
    calls++;
    return new Response("<h1>private gateway diagnostics</h1>", { status: 502 });
  })({ query: "Question" }, signal(), () => {}), /unavailable/);
  assert.equal(calls, 1);
});
test("session expiry retains its status for the session-expired handler", async () => {
  await assert.rejects(() => client(async () => Response.json({ error: "Sign in again" }, { status: 401 }))(
    { query: "Question" }, signal(), () => {}), err => err.status === 401);
});
test("successful HTML responses are rejected instead of empty answers", async () => {
  await assert.rejects(() => client(async () => new Response("<html>Login</html>"))(
    { query: "Question" }, signal(), () => {}), /invalid response/);
});

function proxy(fetch) { return load("lib/chat-proxy.ts", { fetch }).proxyChat; }
const request = (body = { query: "Question", conversation_id: "conversation-1" }) => new Request("https://site.invalid/chat", {
  method: "POST", body: JSON.stringify(body),
});
test("proxy requires the cookie and validates input without calling the backend", async () => {
  const handler = proxy(() => assert.fail("Unexpected model request"));
  assert.equal((await handler(request())).status, 401);
  for (const body of [null, {}, { query: " " }, { query: "x".repeat(2001) }, { query: "Q", conversation_id: 5 }]) {
    assert.equal((await handler(request(body), "test-token")).status, 400);
  }
});
test("proxy pipes SSE with cookie auth and private no-store headers", async () => {
  const response = await proxy(async (url, options) => {
    assert.equal(url, "https://backend.invalid/api/atlas/ask/stream-http");
    assert.equal(options.headers.Authorization, "Bearer test-token");
    assert.equal(options.cache, "no-store");
    assert.equal(options.redirect, "error");
    return sse('data: {"type":"complete","answer":"OK"}\n\n');
  })(request(), "test-token");
  assert.equal(response.status, 200);
  assert.match(response.headers.get("cache-control"), /private, no-store/);
  assert.equal((await collect(response))[0].answer, "OK");
});
test("proxy bounds outages without raw upstream details or automatic retries", async () => {
  for (const status of [401, 403, 429, 422, 500, 502, 503]) {
    let calls = 0;
    const response = await proxy(async () => {
      calls++;
      return new Response("<h1>private SQL or proxy diagnostics</h1>", { status });
    })(request(), "test-token");
    assert.equal(calls, 1);
    assert.doesNotMatch(await response.text(), /private SQL|<h1>/);
  }
  const response = await proxy(async () => { throw new Error("DNS failed"); })(request(), "test-token");
  assert.equal(response.status, 503);
});
test("interrupted upstream bodies become SSE errors rather than silent closures", async () => {
  let reads = 0;
  const response = await proxy(async () => sse(new ReadableStream({
    pull(c) {
      if (++reads === 1) c.enqueue(new TextEncoder().encode('data: {"type":"start"}\n\n'));
      else c.error(new Error("private network error"));
    },
  })))(request(), "test-token");
  const events = await collect(response);
  assert.equal(events.at(-1).type, "error");
  assert.doesNotMatch(events.at(-1).message, /private/);
});
test("closing the browser stream cancels the upstream model request", async () => {
  let upstreamSignal;
  let cancelled = false;
  const response = await proxy(async (_, options) => {
    upstreamSignal = options.signal;
    return sse(new ReadableStream({ cancel() { cancelled = true; } }));
  })(request(), "test-token");
  await response.body.cancel();
  assert.equal(upstreamSignal.aborted, true);
  assert.equal(cancelled, true);
});
