const { test } = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");
const ts = require("typescript");

function load(file, requireStub) {
  const source = fs.readFileSync(path.join(__dirname, file), "utf8");
  const compiled = ts.transpileModule(source, { compilerOptions: {
    module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022,
  } }).outputText;
  const sandboxModule = { exports: {} };
  vm.runInNewContext(compiled, {
    module: sandboxModule, exports: sandboxModule.exports, Response, Request, URL, setTimeout, Promise,
    fetch: () => assert.fail("Unexpected fetch"), require: requireStub,
  });
  return sandboxModule.exports;
}

const { createLiveCall, describeVerdict } = load("../lib/live-call.ts", (name) => {
  throw new Error(`Unexpected dependency: ${name}`);
});

const VERDICT = { verdict: "NO-GO", regulation: "NDPA 2023 s25", reasoning: "No lawful basis for sharing.",
  flags: ["consent"], confidence: 0.9, checked_at: "2026-10-08T00:00:00Z" };

// A fake clock: sleep advances time, so pause detection runs instantly.
function harness(overrides = {}) {
  let clock = 1_000_000;
  const sent = [];
  const questions = [];
  const call = createLiveCall({
    send: (event) => sent.push(event),
    check: async (q) => { questions.push(q); return VERDICT; },
    greeting: "Iroko compliance check ready.",
    now: () => clock,
    sleep: async (ms) => { clock += ms; },
    ...overrides,
  });
  return { call, sent, questions, advance: (ms) => { clock += ms; } };
}

const delta = (text) => ({ type: "session.input_transcript.delta", delta: text });
const delegation = (id, target = "client") => ({ type: "session.delegation.created", delegation: { id, type: "delegation", target } });

test("greets as general commentary when the session starts", () => {
  const { call, sent } = harness();
  call.handle({ type: "session.started" });
  assert.equal(sent.length, 1);
  assert.equal(sent[0].type, "session.commentary.append");
  assert.equal(sent[0].delegation_id, null);
  assert.match(sent[0].content, /Iroko compliance check ready\./);
});

test("a delegation is answered with the verdict, tied to its id", async () => {
  const { call, sent, questions, advance } = harness();
  call.handle(delta("Can we share BVN records with a marketing partner without consent?"));
  advance(2000);
  await call.handle(delegation("item_1"));
  assert.deepEqual(questions, ["Can we share BVN records with a marketing partner without consent?"]);
  assert.equal(sent.at(-1).type, "session.commentary.append");
  assert.equal(sent.at(-1).delegation_id, "item_1");
  assert.match(sent.at(-1).content, /Verdict: NO-GO\. Regulation: NDPA 2023 s25\./);
});

test("an early delegation waits for the caller to finish the question", async () => {
  // GPT-Live delegated after "Please check this for me" in a live test; the rest came later.
  let clock = 0;
  const words = [" Can our bank share", " customer BVN records", " without consent?"];
  const questions = [];
  const call = createLiveCall({
    send: () => {},
    check: async (q) => { questions.push(q); return VERDICT; },
    now: () => clock,
    sleep: async (ms) => {
      clock += ms;
      if (words.length && clock % 600 === 0) call.handle(delta(words.shift()));
    },
  });
  call.handle(delta("Please check this for me."));
  await call.handle(delegation("item_early"));
  assert.deepEqual(questions, ["Please check this for me. Can our bank share customer BVN records without consent?"]);
});

test("a repeat delegation with nothing new said reuses the last check", async () => {
  const { call, sent, questions, advance } = harness();
  call.handle(delta("Is a 15 percent liquidity ratio compliant?"));
  advance(2000);
  await Promise.all([call.handle(delegation("item_a")), call.handle(delegation("item_b"))]);
  assert.equal(questions.length, 1);
  assert.deepEqual(sent.map((e) => e.delegation_id), ["item_a", "item_b"]);
  assert.equal(sent[0].content, sent[1].content);
});

