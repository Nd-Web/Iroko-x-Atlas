# Iroko AI — Hackathon Judge Setup Guide

**Total time to first live signal: under 5 minutes.**  
This guide gets you from zero to a running Iroko AI instance with live web intelligence.

---

## What You Need Before Starting

| Requirement | Where to get it | Time |
|---|---|---|
| Docker Desktop | https://www.docker.com/products/docker-desktop | 2 min install |
| Bright Data API key | https://brightdata.com → free trial | 2 min signup |
| Git | Already installed on most systems | — |

> **No Azure account required** to see the system run. Azure keys unlock LLM-powered verdicts and document RAG — the web intelligence pipeline works without them in mock/degraded mode.

---

## Step 1 — Clone the Repository

```bash
git clone https://github.com/your-org/iroko-ai.git
cd iroko-ai
```

---

## Step 2 — Create Your .env File

```bash
cp .env.example backend/.env
```

Open `backend/.env` in any editor. The minimum you need to set:

```bash
# Required for the app to start — generate any 64-char string
SECRET_KEY=any_random_64_character_string_will_work_here_just_make_it_long

# Required for live web intelligence (see Step 3)
BRIGHTDATA_API_KEY=your_key_here
BRIGHTDATA_CUSTOMER_ID=your_customer_id_here
```

