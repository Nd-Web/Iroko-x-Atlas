# Iroko AI — Powered by Atlas

> **Multi-agent enterprise document intelligence for MTN Nigeria**

---

## Demo

🎥 [Watch the demo video](#) &nbsp;|&nbsp; 🚀 [Live demo](#)

<!-- Replace # with actual URLs when available -->

![Iroko AI Dashboard — Ask Atlas anything about MTN's enterprise document estate](./backend/mtn_logo.jpg)

---

## The Problem

Telecom employees at MTN Nigeria work across thousands of fragmented documents spread across multiple systems and formats — RCA reports, vendor contracts, NCC regulatory filings, customer complaint logs, BoQ spreadsheets, and more. Finding critical information, deriving cross-document insights, and acting on time-sensitive issues (expiring contracts, compliance deadlines, complaint spikes) takes hours when it should take seconds.

## The Solution

**Iroko AI**, powered by Atlas, is a multi-agent AI system that ingests, indexes, and reasons across an enterprise's entire document estate. Ask it a question in plain English — or Nigerian Pidgin — and five specialised AI agents collaborate to search the knowledge base, analyse the data, validate confidence, and synthesise a cited answer with actionable recommendations, all in under 10 seconds.

---

## Quick Start

### Prerequisites

- **Docker + Docker Compose**
- **Azure OpenAI resource** (GPT-4o deployment)
- **Azure AI Search resource**

### 1. Clone and configure

```bash
git clone <repo>
cd iroko-ai-v2
cp .env.example backend/.env
# Edit backend/.env with your Azure credentials
```

### 2. Run with Docker

```bash
docker-compose up --build
```

### 3. Open

| Service | URL |
|---|---|
| **Frontend** | [http://localhost:3000](http://localhost:3000) |
| **API docs** | [http://localhost:8000/docs](http://localhost:8000/docs) |
| **Default login** | `admin@mtn.ng` / `AtlasAdmin2026!` |

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    Iroko AI — Powered by Atlas                  │
│                                                                 │
│  ┌──────────┐  REST / SSE / WebSocket  ┌─────────────────────┐ │
│  │ Frontend │ ◄────────────────────── │   FastAPI Backend    │ │
│  │ (Next.js)│                          │                     │ │
│  └──────────┘                          │  ┌───────────────┐  │ │
│                                        │  │  Strategist   │  │ │
│                                        │  │ (Orchestrator)│  │ │
│                                        │  └──────┬────────┘  │ │
│                                        │         │           │ │
│             ┌──────────────────────────┼─────────┼─────────┐ │ │
│             │    Agent Pipeline        │         │         │ │ │
│             │  ┌────────────┐  ┌───────┴───┐  ┌─┴──────┐  │ │ │
│             │  │ Researcher │  │  Analyst  │  │Watchdog│  │ │ │
│             │  └─────┬──────┘  └─────┬─────┘  └───┬────┘  │ │ │
│             │        │               │             │       │ │ │
│             │  ┌─────┴──────┐  ┌─────┴─────────────┴────┐ │ │ │
│             │  │   Scribe   │  │    Azure AI Services    │ │ │ │
│             │  └────────────┘  └───────────────────────┬─┘ │ │ │
│             └─────────────────────────────────────────┼───┘ │ │
│                                                       │     │ │
│  ┌────────────────────────────────────────────────────▼───┐ │ │
│  │                    Azure Infrastructure                 │ │ │
│  │  AI Search      Cosmos DB       Blob Storage   OpenAI   │ │ │
│  │  (iroko-chunks) (Gremlin Graph) (raw-docs)    (GPT+Emb) │ │ │
│  │  Doc Intelligence   Key Vault    Speech    AI Foundry   │ │ │
│  └─────────────────────────────────────────────────────────┘ │ │
└─────────────────────────────────────────────────────────────────┘
```

---

## The Five Agents

| Agent | Role | When it activates |
|---|---|---|
| **Researcher** | Hybrid search (BM25 + vector) across all indexed documents with Cohere reranking | Every query — retrieves evidence |
| **Analyst** | Quantitative analysis — statistics, trend detection, anomaly detection, chart data | Numerical questions, KPI queries |
| **Watchdog** | Corrective-RAG confidence gating; proactive monitoring for contracts, compliance, complaints | Every query (confidence check) + background alerting |
| **Scribe** | Synthesises multi-source findings into structured, cited answers in the user's language | Every query — produces the final answer |
| **Strategist** | Orchestrator — plans investigation path, routes to correct agents, assembles final response | Every query — the entry point |

The **Strategist** acts as the brain: it reads the query, plans a multi-step investigation, directs the other four agents, and assembles a coherent answer with citations, suggested actions, and follow-up questions.

---

## Key Features

- **Hybrid RAG** — BM25 lexical search + 3072-dim HNSW vector search (`text-embedding-3-large`) with semantic reranking on `iroko-chunks` index
- **Cohere Reranking** — Top-20 candidates reranked to top-5 by true relevance before generation
- **Corrective RAG** — Watchdog computes coverage confidence; queries with confidence < 0.7 are blocked and logged as knowledge gaps rather than hallucinated
- **Proactive Alerts** — Watchdog runs background checks for contract expiry (90-day window), complaint spikes, policy conflicts, and regulatory deadlines
- **Live Agent Trace** — Every response streams a real-time trace of agent actions via SSE or WebSocket, visible in the UI
- **Morning Briefing** — Personalised daily digest of critical alerts, upcoming deadlines, and recent documents
- **Pidgin Support** — Nigerian Pidgin English detected and flagged; responses acknowledge multi-lingual context
- **Knowledge Graph** — Document and entity vertices written to Cosmos DB Gremlin on every ingest
- **NDPA-Aware** — Cross-border transfer tracking, data retention gap detection, compliance deadline monitoring built into Watchdog
- **Full Audit Trail** — Every agent run, query, and document action persisted in PostgreSQL

---

## Tech Stack

| Layer | Technology |
|---|---|
| **Frontend** | Next.js 14 · TypeScript · Tailwind CSS |
| **API Framework** | FastAPI 0.115 + Uvicorn |
| **Agent Orchestration** | Microsoft Semantic Kernel 1.11 |
| **LLM (reasoning)** | Azure OpenAI — GPT-4o / GPT-5.4-mini |
| **Embeddings** | Azure OpenAI — `text-embedding-3-large` (3072 dims) |
| **Vector + Hybrid Search** | Azure AI Search — `iroko-chunks` index |
| **OCR / Document Parsing** | Azure AI Document Intelligence (`prebuilt-read`) |
| **Reranking** | Cohere Rerank v3 |
| **Knowledge Graph** | Azure Cosmos DB Gremlin API |
| **Document Storage** | Azure Blob Storage — `raw-documents` container |
| **Secret Management** | Azure Key Vault |
| **Authentication** | JWT (python-jose) + bcrypt |
| **Database** | PostgreSQL 16 (via Docker) / SQLite (local dev) |
| **Streaming** | SSE (`StreamingResponse`) + WebSocket |
| **Containerisation** | Docker + Docker Compose |

---

## Demo Data vs. Production

| Feature | Demo mode | Production |
|---|---|---|
| **Document Q&A** | Requires Azure AI Search index with real docs | Same — point to your index |
| **Fraud signals** | Seeded demo data (realistic MTN Nigeria scenarios) | Connect to OMC-R event streams, ERP/AP, MoMo logs |
| **Network intelligence** | Simulated OMC-R data | Live OMC-R API integration |
| **Alerts** | Real — generated from document analysis | Same |
| **User auth** | Real JWT + PostgreSQL | Same |

---

## Project Structure

```
iroko-ai-v2/
├── docker-compose.yml         # Full-stack orchestration
├── .env.example               # Template for backend secrets
│
├── backend/                   # FastAPI + Semantic Kernel
│   ├── main.py                # App entry point, CORS, startup
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── agents/
│   │   ├── kernel.py          # Semantic Kernel setup (GPT-4o, embeddings)
│   │   ├── strategist.py      # Orchestrator — investigation planner
│   │   ├── researcher.py      # Hybrid search + Cohere reranking
│   │   ├── analyst.py         # Quantitative analysis + chart data
│   │   ├── watchdog.py        # Confidence gating + proactive alerts
│   │   ├── scribe.py          # Answer synthesis + drafting
│   │   ├── orchestrator.py    # OrchestratorAgent wrapper
│   │   ├── base_agent.py      # BaseAgent (tracing + retry)
│   │   ├── analyst_agent.py   # AnalystAgent wrapper
│   │   ├── research_agent.py  # ResearchAgent wrapper
│   │   └── monitor_agent.py   # MonitorAgent wrapper
│   ├── routes/                # API endpoints
│   ├── services/              # Azure integrations, auth, DB
│   ├── models/                # SQLAlchemy + Pydantic schemas
│   └── scripts/               # Seed data + sample docs
│
└── frontend/                  # Next.js 14 + TypeScript + Tailwind
    ├── Dockerfile
    ├── app/                   # Next.js App Router pages
    ├── components/            # Shared React components
    ├── hooks/                 # useChat, useInsights, useSearch
    ├── lib/                   # API client, types, config, streaming
    ├── context/               # AuthContext
    └── services/              # Domain service modules
```

---

## Demo Scenarios

The system ships with eight seed documents that demonstrate cross-document reasoning across a telco enterprise estate:

| Query | Agents involved | Documents cited |
|---|---|---|
| *"What happened with the Ikeja cluster outage?"* | Researcher → Analyst → Watchdog → Scribe | RCA report, IHS tower lease, Ericsson SLA, Enterprise SLA register |
| *"What is our total SLA credit exposure?"* | Researcher → Analyst → Scribe | Enterprise SLA register, IHS contract, Ericsson contract |
| *"Are we compliant with the new NCC regulations?"* | Researcher → Watchdog → Analyst → Scribe | NCC QoS return, NDPA Article 24 record, data retention policy |
| *"What's the status of the Kano-Kaduna fibre rollout?"* | Researcher → Analyst → Scribe | Fibre route BoQ |
| *"Wetin cause the MoMo complaint spike?"* (Pidgin) | Researcher → Analyst → Watchdog → Scribe | MoMo complaints report, Ikeja cluster RCA |

---

## Hackathon

Built for the **TechEx Intelligent Enterprise Solutions Hackathon** (May 2026) and submitted to the **AI Agent Olympics Hackathon** (May 2026) on [lablab.ai](https://lablab.ai).

Originally developed as a finalist solution for the **TeKnowledge × Microsoft 2026 Agentic AI Hackathon** (Problem Statement: MTN Nigeria Productivity & Workflow Management).

---

## Team

Built by **Team 4** for the TeKnowledge × Microsoft 2026 Agentic AI Hackathon.

---

## License

Internal hackathon prototype. All rights reserved — Iroko AI / Team 4, 2026.
