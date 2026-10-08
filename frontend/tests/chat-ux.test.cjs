const { test } = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");
const ts = require("typescript");
const moduleUnderTest = { exports: {} };
const source = ts.transpileModule(fs.readFileSync(path.join(__dirname, "../lib/chat-ux.ts"), "utf8"), {
  compilerOptions: { module: ts.ModuleKind.CommonJS },
}).outputText;
vm.runInNewContext(source, { module: moduleUnderTest, exports: moduleUnderTest.exports });
const { shouldSubmitChat, isNearChatBottom, splitLatestExchange, CHAT_MAX_CHARS } = moduleUnderTest.exports;

test("Enter sends while Shift+Enter and IME composition remain editable", () => {
  const event = { key: "Enter", shiftKey: false, altKey: false, nativeEvent: {} };
  assert.equal(shouldSubmitChat(event), true);
  assert.equal(shouldSubmitChat({ ...event, shiftKey: true }), false);
  assert.equal(shouldSubmitChat({ ...event, altKey: true }), false);
  assert.equal(shouldSubmitChat({ ...event, nativeEvent: { isComposing: true } }), false);
  assert.equal(shouldSubmitChat({ ...event, nativeEvent: { keyCode: 229 } }), false);
  assert.equal(shouldSubmitChat({ ...event, key: "a" }), false);
  assert.equal(CHAT_MAX_CHARS, 2000);
});

test("auto-scroll only follows readers near the latest message", () => {
  assert.equal(isNearChatBottom({ scrollHeight: 1800, scrollTop: 1200, clientHeight: 600 }), true);
  assert.equal(isNearChatBottom({ scrollHeight: 1800, scrollTop: 500, clientHeight: 600 }), false);
});

test("compact view focuses the last question without discarding previous messages", () => {
  const messages = [{ role: "user", id: "q1" }, { role: "assistant", id: "a1" }, { role: "user", id: "q2" }, { role: "assistant", id: "a2" }];
  const view = splitLatestExchange(messages);
  assert.equal(view.previous.length, 2);
  assert.equal(view.current.length, 2);
  assert.equal(view.current[0].id, "q2");
  assert.equal(messages.length, 4);
  assert.equal(splitLatestExchange([]).current.length, 0);
  assert.equal(splitLatestExchange([{ role: "assistant" }]).current.length, 1);
});
