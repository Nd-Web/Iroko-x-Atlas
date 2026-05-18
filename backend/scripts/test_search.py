import os
from dotenv import load_dotenv
from azure.search.documents import SearchClient
from azure.core.credentials import AzureKeyCredential

load_dotenv()

endpoint = os.getenv("AZURE_SEARCH_ENDPOINT", "")
key = os.getenv("AZURE_SEARCH_API_KEY", "")
index_name = os.getenv("AZURE_SEARCH_INDEX_NAME", "iroko-chunks")

if not endpoint or not key:
    raise ValueError("AZURE_SEARCH_ENDPOINT and AZURE_SEARCH_API_KEY must be set in .env")

client = SearchClient(
    endpoint=endpoint,
    index_name=index_name,
    credential=AzureKeyCredential(key),
)

try:
    results = list(client.search(
        search_text="IHS Nigeria tower lease expire",
        top=3,
        query_type="semantic",
        semantic_configuration_name="iroko-semantic",
        select=["id", "title"],
    ))
    print("Results: " + str(len(results)))
    for r in results:
        t = r.get("title", "?")
        s = r.get("@search.score", 0)
        print("  " + t + " score=" + str(round(s, 2)))
except Exception as e:
    print("ERROR: " + str(type(e).__name__) + ": " + str(e))