# Iroko AI × MTN — Full Demo Script

**Target: 15–18 minutes + Q&A.** Every question, click, and number in this script has been verified against the live system.

---

## The problem statement (read it back to them first)

> *"Telecom employees work across vast volumes of fragmented documents — stored in multiple systems and formats. This fragmentation makes it time-consuming to locate critical information, derive insights, and make timely decisions, reducing overall work efficiency. Design an AI-driven solution that aggregates, understands, and analyzes enterprise documents in real time, delivering contextual insights, analytics for improved productivity."*

Your demo maps 1-to-1 onto its four verbs: **AGGREGATE → UNDERSTAND → ACT → MEASURE.** Say that out loud at the start — it's your table of contents.

---

## Pre-flight checklist (do this 15 minutes before)

1. **Wake the backend.** Open irokoai.site and log in ~10 min before you present. The free-tier server sleeps; the first hit takes ~60s to cold-start. Never let the audience see the cold start.
2. **Warm the AI.** Ask one throwaway question in Chat ("hello") so the model path is warm.
3. **Hard-refresh** (Ctrl+Shift+R) each page you'll show.
4. Log in as **admin@mtn.ng / AtlasAdmin2026!** (superadmin — sees everything).
5. Have the **Workflows** page open in a second tab, already loaded.
6. Close every unrelated tab. Full-screen the browser (F11).

**Timing reality:** live AI answers take **20–45 seconds** — that is your narration window, not dead air. The script tells you exactly what to say while it thinks.

---

## COLD OPEN — the hook (1 min)

*Stand on the login page. Don't touch anything yet.*

> "Somewhere in MTN right now, an engineer is looking for one clause in a vendor contract. It's in SharePoint — or Teams, or an email attachment, or a shared drive. Industry studies put that search at **15 to 30 minutes per request**. Multiply that by every employee, every request, every day — that's the productivity leak in the problem statement.
>
> But the cost isn't just time. When the answer arrives late, the NCC return is filed late at **₦5 million per day**, the SLA penalty goes unclaimed, the contract auto-lapses. Fragmentation isn't an inconvenience — it's unclaimed money and regulatory exposure.
>
> Iroko AI closes that gap in four moves: it **aggregates** the fragmented documents, **understands** them, turns insight into **action**, and **measures** the productivity it returns. Let me show you each one."

*Log in. The MTN × Iroko dark interface loads.*

> "Built for MTN — your brand, your regulators, your vendors, your Nigeria."

---

## ACT 1 — AGGREGATE (2 min) · *Documents + Connectors*

**Go to: Documents**

> "Move one: get everything into one brain. This corpus holds MTN's operational reality — an RCA for the Ikeja outage, the IHS tower lease, an Ericsson RAN SLA, the NCC QoS quarterly return, an NDPA processing record, MoMo complaint analyses, enterprise customer SLAs. PDF, DOCX, XLSX — every format, one searchable index. Each document is parsed, semantically chunked, and vectorised the moment it lands."

**Go to: Connectors**

> "And nobody has to upload anything manually. Iroko connects directly to **SharePoint, OneDrive, Microsoft Teams, and Slack** with enterprise OAuth — and then **auto-syncs every five minutes**. A contract dropped into SharePoint is searchable intelligence five minutes later, automatically. This is how fragmentation ends: not by asking people to change where they store things, but by meeting the documents where they already live."

**Why they need it:** *"Your documents stay where they are. The intelligence layer comes to them."*

---

## ACT 2 — UNDERSTAND (5 min) · *Chat: the multi-agent brain*

**Go to: Chat.** Type exactly:

> **"What caused the Ikeja cluster outage and what is our SLA exposure?"**

*While it thinks (~30s), point at the Reasoning Chain panel:*

> "Watch the right side — this is not a chatbot wrapper. Five specialist agents are working: the **Researcher** is running hybrid semantic search across the corpus; the **Watchdog** is checking coverage and compliance risk; the **Analyst** is computing the financial exposure; the **Strategist** is synthesising; and a verdict engine stamps a GO / MONITOR / NO-GO decision. Every step is visible — no black box, which matters when a regulator asks *why* the system said what it said."

