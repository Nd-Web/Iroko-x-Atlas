# Iroko AI — Live Demo Runbook (July 17)

## Before the meeting (30–10 minutes prior)

1. **Warm up the backend** — Render free-tier cold starts take 60s+:
   - Open `https://iroko-x-atlas.onrender.com/health` → wait for `{"status":"ok"}`.
   - Log in once and send one chat message so the LLM path is warm.
2. **Deploy the latest backend** — the repositioning changed backend files
   (`main.py`, `agents/researcher.py`, `agents/strategist.py`, `services/fraud_service.py`,
   `routes/search.py`, `services/document_processor.py`). Push to the branch Render deploys
   from and confirm the redeploy finished BEFORE the meeting. Without it, the old fintech
   fallbacks and the broken `/api/search` org filter are still live.
3. **Frontend env** — `frontend/.env.local` now points at the Render backend. If you demo a
   locally-run frontend (`npm run dev`), nothing else to change. If you demo the deployed
   frontend, confirm its `NEXT_PUBLIC_API_URL` also points at Render.
4. Have a **sample document ready to upload** (any PDF/txt — e.g. one of
   `backend/scripts/sample_docs/*.txt` renamed) for the live-upload moment.

## Login

- **admin@mtn.ng / AtlasAdmin2026!** (superadmin, org "MTN Nigeria") — verified working on Render.
- Do NOT click "Sign up" (disabled by design; redirects to login).

## The strong demo path (all verified live)

1. **Login** → lands on Dashboard (live intel signals, compliance check panel).
2. **Chat** (`/chat`) — ask: *"What caused the Ikeja cluster power outage and what did it cost us?"*
   → streams agent actions (Strategist → Researcher → Watchdog → Analyst) then an executive
   answer with citations. Conversation list in the sidebar is live; clicking one loads its history.
   Follow-up: *"What penalties apply if IHS misses the diesel backup SLA again?"*
3. **Alerts** (`/agents/noc`, sidebar "Alerts") — live seeded alerts; **Acknowledge/Resolve work**.
   The Ikeja availability gauge shows a deliberate 82.7% BREACH — good talking point.
   "Ask Watchdog" panel is live chat.
4. **Search** (`/search`) — try *"IHS diesel backup SLA penalties"* → live hybrid search over the
   indexed telco corpus (requires backend redeploy, see above).
5. **Documents** (`/documents`) — shows the 8 indexed documents; **Upload works live**
   (extract → chunk → embed → index) with progress toasts.
6. **Insights** (`/insights`) — live seeded alerts as insights (SLA breach, NCC deadline,
   MoMo complaint spike); Review/Dismiss work.
7. **Network Intelligence** (`/network-intelligence`) — Nigeria map + incidents (live from
   `/api/network` with seeded data, falls back to matching constants).
8. **Audit Trail** (`/audit-trail`) — live entries via the intel API when available; search box
   filters; **Export CSV downloads a real file**.
9. **Compliance Reports** (`/compliance/reports`) — live compliance checker
   (*"We plan to launch a new analytics pipeline on MoMo transaction data next quarter — what
   NDPA obligations apply?"*); report/DSR/DPIA modals show real detail views.
10. **User Management** — fully live (list, invite, roles view).
11. Finish on **Analytics** (`/analytics`) — agent performance overview.

## Avoid on stage

- `/agents/care`, `/agents/field`, `/agents/compliance`, `/agents/contracts` — re-flavored and
  coherent, but data is static and some secondary buttons ("View all", "Get script", "+ New DPIA")
  are demo-only.
- `/settings/integrations` (static "connected" cards) — use `/integrations` (live OAuth) instead.
- Deep multi-turn Pidgin conversations — supported, but keep it to one flourish.

## If something fails live

- Chat now shows a visible **error banner with Retry** instead of a vanishing bubble.
- Every live page falls back to canonical telecom demo data that matches the seeded corpus —
  the story stays coherent even offline.
- Alerts page badge says "DEMO DATA" instead of "LIVE MONITORING" when it's on fallback —
  glance at it before showing.

## Known rough edges (post-demo backlog)

- Repo docs (READMEs, HACKATHON_SETUP.md) still carry old positioning + hardcoded creds.
- Duplicate auth route trees (`app/(auth)/*` vs `app/auth/*`); dead footer links on the homepage.
- `/api/fraud` page surface: fraud signals are canned (now telecom-flavored) — no DB.
- Render free tier will cold-start again if idle >15 min — keep a tab pinging `/health`
  during the meeting.