test("a new question after a check runs a new check", async () => {
  const { call, questions, advance } = harness();
  call.handle(delta("First question?"));
  advance(2000);
  await call.handle(delegation("item_1"));
  call.handle(delta("Second question?"));
  advance(2000);
  await call.handle(delegation("item_2"));
  assert.deepEqual(questions, ["First question?", "Second question?"]);
});

test("a failed check tells the agent not to answer from memory", async () => {
  const { call, sent, advance } = harness({ check: async () => { throw new Error("Compliance check failed (503)"); } });
  call.handle(delta("Can we skip KYC for small accounts?"));
  advance(2000);
  await call.handle(delegation("item_x"));
  assert.match(sent.at(-1).content, /could not complete this check \(Compliance check failed \(503\)\)/);
  assert.match(sent.at(-1).content, /Do not give a verdict from memory/);
});

test("ignores delegations meant for the Responses backend", async () => {
  const { call, sent } = harness();
  await call.handle(delegation("item_r", "responses"));
  assert.equal(sent.length, 0);
});

test("reports when the session closes", () => {
  const reasons = [];
  const { call } = harness({ onClosed: (reason) => reasons.push(reason) });
  call.handle({ type: "session.closed", reason: "close_requested" });
  assert.deepEqual(reasons, ["close_requested"]);
});

test("verdict text names the source document and its rule", () => {
  const text = describeVerdict({ ...VERDICT, source: "Prohibition of Placement in Funds Managed by Uninsured Entities",
    evidence: "All OFIs are required to immediately divest." });
  assert.match(text, /Source document: Prohibition of Placement in Funds Managed by Uninsured Entities\./);
  assert.match(text, /Rule as written: "All OFIs are required to immediately divest\."/);
});

test("verdict text stays inside the commentary size limit", () => {
  const text = describeVerdict({ ...VERDICT, reasoning: "x".repeat(5000) });
  assert.ok(text.length <= 1500);
  assert.match(text, /^Iroko compliance engine result\. Verdict: NO-GO\./);
});

const route = (token, fetch) => {
  const source = fs.readFileSync(path.join(__dirname, "../app/api/voice/live-session/route.ts"), "utf8");
  const compiled = ts.transpileModule(source, { compilerOptions: {
    module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022,
  } }).outputText;
  const sandboxModule = { exports: {} };
  vm.runInNewContext(compiled, {
    module: sandboxModule, exports: sandboxModule.exports, Response, Request, URL, fetch,
    require(name) {
      if (name === "next/headers") return { cookies: async () => ({ get: () => token ? { value: token } : undefined }) };
      if (name === "@/lib/config") return { API_BASE: "https://backend.invalid", COOKIE_NAME: "session" };
      throw new Error(`Unexpected dependency: ${name}`);
    },
  });
  return sandboxModule.exports.POST;
};
const offer = () => new Request("https://iroko.invalid/api/voice/live-session", {
  method: "POST", body: JSON.stringify({ sdp: "v=0\r\n" }) });

test("live-session proxy: signed-out callers never reach the backend", async () => {
  const response = await route(null, () => assert.fail("Unexpected fetch"))(offer());
  assert.equal(response.status, 401);
});

test("live-session proxy: forwards the offer with the session token", async () => {
  const response = await route("tok", async (url, options) => {
    assert.equal(url, "https://backend.invalid/api/voice/live-session");
    assert.equal(options.headers.Authorization, "Bearer tok");
    assert.deepEqual(JSON.parse(options.body), { sdp: "v=0\r\n" });
    return Response.json({ sdp: "v=0 answer", session_id: "live_1", greeting: "hi" }, { status: 200 });
  })(offer());
  assert.equal(response.status, 200);
  assert.equal((await response.json()).session_id, "live_1");
});

test("live-session proxy: passes the backend's reason through", async () => {
  const response = await route("tok", async () => Response.json(
    { detail: "Cannot reach the voice service at example.openai.azure.com (ConnectError)." }, { status: 502 }))(offer());
  assert.equal(response.status, 502);
  assert.match((await response.json()).error, /Cannot reach the voice service/);
});
