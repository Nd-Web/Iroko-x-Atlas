import os
from dotenv import load_dotenv
from azure.search.documents.indexes import SearchIndexClient
from azure.core.credentials import AzureKeyCredential

load_dotenv()

endpoint = os.getenv("AZURE_SEARCH_ENDPOINT", "")
key = os.getenv("AZURE_SEARCH_API_KEY", "")
index_name = os.getenv("AZURE_SEARCH_INDEX_NAME", "iroko-chunks")

print("Endpoint:", endpoint)
print("Index:", index_name)

if not endpoint or not key:
    print("Azure Search not configured properly in .env")
    exit(1)

client = SearchIndexClient(endpoint=endpoint, credential=AzureKeyCredential(key))

try:
    index = client.get_index(index_name)
    print(f"\nFields in index '{index_name}':")
    for field in index.fields:
        print(f" - {field.name} ({field.type})")
except Exception as e:
    print("Error getting index:", e)