*The answer lands: root cause (AES feeder failure + IHS diesel backup miss), availability 82.7% vs the NCC 95% floor, **₦2.66M SLA exposure**, recommended actions.*

> "Thirty seconds. The manual version of this answer is an engineer opening the RCA, the IHS contract, and the NCC return — three documents in three places — and doing the penalty arithmetic by hand. That's the 15-to-30-minute search, done in half a minute, **with citations back to the source documents** so every claim is checkable."

**Now the hard one.** Type:

> **"What NDPA rules govern data localization and model explainability for our AI tools?"**

*While it thinks:*

> "This is the question that kills generic chatbots — it needs *Nigerian* regulatory depth, not internet averages. Iroko carries a built-in NCC and NDPA/NDPR knowledge base: sections, penalty figures, enforcement precedents."

*The answer lands: NDPA §41 cross-border transfers, §28 DPIA, §32 automated-decision transparency, penalties up to ₦10M or 2% of annual gross revenue, the MultiChoice ₦766M precedent.*

> "Section numbers. Naira figures. Real enforcement precedents. This is a regulatory analyst's briefing, on demand, in under a minute — and the same engine powers a **voice compliance agent**: you can literally *call* Iroko and ask a compliance question out loud, and it answers in a Nigerian voice." *(Optionally demo: Compliance tab → start call → "Can we store subscriber data in a US cloud region?")*

**Why they need it:** *"Every employee gets the recall of your best analyst — network ops, legal, procurement, CX — without waiting in anyone's queue."*

---

## ACT 3 — ACT (4 min) · *Workflows: the problem statement's first word*

