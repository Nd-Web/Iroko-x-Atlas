"""
Iroko AI — Powered by Atlas
============================
AI-Powered Enterprise Document Intelligence Platform
Finalist solution for TeKnowledge × Microsoft 2026 Agentic AI Hackathon

Built by Team 4 | AI Lead: Ndubuisi Ekeh
Stack: FastAPI + Semantic Kernel + Azure OpenAI + Azure AI Search
"""

from dotenv import load_dotenv
load_dotenv()

# Load remaining secrets from Azure Key Vault (fills any gaps not covered by .env)
from services.keyvault import load_secrets_from_keyvault
load_secrets_from_keyvault()

# ── Strict environment validation ────────────────────────────────────────────
# Validates ALL required env vars before proceeding. Exits with a clear
# error report if anything is missing.
from services.settings import validate_environment
try:
    settings = validate_environment()
except SystemExit:
    import logging as _log
    _log.getLogger(__name__).warning(
        "Environment validation failed — running in demo/mock mode. "
        "Azure features will be unavailable until .env is configured."
    )

import os
import logging
import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware

# Routes
from routes.auth import router as auth_router
from routes.users import router as users_router
from routes.ask import router as ask_router
from routes.documents import router as documents_router
from routes.alerts import router as alerts_router
from routes.analytics import router as analytics_router
from routes.connectors import router as connectors_router
from routes.network import router as network_router
from routes.cx import router as cx_router
from routes.omcr import router as omcr_router
from routes.fraud import router as fraud_router
# New v2 routes
from routes.health import router as health_router
from routes.insights import router as insights_router
from routes.search import router as search_router_v2
from routes.agents import router as agents_router
from routes.chat import router as chat_router

# Database
from models.database import init_db

# Auth (needed for debug endpoints)
from services.auth_utils import get_current_user

# Logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
)
logger = logging.getLogger(__name__)

# ─── Lifespan ─────────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    # ── Startup ──
    logger.info("Iroko AI starting up...")

    # Initialise database
    init_db()
    logger.info("Database initialised.")

    # Create default admin if no users exist
    from models.database import SessionLocal, User
    from services.auth_utils import hash_password, generate_api_key

    db = SessionLocal()
    try:
        user_count = db.query(User).count()
        if user_count == 0:
            default_password = os.getenv("ATLAS_ADMIN_PASSWORD", "AtlasAdmin2026!")
            admin = User(
                email=os.getenv("ATLAS_ADMIN_EMAIL", "admin@mtn.ng"),
                hashed_password=hash_password(default_password),
                full_name="Iroko AI Superadmin",
                organisation="MTN Nigeria",
                department="Technology",
                role="superadmin",
                api_key=generate_api_key(),
            )
            db.add(admin)
            db.commit()
            logger.info(f"Bootstrap superadmin created: {admin.email}")
            logger.info("Set ATLAS_ADMIN_PASSWORD env var to override the default password.")
    finally:
        db.close()

    # Start connector auto-sync scheduler
    from services.connector_sync import start_sync_scheduler
    start_sync_scheduler()
    logger.info("Connector auto-sync scheduler started.")

    # Run initial OMC-R sync, then schedule every 60 seconds
    from services.omcr_sync import run_omcr_sync
    from services.connector_sync import get_scheduler
    try:
        await run_omcr_sync()
        logger.info("Initial OMC-R sync complete.")
    except Exception as exc:
        logger.warning(f"Initial OMC-R sync skipped (omcr-demo unreachable?): {exc}")
    get_scheduler().add_job(
        run_omcr_sync,
        "interval",
        seconds=60,
        id="omcr_sync",
        replace_existing=True,
    )

    logger.info("Iroko AI ready.")
    logger.info(f"Docs: http://localhost:8000/docs")

    # Pre-compute suggestion-box answers in background
    from routes.ask import warm_starter_cache
    asyncio.ensure_future(warm_starter_cache())

    yield

    # ── Shutdown ──
    from services.connector_sync import stop_sync_scheduler
    stop_sync_scheduler()
    logger.info("Iroko AI shut down.")


# ─── App ─────────────────────────────────────────────────────────────────────

