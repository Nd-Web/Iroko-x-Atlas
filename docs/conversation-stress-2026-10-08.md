# Conversation stress testing — 8 October 2026

## Scope

Real chat endpoints with the configured model, live search and bounded official-source
research, using an isolated SQLite database seeded from the existing 20-document public
CBN snapshot. Test messages are authored synthetic conversations, not private customer
transcripts. Model-call and turn budgets are explicit. No production database writes,
training jobs, deployment, or account changes were made.

The OpenAI Docs skill informed the use of realistic multi-turn cases, adversarial inputs
and manual inspection alongside mechanical grading, following the
[official evaluation guidance](https://developers.openai.com/api/docs/guides/evaluation-best-practices).

## Results

| Run | Turns passing automated checks | Findings |
| --- | --- | --- |
| Initial six conversations | 22/30 | Casual slang routed to research; recall/source-follow-up failures |
| Intermediate correction run | 25/30 | Citation response-schema bug and remaining casual routing issue |
| Final six conversations, JSON endpoint | 30/30 | All defined checks passed; 34 logical model calls |
| Three additional conversation sequences | 14/15 initially | Correct escaped source title misgraded; manual review separately found irrelevant NDPC site-policy material |
| Additional sequences, SSE endpoint after correction | 15/15 | Token/completion consistency and persisted conversation counts checked; 12 logical model calls |
| Final citation-boundary SSE regression | 5/5 | Previous-source recall works with title-only history and no reused excerpt |

Across these six runs, 125 live turns were executed, including repeated regression cases.

582 focused local tests passed, including 240 greeting-plus-factual-question combinations,
conversation isolation/history tests, streaming lifecycle checks, research validation,
source-grounding checks and dataset integrity. Existing deprecation warnings remain.

JSON run latency: median 2.1 seconds, maximum 38.0 seconds. The additional SSE run had
median 0.1 seconds and maximum 25.5 seconds. Many turns use deterministic recall, so
these medians do **not** represent typical regulatory research latency. Only one or
two conversations ran concurrently; this is not a production capacity/load benchmark.

## Fixes driven by failures

- Recognise bounded casual/slang combinations without swallowing mixed factual messages.
- Recall first/previous messages, including alternate wording and conversation suffixes.
- Answer questions about earlier searches from recorded server activity, not another
  document search. Preserve website checked/unavailable status across saved history.
- Return previous citation identities in the API's required shape, explicitly as historical
  references. Do not reintroduce old excerpts as new evidence. Collapse duplicate identities.
- Keep plain-language/list-format follow-ups attached to the prior factual topic.
- Decline explicit requests to fabricate fines/citations without inventing figures.
- Exclude regulator website privacy/cookie/terms pages from regulatory-source discovery.
- Grade literal Markdown-escaped names as users see them, rather than flagging a missing name.

## Remaining limitations

A passing check is not expert approval or proof of legal accuracy. Manual review caught
an NDPC answer that passed broad mechanical checks but described the regulator's own
privacy policy. After filtering that page, the answer accurately acknowledged that the
resources listing did not establish substantive fintech obligations. The research path
still needs broader primary-instrument coverage to answer that request fully.

Some longer answers still repeat caveats or ask generic follow-ups. Cloud/model latency
and unavailable official sites remain variable. These development sequences were rerun
after fixes; they are regression checks, not an untouched external benchmark. The separate
100-example held-out dataset was not used for tuning or run here. No model weights were
retrained: changes are application routing, memory, source selection and validation.

## Reproduce locally

From `backend`, with the existing local environment configured:

```powershell
.venv/Scripts/python.exe scripts/build_conversation_stress.py --seed 731 --output ../.dist/rag-evaluation/stress-731.json
.venv/Scripts/python.exe scripts/evaluate_conversations.py run --configured-model --scenarios ../.dist/rag-evaluation/stress-731.json --concurrency 2 --max-turns 35 --max-model-calls 120
.venv/Scripts/python.exe scripts/build_conversation_stress.py --fresh --output ../.dist/rag-evaluation/stress-fresh.json
.venv/Scripts/python.exe scripts/evaluate_conversations.py run --configured-model --stream --scenarios ../.dist/rag-evaluation/stress-fresh.json --concurrency 1 --max-turns 20 --max-model-calls 75
```

These commands incur model/search usage. The runner replaces `DATABASE_URL` in its process
before importing application database modules; it never edits `.env`. The local snapshot
must already exist. It does not take a new snapshot from production. JSON reports and
isolated test databases remain under ignored `.dist/rag-evaluation/`.

Reports for this iteration:

- `conversations-20261007-192046.json` — initial failures
- `conversations-20261008-120124.json` — intermediate failures
- `conversations-20261008-120644.json` — 30/30 JSON run
- `conversations-20261008-120530.json` — additional-case discovery
- `conversations-20261008-182129.json` — 15/15 SSE run
- `conversations-20261008-182348.json` — final 5/5 citation-boundary SSE check

Report filename times come from the execution host; this report's date uses Africa/Lagos.
