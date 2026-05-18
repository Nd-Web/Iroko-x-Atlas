import os
from dotenv import load_dotenv
from azure.search.documents.indexes import SearchIndexClient
from azure.search.documents.indexes.models import SearchIndex, SimpleField, SearchableField, SearchFieldDataType
from azure.core.credentials import AzureKeyCredential

load_dotenv()

endpoint = os.getenv("AZURE_SEARCH_ENDPOINT", "")
key = os.getenv("AZURE_SEARCH_API_KEY", "")

if not endpoint or not key:
    raise ValueError("AZURE_SEARCH_ENDPOINT and AZURE_SEARCH_API_KEY must be set in .env")

client = SearchIndexClient(endpoint=endpoint, credential=AzureKeyCredential(key))

fields = [
    SimpleField(name="id", type=SearchFieldDataType.String, key=True),
    SimpleField(name="org_id", type=SearchFieldDataType.String, filterable=True),
    SimpleField(name="document_id", type=SearchFieldDataType.String, filterable=True),
    SimpleField(name="chunk_index", type=SearchFieldDataType.Int32),
    SearchableField(name="content", type=SearchFieldDataType.String),
    SimpleField(name="source", type=SearchFieldDataType.String, filterable=True),
    SimpleField(name="category", type=SearchFieldDataType.String, filterable=True),
    SimpleField(name="doc_type", type=SearchFieldDataType.String, filterable=True),
    SimpleField(name="title", type=SearchFieldDataType.String, filterable=True),
    SimpleField(name="page_number", type=SearchFieldDataType.Int32),
    SimpleField(name="department", type=SearchFieldDataType.String, filterable=True),
]

try:
    client.delete_index("iroko-chunks")
    print("Old index deleted")
except Exception:
    pass

index = SearchIndex(name="iroko-chunks", fields=fields)
client.create_or_update_index(index)
print("Index iroko-chunks recreated with all fields")