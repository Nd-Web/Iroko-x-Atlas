const { test } = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");
const ts = require("typescript");

function load(file) {
  const source = fs.readFileSync(path.join(__dirname, file), "utf8");
  const compiled = ts.transpileModule(source, { compilerOptions: {
    module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022,
  } }).outputText;
  const sandboxModule = { exports: {} };
  vm.runInNewContext(compiled, {
    module: sandboxModule, exports: sandboxModule.exports, URL, WeakMap, Map, Set,
    require: (name) => { throw new Error(`Unexpected dependency: ${name}`); },
  });
  return sandboxModule.exports;
}

const view = load("../lib/compliance-graph-view.ts");
const { recordUrl, citationUrl } = load("../lib/citation-url.ts");
const { createChatMessageAdapter } = load("../lib/chat-presentation.ts");

test("relationship states keep stated, suggested, confirmed and re-review apart", () => {
  assert.equal(view.statusTone({ basis: "stated", review_status: "proposed" }), "info");
  assert.equal(view.statusTone({ basis: "suggested", review_status: "proposed" }), "gray");
  assert.equal(view.statusTone({ basis: "suggested", review_status: "confirmed" }), "success");
  assert.equal(view.statusTone({ basis: "stated", review_status: "needs_re_review" }), "warning");
  assert.equal(view.statusShortLabel({ basis: "suggested", review_status: "proposed" }), "Suggested by Iroko");
  assert.equal(view.statusShortLabel({ basis: "stated", review_status: "proposed" }), "Stated in source");
});

test("gaps in records are never shown as alarms or verdicts", () => {
  for (const state of view.COVERAGE_ORDER) {
    assert.notEqual(view.coverageTone(state), "danger", state);
    assert.equal(view.hasVerdictWording(view.COVERAGE_SHORT[state]), false, state);
  }
  for (const label of Object.values(view.APPLICABILITY_SHORT)) assert.equal(view.hasVerdictWording(label), false, label);
  assert.equal(view.coverageTone("no_control_linked"), "gray");
  assert.equal(view.hasVerdictWording("The bank is non-compliant"), true);
  assert.equal(view.hasVerdictWording("Chief Compliance Officer reviews accounts"), false);
});

test("lane layout is deterministic, keeps lanes and orders by neighbours", () => {
  const nodes = [
    { id: "c:2", lane: 2, label: "Zeta control" },
    { id: "r:1", lane: 1, label: "B requirement" },
    { id: "r:2", lane: 1, label: "A requirement" },
    { id: "i:1", lane: 0, label: "Circular" },
    { id: "c:1", lane: 2, label: "Alpha control" },
  ];
  const edges = [
    { id: "e1", from: "i:1", to: "r:1" }, { id: "e2", from: "i:1", to: "r:2" },
    { id: "e3", from: "c:2", to: "r:2" }, { id: "e4", from: "c:1", to: "r:1" },
  ];
  const first = view.laneLayout(nodes, edges);
  const second = view.laneLayout([...nodes].reverse(), [...edges].reverse());
  assert.deepEqual(first.map((p) => [p.node.id, p.lane, p.row]), second.map((p) => [p.node.id, p.lane, p.row]));
  const place = Object.fromEntries(first.map((p) => [p.node.id, p]));
  assert.equal(place["i:1"].lane, 0);
  assert.equal(place["c:1"].lane, 2);
  // Controls follow the rows of the requirements they connect to.
  assert.equal(place["c:2"].row < place["c:1"].row, place["r:2"].row < place["r:1"].row);
  const pathD = view.connectorPath(place["i:1"], place["r:1"], { laneWidth: 200, cardWidth: 170, rowHeight: 76, cardHeight: 60, top: 36 });
  assert.match(pathD, /^M 170 \d+ C/);
});

test("upload role hints mirror the server's first guess", () => {
  assert.equal(view.roleHint("AML_CFT_Policy_v4.pdf"), "policy");
  assert.equal(view.roleHint("KYC procedure manual.docx"), "procedure");
  assert.equal(view.roleHint("Q1 training attendance register.xlsx"), "evidence_record");
  assert.equal(view.roleHint("CBN circular on BVN.pdf"), "regulation");
  assert.equal(view.roleHint("notes.txt"), null);
});

test("record citations open only inside the Knowledge Graph", () => {
  assert.equal(recordUrl({ source_kind: "iroko_record", record_url: "/knowledge-graph?link=abc123" }), "/knowledge-graph?link=abc123");
  assert.equal(recordUrl({ source_kind: "iroko_record", record_url: "javascript:alert(1)" }), undefined);
  assert.equal(recordUrl({ source_kind: "iroko_record", record_url: "https://evil.example/knowledge-graph" }), undefined);
  assert.equal(recordUrl({ source_kind: "iroko_record", record_url: "//evil.example" }), undefined);
  assert.equal(recordUrl({ source_kind: "official_live", record_url: "/knowledge-graph?link=a" }), undefined);
  assert.equal(citationUrl("/knowledge-graph?link=a"), undefined);
});

test("the chat adapter keeps a citation's provenance", () => {
  const adapt = createChatMessageAdapter();
  const message = { id: "m1", role: "assistant", content: "x", citations: [{
    document_id: "record:ws", document_title: "Iroko compliance record", excerpt: "e", chunk_id: "record:link:1",
    provenance: { source_kind: "iroko_record", record_url: "/knowledge-graph?link=1" },
  }] };
  const [citation] = adapt(message).citations;
  assert.equal(citation.chunk_id, "record:link:1");
  assert.equal(citation.provenance.record_url, "/knowledge-graph?link=1");
});
