"""
Strategist test harness — verifies all 10 required test cases.
Run from the project root: python test_strategist.py
"""
import asyncio
import json
import os
import sys
import io

# Force UTF-8 output on Windows
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

# ── Ensure project root is on the path ───────────────────────────────────────
sys.path.insert(0, os.path.dirname(__file__))

# ── Load .env then Key Vault ──────────────────────────────────────────────────
from dotenv import load_dotenv
load_dotenv()

print("Loading Azure Key Vault secrets...")
try:
    from services.keyvault import load_secrets_from_keyvault
    n = load_secrets_from_keyvault()
    print(f"Key Vault: {n} secret(s) loaded.")
except Exception as e:
    print(f"Key Vault load failed (may continue with .env overrides): {e}")

# ── Verify LLM credentials ────────────────────────────────────────────────────
endpoint = os.getenv("AZURE_OPENAI_ENDPOINT", "")
api_key  = os.getenv("AZURE_OPENAI_API_KEY", "")
print(f"AZURE_OPENAI_ENDPOINT : {'SET (' + endpoint[:30] + '...)' if endpoint else 'NOT SET ❌'}")
print(f"AZURE_OPENAI_API_KEY  : {'SET (' + api_key[:6] + '...)' if api_key else 'NOT SET ❌'}")

if not endpoint or not api_key:
    print("\n⚠️  Cannot run LLM tests — Azure credentials missing.")
    print("   Canned scenario tests will still run.")

print()

# ── Import Strategist ─────────────────────────────────────────────────────────
from agents.strategist import StrategistAgent

TEST_QUERIES = [
    ("hi",                              "greeting — friendly English"),
    ("how are you doing",               "small talk — NOT a doc search"),
    ("how body nau",                    "Pidgin small talk"),
    ("What is the weather today?",      "out-of-domain decline"),
    ("Wetin dey happen for Ikeja cluster?", "canned NOC incident (Pidgin input)"),
    ("What is our SLA credit exposure?",    "canned SLA exposure"),
    ("What is our NCC compliance status?",  "canned compliance report"),
    ("Tell me about IHS Nigeria",           "LLM document query"),
    ("What is fibre status in Lagos?",      "LLM — Lagos not in docs, should flag"),
    ("What about IHS?",                     "follow-up using prior context"),
]


async def run_tests():
    agent = StrategistAgent()

    for i, (query, expectation) in enumerate(TEST_QUERIES, 1):
        print(f"\n{'=' * 72}")
        print(f"TEST {i:02d}: \"{query}\"")
        print(f"EXPECT : {expectation}")
        print('-' * 72)

        try:
            result_str = await agent.investigate(question=query)
            result = json.loads(result_str)

            intent    = result.get("intent", "?")
            is_pidgin = result.get("is_pidgin", False)
            duration  = result.get("duration_text", "?")
            agent_nm  = result.get("agent_name", "?")
            answer    = result.get("answer", "")
            citations = result.get("citations", [])
            followups = result.get("suggested_followups", [])
            trace     = result.get("agent_trace", [])
            error     = result.get("error")

            print(f"Intent   : {intent}")
            print(f"Is Pidgin: {is_pidgin}")
            print(f"Duration : {duration}")
            print(f"AgentName: {agent_nm}")

            if error:
                print(f"⚠️  ERROR : {error}")

            print(f"\nANSWER:\n{answer}")

            if citations:
                print(f"\nCITATIONS ({len(citations)}):")
                for c in citations:
                    print(f"   [{c.get('document_id')}] {c.get('document_title')}")
                    print(f"     -> {c.get('excerpt')}")

            if followups:
                print(f"\nFOLLOW-UPS:")
                for f in followups:
                    print(f"   * {f}")

            if trace:
                print(f"\nTRACE ({len(trace)} steps):")
                for t in trace:
                    print(f"   [{t.get('agent')}] {t.get('tool')}: {t.get('description')}")

        except Exception as e:
            print(f"❌ EXCEPTION: {e}")
            import traceback
            traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(run_tests())
