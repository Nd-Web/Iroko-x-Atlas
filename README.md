<div align="center">

# 🌳 IROKO AI
### Enterprise Web Intelligence for African Telecoms

[![FastAPI](https://img.shields.io/badge/FastAPI-0.115-009688?style=for-the-badge&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![Semantic Kernel](https://img.shields.io/badge/Semantic_Kernel-1.11-5C2D91?style=for-the-badge&logo=microsoft&logoColor=white)](https://github.com/microsoft/semantic-kernel)
[![Azure OpenAI](https://img.shields.io/badge/Azure_OpenAI-GPT--4o-0078D4?style=for-the-badge&logo=microsoftazure&logoColor=white)](https://azure.microsoft.com/en-us/products/ai-services/openai-service)
[![Bright Data](https://img.shields.io/badge/Bright_Data-Web_Intelligence-FF6B35?style=for-the-badge)](https://brightdata.com)
[![Next.js](https://img.shields.io/badge/Next.js-14-000000?style=for-the-badge&logo=nextdotjs&logoColor=white)](https://nextjs.org)
[![Railway](https://img.shields.io/badge/Railway-Deployed-0B0D0E?style=for-the-badge&logo=railway&logoColor=white)](https://railway.app)

*Built for the **Web Data Unlocked** Hackathon — Bright Data × NVIDIA × LabLab.ai · May 25–31, 2026*

🎥 [Demo Video](#) &nbsp;|&nbsp; 🚀 [Live Platform](#) &nbsp;|&nbsp; 📄 [API Docs](#)

</div>

---

> **With over $3.5 billion annually lost to telecom fraud and cybercrime in Africa, ₦2.97 billion in recent NCC service quality sanctions, and the sudden April 2026 suspension of MTN's high-margin "Xtratime" service, African telcos operate in a high-stakes environment.** These critical events break first on the open web, yet operators continue to make decisions without live web intelligence.

Nigerian telecoms operate inside one of the most aggressive regulatory environments on the continent. The NCC issues enforcement updates, frequency directives, and consumer protection rulings continuously — none of it available via structured API. Competitive signals (tariff undercuts, infrastructure deals, spectrum acquisitions) break first on the open web, days before they reach internal intelligence channels. Fraud patterns evolve weekly. Vendor risk surfaces in procurement news before it surfaces in contracts. The operators making billion-naira capital allocation decisions are doing so with data that is weeks stale.

**Iroko AI is the fix.** It deploys five specialised AI agents against live web sources, applies Nigeria-specific NCC regulatory logic, and delivers GO / NO-GO / MONITOR verdicts with a SHA-256-chained audit trail that maps every finding to specific NCC regulation sections — in real time, before the decision is made.

---

## What Iroko AI Does

- **Monitors five live intelligence domains simultaneously** — NCC regulatory updates, competitor moves (MTN, Airtel, Glo, 9mobile), vendor risk signals, active fraud patterns, and market shifts — pulling fresh data from the open web on every query via Bright Data connectors.
- **Converts raw web signals into compliance verdicts** — a multi-stage pipeline runs signals through a signal knowledge graph (NetworkX compound risk detection), an adversarial debate sub-agent (threat vs. noise), institutional memory recall, and a VerdictEngine that outputs GO / MONITOR / NO-GO with mapped NCC regulation references.
- **Generates a tamper-evident audit trail** — every agent action, verdict, and compliance check is written to a SHA-256 hash-chained log pinned to the exact NCC regulation section it references, providing regulator-ready evidence of due diligence.
- **Streams live reasoning via SSE** — the full 6-stage web intelligence pipeline streams agent reasoning steps to the frontend in real time, so compliance teams see exactly how a verdict was reached, not just what it was.
- **Produces boardroom-ready compliance briefs** — on demand, a PDF brief (ReportLab) consolidates the live signal scan, compound risk entities, verdict, NCC references, and recommended actions into a single downloadable document.

---

## Why Bright Data Is Essential

African government and telecom web sources present a class of problems that standard HTTP clients cannot solve. Iroko AI uses **all five** Bright Data product surfaces — this is not an optional integration, it is load-bearing infrastructure.

**Web Unlocker** is the foundation layer. `ncc.gov.ng` is a JavaScript-rendered portal that blocks datacenter IP ranges and returns empty DOM to headless browsers without residential proxy resolution. The same is true for NCC enforcement bulletin pages, Nigerian court record portals, and telco investor relations pages. Web Unlocker's residential proxy network — combined with automatic Cloudflare and bot-detection bypass — is the only reliable way to retrieve this content programmatically. Every call to `fetch_regulatory_signals()`, `fetch_vendor_risk_signals()`, and `fetch_fraud_signals()` routes through Web Unlocker.

**SERP API** powers real-time competitive and market signal collection. `fetch_competitor_signals()` and `fetch_market_intel_signals()` issue structured Google/Bing SERP queries — "MTN Nigeria tariff 2026", "Airtel spectrum acquisition", "NCC fine Q2 2026" — and receive ranked, structured results without browser overhead. This allows the agent pipeline to sweep five competitive dimensions in parallel in under 10 seconds. Without SERP API, this would require a fleet of browser instances.

**Web Scraper API** (Bright Data Datasets v3) handles schema-driven extraction for structured sources — telecom procurement portals, stock exchange filings, and regulatory gazette PDFs — where raw HTML extraction would require custom parsers per site. The `scrape_structured()` method submits a schema and URL to the Datasets trigger endpoint and receives clean, typed data. The system gracefully falls back to Web Unlocker + raw HTML when the Datasets API is unreachable, ensuring no signal category goes dark.

**Scraping Browser** handles the hardest extraction cases — JS-heavy government regulatory portals with lazy-loaded tables, dynamically paginated enforcement documents, and interactive NCC data pages that require clicks and scrolls to reveal complete content. When the Researcher Agent detects that a static Web Unlocker fetch returned incomplete or empty DOM, it escalates to Scraping Browser, which opens a full Playwright browser session over Bright Data's Chrome DevTools Protocol (CDP) endpoint with residential proxy routing. The agent programmatically scrolls the page, clicks pagination controls, and waits for dynamic content to load before extracting the full regulatory text. This gracefully falls back to Web Unlocker when the Scraping Browser zone is unavailable.

**MCP Server** (Model Context Protocol) enables LLM-native web access. The Semantic Kernel agent pipeline can invoke Bright Data's MCP server directly from agent tool calls, allowing agents to request live web data mid-reasoning without round-tripping to the FastAPI layer. This is what makes the streaming pipeline genuinely agentic — agents don't receive pre-fetched context, they pull the web data they need when they need it, within the reasoning loop.

---

## Architecture

```
╔══════════════════════════════════════════════════════════════════════════════╗
║                         IROKO AI — WEB INTELLIGENCE PLATFORM                ║
╠══════════════════════════════════════════════════════════════════════════════╣
║                                                                              ║
║   ┌─────────────────────────────────────────────────────────────────────┐   ║
║   │                    BRIGHT DATA INTELLIGENCE LAYER                   │   ║
║   │                                                                     │   ║
║   │  ┌────────────┐ ┌──────────┐ ┌────────────┐ ┌───────────┐ ┌────────┐│   ║
║   │  │Web Unlocker│ │ SERP API │ │Web Scraper │ │ Scraping  │ │  MCP   ││   ║
║   │  │ncc.gov.ng  │ │Competitor│ │   API      │ │ Browser   │ │ Server ││   ║
║   │  │Fraud portal│ │Market    │ │Structured  │ │JS-heavy   │ │LLM-    ││   ║
║   │  │Vendor sites│ │sweeps    │ │extraction  │ │govt pages │ │native  ││   ║
║   │  └─────┬──────┘ └────┬─────┘ └─────┬──────┘ └─────┬─────┘ └───┬───┘│   ║
║   └────────┼─────────────┼─────────────┼──────────────┼────────────┼────┘   ║
║            └─────────────┴─────────────┴──────────────┴────────────┘        ║
║                                      │                                      ║
║                          run_all_signals(client)                            ║
║                   [regulatory · competitor · vendor_risk                    ║
║                         · fraud · market_intel]                             ║
║                                      │                                      ║
║   ┌──────────────────────────────────▼──────────────────────────────────┐  ║
║   │                      5-AGENT SEMANTIC KERNEL PIPELINE               │  ║
║   │                                                                     │  ║
║   │  ┌─────────────┐   ┌─────────────┐   ┌─────────────┐              │  ║
║   │  │  RESEARCHER │   │  WATCHDOG   │   │   ANALYST   │              │  ║
║   │  │             │   │             │   │             │              │  ║
║   │  │ Regulatory  │   │ Competitor  │   │ Vendor Risk │              │  ║
║   │  │ signals +   │   │ + fraud     │   │ + debate    │              │  ║
║   │  │ NCC corpus  │   │ signals +   │   │ sub-agents  │              │  ║
║   │  │ Azure Search│   │ audit write │   │ + graph     │              │  ║
║   │  └──────┬──────┘   └──────┬──────┘   └──────┬──────┘              │  ║
║   │         │                 │                  │                     │  ║
║   │  ┌──────▼──────┐   ┌──────▼────────────────────────────────────┐  │  ║
║   │  │ STRATEGIST  │   │                  SCRIBE                   │  │  ║
║   │  │             │   │                                           │  │  ║
║   │  │ Market intel│   │  Report generation · PDF brief · Audit   │  │  ║
║   │  │ + verdict   │   │  synthesis · NCC reference formatting     │  │  ║
║   │  │ orchestrate │   │                                           │  │  ║
║   │  └──────┬──────┘   └───────────────────────┬───────────────────┘  │  ║
║   └─────────┼───────────────────────────────────┼───────────────────────┘  ║
║             │                                   │                           ║
║   ┌─────────▼───────────────────────────────────▼───────────────────────┐  ║
║   │                    INTELLIGENCE SERVICES LAYER                      │  ║
║   │                                                                     │  ║
║   │  ┌──────────────┐  ┌──────────────┐  ┌─────────────────────────┐  │  ║
║   │  │Signal Graph  │  │  Verdict     │  │   NCC Live Rules        │  │  ║
║   │  │(NetworkX)    │  │  Engine      │  │   (PDF→enforcement)     │  │  ║
║   │  │Compound risk │  │  GO/MONITOR/ │  │   Section mapping       │  │  ║
║   │  │detection     │  │  NO-GO       │  │   Live delta tracking   │  │  ║
║   │  └──────────────┘  └──────────────┘  └─────────────────────────┘  │  ║
║   │                                                                     │  ║
║   │  ┌──────────────┐  ┌──────────────┐  ┌─────────────────────────┐  │  ║
║   │  │ Regulatory   │  │    Fraud     │  │   Capability Guard      │  │  ║
║   │  │ Memory       │  │ Intelligence │  │   (Heimdall pattern)    │  │  ║
║   │  │ (historical  │  │ (noise filter│  │   Per-agent scoping     │  │  ║
║   │  │  recall)     │  │ + LLM triage)│  │   PermissionError guard │  │  ║
║   │  └──────────────┘  └──────────────┘  └─────────────────────────┘  │  ║
║   └─────────────────────────────────────────────────────────────────────┘  ║
║                                      │                                      ║
║   ┌──────────────────────────────────▼──────────────────────────────────┐  ║
║   │                   SHA-256 HASH-CHAINED AUDIT TRAIL                  │  ║
║   │     Every verdict · Every agent action · Every NCC section ref      │  ║
║   │     Tamper-evident · Verifiable · Regulator-ready                   │  ║
║   └─────────────────────────────────────────────────────────────────────┘  ║
║                                      │                                      ║
║   ┌──────────────────────────────────▼──────────────────────────────────┐  ║
║   │          NEXT.JS 14 DASHBOARD — 3-TAB INTELLIGENCE PANEL           │  ║
║   │   Live Signals · Verdict & Compliance · Audit Trail + Chain Badge   │  ║
║   └─────────────────────────────────────────────────────────────────────┘  ║
╚══════════════════════════════════════════════════════════════════════════════╝
```

---

## Hackathon Track Coverage

| Track | Iroko AI Capability | Implementation |
|---|---|---|
| **GTM Intelligence** | Competitor signal sweep across all 4 Nigerian MNOs | `fetch_competitor_signals()` → SERP API → Watchdog agent → compound risk graph |
| **GTM Intelligence** | Market entry signal detection (infrastructure deals, spectrum) | `fetch_market_intel_signals()` → StrategistAgent → GO/MONITOR verdict |
| **Finance & Market Intelligence** | Vendor financial risk assessment with adversarial debate | `fetch_vendor_risk_signals()` → ThreatDebateAgent (argue\_threat ∥ argue\_noise) → reconcile() |
| **Finance & Market Intelligence** | Compound risk scoring across correlated signals | SignalGraphService (NetworkX DiGraph) → volume-boosted compound\_risk\_score |
| **Finance & Market Intelligence** | Institutional memory for historical regulatory impact | RegulatoryMemoryService → keyword-Jaccard similarity → lessons\_learned injection |
| **Security & Compliance** | NCC PDF → live enforcement rules auto-compilation | `ncc_live_rules.py` → `compile_live_enforcement_rules()` → regulation section delta |
| **Security & Compliance** | GO / NO-GO / MONITOR verdict per decision | VerdictEngine → `check_decision_against_rules()` → mapped NCC refs + violations |
| **Security & Compliance** | SHA-256 hash-chained, tamper-evident audit trail | AuditService → chain integrity verification → `GET /api/v1/intel/audit-trail?verify_chain=true` |
| **Security & Compliance** | Per-agent capability enforcement (zero scope creep) | CapabilityGuard → `require()` → PermissionError on violation → audit\_access\_attempt() |
| **Security & Compliance** | Multi-source fraud noise filter + LLM triage | FraudIntelligenceService → entity gate + Jaccard dedup + llm\_triage → fraud alert |

---

## Architectural Inspirations

This system assembled patterns from ten reference projects, each contributing a distinct architectural principle:

| Reference Project | Pattern Borrowed | Applied In |
|---|---|---|
| **ContextBridge** | Institutional memory layer with historical event recall | `regulatory_memory.py` — RegulatoryMemoryEntry + Jaccard similarity search |
| **NexusGraph AI** | In-memory signal correlation graph, compound risk scoring | `signal_graph.py` — NetworkX DiGraph, volume-boost compound score formula |
| **BrandIntel** | Multi-source signal collection → noise filter → alert pipeline | `fraud_intelligence.py` — collect → filter → triage → verdict |
| **Diligence** | Adversarial sub-agent debate (pro/con) → reconciler scoring | `debate_agent.py` — `argue_threat` ∥ `argue_noise` → `reconcile()` |
| **Heimdall** | Cryptographic-style permission scoping per agent | `agent_capabilities.py` — AgentCapability enum + CapabilityGuard |
| **InsightForge** | Boardroom-ready intelligence panel, multi-tab dashboard | `WebIntelDashboard.tsx` — Live Signals, Verdict & Compliance, Audit Trail |
| **Foxhole** | Sharp opening statistic hook, confident technical framing | This README — $500m statistic as first sentence |
| **Core Iroko Architecture** | Streaming SSE reasoning pipeline with per-step yield | `orchestrator.py` → `web_intel_pipeline()` — 6-stage async generator |
| **Core Iroko Architecture** | FastAPI router pattern with Pydantic response models | `routes/web_intel.py` — 6 typed endpoints |
| **Core Iroko Architecture** | BaseAgent with `_log_trace()` and `_with_retry()` | All 5 specialist agents + ThreatDebateAgent |

---

## Setup

### Prerequisites

- Python 3.11+, Node.js 18+
- Azure OpenAI resource (GPT-4o deployment)
- Bright Data account with Web Unlocker, SERP API, Web Scraper API enabled
- PostgreSQL 16 (or Docker)

### Environment Variables

```bash
# Azure OpenAI
AZURE_OPENAI_ENDPOINT=https://your-resource.openai.azure.com/
AZURE_OPENAI_API_KEY=your-key
AZURE_OPENAI_DEPLOYMENT=gpt-4o
AZURE_OPENAI_EMBEDDING_DEPLOYMENT=text-embedding-3-large

# Bright Data
BRIGHTDATA_API_KEY=your-bright-data-api-key
BRIGHTDATA_WEB_UNLOCKER_ZONE=isp_proxy1
BRIGHTDATA_SERP_ZONE=serp_api1
BRIGHTDATA_SCRAPER_DATASET_ID=your-dataset-id
BRIGHTDATA_MCP_SERVER_URL=https://mcp.brightdata.com  # optional

# Database
DATABASE_URL=postgresql://user:pass@localhost:5432/iroko
SECRET_KEY=your-jwt-secret

# Azure AI Search (optional — for document RAG)
AZURE_SEARCH_ENDPOINT=https://your-search.search.windows.net
AZURE_SEARCH_KEY=your-search-key
AZURE_SEARCH_INDEX=iroko-chunks
```

### Bright Data Setup

1. Log in to [brightdata.com](https://brightdata.com) and create a project.
2. Enable three zones: **Web Unlocker** (residential), **SERP API**, and **Web Scraper API** (Datasets v3).
3. Copy the API key and zone names to your `.env`.
4. (Optional) Enable the **MCP Server** add-on and set `BRIGHTDATA_MCP_SERVER_URL`.

### Run Backend

```bash
cd backend
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
# API docs: http://localhost:8000/docs
```

### Run Frontend

```bash
cd frontend
npm install
npm run dev
# Dashboard: http://localhost:3000
```

### Docker (full stack)

```bash
docker-compose up --build
# Frontend: http://localhost:3000
# Backend:  http://localhost:8000/docs
# Login:    admin@mtn.ng / AtlasAdmin2026!
```

### Key API Endpoints

```
GET  /api/v1/intel/signals              # Live signals — all 5 domains
GET  /api/v1/intel/regulatory           # NCC live enforcement rules
POST /api/v1/intel/check-compliance     # Verdict check for a decision text
GET  /api/v1/intel/audit-trail          # Hash-chained audit trail
GET  /api/v1/intel/brief                # PDF compliance brief (download)
GET  /api/v1/intel/health               # Bright Data connection status
GET  /api/v1/intel/stream?query=...     # SSE streaming pipeline
```

---

## What Makes This Submission Different

**1. African market monopoly — built for no one else.**
Every design decision is Africa-specific: the NCC regulation corpus, the four Nigerian MNO competitive map (MTN, Airtel, Glo, 9mobile), the web sources (ncc.gov.ng, Nigerian court portals, local telco investor pages), the fraud signal patterns (MoMo abuse, SIM swap, interconnect fraud). This is not a generic compliance tool with a Nigeria flag. The entity extraction, regulation mapping, and signal weighting are tuned to the specific intelligence needs of operators under NCC jurisdiction. No other submission in this hackathon is solving this problem for this market.

**2. A compliance audit trail that would survive a regulator audit.**
The hash-chained SHA-256 audit log is not a dashboard feature — it is the accountability layer. Every compliance check is written as a chain entry that references the specific NCC regulation section it evaluated against. `verify_chain_integrity()` detects any post-hoc modification. A telecom operator could hand this log to the NCC in a dispute and demonstrate exactly what signals were seen, what verdict was issued, and when — with a cryptographic proof that the record was not altered. No other submission in this space produces audit evidence at this fidelity.

**3. Adversarial debate agents — verdicts that have been challenged before they reach you.**
When a vendor risk signal fires, Iroko AI does not just surface it. It spawns two sub-agents: one makes the strongest possible case that the signal is a genuine threat; the other makes the strongest possible case that it is noise. A senior reconciler reads both arguments and issues a confidence-weighted verdict. This is not a gimmick — it is a systematic way to reduce false-positive fatigue in compliance workflows. Operators act on NO-GO verdicts. A verdict that has already survived an adversarial challenge is a verdict worth acting on.

---

## Team

**Ndubuisi Ekeh** — AI Lead, Lagos, Nigeria  
TeKnowledge × Microsoft 2026 Agentic AI Hackathon Finalist  
Building production AI systems for African enterprise since 2023.

---

## License

Hackathon submission — all rights reserved, Iroko AI / Ndubuisi Ekeh, 2026.
