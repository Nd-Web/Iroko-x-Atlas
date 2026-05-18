# Iroko AI — Powered by Atlas

> **TeKnowledge × Microsoft 2026 Agentic AI Hackathon**
> Problem Statement: MTN Nigeria — Productivity & Workflow Management


---

## The Problem

Telecom employees at MTN Nigeria work across thousands of fragmented documents spread across multiple systems and formats — RCA reports, vendor contracts, NCC regulatory filings, customer complaint logs, BoQ spreadsheets, and more. Finding critical information, deriving cross-document insights, and acting on time-sensitive issues (expiring contracts, compliance deadlines, complaint spikes) takes hours when it should take seconds.

## The Solution

**Iroko AI**, powered by Atlas, is a multi-agent AI system that ingests, indexes, and reasons across an enterprise's entire document estate. Ask it a question in plain English — or Nigerian Pidgin — and five specialised AI agents collaborate to search the knowledge base, analyse the data, validate confidence, and synthesise a cited answer with actionable recommendations, all in under 10 seconds.

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
│  │                                                         │ │ │
│  │  AI Search      Cosmos DB       Blob Storage  OpenAI   │ │ │
│  │  (iroko-chunks) (Gremlin Graph) (raw-docs)   (GPT+Emb) │ │ │
│  │                                                         │ │ │
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
- **Knowledge Graph** — Document and entity vertices written to Cosmos DB Gremlin (`iroko-knowledge-graph`) on every ingest
- **NDPA-Aware** — Cross-border transfer tracking, data retention gap detection, compliance deadline monitoring built into Watchdog
- **Full Audit Trail** — Every agent run, query, and document action persisted in SQLite (upgradeable to PostgreSQL)

---

## Tech Stack

| Layer | Technology |
|---|---|
| API Framework | FastAPI 0.115 + Uvicorn |
| Agent Orchestration | Microsoft Semantic Kernel 1.11 |
| LLM (reasoning) | Azure OpenAI — GPT-4o / GPT-5.4-mini |
| Embeddings | Azure OpenAI — `text-embedding-3-large` (3072 dims) |
| Vector + Hybrid Search | Azure AI Search — `iroko-chunks` index |
| OCR / Document Parsing | Azure AI Document Intelligence (`prebuilt-read`) |
| Reranking | Cohere Rerank v3 |
| Knowledge Graph | Azure Cosmos DB Gremlin API |
| Document Storage | Azure Blob Storage — `raw-documents` container |
| Secret Management | Azure Key Vault (`irokovault2026`) |
| Authentication | JWT (python-jose) + bcrypt |
| Database (local/dev) | SQLite via SQLAlchemy 2.0 |
| Streaming | SSE (`StreamingResponse`) + WebSocket |
| Language | Python 3.10 |

---

## Azure Services

| Resource | SKU | Purpose |
|---|---|---|
| `iroko-search-engine` | Basic | Hybrid BM25 + vector search index |
| `rg-iroko-hackathon` (Doc Intelligence) | S0 | OCR and layout extraction from PDF/DOCX |
| `irokostorage2026` | StorageV2 | Raw document archive (`raw-documents`) |
| `ai-irokoaihub914849043532` | AI Services | GPT-4o, GPT-5.4-mini, text-embedding-3-large |
| `irokograph2026` | Cosmos DB Gremlin | Knowledge graph (`iroko-knowledge-graph`) |
| `irokovault2026` | Key Vault (RBAC) | All service keys and endpoints |
| `iroko-speech` | S0 | Speech-to-text for voice queries |
| `iroko-ai-hub` | AI Foundry Hub | Model governance and project workspace |

All resources are deployed in **Sweden Central**.

---

## Quick Start

### Prerequisites

- Python 3.10
- Azure service principal with `Key Vault Secrets User` role on `irokovault2026`

### 1. Clone and set up environment

```bash
git clone https://github.com/irokoAI/atlascore-backend.git
cd atlascore-backend

python -m venv venv
# Windows
venv\Scripts\pip install -r requirements.txt
# macOS / Linux
venv/bin/pip install -r requirements.txt
```

### 2. Configure credentials

Create a `.env` file in the project root:

```env
# Azure Service Principal — grants access to Key Vault
AZURE_CLIENT_ID=<your-client-id>
AZURE_CLIENT_SECRET=<your-client-secret>
AZURE_TENANT_ID=<your-tenant-id>

# Key Vault URL (all other secrets are loaded from here automatically)
AZURE_KEYVAULT_URL=https://irokovault2026.vault.azure.net/

# Local database
DATABASE_URL=sqlite:///./atlas.db

# Optional: override any Key Vault secret locally
# AZURE_SEARCH_ENDPOINT=
# AZURE_OPENAI_ENDPOINT=
# COHERE_API_KEY=
```

At startup, the backend loads all Azure service keys directly from Key Vault using `DefaultAzureCredential`. No hardcoded secrets needed.

### 3. Run

```bash
# Windows
venv\Scripts\uvicorn main:app --host 0.0.0.0 --port 8000

# macOS / Linux
venv/bin/uvicorn main:app --host 0.0.0.0 --port 8000
```

The server starts, initialises the SQLite database, and creates a default admin account:

```
Email:    admin@mtn.ng
Password: AtlasAdmin2026!
```

Interactive API docs: **http://localhost:8000/docs**

---

## API Reference

### Authentication

```http
POST /api/auth/login
Content-Type: application/json

{ "email": "admin@mtn.ng", "password": "AtlasAdmin2026!" }
```

