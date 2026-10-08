"""Build a self-contained review page for evaluation runs (a "data viewer").

Reviewing answers is the highest-value evaluation activity, and a viewer that shows all
context in one place with one-click verdicts makes it many times faster than a spreadsheet.
The page shows each question (or whole conversation), the answer, the cited excerpts, what
the pipeline did, and Pass / Fail buttons with notes. Keys: J/K next/previous, P pass, F fail,
N notes. Verdicts stay in the browser and export as JSON; those labels are what an automated
judge must later agree with.

Run from backend:
  python scripts/build_review_viewer.py ../.dist/rag-evaluation/nano-*/results.json \
      ../.dist/rag-evaluation/conversations-*.json
Writes .dist/review/review-<time>.html. Open it in any browser; nothing is uploaded.
"""

import glob
import html
import json
import sys
from datetime import datetime
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))
sys.path.insert(0, str(Path(__file__).resolve().parent))
OUT = BACKEND.parent / ".dist" / "review"


def answer_items(records, run):
    from review_eval_traces import failure_modes, pipeline_facts

    for record in records:
        result = record.get("result", {})
        yield {
            "id": f"{run}:{record['case_id']}", "run": run, "kind": "question", "title": record["question"],
            "expected": record.get("expected", ""),
            "automatic": failure_modes(pipeline_facts(record)),
            "turns": [{"user": record["question"], "answer": result.get("answer", record.get("error_type", "")),
                       "status": result.get("answer_status"),
                       "citations": [{"title": c.get("document_title", ""), "excerpt": c.get("excerpt", "")}
                                     for c in result.get("citations", [])]}],
        }


def conversation_items(report, run):
    for record in report["records"]:
        yield {
            "id": f"{run}:{record['id']}", "run": run, "kind": record["category"],
            "title": " → ".join(t["user"] for t in record["turns"]), "expected": "",
            "automatic": record["first_failure"]["failures"] if record["first_failure"] else [],
            "turns": [{"user": t["user"], "answer": t["answer"], "status": t["status"],
                       "intent": t.get("intent"), "resolved_question": t.get("resolved_question"),
                       "citations": [{"title": title, "excerpt": ""} for title in t["citations"]]}
                      for t in record["turns"]],
        }


def load(paths):
    items = []
    for pattern in paths:
        for path in sorted(glob.glob(pattern)):
            data = json.loads(Path(path).read_text(encoding="utf-8"))
            run = Path(path).parent.name if Path(path).name == "results.json" else Path(path).stem
            items.extend(conversation_items(data, run) if isinstance(data, dict) else answer_items(data, run))
    return items