app = FastAPI(
    title="Iroko AI",
    description="Iroko AI, powered by Atlas — enterprise document intelligence. "
                "Multi-agent system built on Azure OpenAI + Microsoft Semantic Kernel.",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# ─── CORS ────────────────────────────────────────────────────────────────────

_allowed_origins = [
    o.strip()
    for o in os.getenv("CORS_ALLOWED_ORIGINS", "http://localhost:3000").split(",")
    if o.strip()
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─── Routes ──────────────────────────────────────────────────────────────────

app.include_router(auth_router)
app.include_router(users_router)
app.include_router(ask_router)
app.include_router(documents_router)
app.include_router(alerts_router)
app.include_router(analytics_router)
app.include_router(connectors_router)
app.include_router(network_router)
app.include_router(cx_router)
app.include_router(omcr_router)
# New v2 routes
app.include_router(health_router)
app.include_router(insights_router)
app.include_router(search_router_v2)
app.include_router(agents_router)
app.include_router(chat_router)
app.include_router(fraud_router)

# ─── Health ──────────────────────────────────────────────────────────────────

@app.get("/health")
async def health():
    return {
        "status": "healthy",
        "service": "Iroko AI Backend",
        "version": "1.0.0",
    }


@app.get("/api/debug/search")
async def debug_search(q: str = "IHS Nigeria tower lease", current_user = Depends(get_current_user)):
    if current_user.role not in ("superadmin", "admin"):
        raise HTTPException(status_code=403, detail="Debug endpoints require admin role")
    import os as _os
    from services.azure_search import get_search_client, hybrid_search, check_retrieval_quality
    client = get_search_client()
    env_info = {
        "AZURE_SEARCH_ENDPOINT": bool(_os.getenv("AZURE_SEARCH_ENDPOINT")),
        "AZURE_SEARCH_API_KEY": bool(_os.getenv("AZURE_SEARCH_API_KEY")),
        "AZURE_OPENAI_ENDPOINT": bool(_os.getenv("AZURE_OPENAI_ENDPOINT")),
        "client_is_none": client is None,
    }
    if client is None:
        return {"env": env_info, "results": [], "error": "client is None"}
    try:
        raw = await hybrid_search(query=q, top=5)
        quality = check_retrieval_quality(q, raw)
        return {
            "env": env_info,
            "result_count": len(raw),
            "quality": quality,
            "first_result_score": raw[0].get("@search.score") if raw else None,
            "first_result_reranker_score": raw[0].get("@search.reranker_score") if raw else None,
            "first_result_title": raw[0].get("title") if raw else None,
        }
    except Exception as e:
        return {"env": env_info, "error": str(e)}


@app.get("/api/debug/llm")
async def debug_llm(current_user = Depends(get_current_user)):
    if current_user.role not in ("superadmin", "admin"):
        raise HTTPException(status_code=403, detail="Debug endpoints require admin role")
    import os as _os, traceback as tb
    from openai import AsyncAzureOpenAI
    endpoint = _os.getenv("AZURE_OPENAI_ENDPOINT")
    api_key = _os.getenv("AZURE_OPENAI_API_KEY")
    api_version = _os.getenv("AZURE_OPENAI_API_VERSION", "2025-01-01-preview")
    deployment = _os.getenv("AZURE_OPENAI_GPT4O_DEPLOYMENT", "gpt-5.4-mini")
    env_info = {"endpoint": endpoint, "deployment": deployment, "api_version": api_version, "api_key_set": bool(api_key)}

    # Test 1: minimal prompt
    client = AsyncAzureOpenAI(azure_endpoint=endpoint, api_key=api_key, api_version=api_version)
    try:
        r = await client.chat.completions.create(model=deployment, messages=[{"role":"user","content":"Say ok"}], max_completion_tokens=10, temperature=0.0)
        test1 = {"ok": True, "response": r.choices[0].message.content}
    except Exception as e:
        test1 = {"ok": False, "error": str(e), "type": type(e).__name__, "traceback": tb.format_exc()}

    # Test 2: simulate Strategist reason — large prompt with 2000 token budget
    long_prompt = ("You are Iroko AI, MTN Nigeria's enterprise intelligence assistant.\n"
                   "Answer the user's question grounded ONLY in the evidence below.\n\n"
                   "Question: \"What is the monthly fee for the IHS Nigeria tower lease?\"\n\n"
                   "Retrieved Evidence:\nARTICLE 1  SCOPE OF AGREEMENT\nIHS hereby grants to MTN a non-exclusive "
                   "licence to co-locate telecommunications equipment on 847 tower sites across Nigeria. "
                   "Monthly tower lease fee: NGN 45,000,000. SLA: 99.5% uptime. Renewal notice due 90 days prior.\n\n"
                   "RULES:\n1. Give a detailed answer\n2. Cite document IDs\n3. Pidgin: False\n\n"
                   "Respond with valid JSON: {\"answer\": \"...\", \"citations\": [], \"suggested_actions\": [], "
                   "\"suggested_followups\": [], \"confidence\": \"high|medium|low\"}")
    try:
        r2 = await client.chat.completions.create(model=deployment, messages=[{"role":"user","content":long_prompt}], max_completion_tokens=2000, temperature=0.3)
        test2 = {"ok": True, "response": r2.choices[0].message.content[:300]}
    except Exception as e:
        test2 = {"ok": False, "error": str(e), "type": type(e).__name__, "traceback": tb.format_exc()}

    return {"env": env_info, "test_minimal": test1, "test_reason_prompt": test2}


@app.get("/")
async def root():
    return {
        "name": "Iroko AI",
        "tagline": "Powered by Atlas",
        "description": "AI-powered enterprise document intelligence",
        "docs": "/docs",
        "health": "/health",
    }