Returns a JWT bearer token. Include it in all subsequent requests:
```
Authorization: Bearer <token>
```

---

### Ask (Standard)

```http
POST /api/atlas/ask
Authorization: Bearer <token>
Content-Type: application/json

{
  "query": "What is our SLA exposure from the Ikeja cluster outage?",
  "conversation_id": null,
  "department_filter": null
}
```

**Response:**
```json
{
  "conversation_id": "...",
  "message_id": "...",
  "answer": "**Contract & SLA Exposure Analysis**\n\n...",
  "agent_trace": [
    { "agent": "Strategist", "tool": "plan", "timestamp": "..." },
    { "agent": "Researcher", "tool": "search_documents", "timestamp": "..." },
    { "agent": "Analyst",    "tool": "compute_statistics", "timestamp": "..." },
    { "agent": "Scribe",     "tool": "synthesise_answer",  "timestamp": "..." }
  ],
  "citations": [
    { "document_id": "doc_008", "document_title": "Enterprise Customer SLA Register — EBU", "excerpt": "..." }
  ],
  "suggested_followups": [
    "Which enterprise customers have the highest SLA credit entitlements?"
  ]
}
```

---

### Ask (Streaming SSE)

```http
POST /api/atlas/ask/stream-http
Authorization: Bearer <token>
```

Streams four event types in real time:

| Event type | Content |
|---|---|
| `start` | `"Iroko AI is thinking..."` |
| `agent_action` | Agent name, tool, description as each agent fires |
| `token` | Answer text streamed word-by-word |
| `complete` | Full answer, citations, suggested follow-ups |

---

### Morning Briefing

```http
POST /api/atlas/briefing
Authorization: Bearer <token>
```

Returns a personalised daily digest — active alerts, upcoming deadlines, key metrics, recently indexed documents.

---

### Documents

```http
POST   /api/documents          # Upload a document (PDF, DOCX, XLSX, TXT, CSV)
GET    /api/documents          # List all documents (filter by department, type, status)
GET    /api/documents/{id}     # Get document metadata
DELETE /api/documents/{id}     # Delete a document (admin/analyst only)
```

On upload, the pipeline runs automatically:
1. File saved to Azure Blob Storage (`raw-documents/{doc_id}/{filename}`)
2. Text extracted via Azure AI Document Intelligence
3. Text cleaned, section-detected, and semantically chunked
4. Chunks embedded (`text-embedding-3-large`) and indexed in `iroko-chunks`
5. Document vertex written to Cosmos DB Gremlin knowledge graph

---

### Alerts

```http
GET  /api/alerts               # List all active alerts
POST /api/alerts/{id}/acknowledge
POST /api/alerts/{id}/resolve
```

Alert types generated by the Watchdog agent:
- `contract_expiry` — contracts expiring within 90 days
- `complaint_spike` — complaint volume above rolling baseline
- `policy_conflict` — internal policy contradicts new regulation
- `regulatory_deadline` — NCC / NDPA filing due within 30 days

---

### Analytics

```http
GET /api/analytics/dashboard   # KPIs: documents, queries, alerts, top departments
GET /api/analytics/health      # System health checks
```

---

## Document Ingestion Pipeline

```
Upload → Blob Storage (raw-documents)
       → Azure AI Document Intelligence (OCR / layout)
       → clean_text()  — normalise, strip noise, NGN currency
       → smart_chunk_document()  — heading-aware semantic chunks
       → text-embedding-3-large  — 3072-dim vectors (batched ×16)
       → iroko-chunks index  — BM25 fields + vector field
       → Cosmos DB Gremlin  — document vertex upserted
```

---

## Project Structure

```
atlascore-backend/
├── main.py                    # FastAPI app, CORS, startup
├── requirements.txt
├── .env                       # Local secrets (git-ignored)
│
├── agents/
│   ├── kernel.py              # Semantic Kernel setup (GPT-4o, nano, embeddings)
│   ├── strategist.py          # Orchestrator — investigation planner
│   ├── researcher.py          # Hybrid search + Cohere reranking
│   ├── analyst.py             # Quantitative analysis + chart data
│   ├── watchdog.py            # Confidence gating + proactive alerts
│   └── scribe.py              # Answer synthesis + drafting
│
├── routes/
│   ├── ask.py                 # /api/atlas/ask  (standard + SSE + WebSocket)
│   ├── documents.py           # /api/documents  (upload, list, delete)
│   ├── alerts.py              # /api/alerts
│   ├── analytics.py           # /api/analytics
│   └── auth.py                # /api/auth/login, /register
│
├── services/
│   ├── keyvault.py            # Azure Key Vault secret loader (DefaultAzureCredential)
│   ├── embeddings.py          # text-embedding-3-large batched helper
│   ├── azure_search.py        # Hybrid search client (iroko-chunks)
│   ├── blob_storage.py        # Azure Blob Storage uploader
│   ├── cosmos_graph.py        # Cosmos DB Gremlin graph writes
│   ├── document_processor.py  # OCR + semantic chunking pipeline
│   └── auth_utils.py          # JWT + password hashing
│
├── models/
│   ├── database.py            # SQLAlchemy models (User, Document, Alert, etc.)
│   └── schemas.py             # Pydantic request/response schemas
│
└── scripts/
    └── seed_data.py           # Seed the demo corpus (8 sample enterprise documents)
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

## Team

Built by **Team 4** for the TeKnowledge × Microsoft 2026 Agentic AI Hackathon.

---

## License

Internal hackathon prototype. All rights reserved — Iroko AI / Team 4, 2026.
