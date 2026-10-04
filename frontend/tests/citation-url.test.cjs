const { test } = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");
const ts = require("typescript");
const moduleUnderTest = { exports: {} };
const source = ts.transpileModule(fs.readFileSync(path.join(__dirname, "../lib/citation-url.ts"), "utf8"), {
  compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 },
}).outputText;
vm.runInNewContext(source, { module: moduleUnderTest, exports: moduleUnderTest.exports, URL });
const { citationUrl } = moduleUnderTest.exports;

test("official public sources retain their exact HTTPS link", () => {
  assert.equal(citationUrl("https://www.cbn.gov.ng/rules.pdf"), "https://www.cbn.gov.ng/rules.pdf");
  assert.equal(citationUrl("https://ndpc.gov.ng/resources/"), "https://ndpc.gov.ng/resources/");
});
test("forged sources and private/script URLs cannot become citation links", () => {
  for (const value of [null, "", "javascript:alert(1)", "http://cbn.gov.ng/test", "https://127.0.0.1/private", "https://cbn.gov.ng.attacker.invalid/", "https://user:password@cbn.gov.ng/", "https://cbn.gov.ng:8080/test", "/documents"]) {
    assert.equal(citationUrl(value), undefined);
  }
});
