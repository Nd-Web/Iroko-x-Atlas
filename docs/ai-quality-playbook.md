# Improving Iroko's answers: the playbook

How we measure and improve Iroko's chat. It follows the practice taught in the leading
courses on AI evaluation and retrieval (sources at the end). We improve the system around
the model (routing, retrieval, prompts, checks, conversation handling), not the model
itself. In short:

1. **Measure** retrieval and answers separately.
2. **Read the failures** and group them into failure modes (error analysis).
3. **Fix the most frequent failure mode**, then measure again.
4. **Collect real users' verdicts** and turn the bad ones into new test cases.

Run every command from `backend/`. The evaluation scripts read the production search
index but write only to an isolated SQLite copy of the CBN corpus, never to production.

## 1. Measure retrieval and answers separately

A wrong answer has two possible causes: search never found the right passage, or the model
misused a passage it was given. They need different fixes, so they are measured apart.

**Retrieval.** `scripts/evaluate_retrieval.py` asks the model to write two questions per
extracted passage: a *specific* one that names the document, and a *natural* one phrased
the way a compliance officer types it. It then checks whether real search returns that
passage.

```
python scripts/evaluate_retrieval.py generate   # rewrite tests/evals/cbn_retrieval_questions.json
python scripts/evaluate_retrieval.py run        # recall@1/3/5/12/20 and MRR
```

On 2026-10-06 (20 CBN documents, 88 passages, 167 questions), the right passage was among
the 12 the model reads **100%** of the time, and the right document ranked first 97% of
the time. Retrieval is not the bottleneck today, so retrieval upgrades (contextual chunk
descriptions, a reranker) can wait. Re-run this whenever the library grows substantially:
recall falls as more documents compete. Read a sample of generated questions after each
`generate`; a question its passage does not answer measures nothing.

**Answers.** `scripts/evaluate_document_answers.py run --modes normal --concurrency 2`
runs 28 graded CBN questions through the real chat pipeline. Its "candidate_pass" check is
a set of regular expressions, so read every failing answer: some are correct answers the
pattern missed. The model's output varies, so compare several runs, never one.

**Conversations.** The 28 questions all name their document; real users do not.
`scripts/evaluate_conversations.py run` plays 24 realistic chats (34 turns) from
`tests/evals/conversation_scenarios.json` through the API turn by turn: natural and vague
phrasing, follow-ups, topic switches, the document library, questions the documents cannot
answer, out-of-scope requests, implications, comparisons and Pidgin. Checks are code, not a
model: the routed intent, required and forbidden text (such as an invented naira figure),
and the documents cited. A failed chat reports its **first** failing turn, because later
failures usually follow from it. Add a scenario whenever a real conversation goes wrong.

## 2. Error analysis: read the traces

`scripts/build_review_viewer.py <results.json or conversations-*.json ...>` writes a
self-contained review page under `.dist/review/`. It shows each question or conversation,
the answer as users see it, the cited excerpts and what the pipeline did, with one-click
Pass / Fail and a notes box (keys: J/K next/previous, P pass, F fail, N notes). Verdicts stay
in the browser and export as JSON. Give this page to the compliance expert: reviewing in a
purpose-built viewer is many times faster than in a spreadsheet, and the first look at it
exposed raw HTML table markup in the sources panel.

`scripts/review_eval_traces.py <results.json ...>` gives the same answers as a CSV, with
the pipeline facts (status, which check dropped a claim, auditor issues) and automatic
failure-mode counts.

- Review about 100 diverse answers. For each failing one, write what went wrong in plain
  words, then group the notes into failure modes and count them.
- Fix the most frequent mode first. Prefer a code check when a rule can decide; use a
  model judge only for judgement calls.
- Repeat every 2–4 weeks, and after any incident.

What error analysis found on 2026-10-06, across the answer and conversation suites:

| Failure mode | Cause | Fix |
|---|---|---|
| Complete questions refused with "which one do you mean?" (8 of 28) | "must **they**" read as a reference to an earlier message | A pronoun points back only when the message names no subject |
| "Reasoning unavailable" under load | Token quota exhausted; retries fired inside the same minute | Wait for Azure's retry hint; output allowances sized to real use |
| True quotes rejected | Markdown `4\.`, stray quotation marks, dashes, `09` vs `9` | Compare by text and by value, never by formatting |
| True claims rejected | One-word misquotes; right words cited to the neighbouring passage | Align near-exact quotes to the verbatim source; re-attribute verbatim quotes |
| Whole audit discarded | Auditor returned one verdict too many | Re-ask the audit alone with the exact count; never guess alignment |
| No direct answer (38%) | Auditor judged completeness, not support; saw a raw "Yes." | Separate support from completeness; audit the text users will see |
| Complete answers marked "partial" | Applicability flagged on every historical answer | List applicability gaps only when the question asks about currency |
| "STR deadline?" sent back for clarification (5 of 24 chats) | Shorthand unknown to the router; the model chose "clarify" | Compliance shorthand routes directly; a question naming its subject is never sent back |
| Wrong document's fines after "Is there a fine for not complying?" | Elliptical follow-up treated as a new question | Short questions with nothing specific of their own continue the topic |
| "Who receives those?" lost the topic | Pronoun after an unlisted verb | Pronouns after common verbs point back |
| Raw `<tr><td>` markup in the sources panel | Tables extracted as HTML | Excerpts shown as readable rows; the verified quote is unchanged |

