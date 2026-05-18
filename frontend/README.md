# Iroko AI

> **Enterprise Network & Document Intelligence for MTN Nigeria**
> Powered by the Atlas Multi-Agent Backend — every answer is grounded in verified documents, every interaction is logged to a cryptographically chained audit trail, and every network event is surfaced in real time from the live OMC-R feed.

---

## Overview

Iroko AI is an enterprise-grade internal platform built for MTN Nigeria. It connects the **Atlas Multi-Agent System** to the company's entire document corpus — contracts, incident reports, compliance filings, site cards, vendor SLAs, and customer care runbooks — and returns cite-first answers backed by verifiable evidence.

Beyond document intelligence, the platform integrates directly with the **OMC-R network feed**, providing a live view of tower health, active alarms, KPI trends, and real-time network events across the MTN Nigeria estate.

The platform is multilingual by design (English and Nigerian Pidgin; extensible to Yoruba, Hausa, and Igbo) and satisfies all NCC (Nigerian Communications Commission) and NDPA (Nigeria Data Protection Act) regulatory requirements out of the box.

---

## Tech Stack

| Layer | Technology | Version |
|---|---|---|
| Framework | Next.js (App Router) | 16.2.4 |
| Language | TypeScript | 5.x |
| UI Library | React | 19.2.4 |
| Styling | Tailwind CSS v4 | 4.x |
| Backend Engine | AtlasCore (FastAPI + Microsoft Semantic Kernel) | — |
| Search | Azure AI Search (Hybrid BM25 + Vector) | — |
| Network Feed | OMC-R Demo Connector (live BTS telemetry) | — |
| Auth | httpOnly JWT cookie (server-side via Next.js Route Handlers) | — |

> **Zero runtime UI dependencies** beyond Next.js, React, React DOM, and React Markdown. All components are hand-built with Tailwind utilities.

---

## The Atlas Multi-Agent System

Iroko AI is powered by a multi-agent orchestration layer built on Microsoft Semantic Kernel. Five specialised agents collaborate on every query:

| Agent | Role |
|---|---|
| **Strategist** | Master orchestrator — decomposes complex queries and synthesises final responses |
| **Researcher** | Retrieval layer — executes hybrid BM25 + vector search across the indexed document corpus |
| **Analyst** | Data specialist — extracts quantitative insights and identifies performance patterns |
| **Scribe** | Generation layer — produces grounded reports, compliance drafts, and structured briefs |
| **Watchdog** | Safety layer — evaluates retrieval confidence and blocks low-confidence responses before they reach the user |

---

## Features

### Dashboard (`/dashboard`)
Executive overview with real-time KPI stat cards, Atlas agent utilisation metrics, query volume trend charts, and a recent conversations log. All data is fetched live from the AtlasCore analytics endpoints.

### AI Chat (`/chat`)
Full conversational interface with SSE streaming responses. Includes a live **Agent Trace** panel that exposes the internal reasoning chain — showing how the Strategist, Researcher, Watchdog, Analyst, and Scribe agents collaborate on each query in real time.

**Voice input** is supported via the browser's Web Speech API — click the microphone button to dictate a query and have it transcribed live into the input field before sending. The backend also exposes a `POST /api/atlas/voice` endpoint (Azure OpenAI Whisper) for server-side transcription when required.

Conversation history is persisted server-side and restored across sessions. The sidebar reflects real backend connectivity status (online / offline / checking) and updates in response to actual API calls.

### Search (`/search`)
Hybrid document search powered by Azure AI Search. Combines BM25 keyword matching with dense vector similarity for high-recall, high-precision retrieval across the full document corpus.

### Documents (`/documents`)
Browse, preview, and manage the ingested document corpus. Supports filtering by document type, upload date, and coverage status.

### Analytics (`/analytics`)
Usage trends, retrieval quality metrics, agent utilisation breakdown, and response latency tracking. All charts are backed by live data from the AtlasCore analytics API.

### Network Intelligence (`/network-intelligence`)
Live OMC-R network dashboard that polls the MTN Nigeria tower estate every 30 seconds. Surfaces:

