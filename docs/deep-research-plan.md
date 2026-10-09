# Iroko Deep Research — saved feature proposal

Saved: 2026-10-08
Status: Deferred for later discussion. Not implemented or authorized for implementation by this note.

## User intent

The user wants a separate capability that improves Iroko's core intelligence, not another dashboard or compliance-management workflow. Claude is handling the knowledge graph separately. The user asked to save this Deep Research proposal and remember it for later.

## Proposed feature

A user-selectable **Deep Research** mode for questions requiring a multi-step investigation. Iroko already retrieves documents and searches official websites; the proposed improvement is identifying missing evidence, refining searches, and investigating further within explicit limits before answering.

For the pilot, start with one focused use case:

> Investigate a proposed business action against relevant regulations and the customer's accessible uploaded policies, with traceable findings.

Example question:

> Can our microfinance bank launch this lending product, and what compliance risks should we consider?

## Proposed investigation flow

1. Understand the institution's licence, proposed product and relevant activities; ask only essential missing questions.
2. Break the question into evidence needs, such as licensing permissions, customer protection, data handling and reporting requirements.
3. Examine authorized internal documents and official public sources; assess coverage and refine searches where evidence is weak.
4. Cross-check findings for exceptions, amendments, conflicting guidance, currentness and applicability.
5. Produce a research brief with findings, supporting clauses, potential gaps, recommended next steps and unresolved questions.
6. Preserve the investigation context for follow-ups, such as comparing the requirements with an accessible internal policy.

## Relationship to the knowledge graph

The graph connects evidence and relationships. Deep Research investigates a question, uses available evidence and seeks missing pieces. It should work independently of the graph initially and be able to consume graph results later. Do not take over or duplicate Claude's graph work.

## Boundaries

- Keep ordinary chat fast; offer or select deeper research for complex questions.
- Bound each investigation by search count, elapsed time and spending.
- Do not send private documents or sensitive customer details to public search.
- Respect tenant permissions and document-only requests throughout retrieval and follow-ups.
- Missing evidence means unverified, not automatically non-compliant.
- Do not invent penalties, applicability, institutional compliance status or claims of exhaustive regulatory coverage.
- Provide research support, not autonomous compliance approval or execution of business actions.
- This proposal does not require training a new model or selecting a new vendor.

## Validation before claiming improvement

Compare against Iroko's current answers on real pilot questions. Check evidence support, coverage, applicability, useful handling of missing information, follow-up continuity, latency and cost. Do not promise accuracy gains before measuring them.

Conceptual reference: [Adaptive-RAG: Learning to Adapt Retrieval-Augmented Large Language Models through Question Complexity](https://arxiv.org/abs/2403.14403). Published results are not evidence that this proposed Iroko feature will achieve the same outcomes.

## Resuming later

Read this note, inspect the then-current retrieval and graph implementations, and agree the pilot scope and investigation limits with the user before building. This is a saved proposal, not a queued deployment or background task.