The answer suite went from 13/28 to 23–25/28 with no wrongful refusals, and the conversation
suite from 16/24 to 24/24 (twice in a row). Open issues: the model rarely states a conclusion
the source only implies (for example that two printed figures disagree), and the slowest
comparison questions can take close to two minutes on the test model, which is near the
chat's time limit.

## 3. Production feedback: the data flywheel

Every answer in the chat asks **"Was this answer right?"**. A "No" asks what was wrong
(wrong or unsupported fact, missed part of the question, wrong document, hard to
understand, something else) and allows an optional note. Votes are stored per answer in
`answer_feedback`.

```
python scripts/export_answer_feedback.py --since 2026-10-01
```

This writes all votes, plus evaluation-case skeletons for every "No", under `.dist/feedback/`
(git-ignored; it contains customer questions). Then:

1. Once a week, one domain expert reviews the "No" answers. One expert owns the quality bar.
2. For each real failure, write what the answer should have said, and add the case to
   `tests/evals/`.
3. Track the "No" rate per week. It is the slow, honest measure that the fast suites only
   approximate.

## 4. Next step: a model judge you can trust

The regex checks in the answer suite are coarse. The next step is a binary pass/fail
judge for each important failure mode (for example "states a figure the sources do not
contain" or "misses part of the question"). Build each one this way:

1. The domain expert labels 100–200 answers pass/fail for that failure mode.
2. Use about 15% as examples in the judge prompt, about 40% to tune it, and about 45% as an
   untouched test.
3. Report how many real failures the judge catches (true positive rate) and how many good
   answers it passes (true negative rate). Only trust a judge with both high.

## 5. Models: test with nano, run on sol

Production will run on **gpt-6.1 sol**; the evaluation suites run on **gpt-5.4-nano** to keep
testing cheap. Every improvement in this playbook lives in the system around the model, so
it carries over when the model changes. Two cautions:

- A stronger model makes fewer slips (misquotes, miscounted audit verdicts), so some fixes
  here will rarely trigger on sol. They stay as safety nets; do not remove them.
- Before switching production to a new model, re-run every suite against it. The answer
  and conversation harnesses currently insist on the nano deployment, so a test run can never
  spend production's model budget; widen that check deliberately when testing sol.

## 6. Capacity

Each model deployment has its own tokens-per-minute quota, and Azure counts each request's
prompt plus its maximum output against it. An answer uses about 20,000 tokens (draft plus
audit). The nano test deployment allows 121,000 a minute, so roughly six answers a minute.
Throttled calls wait up to 30 seconds for capacity before failing. Check the sol
deployment's quota against expected traffic before onboarding several users at once.

## Sources

- Hamel Husain and Shreya Shankar, [AI evals FAQ](https://hamel.dev/blog/posts/evals-faq/):
  error analysis, binary judges, judge validation, first failure in multi-turn traces.
- Hamel Husain, [A field guide to rapidly improving AI products](https://hamel.dev/blog/posts/field-guide/):
  custom data viewers, domain experts, synthetic data, experiments over features.
- Jason Liu, [Decomposing RAG systems](https://jxnl.co/writing/2024/11/18/decomposing-rag-systems-to-identify-bottlenecks/):
  topics (missing content) versus capabilities (what the system cannot do).
- Jason Liu, [Systematically improving RAG](https://parlance-labs.com/education/rag/jason.html):
  synthetic questions, recall, segmentation, feedback.
- Jo Bergum, [Back to basics for RAG](https://parlance-labs.com/education/rag/jo.html), and
  Ben Clavié, [Beyond the basics of RAG](https://parlance-labs.com/education/rag/ben.html):
  hybrid search, rerankers, retrieval evaluation.
- Anthropic, [Contextual retrieval](https://www.anthropic.com/news/contextual-retrieval).
- Kyle Corbitt, [Fast and slow evals in production](https://parlance-labs.com/education/fine_tuning/kyle.html):
  review real inputs, keep a random test set, monitor for drift.