- **Stat bar** — Network Health %, Critical Alarms, Major Alarms, Sites Active/Total, Sites Down
- **KPI cards** — Call Success Rate, Handover Success Rate, and RRC Setup Success, each with a live SVG sparkline from 48-point trend data, delta vs. SLA target, and on/below-target badge
- **Active Alarms** — full alarm list sorted critical → major → warning, with severity filter tabs, expandable rows showing the full description, first/last occurrence timestamps, and numbered suggested actions
- **BTS Tower grid** — all 20 towers with colour-coded status (active / degraded / down) and per-tower alarm counts
- **Live Events log** — rolling feed of the last 30 OMC-R simulator events with relative timestamps

Data is sourced entirely from the `/api/connectors/omcr/snapshot` proxy route.

### Alerts (`/agents/noc`)
Watchdog alert management dashboard. Pulls live compliance and operational alerts from the AtlasCore backend, surfaces critical and warning events with full metadata, and supports filtered browsing with pagination. Clicking **Ask Agent** on any alert navigates directly to the AI Chat page with the alert pre-loaded in the input field, ready to send.

### Knowledge Gap (`/knowledge-graph`)
Identifies topics where the document corpus has weak coverage. Uses Watchdog confidence scores to produce a ranked gap analysis — showing which queries return low-confidence answers and what documents need to be ingested to close each gap.

### Integrations (`/integrations`)
OAuth-based connector management for external data sources. Supports connecting, syncing, and disconnecting the following platforms:

| Platform | Capability |
|---|---|
| **Microsoft OneDrive** | File and document sync |
| **SharePoint** | Site and document library ingestion |
| **Microsoft Teams** | Channel conversations and file import |
| **Slack** | Workspace messages and thread ingestion |

The OAuth flow is fully handled in-app — users are redirected to the provider and returned to `/integrations/callback`, which exchanges the authorisation code and provisions the connector automatically.

### Compliance & Reports (`/compliance/reports`)
Tools for assembling NCC quarterly returns and NDPA audit packages. Includes a **DPIA Wizard** powered by the Scribe agent.

### Audit Trail (`/audit-trail`)
Append-only query log where every entry is cryptographically chained. Every AI response is traceable to a specific set of source document chunks, satisfying regulatory audit requirements.

### User Management (`/user-management`)
Full user lifecycle management — create users, manage roles, send invitations, activate and deactivate accounts.

### Settings
- **Profile** (`/settings/profile`) — personal info, language preference, voice input
- **System** (`/settings/system`) — Atlas agent configuration, data sovereignty policy, routing rules

---

## Project Structure

```
iroko-ai/
├── app/
│   ├── (auth)/                              # Auth route group (no app shell)
│   │   ├── login/                           # Sign in
│   │   ├── invite/[token]/                  # Accept invitation
│   │   ├── forgot-password/                 # Password reset request
│   │   └── reset-password/                  # Password reset confirmation
│   │
│   ├── api/                                 # Next.js Route Handlers (proxy layer)
│   │   ├── analytics/                       # Analytics + knowledge-gap endpoints
│   │   ├── alerts/                          # Watchdog alerts — list, acknowledge, resolve
│   │   ├── atlas/                           # Chat (SSE stream), conversations, voice
│   │   ├── auth/                            # Login, logout, me, invite, password reset
│   │   ├── connectors/                      # OAuth connectors — CRUD, auth-url, sync, browse, import
│   │   │   └── omcr/                        # OMC-R direct connector — status, sync, snapshot
│   │   └── users/                           # User management — CRUD, activate, deactivate
│   │
│   ├── agents/
│   │   ├── noc/                             # Alerts — live Watchdog alerts + Ask Agent integration
│   │   ├── care/                            # Customer care agent
│   │   ├── compliance/                      # Compliance agent
│   │   ├── contracts/                       # Contracts agent
│   │   └── field/                           # Field operations agent
│   │
│   ├── dashboard/                           # Executive KPI dashboard
│   ├── chat/                                # AI chat with Agent Trace panel + voice input
│   ├── search/                              # Hybrid document search
│   ├── documents/                           # Document corpus browser
│   ├── analytics/                           # Usage and quality analytics
│   ├── network-intelligence/                # Live OMC-R network dashboard
│   ├── integrations/                        # OAuth connector management + callback handler
│   ├── knowledge-graph/                     # Knowledge gap analysis
│   ├── compliance/reports/                  # Compliance reports + DPIA wizard
│   ├── audit-trail/                         # Cryptographic query audit log
│   ├── user-management/                     # User and role management
│   └── settings/                            # Profile, system, and integration settings
│
├── components/
│   ├── layout/
│   │   ├── AppShell.tsx                     # Main layout wrapper (sidebar + topbar + content)
│   │   ├── Sidebar.tsx                      # Left navigation with grouped sections
│   │   └── Topbar.tsx                       # Page header with title, breadcrumb, and actions
│   ├── dashboard/
│   │   └── DashboardCharts.tsx              # Query volume and document coverage charts
│   ├── pages/
│   │   ├── Alert.tsx                        # Alerts page body (live Watchdog alerts)
│   │   ├── AuditTrailContent.tsx            # Audit trail page body
│   │   ├── DocumentsContent.tsx             # Documents page body
│   │   └── UserManagementContent.tsx        # User management page body
│   └── ui/
│       └── LoadingSpinner.tsx               # Shared animated spinner component
│
├── context/
│   └── AuthContext.tsx                      # Global auth state — user, login, logout
│
├── lib/
│   ├── api-client.ts                        # Server-side fetch helper (reads httpOnly JWT cookie)
│   ├── config.ts                            # Centralised runtime constants (API base URL, cookie name)
│   └── types.ts                             # Shared TypeScript interfaces
│
└── public/                                  # Static assets
```

