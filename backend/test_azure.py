import os
import requests
from dotenv import load_dotenv

load_dotenv()

endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
api_key = os.getenv("AZURE_OPENAI_API_KEY")
deployment = os.getenv("AZURE_OPENAI_NANO_DEPLOYMENT")

url = f"{endpoint}/openai/deployments/{deployment}/chat/completions?api-version=2025-01-01-preview"

headers = {
    "api-key": api_key,
    "Content-Type": "application/json"
}

body = {
    "messages": [
        {"role": "user", "content": "Say hello in one sentence."}
    ],
    "max_tokens": 50,
    "temperature": 0.7
}

print("🔍 Testing Azure OpenAI...\n")

response = requests.post(url, headers=headers, json=body)

print("Status:", response.status_code)
print("Response:")
print(response.text)