"""
Configure the Iroko AI voice compliance agent on AethexAI (telecom-facing).

The agent assesses actions against Nigerian telecom regulation (NCC) and data
protection law (NDPA 2023 / NDPC, incl. the former NDPR) — NOT fintech (CBN/SEC).

This script is idempotent: it UPDATES the existing agent in place (so re-running
never creates orphan agents). Point it at a different agent by setting
IROKO_AGENT_ID; if that agent doesn't exist it falls back to creating one.

Run:
    IROKO_AGENT_API_KEY=ae_live_... python setup_aethex_agent.py
"""
import os
import requests

API_KEY = os.environ["IROKO_AGENT_API_KEY"]
BASE_URL = "https://api.aethexai.com/api/v1"
headers = {"X-API-Key": API_KEY, "Content-Type": "application/json"}

# The live agent the frontend calls (NEXT_PUBLIC_IROKO_AGENT_ID); override via env.
AGENT_ID = os.getenv("IROKO_AGENT_ID", "9aad19b0-5d6e-4306-ac66-cbc8e2486cae")
# "Ada" — the Nigerian-English voice the frontend already uses (frontend/lib/agent.ts).
VOICE_ID = "354d8730-388b-5d94-a7e8-9f8bc87dc4fc"

SYSTEM_PROMPT = """You are the voice of Iroko AI, a regulatory-intelligence assistant for Nigerian telecom operators such as MTN Nigeria.

When the user describes an action, product, decision, data-handling practice, or statement, assess it against Nigerian TELECOM and DATA-PROTECTION regulation only:
- Nigerian Communications Commission (NCC): Quality of Service (availability >= 98%, dropped-call rate <= 2%, quarterly QoS returns; ~N5M per KPI breach), SIM/NIN registration (N200k per improperly registered SIM), Consumer Code of Practice, licensing and Annual Operating Levy, and equipment type approval.
- Nigeria Data Protection Act 2023 (NDPA), the NDPC, and the former NDPR: lawful basis and consent, records of processing (s24), DPIAs (s28), Data Protection Officer (s29), automated-decision transparency (s32), personal-data breach notification to the NDPC within 72 hours (s34), and cross-border transfer / data-localization rules (s41). NDPA penalties reach up to the higher of N10 million or 2% of annual gross revenue.

Always give a clear verdict FIRST: GO, MONITOR, or NO-GO.
Then explain in two to three sentences which specific regulation applies and why, naming the regulator (NCC or NDPC) and the key obligation or penalty.
Be direct, professional, and concise. Do not ask follow-up questions.
Never give financial-sector (CBN or SEC) advice — you focus strictly on telecom and data protection."""

payload = {
    "name": "Iroko Telecom Compliance Voice",
    "system_prompt": SYSTEM_PROMPT,
    "first_message": "Iroko telecom compliance check ready. Describe the action, product, or data-handling practice you want me to assess against NCC and NDPA rules.",
    "voice_id": VOICE_ID,
    "language": "english",
    "temperature": 0.2,
    "response_min_sentences": 2,
    "response_max_sentences": 3,
    "max_duration_seconds": 120,
    "script_adherence": "strict",
}

# Update the existing agent in place (idempotent).
resp = requests.patch(f"{BASE_URL}/agents/{AGENT_ID}", headers=headers, json=payload)

if resp.status_code == 404:
    # Agent doesn't exist — create a fresh one instead.
    print(f"Agent {AGENT_ID} not found; creating a new one.")
    resp = requests.post(f"{BASE_URL}/agents", headers=headers, json=payload)
    resp.raise_for_status()
    AGENT_ID = resp.json()["id"]
    print(f"Created new agent. Set NEXT_PUBLIC_IROKO_AGENT_ID={AGENT_ID} in frontend/.env.local.")
else:
    resp.raise_for_status()

# Verify.
agent = requests.get(f"{BASE_URL}/agents/{AGENT_ID}", headers=headers).json()
sp = agent.get("system_prompt", "")
print(f"Agent {AGENT_ID} is now: {agent.get('name')}")
print(f"  Telecom-facing (NCC & NDPA present): {('NCC' in sp and 'NDPA' in sp)}")
print(f"  Voice id: {agent.get('voice_id')}")
