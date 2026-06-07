import os
from dotenv import load_dotenv
from azure.search.documents.indexes import SearchIndexClient
from azure.search.documents.indexes.models import (
    SearchIndex,
    SimpleField,
    SearchableField,
    SearchField,
    SearchFieldDataType,
    VectorSearch,
    HnswAlgorithmConfiguration,
    VectorSearchProfile,
    SemanticConfiguration,
    SemanticPrioritizedFields,
    SemanticField,
    SemanticSearch
)
from azure.core.credentials import AzureKeyCredential

load_dotenv()

endpoint = os.getenv("AZURE_SEARCH_ENDPOINT", "")
key = os.getenv("AZURE_SEARCH_API_KEY", "")
index_name = os.getenv("AZURE_SEARCH_INDEX_NAME", "iroko-chunks")

if not endpoint or not key:
    raise ValueError("AZURE_SEARCH_ENDPOINT and AZURE_SEARCH_API_KEY must be set in .env")

client = SearchIndexClient(endpoint=endpoint, credential=AzureKeyCredential(key))

# Define vector search configuration matching the 3072-dim embeddings (text-embedding-3-large)
vector_search = VectorSearch(
    algorithms=[HnswAlgorithmConfiguration(name="iroko-hnsw-config")],
    profiles=[VectorSearchProfile(name="iroko-vector-profile", algorithm_configuration_name="iroko-hnsw-config")]
)

# Define semantic configuration matching SEMANTIC_CONFIG="iroko-semantic"
semantic_config = SemanticConfiguration(
    name="iroko-semantic",
    prioritized_fields=SemanticPrioritizedFields(
        title_field=SemanticField(field_name="title"),
        content_fields=[SemanticField(field_name="content")],
        keywords_fields=[SemanticField(field_name="department")]
    )
)

fields = [
    SimpleField(name="id", type=SearchFieldDataType.String, key=True),
    SearchableField(name="content", type=SearchFieldDataType.String),
    SearchableField(name="title", type=SearchFieldDataType.String, filterable=True),
    SimpleField(name="doc_id", type=SearchFieldDataType.String, filterable=True),
    SimpleField(name="parent_id", type=SearchFieldDataType.String, filterable=True),
    SimpleField(name="doc_type", type=SearchFieldDataType.String, filterable=True),
    SimpleField(name="source", type=SearchFieldDataType.String, filterable=True),
    SimpleField(name="language", type=SearchFieldDataType.String, filterable=True),
    SimpleField(name="classification", type=SearchFieldDataType.String, filterable=True),
    SimpleField(name="department", type=SearchFieldDataType.String, filterable=True),
    SimpleField(name="region", type=SearchFieldDataType.String, filterable=True),
    SimpleField(name="chunk_index", type=SearchFieldDataType.Int32),
    SimpleField(name="created_at", type=SearchFieldDataType.String, filterable=True),
    SearchField(
        name="content_vector",
        type=SearchFieldDataType.Collection(SearchFieldDataType.Single),
        vector_search_dimensions=3072,
        vector_search_profile_name="iroko-vector-profile"
    )
]

try:
    client.delete_index(index_name)
    print(f"Old index '{index_name}' deleted")
except Exception as e:
    print(f"No existing index to delete or error: {e}")

index = SearchIndex(
    name=index_name,
    fields=fields,
    vector_search=vector_search,
    semantic_search=SemanticSearch(configurations=[semantic_config])
)

client.create_or_update_index(index)
print(f"Index '{index_name}' created successfully with all required fields (including content_vector and semantic configuration).")