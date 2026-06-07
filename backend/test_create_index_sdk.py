import os
from dotenv import load_dotenv
from azure.search.documents.indexes import SearchIndexClient
from azure.core.credentials import AzureKeyCredential

load_dotenv()

endpoint = os.getenv("AZURE_SEARCH_ENDPOINT", "")
key = os.getenv("AZURE_SEARCH_API_KEY", "")

if not endpoint or not key:
    print("Azure Search not configured in .env")
    exit(1)

try:
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
    print("All imports from azure.search.documents.indexes.models succeeded!")
except Exception as e:
    print("Import error:", e)
