const { test } = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");
const ts = require("typescript");

// Minimal hook runner: ref/state lifetimes persist across explicit renders.
// Network behavior is separately exercised by chat-stream.test.cjs.
function harness(streamChat, fetchMock) {
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
  const hookModule = { exports: {} };
  vm.runInNewContext(source, {
    module: hookModule, exports: hookModule.exports, AbortController, Error, console, fetch: fetchMock,
    sessionStorage: { removeItem() {} },
    require(name) {
      if (name === "react") return react;
      if (name === "@/context/AuthContext") return { useAuth: () => ({ triggerSessionExpiry() { expiries++; } }) };
      if (name === "@/lib/chat-stream") return { streamChat };
      throw new Error(`Unexpected module: ${name}`);
    },
  });
  return {
    render() { index = 0; return hookModule.exports.useChat(); },
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

test("stopping cancels the request and fences late completions", async () => {
  let resolve;
  let signal;
  const state = harness((_body, requestSignal) => {
    signal = requestSignal;
    return new Promise(done => { resolve = done; });
  });
  const work = state.render().sendMessage("Question");
  state.render().stopMessage();
  assert.equal(signal.aborted, true);
  assert.equal(state.render().isLoading, false);
  assert.equal(state.render().messages.length, 1);
  resolve(complete);
  await work;
  assert.equal(state.render().messages.length, 1);
  assert.equal(state.render().error, null);
});

test("stopping preserves visible text but labels it incomplete", async () => {
  let resolve;
  const state = harness((_body, _signal, event) => {
    event({ type: "token", content: "Partial verified text" });
    return new Promise(done => { resolve = done; });
  });
  const work = state.render().sendMessage("Question");
  state.render().stopMessage();
  const stopped = state.render().messages[1];
  assert.equal(stopped.content, "Partial verified text");
  assert.equal(stopped.interrupted, true);
  resolve(complete);
  await work;
  assert.equal(state.render().messages[1].interrupted, true);
});

test("retry does not duplicate an unanswered user question", async () => {
  let calls = 0;
  const state = harness(async () => {
    if (++calls === 1) throw new Error("Temporary failure");
    return complete;
  });
  await state.render().sendMessage("Question");
  await state.render().sendMessage("Question", { retry: true });
  assert.equal(calls, 2);
  assert.equal(state.render().messages.filter(message => message.role === "user").length, 1);
  assert.equal(state.render().messages.length, 2);
});

test("oversized deep-link questions never reach the model", async () => {
  let calls = 0;
  const state = harness(async () => { calls++; return complete; });
  await state.render().sendMessage("x".repeat(2001));
  assert.equal(calls, 0);
  assert.equal(state.render().messages.length, 0);
  assert.match(state.render().error, /2,000/);
});

test("history loading has a distinct state and does not generate an answer", async () => {
  let resolve;
  let modelCalls = 0;
  const state = harness(async () => { modelCalls++; return complete; }, () => new Promise(done => { resolve = done; }));
  const work = state.render().loadConversation("existing");
  assert.equal(state.render().isLoadingHistory, true);
  await state.render().sendMessage("Do not send while loading");
  assert.equal(modelCalls, 0);
  resolve({ ok: true, json: async () => ({ messages: [{ id: 1, role: "assistant", content: "Saved answer" }] }) });
  await work;
  assert.equal(state.render().isLoadingHistory, false);
  assert.equal(state.render().conversationId, "existing");
  assert.equal(state.render().messages[0].content, "Saved answer");
});

test("a saved conversation can be resumed using its id without regenerating history", async () => {
  const requests = [];
  const state = harness(async body => { requests.push(body); return complete; }, async () => ({
    ok: true, json: async () => ({ messages: [
      { id: "saved-q", role: "user", content: "Original question", created_at: "2026-10-04T12:00:00Z" },
      { id: "saved-a", role: "assistant", content: "Original answer", citations: [{ document_id: "source" }], agent_trace: [{ agent: "Researcher" }] },
    ] }),
  }));
  await state.render().loadConversation("saved-id");
  assert.equal(requests.length, 0);
  assert.equal(state.render().messages[1].citations[0].document_id, "source");
  assert.equal(state.render().messages[1].trace[0].agent, "Researcher");
  await state.render().sendMessage("Follow up question");
  assert.equal(requests[0].conversation_id, "saved-id");
  assert.equal(state.render().messages[0].content, "Original question");
});

test("a failed history fetch preserves the current chat and never exposes HTML", async () => {
  const state = harness(async () => complete, async () => ({ ok: false, status: 502, text: async () => "<html>Gateway details</html>" }));
  await state.render().sendMessage("Current question");
  await state.render().loadConversation("unavailable");
  const result = state.render();
  assert.equal(result.conversationId, "conversation-1");
  assert.equal(result.messages.length, 2);
  assert.equal(result.isLoadingHistory, false);
  assert.match(result.error, /could not be loaded/);
  assert.equal(result.error.includes("html"), false);
});

test("late history response cannot overwrite a newer selected conversation", async () => {
  let resolveOld;
  const state = harness(async () => complete, url => url.includes("old-id")
    ? new Promise(resolve => { resolveOld = resolve; })
    : Promise.resolve({ ok: true, json: async () => ({ messages: [{ id: "new-q", role: "user", content: "Newer saved question" }] }) }));
  const old = state.render().loadConversation("old-id");
  await state.render().loadConversation("new-id");
  resolveOld({ ok: true, json: async () => ({ messages: [{ id: "old-q", role: "user", content: "Old saved question" }] }) });
  await old;
  assert.equal(state.render().conversationId, "new-id");
  assert.equal(state.render().messages[0].content, "Newer saved question");
});

test("malformed history is not mistaken for an empty saved conversation", async () => {
  const state = harness(async () => complete, async () => ({ ok: true, json: async () => ({}) }));
  await state.render().loadConversation("saved-id");
  assert.match(state.render().error, /incomplete/);
  assert.equal(state.render().conversationId, null);
});