---

## Authentication

All API calls are authenticated via an `iroko_token` httpOnly cookie set at login. The `apiRequest` helper in `lib/api-client.ts` reads this cookie server-side and forwards the JWT as a `Bearer` token to the AtlasCore backend at `https://iroko-atlascore.azurewebsites.net`. Client components never call the backend directly — all requests go through Next.js Route Handlers, which act as an authenticated proxy layer.

---

## API Proxy Pattern

Every backend endpoint is mirrored as a Next.js Route Handler under `app/api/`. This keeps the AtlasCore backend URL and the JWT out of the browser entirely, and allows server-side authentication to be applied uniformly.

```
Browser → /api/connectors/omcr/snapshot → Route Handler → AtlasCore (with Bearer token)
Browser → /api/atlas/ask/stream         → Route Handler → AtlasCore SSE stream
Browser → /api/alerts                   → Route Handler → AtlasCore (with Bearer token)
```

The voice endpoint (`/api/atlas/voice`) is a special case — it proxies `multipart/form-data` rather than JSON, so it bypasses the standard `apiRequest` helper and forwards the raw form data directly with the auth header attached server-side.

---

## Architecture Decisions

**Multi-agent over single RAG** — Complex telecom-domain queries (e.g., calculating SLA penalty exposure across multiple vendor contracts) require more than retrieval. Delegating to specialised agents improves accuracy and auditability.

**Server-side auth proxy** — httpOnly cookies prevent token theft via XSS. Route Handlers act as a secure proxy so the AtlasCore URL and credentials are never exposed to the client.

**OMC-R as a direct connector** — The OMC-R feed is a system-level integration (not user-configured OAuth), so it is surfaced under a dedicated `/network-intelligence` route rather than the OAuth integrations page. The snapshot endpoint is polled every 30 seconds client-side; the envelope wrapper is unwrapped at the route handler layer so the page receives a clean typed object.

**Browser Speech API for voice input** — Live dictation in the chat input uses the native `SpeechRecognition` API (zero latency, no upload required). The server-side Whisper endpoint (`POST /api/atlas/voice`) is available for higher-accuracy transcription when the backend connector is active.

**Ask Agent deep-link pattern** — The Alerts page constructs a pre-populated query from alert metadata and passes it to the Chat page via a `?q=` URL parameter. The chat page's `SearchParamsPrefill` component picks this up on mount and loads it into the textarea, keeping the two pages decoupled.

**Async server components for data pages** — Dashboard, Analytics, and similar pages use async server components with `Promise.allSettled` for parallel data fetching with graceful degradation. Interactive pages use client-side fetching through the proxy routes.

**Data sovereignty** — All processing and retrieval is routed within the designated jurisdiction. No data leaves the specified region during inference or document retrieval.

---

## License

Proprietary — MTN Nigeria internal use only.
