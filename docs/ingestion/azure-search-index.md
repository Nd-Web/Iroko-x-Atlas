# Proposed Azure AI Search index: `iroko-regulatory-chunks`

**Status: proposal. The index has NOT been created.** Review before Phase 5.

Follows the pattern already in `backend/create_index.py` (same SDK, same
`SearchIndexClient`, same HNSW + semantic configuration shape) so there is one
way indexes are defined in this repo.

## Why a separate index rather than reusing `iroko-chunks`

`iroko-chunks` holds internal corporate documents with fields shaped for that
job (`department`, `classification`, `region`). Regulatory chunks need
citation-grade fields — `reference_number`, `page_start`/`page_end`, character
offsets, `is_latest` — and a different filter profile. Mixing them would mean
nullable fields on both sides and filter conditions on every internal query.

Both indexes share the same vector profile shape and the same 3072-dimension
`text-embedding-3-large` embeddings, so the embedding client is reused as-is.
The service's 15-index quota is at 1.

## Field definitions

| Field | Type | Attributes | Source |
|---|---|---|---|
| `id` | String | key | `{document_id}_{chunk_index}` |
| `content` | String | searchable | `regulatory_chunks.text`, verbatim |
| `section_heading` | String | searchable, filterable | `regulatory_chunks.section_heading` |
| `title` | String | searchable, filterable | document title |
| `document_id` | String | filterable | FK |
| `chunk_index` | Int32 | filterable, sortable | ordering within document |
| `regulator` | String | filterable, facetable | `CBN`, `SEC`, … |
| `doc_type` | String | filterable, facetable | `circular`, `guideline`, … |
| `category` | String | filterable, facetable | regulator's own label |
| `reference_number` | String | searchable, filterable | verbatim |
| `reference_number_normalized` | String | filterable | trimmed/collapsed/uppercased; exact-match boost |
| `published_date` | DateTimeOffset | filterable, sortable, facetable | nullable |
| `is_latest` | Boolean | filterable | default filter `is_latest eq true` |
| `page_start`, `page_end` | Int32 | filterable | citation page range |
| `char_start`, `char_end` | Int32 | retrievable only | offsets into joined document text |
| `text_sha256` | String | filterable | verbatim-integrity proof |
| `content_sha256` | String | filterable | document identity |
| `source_url` | String | retrievable only | most recently seen URL |
| `content_vector` | Collection(Single) | 3072 dims, `iroko-reg-vector-profile` | embedding of `context_header + "\n\n" + text` |

`char_start`/`char_end`/`source_url` are retrievable only — they belong in the
citation, never in a filter or query.

## Definition (mirrors `backend/create_index.py`)

```python
vector_search = VectorSearch(
    algorithms=[HnswAlgorithmConfiguration(name="iroko-reg-hnsw")],
    profiles=[VectorSearchProfile(
        name="iroko-reg-vector-profile",
        algorithm_configuration_name="iroko-reg-hnsw",
    )],
)

semantic_config = SemanticConfiguration(
    name="iroko-regulatory-semantic",
    prioritized_fields=SemanticPrioritizedFields(
        title_field=SemanticField(field_name="title"),
        content_fields=[SemanticField(field_name="content")],
        keywords_fields=[SemanticField(field_name="section_heading")],
    ),
)

fields = [
    SimpleField(name="id", type=SearchFieldDataType.String, key=True),
    SearchableField(name="content", type=SearchFieldDataType.String),
    SearchableField(name="section_heading", type=SearchFieldDataType.String, filterable=True),
    SearchableField(name="title", type=SearchFieldDataType.String, filterable=True),
    SimpleField(name="document_id", type=SearchFieldDataType.String, filterable=True),
    SimpleField(name="chunk_index", type=SearchFieldDataType.Int32, filterable=True, sortable=True),
    SimpleField(name="regulator", type=SearchFieldDataType.String, filterable=True, facetable=True),
    SimpleField(name="doc_type", type=SearchFieldDataType.String, filterable=True, facetable=True),
    SimpleField(name="category", type=SearchFieldDataType.String, filterable=True, facetable=True),
    SearchableField(name="reference_number", type=SearchFieldDataType.String, filterable=True),
    SimpleField(name="reference_number_normalized", type=SearchFieldDataType.String, filterable=True),
    SimpleField(name="published_date", type=SearchFieldDataType.DateTimeOffset,
                filterable=True, sortable=True, facetable=True),
    SimpleField(name="is_latest", type=SearchFieldDataType.Boolean, filterable=True),
    SimpleField(name="page_start", type=SearchFieldDataType.Int32, filterable=True),
    SimpleField(name="page_end", type=SearchFieldDataType.Int32, filterable=True),
    SimpleField(name="char_start", type=SearchFieldDataType.Int32),
    SimpleField(name="char_end", type=SearchFieldDataType.Int32),
    SimpleField(name="text_sha256", type=SearchFieldDataType.String, filterable=True),
    SimpleField(name="content_sha256", type=SearchFieldDataType.String, filterable=True),
    SimpleField(name="source_url", type=SearchFieldDataType.String),
    SearchField(
        name="content_vector",
        type=SearchFieldDataType.Collection(SearchFieldDataType.Single),
        vector_search_dimensions=3072,
        vector_search_profile_name="iroko-reg-vector-profile",
    ),
]
```

## Analyzers

Default `standard.lucene` on all searchable fields, matching `iroko-chunks`.
Nigerian regulatory text is English, and reference numbers like
`BPS/DIR/GEN/CIR/04/007` are handled by the exact-match path against
`reference_number_normalized`, not by the analyzer. A custom analyzer is not
proposed; if slash-delimited tokens prove troublesome in Phase 5, a keyword
analyzer on `reference_number` is the smallest fix.

## Query shape

Unchanged from the brief's section 12 contract: vector cosine search plus
keyword search, merged with reciprocal rank fusion (k = 60). Azure AI Search
returns both result sets in one request, so fusion happens client-side exactly
as `services/azure_search.hybrid_search` already does.

Default filter is `is_latest eq true`, dropped when
`include_old_versions=True`. `regulators`, `doc_types`, `published_after` and
`published_before` compose into an OData `$filter`. A query containing something
shaped like a reference number runs an exact
`reference_number_normalized eq '…'` lookup first, ranked above fused results.

## Reindex job

`reindex_regulatory_chunks(regulator=None, since=None, full=False)` — Postgres
is the source of truth, so the index is disposable and rebuildable:

1. Stream `regulatory_chunks` joined to `regulatory_documents` from Postgres.
2. Build documents in batches of 1,000 (Azure's `mergeOrUpload` ceiling).
3. `mergeOrUpload` so reruns are idempotent.
4. Delete index documents whose `document_id` is no longer `is_latest`, unless
   retaining old versions for `include_old_versions` queries — **open question
   below**.
5. Record counts and duration; emit one audit event per run.

The nightly pipeline indexes incrementally as documents reach `embedded`; this
job exists for rebuilds, backfills and schema changes.

## Open questions

1. **Old versions in the index.** Superseded versions stay in Postgres forever.
   Should they also stay in the search index to serve `include_old_versions`,
   or should that flag fall back to a Postgres-only lookup? Indexing everything
   is simpler but grows the index with rarely-queried content.
2. **Spreadsheets.** `stored_unparsed` documents produce no chunks and so never
   reach the index. Watchdog sees them via Postgres and the notification event.
   Confirm that is acceptable, since they will be invisible to
   `search_regulatory_chunks`.