**Go to: Workflows** *(your pre-loaded tab — it's already populated).*

> "MTN titled this challenge **'Workflow Management** and Realtime Analytics' — so here's the part most document-AI tools never build: what happens *after* the insight.
>
> Iroko doesn't stop at telling you something is wrong. Every risk its Watchdog finds becomes a **task** — automatically **routed to the owning department** with a **priority and an SLA clock**. Contract expiry goes to Procurement. A complaint spike goes to Customer Experience. A policy conflict goes to Regulatory Affairs. Critical items get a 24-hour clock; warnings get 72."

*Point at the board: 12 tasks across Procurement, Regulatory Affairs, CX, Network Operations — each with priority badge and due date.*

**Click "Run Intelligence Sweep."**

> "This button is the whole thesis in one click: the Watchdog re-scans the entire corpus right now — expiring contracts, complaint spikes, policy conflicts, regulatory deadlines — and every new finding lands here as an owned, deadlined task. Documents in; routed work out. No human had to notice the risk, write the ticket, or decide who owns it."

**Then show the compliance-to-action loop.** Go to Compliance → checker → type: *"Activate 5,000 SIM cards without NIN verification"* → Check.

> "**NO-GO.** And here's the part I want you to remember —" *(switch to Workflows tab, refresh)* "— that verdict just became a **Regulatory Affairs task with a 24-hour SLA**, automatically. The 2015 SIM-registration fine was **₦1.04 trillion**. This loop — detect, decide, assign, deadline — is what 'workflow management' means when an AI does it."

**Why they need it:** *"Insights that don't become actions are just interesting. Iroko closes the loop."*

---

## ACT 4 — MEASURE (3 min) · *Analytics + Knowledge Graph*

**Go to: Analytics**

> "The problem statement asks for improved productivity — so we **measure it, honestly**. This isn't a vanity dashboard: every number is computed from real usage. Average time-to-answer: about **5 seconds of AI work versus a 15-minute manual baseline** — and we deliberately used the *conservative* end of the industry's 15-to-30-minute range. That compounds to **~14 staff-hours returned in 30 days** at demo usage. Scale that to thousands of employees and this system pays for itself on time-saved alone — before you count a single avoided penalty."

*Point at: queries trend (real per-day counts), tasks auto-generated, chunks searchable.*

**Go to: Knowledge Graph**

> "And here's the corpus as your organisation actually is: **57 nodes, ~70 relationships**, built live from the documents — every vendor, regulator, regulation, contract, alert, and action task, connected. Click IHS Nigeria —" *(click a vendor node)* "— and you see everything it touches: the tower lease, the Ikeja RCA, the SLA-breach alert, the recovery task. When you ask *'what's our exposure if this vendor fails?'*, this web is how Iroko connects dots that no keyword search ever could."

**Why they need it:** *"You can't manage what you can't see. This is the first time the document estate has a live map and a live productivity meter."*

---

## CLOSE (1 min)

> "Back to the problem statement — one line each:
> - **Fragmented documents in multiple systems?** Auto-synced connectors, one intelligent index. *Aggregate.*
> - **Time-consuming to locate information and derive insights?** Cited, multi-agent answers in ~30 seconds against a 15-minute baseline. *Understand.*
> - **Timely decisions?** Every insight becomes a routed, SLA-tracked task; every compliance NO-GO becomes an assignment. *Act.*
> - **Improved productivity?** Measured live — hours saved, time-to-answer, throughput. *Measure.*
>
> Everything you watched ran on realistic seeded MTN data — because the moment you connect your SharePoint, **this exact pipeline runs on your real documents. Nothing has to be rebuilt.** The system is live, audited, role-based, and running on Azure today. The question isn't whether the technology works — you just watched it. The question is how many 15-minute searches MTN wants to keep paying for."

---

## Q&A — objection handling

**"Is this real data?"**
> "Realistic seeded MTN operational data — we don't have access to your production documents yet, deliberately. But nothing here is a mock-up: the same ingestion, search, AI, and workflow pipeline runs end-to-end on it. Connect SharePoint and the identical system runs on your real corpus, day one."

**"What about hallucinations?"**
> "Three defences: answers are **grounded** in retrieved document chunks, not the model's imagination; **citations** on answers let anyone verify the source; and a **corrective-RAG gate** flags low-coverage answers as knowledge gaps instead of bluffing. Plus the full reasoning chain is visible per answer."

**"Security and access?"**
> "Role-based access (superadmin/admin/analyst/viewer), JWT auth, an **immutable hash-chained audit trail** of every agent decision — built for regulated industries. Runs entirely on Azure; deployable inside MTN's own tenant so no document leaves your control."

**"Which AI models?"**
> "Azure OpenAI GPT-5.6, tiered: a fast model for routing, a workhorse for answers, and the flagship reserved for high-stakes compliance verdicts — quality where it matters, speed where users feel it."

**"What does scaling look like?"**
> "Every component is a managed Azure service — AI Search, OpenAI, blob storage — that scales by configuration, not re-architecture. The demo runs on minimal tiers; production is a tier change and connecting your tenant."

**"What would a pilot look like?"**
> "Pick one department — say Procurement. Connect its SharePoint library, 2–3 weeks, and we measure: time-to-answer, contracts flagged before expiry, tasks auto-routed. The productivity dashboard you saw becomes the pilot's scorecard. It measures its own ROI."

---

## Emergency fallbacks

| Problem | Move |
|---|---|
| Backend cold / slow first answer | You pre-warmed it. If it still lags: "It's on a free demo tier — production runs on dedicated capacity" — and narrate the reasoning chain while waiting. |
| Chat answer takes 45s+ | Never stand silent: walk through the agent steps on screen — that IS the demo. |
| A page looks empty | Hard-refresh (Ctrl+Shift+R). Workflows: click Run Intelligence Sweep to repopulate live. |
| Internet dies | Fall back to the local build (backend venv + `npm run dev`) — same system, same data. |
| Voice agent flaky on venue Wi-Fi | Skip it: "happy to show the voice agent after" — nothing else depends on it. |

**Demo logins**
- `admin@mtn.ng / AtlasAdmin2026!` — superadmin (use this)
- `adaeze.nwosu@mtn.ng / Password2026!` — Legal analyst (if showing roles)

**The one-sentence pitch, memorised:**
> "Iroko turns MTN's fragmented documents into cited answers in thirty seconds, turns those answers into routed tasks with deadlines, and proves the hours it gives back — on your Azure, with your regulators built in."
