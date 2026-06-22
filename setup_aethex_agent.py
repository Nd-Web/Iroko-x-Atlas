import os
import requests

API_KEY = os.environ["IROKO_AGENT_API_KEY"]
BASE_URL = "https://api.aethexai.com/api/v1"
headers = {"X-API-Key": API_KEY, "Content-Type": "application/json"}

# Step 1 — get first available English voice
voices = requests.get(f"{BASE_URL}/voices?language=english", headers=headers)
voices.raise_for_status()
voice_list = [v for v in voices.json() if not v.get("is_cloned")]
voice_id = voice_list[0]["id"]
print(f"Using voice: {voice_id}")

# Step 2 — create the compliance agent
agent = requests.post(f"{BASE_URL}/agents", headers=headers, json={
    "name": "Iroko Compliance Voice",
    "system_prompt": """You are a compliance assistant for Iroko AI, a regulatory intelligence platform for African financial institutions.
When the user describes a financial product, action, policy, or statement, assess it against CBN (Central Bank of Nigeria) and NCC regulations.
Respond with a clear verdict first: GO, MONITOR, or NO-GO.
Then explain in two sentences maximum which specific regulation applies and why.
Be direct and professional. Do not ask follow-up questions.""",
    "first_message": "Iroko compliance check ready. Describe the action or product you want assessed.",
    "voice_id": voice_id,
    "language": "english",
    "temperature": 0.2,
    "response_min_sentences": 2,
    "response_max_sentences": 3,
    "max_duration_seconds": 120,
    "script_adherence": "strict"
})
agent.raise_for_status()
agent_data = agent.json()

print(f"\nAgent created successfully.")
print(f"NEXT_PUBLIC_IROKO_AGENT_ID={agent_data['id']}")
print(f"\nAdd this to your frontend/.env.local file.")
