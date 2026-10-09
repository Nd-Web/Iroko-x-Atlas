const { test } = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");
const ts = require("typescript");

function load(relative, globals = {}) {
  const subjectModule = { exports: {} };
  const source = ts.transpileModule(fs.readFileSync(path.join(__dirname, "..", relative), "utf8"), {
    compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022, jsx: ts.JsxEmit.ReactJSX },
  }).outputText;
  vm.runInNewContext(source, { module: subjectModule, exports: subjectModule.exports, ...globals });
  return subjectModule.exports;
}
const { createChatMessageAdapter } = load("lib/chat-presentation.ts");
const { previousQuestions } = load("lib/chat-ux.ts");
const { pilotDayKey, groupPilotSlots } = load("lib/pilot-calendar.ts");

test("calendar groups by WAT, including UTC midnight and year boundaries", () => {
  assert.equal(pilotDayKey("2026-10-12T22:59:00Z"), "2026-10-12");
  assert.equal(pilotDayKey("2026-10-12T23:00:00Z"), "2026-10-13");
  assert.equal(pilotDayKey("2026-12-31T23:30:00Z"), "2027-01-01");
  assert.equal(pilotDayKey("2026-10-13T00:00:00+01:00"), "2026-10-13");
});

test("slot grouping preserves order and never mutates availability", () => {
  const slots = Object.freeze(["2026-10-12T08:00:00Z", "2026-10-12T08:30:00Z", "2026-10-13T08:00:00Z"]);
  const days = groupPilotSlots(slots);
  assert.equal(days.length, 2);
  assert.equal(days[0][0], "2026-10-12");
  assert.deepEqual(Array.from(days[0][1]), slots.slice(0, 2));
  assert.equal(days[1][1][0], slots[2]);
  assert.equal(groupPilotSlots([]).length, 0);
  days[0][1].push("changed locally");
  assert.equal(groupPilotSlots(slots)[0][1].length, 2);
});

test("availability formatting creates one formatter across repeated refreshes", () => {
  let constructions = 0;
  const calendar = load("lib/pilot-calendar.ts", { Intl: { DateTimeFormat: function (...args) {
    constructions++;
    return new Intl.DateTimeFormat(...args);
  } } });
  for (let i = 0; i < 3; i++) calendar.groupPilotSlots(Array(480).fill("2026-10-12T08:00:00Z"));
  assert.equal(constructions, 1);
});

const message = () => ({ id: "answer-1", role: "assistant", content: "Supported answer", timestamp: "2026-10-09T00:00:00Z" });

test("unchanged messages retain identity across stream updates", () => {
  const adapt = createChatMessageAdapter();
  const oldMessage = message();
  const first = adapt(oldMessage);
  for (let i = 0; i < 100; i++) {
    adapt({ ...message(), id: "streaming-answer", content: `Token ${i}` });
    assert.equal(adapt(oldMessage), first);
  }
});

test("message updates refresh citations, traces, feedback and interruption state", () => {
  const adapt = createChatMessageAdapter();
  const initial = message();
  const before = adapt(initial);
  const updated = { ...initial, content: "Final answer", answer_status: "verified", interrupted: true,
    feedback: { helpful: false }, citations: [{ document_id: "doc-1", document_title: "Policy", source: "fallback", excerpt: "Clause", source_url: "https://example.test/policy" }],
    trace: [{ agent: "Researcher", description: "Checked evidence", timestamp: initial.timestamp }],
  };
  const result = adapt(updated);
  assert.notEqual(result, before);
  assert.equal(result.content, "Final answer");
  assert.equal(result.citations[0].document_title, "Policy");
  assert.equal(result.citations[0].source_url, "https://example.test/policy");
  assert.equal(result.reasoning_steps[0].message, "Checked evidence");
  assert.equal(result.reasoning_steps[0].status, "done");
  assert.equal(result.feedback.helpful, false);
  assert.equal(result.interrupted, true);
  assert.equal(before.content, "Supported answer");
});

test("same IDs cannot return stale content from a different object or workspace", () => {
  const adapt = createChatMessageAdapter();
  const a = message();
  const b = { ...a, content: "Different record" };
  assert.notEqual(adapt(a), adapt(b));
  assert.equal(adapt(b).content, "Different record");
  assert.notEqual(adapt(a), createChatMessageAdapter()(a));
});

test("question lookup preserves preceding-question semantics for exports", () => {
  const questions = previousQuestions([
    { id: "intro", role: "assistant", content: "Hi" },
    { id: "q1", role: "user", content: "First question" },
    { id: "a1", role: "assistant", content: "First answer" },
    { id: "q2", role: "user", content: "Follow-up" },
    { id: "a2", role: "assistant", content: "Second answer" },
  ]);
  assert.equal(questions.get("intro"), undefined);
  assert.equal(questions.get("q1"), undefined);
  assert.equal(questions.get("a1"), "First question");
  assert.equal(questions.get("q2"), "First question");
  assert.equal(questions.get("a2"), "Follow-up");
  assert.equal(previousQuestions([]).size, 0);
});

test("long chat histories are scanned linearly instead of once per message", () => {
  let reads = 0;
  const messages = Array.from({ length: 2000 }, (_, i) => ({
    id: String(i), content: String(i), get role() { reads++; return i % 2 ? "assistant" : "user"; },
  }));
  const questions = previousQuestions(messages);
  assert.equal(questions.get("1999"), "1998");
  assert.equal(reads, messages.length);
});

for (const handler of ["onMouseEnter", "onFocus", "onTouchStart"]) {
  test(`sidebar prefetch waits for ${handler} and preserves the consumer handler`, () => {
    let active = false;
    let calls = 0;
    const { default: IntentLink } = load("components/ui/IntentLink.tsx", { require(name) {
      if (name === "react") return { useState: () => [active, next => { active = next; }] };
      if (name === "next/link") return { default: "link" };
      if (name === "react/jsx-runtime") return { jsx: (type, props) => ({ type, props }) };
      throw new Error(`Unexpected module ${name}`);
    } });
    const props = { href: "/documents", [handler]: () => { calls++; } };
    const before = IntentLink(props);
    assert.equal(before.props.prefetch, false);
    before.props[handler]({});
    assert.equal(IntentLink(props).props.prefetch, null);
    assert.equal(calls, 1);
  });
}
