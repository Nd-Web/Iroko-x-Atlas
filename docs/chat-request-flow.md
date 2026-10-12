# How an Iroko chat request works

## The document and regulatory question path

1. The browser posts to the same-origin Next.js streaming proxy. The proxy reads
   the HTTP-only session cookie and forwards authentication to FastAPI.
2. FastAPI checks the signed-in user and rate limit, finds or creates that user's
   conversation, loads recent context, and saves the user's message in Postgres.
   Context is bounded to the recent 24 messages / 12 question turns. A separate
   bounded query retains the opening message and first substantive question from
   the first 24 user messages for conversation recall.
3. The Strategist routes the message. Whole greetings, thanks and acknowledgements
   receive a brief conversational reply without model or search calls. A factual
   question with a greeting prefix still needs evidence. Follow-ups reuse the
   previous substantive question; an acknowledgement does not replace its topic.
   Questions about the first or previous user message are answered directly from
   this conversation's saved transcript, without document search or citations.
   Named explanation follow-ups also retain a matching earlier topic and citation
   (for example, asking what a framework's named subject means after discussing it).
   The current question remains the task: a definition does not inherit the previous
   request for every operational condition or the latest regulations. Unrelated named
   subjects and explicit topic switches do not borrow those sources.
   Less familiar social messages use bounded classification and a natural conversational
   response, with no fixed sentence count. A message needing evidence goes back through
   the factual answer path.
   Greetings can use the authenticated account's first name; no name is inferred.
   A pronoun only points back at an earlier turn when the message names no subject
   of its own: "how soon must they be submitted?" after naming the reports is a new
   question, while "does that apply?", "who receives those?" or "the fine for this breach"
   is a follow-up. A short question with nothing specific of its own ("Is there a fine for
   not complying?", "Under which law?") also continues the previous topic, so the answer
   cannot borrow another document's fine; with no previous topic Iroko asks which rule is
   meant. A question that names its own subject ("STR deadline?") is never sent back for
   clarification, and common compliance shorthand (STR, CTR, FTR, PEP) routes directly.
   Library questions ("what documents do you have?", "which circulars mention BVN?")
   are answered straight from the documents the user may access, with their
   regulator, date and reference, and no model call. Only documents with a current
   extracted revision are listed, because only those can be cited.

   The latest answer is shown in full; older answers can still be collapsed in the
   compact view. Casual replies hide PDF export, evidence feedback and activity controls.
   Requested ten-item lists can retain all ten audited findings (up to 12 claims);
   insufficient coverage is reported instead of filling the list with unsupported items.
4. For document questions, the Researcher searches Azure AI Search using lexical
   and vector retrieval when embeddings are available, with keyword fallback.
   Permissions filter search results. Retrieved passages are then checked against
   the canonical extracted records, active revisions and access permissions in
   the database. Suitable short documents can be expanded to their complete text.
   Prior citation IDs can reacquire bounded canonical passages when search misses
   them, but permissions, indexed status and current-revision checks still apply.
   Historical assistant text, source titles and old quotes are never evidence.
5. Eligible regulatory questions may also check bounded, allowlisted official
   regulator sources. This happens for freshness requests or an evidence gap;
   it is not an unrestricted or exhaustive internet search. Freshness requests run
   canonical document retrieval and official research together; a news hit never
   replaces stored primary instruments. Both sets of evidence reach validation.
   Requirement/deadline queries prioritize relevant instrument candidates, not
   simply the newest date mentioned on a news page. This ranking is not legal approval.
   BDC/foreign-exchange, FXBT, NFEM and Authorised Dealer questions can trigger targeted
   CBN research without requiring the user to type "CBN". Selected previous official
   URLs are refetched through the existing HTTPS/domain allowlist; source-bound private
   document questions do not become public research. A missing framework identity in
   a partial regulatory answer is also eligible for a recovery search.
6. The configured model drafts structured, source-backed claims, a natural opening
   paragraph, and up to three next questions. Responses use a normal, task-appropriate
   level of detail: simple questions can be direct, while explanations and comparisons
   include enough supported context. A one-off shortening request does not make future
   answers permanently short. Helpful drafting has a 3,200-token ceiling (including
   JSON and source quotes), not a target response length. Validation checks citation
   identifiers, exact source quotes and numeric support. Harmless formatting is
   ignored (wrapping quotation marks, edge ellipses, markdown escapes such as
   "4\." and leading zeros); an ellipsis inside a quote still fails. A calculation
   may use a printed figure, a number in the question, or an earlier checked result.
   A separate model audit, given only the passages the claims cite, checks whether
   each claim is actually supported. If its verdicts cannot be matched one-to-one
   with the claims, the audit alone is asked once more; verdicts are never guessed
   into alignment. Partial answers preserve supported findings
   while identifying missing facts. These checks reduce errors but do not guarantee
   legal correctness.
   Concept explanations use plain-language meaning and supported mechanics instead
   of requiring a dictionary definition or every framework condition. They still need
   exact supporting quotes and the independent audit. Current rules, fines, permissions
   and institution-specific compliance questions keep the stricter evidence requirements.
7. The approved answer is rendered without a further executive rewrite. The direct
   answer leads it only when the audit approves it, every drafted claim survived
   both checks, and it adds no figure absent from those claims; a leading "Yes" or
   "No" is removed unless the question is a yes/no question. Next questions are shown
   only if they are questions whose figures appear in the evidence; otherwise a
   generic prompt is offered for complete answers. Incomplete answers instead derive
   next steps and follow-ups from unanswered parts, ahead of related-topic suggestions.
   Factual chat answers use four stable sections: what is established, what is not,
   what is needed from the user, and the next step. Any unresolved part is explicit
   in the opening, rather than leading with an enforcement anecdote. Capital minimum,
   actual gap and deadline questions also have independent server-owned coverage checks;
   an auditor's approval of a side fact cannot mark these parts answered.
   Monetary operands normalize scales (such as bn/million) before source checks and
   arithmetic. Unknown units and explicit cross-currency additions/subtractions are
   rejected. Percentage operands use their fractional value. A capital difference is
   conditional arithmetic, not certification of capital unimpaired by losses or compliance.
   Research progress is sent while work runs; answer text
   is streamed only after validation.
   FastAPI saves the assistant answer, citations and activity before the final
   completion event. An unavailable source or failed validation is not permission
   to invent a fine or certify compliance.

Documents are extracted and indexed by the ingestion pipeline **before** this
path. Asking a question normally searches that reusable evidence; it does not
re-extract every uploaded PDF.

Every saved answer asks "Was this answer right?". Votes, with a reason when the
answer was not right, are stored per answer in `answer_feedback` and exported for
review with `scripts/export_answer_feedback.py`; reviewed failures become new
evaluation cases. How the team measures and improves answers is described in
[ai-quality-playbook.md](ai-quality-playbook.md).

## Model capacity

Each answer makes a drafting call and an audit call, plus a small routing call for
ambiguous messages. Azure counts each request's prompt *and* its maximum output
allowance against the deployment's tokens-per-minute quota, so the allowances are
sized near observed use. When Azure throttles a call, the client waits for Azure's
retry hint for up to 30 seconds instead of failing immediately; connection and
server errors retry twice. Each request times out after 90 seconds. If several
people chat at once and the quota is still exhausted, the answer reports that the
reasoning service is unavailable rather than showing an unchecked draft. Raising
the deployment's quota in Azure is the fix for sustained load.

## Saved history

Opening History refreshes an account-scoped list of the latest 50 conversations.
The list uses a single SQL query to count messages without loading their contents.
Selecting a conversation fetches its saved messages and citations; it does not
call the model or regenerate answers. The next question uses that conversation's
identifier. Earlier exchanges remain available through **Show earlier messages**
in the compact chat view.

History proxies allow a 45-second backend budget rather than the previous eight
seconds and return retryable gateway errors when loading fails. A failed or stale
history response cannot overwrite the current conversation. The deployment still
needs a reachable, appropriately provisioned backend; a longer timeout is not a
substitute for production availability.

## Repeated answer checks

From `backend`, run `scripts/evaluate_answer_consistency.py` with an existing active
`--user-id`, `--cases tests/evals/answer_consistency.json`, and `--repeats 3`.
An optional `--report` saves a private local JSON report. The harness reads permitted
documents and uses the real research/model/audit flow; it does not save conversations
or run ingestion jobs. Each repetition must independently satisfy the opening,
section, evidence and missing-input checks. Inspect the full reports as well:
passing those checks is not proof that a rule is currently binding or a bank complies.

## What the agent labels mean

In this document/regulatory path, Strategist, Researcher, Watchdog and Scribe name
routing, retrieval, validation and rendering stages. This is not five autonomous
models running for every message. Other legacy operational, fraud and complaint
intents have separate handlers; the evidence-backed flow described above should
not be assumed to describe those handlers.

The chat's **Activity** panel shows actual recorded workflow steps, not the
model's hidden reasoning. Classification and follow-up context can still be
imperfect, and source coverage is bounded. Ask precise questions and check the
citations, scope, dates and stated gaps before relying on a regulatory answer.
