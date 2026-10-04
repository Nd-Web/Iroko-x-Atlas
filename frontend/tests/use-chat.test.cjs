const { test } = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");
const ts = require("typescript");

// Minimal hook runner: ref/state lifetimes persist across explicit renders.
// Network behavior is separately exercised by chat-stream.test.cjs.
function harness(streamChat) {
  const slots = [];
  let index = 0;
  let expiries = 0;
  const react = {
    useState(initial) {
      const slot = index++;
      if (!(slot in slots)) slots[slot] = initial;
      return [slots[slot], next => { slots[slot] = typeof next === "function" ? next(slots[slot]) : next; }];
    },
    useRef(initial) {
      const slot = index++;
      if (!(slot in slots)) slots[slot] = { current: initial };
      return slots[slot];
    },
    useCallback: callback => callback,
    useEffect() {},
  };
  const source = ts.transpileModule(fs.readFileSync(path.join(__dirname, "../hooks/useChat.ts"), "utf8"), {
    compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 },
  }).outputText;
  const module = { exports: {} };
  vm.runInNewContext(source, {
    module, exports: module.exports, AbortController, Error, console,
    sessionStorage: { removeItem() {} },
    require(name) {
      if (name === "react") return react;
      if (name === "@/context/AuthContext") return { useAuth: () => ({ triggerSessionExpiry() { expiries++; } }) };
      if (name === "@/lib/chat-stream") return { streamChat };
      throw new Error(`Unexpected module: ${name}`);
    },
  });
  return {
    render() { index = 0; return module.exports.useChat(); },
    expiries: () => expiries,
  };
}
const complete = { type: "complete", answer: "Verified reply", conversation_id: "conversation-1", agent_trace: [], citations: [] };

test("rapid double-click sends only one model request", async () => {
  let calls = 0;
  let resolve;
  const state = harness(() => { calls++; return new Promise(done => { resolve = done; }); });
  const chat = state.render();
  const first = chat.sendMessage("Question");
  await chat.sendMessage("Question");
  assert.equal(calls, 1);
  resolve(complete);
  await first;
  const final = state.render();
  assert.equal(final.isLoading, false);
  assert.equal(final.messages.length, 2);
  assert.equal(final.messages[1].content, "Verified reply");
});
test("follow-up reuses the conversation returned by the first stream", async () => {
  const requests = [];
  const state = harness(async body => { requests.push(body); return complete; });
  await state.render().sendMessage("Question");
  await state.render().sendMessage("Follow-up");
  assert.equal(requests[1].conversation_id, "conversation-1");
});
test("clear chat prevents a late completion from restoring old replies", async () => {
  let resolve;
  const state = harness(() => new Promise(done => { resolve = done; }));
  const chat = state.render();
  const work = chat.sendMessage("Question");
  chat.clearChat();
  resolve(complete);
  await work;
  assert.equal(state.render().messages.length, 0);
  assert.equal(state.render().conversationId, null);
});
test("failed requests remove empty replies and show an error", async () => {
  const state = harness(async () => { throw new Error("Model unavailable"); });
  await state.render().sendMessage("Question");
  const final = state.render();
  assert.equal(final.error, "Model unavailable");
  assert.equal(final.isLoading, false);
  assert.equal(final.messages.length, 1);
});
test("401 errors trigger global session expiry", async () => {
  const state = harness(async () => { throw { status: 401 }; });
  await state.render().sendMessage("Question");
  assert.equal(state.expiries(), 1);
});
