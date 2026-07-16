"""
Create / refresh the Iroko AI voice compliance agent on AethexAI.

Telecom-facing: the agent assesses actions against Nigerian telecom regulation
(NCC) and data-protection law (NDPA 2023 / NDPC, incl. the former NDPR) — NOT
fintech (CBN/SEC).

Run:
    IROKO_AGENT_API_KEY=ae_live_... python setup_aethex_agent.py

Then copy the printed NEXT_PUBLIC_IROKO_AGENT_ID into frontend/.env.local.
"""
import os
import requests

API_KEY = os.environ["IROKO_AGENT_API_KEY"]
BASE_URL = "https://api.aethexai.com/api/v1"
headers = {"X-API-Key": API_KEY, "Content-Type": "application/json"}

# ── Step 1 — pick a voice (prefer the Nigerian English voice for MTN context) ─────
# "Ada" is the Nigerian-English voice the frontend already uses for TTS
# (see frontend/lib/agent.ts DEFAULT_VOICE).
ADA_NIGERIAN_VOICE = "354d8730-388b-5d94-a7e8-9f8bc87dc4fc"

voices = requests.get(f"{BASE_URL}/voices?language=english", headers=headers)
voices.raise_for_status()
voice_list = [v for v in voices.json() if not v.get("is_cloned")]

def _is_nigerian(v: dict) -> bool:
    blob = " ".join(
        str(v.get(k, "")) for k in ("name", "accent", "description", "labels", "language")
    ).lower()
    return "nigeria" in blob or "naija" in blob

by_id = {v["id"]: v for v in voice_list}
nigerian = [v for v in voice_list if _is_nigerian(v)]
if ADA_NIGERIAN_VOICE in by_id:
    chosen = by_id[ADA_NIGERIAN_VOICE]
elif nigerian:
    chosen = nigerian[0]
else:
    chosen = voice_list[0]
voice_id = chosen["id"]
# Ada may not appear in the /voices listing but is still a valid voice_id.
if ADA_NIGERIAN_VOICE not in by_id and not nigerian:
    voice_id = ADA_NIGERIAN_VOICE
    chosen = {"name": "Ada (Nigerian English)"}
print(f"Using voice: {chosen.get('name', voice_id)} ({voice_id})")

# ── Step 2 — create the telecom compliance agent ─────────────────────────────────
SYSTEM_PROMPT = """You are the voice of Iroko AI, a regulatory-intelligence assistant for Nigerian telecom operators such as MTN Nigeria.

When the user describes an action, product, decision, data-handling practice, or statement, assess it against Nigerian TELECOM and DATA-PROTECTION regulation only:
- Nigerian Communications Commission (NCC): Quality of Service (availability >= 98%, dropped-call rate <= 2%, quarterly QoS returns; ~N5M per KPI breach), SIM/NIN registration (N200k per improperly registered SIM), Consumer Code of Practice, licensing and Annual Operating Levy, and equipment type approval.
- Nigeria Data Protection Act 2023 (NDPA), the NDPC, and the former NDPR: lawful basis and consent, records of processing (s24), DPIAs (s28), Data Protection Officer (s29), automated-decision transparency (s32), personal-data breach notification to the NDPC within 72 hours (s34), and cross-border transfer / data-localization rules (s41). NDPA penalties reach up to the higher of N10 million or 2% of annual gross revenue.

Always give a clear verdict FIRST: GO, MONITOR, or NO-GO.
Then explain in two to three sentences which specific regulation applies and why, naming the regulator (NCC or NDPC) and the key obligation or penalty.
Be direct, professional, and concise. Do not ask follow-up questions.
Never give financial-sector (CBN or SEC) advice — you focus strictly on telecom and data protection."""

agent = requests.post(f"{BASE_URL}/agents", headers=headers, json={
    "name": "Iroko Telecom Compliance Voice",
    "system_prompt": SYSTEM_PROMPT,
    "first_message": "Iroko telecom compliance check ready. Describe the action, product, or data-handling practice you want me to assess against NCC and NDPA rules.",
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

print("\nTelecom compliance voice agent created successfully.")
print(f"NEXT_PUBLIC_IROKO_AGENT_ID={agent_data['id']}")
print("\nAdd/replace this in frontend/.env.local, then redeploy the frontend.")