PAGE = """<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1"><title>Iroko answer review</title>
<style>
:root{--bg:#f7f7f5;--card:#fff;--ink:#1d1d1b;--muted:#6b6b66;--line:#e2e2dc;--pass:#1f7a3f;--fail:#b3261e;--accent:#2b5fd9}
@media (prefers-color-scheme:dark){:root{--bg:#141413;--card:#1e1e1c;--ink:#ecece8;--muted:#a3a39c;--line:#34342f;--pass:#5cc285;--fail:#f08a7f;--accent:#8fb0ff}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:15px/1.55 system-ui,sans-serif}
header{position:sticky;top:0;background:var(--card);border-bottom:1px solid var(--line);padding:10px 16px;display:flex;flex-wrap:wrap;gap:8px;align-items:center;z-index:1}
header b{margin-right:auto}select,input,button,textarea{font:inherit;color:inherit;background:var(--card);border:1px solid var(--line);border-radius:8px;padding:6px 10px}
button{cursor:pointer}button:focus-visible,select:focus-visible,input:focus-visible,textarea:focus-visible{outline:2px solid var(--accent);outline-offset:1px}
main{max-width:920px;margin:0 auto;padding:16px}.card{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:16px;margin-bottom:12px}
.muted{color:var(--muted);font-size:13px}.turn{border-top:1px solid var(--line);padding-top:12px;margin-top:12px}.turn:first-of-type{border-top:0;margin-top:0;padding-top:0}
.user{font-weight:600}.answer{white-space:pre-wrap;margin:8px 0}.cite{font-size:13px;border-left:3px solid var(--line);padding-left:8px;margin:6px 0}
.tag{display:inline-block;font-size:12px;border:1px solid var(--line);border-radius:999px;padding:1px 8px;margin:2px 4px 2px 0}
.verdict{display:flex;gap:8px;flex-wrap:wrap;align-items:center}.pass[aria-pressed=true]{background:var(--pass);color:#fff;border-color:var(--pass)}
.fail[aria-pressed=true]{background:var(--fail);color:#fff;border-color:var(--fail)}textarea{width:100%;min-height:72px;margin-top:8px}
</style></head><body>
<header><b>Iroko answer review</b><span id="progress" class="muted"></span>
<select id="filter" aria-label="Show"><option value="all">All</option><option value="unreviewed">Unreviewed</option>
<option value="flagged">Automatic checks flagged</option><option value="failed">Marked fail</option></select>
<input id="search" type="search" placeholder="Search" aria-label="Search questions and answers">
<button id="prev" title="Previous (K)">← Prev</button><button id="next" title="Next (J)">Next →</button>
<button id="export">Export verdicts</button></header>
<main id="main"></main>
<script>
const ITEMS = __DATA__;
const KEY = "iroko-review:" + __STAMP__;
let labels = {}; try { labels = JSON.parse(localStorage.getItem(KEY) || "{}"); } catch (e) {}
const save = () => { try { localStorage.setItem(KEY, JSON.stringify(labels)); } catch (e) {} };
let index = 0; const $ = id => document.getElementById(id);
const esc = s => String(s ?? "").replace(/[&<>"]/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]));
// Show answers as the chat does: bold markers become bold (applied after escaping).
const md = s => esc(s).replace(/\\*\\*(.+?)\\*\\*/g, "<b>$1</b>");
function visible() {
  const f = $("filter").value, q = $("search").value.toLowerCase();
  return ITEMS.filter(it => (f === "all" || (f === "unreviewed" && !labels[it.id]?.verdict) ||
    (f === "flagged" && it.automatic.length) || (f === "failed" && labels[it.id]?.verdict === "fail")) &&
    (!q || JSON.stringify(it).toLowerCase().includes(q)));
}
function render() {
  const list = visible(); index = Math.max(0, Math.min(index, list.length - 1));
  const done = ITEMS.filter(it => labels[it.id]?.verdict).length;
  $("progress").textContent = `${done}/${ITEMS.length} reviewed · showing ${list.length ? index + 1 : 0} of ${list.length}`;
  const it = list[index];
  if (!it) { $("main").innerHTML = '<div class="card">Nothing matches this filter.</div>'; return; }
  const label = labels[it.id] || {};
  $("main").innerHTML = `<div class="card"><div class="muted">${esc(it.run)} · ${esc(it.kind)}</div>
    ${it.expected ? `<p><b>Expected:</b> ${esc(it.expected)}</p>` : ""}
    ${it.automatic.length ? `<p>${it.automatic.map(a => `<span class="tag">${esc(a)}</span>`).join("")}</p>` : ""}
    ${it.turns.map(t => `<section class="turn"><div class="user">${esc(t.user)}</div>
      <div class="muted">${t.intent ? "intent: " + esc(t.intent) + " · " : ""}status: ${esc(t.status)}${t.resolved_question && t.resolved_question !== t.user ? " · searched as: " + esc(t.resolved_question) : ""}</div>
      <div class="answer">${md(t.answer)}</div>
      ${t.citations.map(c => `<div class="cite"><b>${esc(c.title)}</b>${c.excerpt ? "<br>" + esc(c.excerpt) : ""}</div>`).join("")}
    </section>`).join("")}</div>
    <div class="card"><div class="verdict"><span>Is this answer right?</span>
      <button class="pass" aria-pressed="${label.verdict === "pass"}" onclick="setVerdict('pass')">Pass (P)</button>
      <button class="fail" aria-pressed="${label.verdict === "fail"}" onclick="setVerdict('fail')">Fail (F)</button></div>
      <label class="muted" for="notes">What went wrong, in plain words (open coding):</label>
      <textarea id="notes" oninput="setNotes(this.value)">${esc(label.notes || "")}</textarea></div>`;
}
function current() { return visible()[index]; }
function setVerdict(v) { const it = current(); if (!it) return; labels[it.id] = {...labels[it.id], verdict: v}; save(); render(); }
function setNotes(v) { const it = current(); if (!it) return; labels[it.id] = {...labels[it.id], notes: v}; save(); }
$("next").onclick = () => { index++; render(); }; $("prev").onclick = () => { index--; render(); };
$("filter").onchange = () => { index = 0; render(); }; $("search").oninput = () => { index = 0; render(); };
$("export").onclick = () => {
  const out = ITEMS.filter(it => labels[it.id]).map(it => ({id: it.id, run: it.run, question: it.title, ...labels[it.id]}));
  const a = document.createElement("a"); a.href = URL.createObjectURL(new Blob([JSON.stringify(out, null, 1)], {type: "application/json"}));
  a.download = "iroko-review-verdicts.json"; a.click();
};
document.addEventListener("keydown", e => {
  if (["TEXTAREA", "INPUT", "SELECT"].includes(e.target.tagName)) { if (e.key === "Escape") e.target.blur(); return; }
  if (e.key === "j") { index++; render(); } else if (e.key === "k") { index--; render(); }
  else if (e.key === "p") setVerdict("pass"); else if (e.key === "f") setVerdict("fail");
  else if (e.key === "n") { e.preventDefault(); $("notes")?.focus(); }
});
render();
</script></body></html>"""


def main(paths):
    if not paths:
        raise SystemExit(__doc__)
    items = load(paths)
    stamp = f"{datetime.now():%Y%m%d-%H%M%S}"
    OUT.mkdir(parents=True, exist_ok=True)
    out = OUT / f"review-{stamp}.html"
    # Escape "</" so answer text can never close the script element.
    data = json.dumps(items, ensure_ascii=False).replace("</", "<\\/")
    out.write_text(PAGE.replace("__DATA__", data).replace("__STAMP__", json.dumps(stamp)), encoding="utf-8")
    print(json.dumps({"items": len(items), "viewer": str(out)}))


if __name__ == "__main__":
    main(sys.argv[1:])