Everything else is pre-filled with working defaults. Leave Azure fields blank — the system degrades gracefully (see [Running Without Azure](#running-without-azure) below).

---

## Step 3 — Get Your Bright Data Key (2 minutes)

1. Go to **https://brightdata.com** and sign up for a free trial account.
2. From the dashboard, click **Account Settings** → **API Keys** → **Add key** → copy it.
3. Your **Customer ID** is the number shown next to your username in the top-right corner of the dashboard.
4. Paste both into `backend/.env`:

```env
BRIGHTDATA_API_KEY=brd_xxxxxxxxxxxxxxxxxxxxxxxxxx
BRIGHTDATA_CUSTOMER_ID=123456
```

The default zone (`residential`) and endpoints are already configured in `.env.example` — no zone setup needed for the basic demo.

---

## Step 4 — Start the Stack

```bash
docker-compose up --build
```

First build takes 2–3 minutes (downloading Python and Node images). Subsequent starts take under 30 seconds.

You'll see the backend print:

```
[OK] Environment validated — all required variables are set.
INFO:     Application startup complete.
```

If you see `BRIGHTDATA_API_KEY -- Bright Data web intelligence disabled`, check Step 3.

---

## Step 5 — Access the Dashboard

| Service | URL | Credentials |
|---|---|---|
| **Web Intelligence Dashboard** | http://localhost:3000 | `admin@mtn.ng` / `AtlasAdmin2026!` |
| **API Docs (Swagger)** | http://localhost:8000/docs | — |
| **Health Check** | http://localhost:8000/api/v1/intel/health | — |

Navigate to the dashboard, log in, and click the **Web Intelligence** tab to see the three-panel interface: Live Signals, Verdict & Compliance, and Audit Trail.

---

## Step 6 — Trigger a Live Web Intelligence Run

This runs the full 6-stage streaming pipeline and returns all 5 signal categories:

```bash
# 1. Get a JWT token
TOKEN=$(curl -s -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@mtn.ng","password":"AtlasAdmin2026!"}' \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])")

# 2. Fetch live signals across all 5 intelligence domains
curl -s http://localhost:8000/api/v1/intel/signals \
  -H "Authorization: Bearer $TOKEN" | python3 -m json.tool

# 3. Check a decision for NCC compliance
curl -s -X POST http://localhost:8000/api/v1/intel/check-compliance \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"decision_text": "We plan to increase data tariffs by 15% in Q3 2026 without a 90-day NCC notification period."}' \
  | python3 -m json.tool

# 4. View the hash-chained audit trail with chain integrity verification
curl -s "http://localhost:8000/api/v1/intel/audit-trail?verify_chain=true&limit=10" \
  -H "Authorization: Bearer $TOKEN" | python3 -m json.tool

# 5. Stream the live reasoning pipeline (SSE — each line is a pipeline step)
curl -N "http://localhost:8000/api/v1/intel/stream?query=NCC+tariff+compliance+2026" \
  -H "Authorization: Bearer $TOKEN"
```

---

## Step 7 — Download a Compliance Brief (PDF)

```bash
# Download the auto-generated PDF compliance brief
curl -s http://localhost:8000/api/v1/intel/brief \
  -H "Authorization: Bearer $TOKEN" \
  --output iroko_compliance_brief.pdf

# Open it
open iroko_compliance_brief.pdf        # macOS
xdg-open iroko_compliance_brief.pdf   # Linux
start iroko_compliance_brief.pdf      # Windows
```

The PDF contains: live signal scan summary, compound risk entities, GO/NO-GO/MONITOR verdict, NCC regulation references, and recommended actions — all generated in real time from the current web intelligence run.

---

## Running Without Azure

Iroko AI is designed to degrade gracefully when Azure credentials are absent. Here is exactly what works and what doesn't:

| Feature | Without Azure | With Azure |
|---|---|---|
| **Live web signal fetch** (Bright Data) | ✅ Full — Bright Data only | ✅ Full |
| **Signal graph & compound risk** | ✅ Full — pure Python/NetworkX | ✅ Full |
| **NCC rule compilation** | ✅ Full — fetched via Bright Data | ✅ Full |
| **Hash-chained audit trail** | ✅ Full — SQLite/Postgres | ✅ Full |
| **PDF compliance brief** | ✅ Full — ReportLab only | ✅ Full |
| **Fraud noise filter** | ✅ Full (keyword-based triage) | ✅ Full + LLM triage |
| **Per-agent capability scoping** | ✅ Full | ✅ Full |
| **LLM-powered verdicts** | ⚠️ Rule-based fallback (no GPT-4o) | ✅ Full |
| **Adversarial debate agents** | ⚠️ Disabled (requires LLM) | ✅ Full |
| **Document Q&A (RAG)** | ❌ Requires Azure AI Search | ✅ Full |
| **Institutional memory LLM enrichment** | ⚠️ Keyword matching only | ✅ Full |

**Bottom line:** with only a Bright Data key, you get live signal collection, compound risk detection, NCC corpus matching, rule-based verdicts, audit trail, and PDF export. The web intelligence core works without Azure.

---

## Checking Bright Data Connection Status

```bash
# No auth required — open endpoint
curl http://localhost:8000/api/v1/intel/health | python3 -m json.tool
```

Expected response when connected:

```json
{
  "status": "healthy",
  "brightdata": {
    "connected": true,
    "latency_ms": 312,
    "mock_mode": false
  }
}
```

If `"mock_mode": true`, your `BRIGHTDATA_API_KEY` or `BRIGHTDATA_CUSTOMER_ID` is not set correctly — revisit Step 3.

---

## Stopping the Stack

```bash
docker-compose down          # stop containers, keep data
docker-compose down -v       # stop containers and wipe the Postgres volume
```

---

## Troubleshooting

**Port 3000 or 8000 already in use:**
```bash
# Find what's using the port
lsof -i :8000
# Kill it, or change ports in docker-compose.yml
```

**Backend exits immediately with `ENVIRONMENT VALIDATION FAILED`:**  
Open `backend/.env` and make sure `SECRET_KEY` is at least 32 characters and is not the literal string `your_64_char_hex_secret_key_here`.

**Bright Data returns 407 (proxy auth failed):**  
Double-check that `BRIGHTDATA_CUSTOMER_ID` matches the numeric ID shown in the Bright Data dashboard header — it is separate from the API key.

**`docker-compose` not found:**  
If you have Docker Desktop v2.x, try `docker compose` (no hyphen).
