"""
Iroko AI -- Strict Application Settings
========================================
Validates ALL required environment variables at startup using Pydantic.
The app will refuse to start if any required key is missing or blank.

Variables are grouped into tiers:
  - CRITICAL  -- App cannot function without these. Fail-fast on startup.
  - REQUIRED  -- Core Azure services. Must be set (via .env or Key Vault).
  - OPTIONAL  -- Connector credentials, feature-specific keys. Warned if missing.
"""
import os
import sys
import logging
from typing import Optional
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings

logger = logging.getLogger(__name__)


# -- Settings Model -------------------------------------------------------

class AppSettings(BaseSettings):
    """
    Central configuration for Iroko AI.
    Reads from environment variables (loaded from .env + Key Vault first).
    """

    # -- CRITICAL: App will not start without these ------------------------

    SECRET_KEY: str = Field(
        ..., description="JWT signing key. Generate with: python -c \"import secrets; print(secrets.token_hex(64))\""
    )
    DATABASE_URL: str = Field(
        default="sqlite:///./atlas.db", description="SQLAlchemy database connection string"
    )

    # -- Azure Service Principal (for Key Vault + Graph) -------------------

    AZURE_CLIENT_ID: str = Field(
        ..., description="Azure AD app registration client ID"
    )
    AZURE_CLIENT_SECRET: str = Field(
        ..., description="Azure AD app registration client secret"
    )
    AZURE_TENANT_ID: str = Field(
        ..., description="Azure AD tenant ID"
    )
    AZURE_KEYVAULT_URL: str = Field(
        ..., description="Azure Key Vault URL (e.g. https://irokovault2026.vault.azure.net/)"
    )

    # -- Azure AI Services -------------------------------------------------

    AZURE_OPENAI_ENDPOINT: str = Field(
        ..., description="Azure OpenAI service endpoint"
    )
    AZURE_OPENAI_API_KEY: str = Field(
        ..., description="Azure OpenAI API key"
    )
    AZURE_OPENAI_API_VERSION: str = Field(
        default="2025-01-01-preview", description="Azure OpenAI API version"
    )
    AZURE_OPENAI_EMBEDDING_DEPLOYMENT: str = Field(
        default="text-embedding-3-large", description="Azure OpenAI embedding model deployment name"
    )
    AZURE_OPENAI_GPT4O_DEPLOYMENT: str = Field(
        default="gpt-4o", description="Azure OpenAI GPT-4o deployment name"
    )
    AZURE_OPENAI_NANO_DEPLOYMENT: str = Field(
        default="gpt-5.4-nano", description="Azure OpenAI nano model deployment name"
    )

    # -- Azure AI Search ---------------------------------------------------

    AZURE_SEARCH_ENDPOINT: str = Field(
        ..., description="Azure AI Search service endpoint"
    )
    AZURE_SEARCH_API_KEY: str = Field(
        ..., description="Azure AI Search admin API key"
    )
    AZURE_SEARCH_INDEX_NAME: str = Field(
        default="iroko-chunks", description="Azure AI Search index name"
    )
    AZURE_SEARCH_SEMANTIC_CONFIG: str = Field(
        default="iroko-semantic", description="Semantic search configuration name"
    )

    # -- Azure Document Intelligence ---------------------------------------

    AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT: str = Field(
        ..., description="Azure Document Intelligence endpoint"
    )
    AZURE_DOCUMENT_INTELLIGENCE_KEY: str = Field(
        ..., description="Azure Document Intelligence API key"
    )

    # -- Azure Blob Storage ------------------------------------------------

    AZURE_STORAGE_CONNECTION_STRING: str = Field(
        ..., description="Azure Blob Storage connection string"
    )
    AZURE_STORAGE_CONTAINER: str = Field(
        default="raw-documents", description="Blob container name for document storage"
    )

    # -- Cosmos DB (Gremlin Graph) -----------------------------------------

    COSMOS_GREMLIN_ENDPOINT: str = Field(
        ..., description="Cosmos DB Gremlin endpoint (wss://...)"
    )
    COSMOS_PRIMARY_KEY: str = Field(
        ..., description="Cosmos DB primary key"
    )
    COSMOS_DATABASE: str = Field(
        default="iroko-graph-db", description="Cosmos DB database name"
    )
    COSMOS_GRAPH: str = Field(
        default="iroko-knowledge-graph", description="Cosmos DB graph name"
    )

    # -- Azure Communication Services --------------------------------------

    ACS_CONNECTION_STRING: str = Field(
        ..., description="Azure Communication Services connection string (for email)"
    )

    # -- Frontend ----------------------------------------------------------

    FRONTEND_URL: str = Field(
        default="http://localhost:3000", description="Frontend URL for email links"
    )

    # -- Connectors (optional -- warn if missing) --------------------------

    MICROSOFT_GRAPH_REDIRECT_URI: str = Field(
        default="http://localhost:3000/connectors/callback",
        description="OAuth redirect URI for Microsoft Graph connectors",
    )

    SLACK_CLIENT_ID: Optional[str] = Field(
        default=None, description="Slack app client ID"
    )
    SLACK_CLIENT_SECRET: Optional[str] = Field(
        default=None, description="Slack app client secret"
    )
    SERVICENOW_CLIENT_ID: Optional[str] = Field(
        default=None, description="ServiceNow OAuth client ID"
    )
    SERVICENOW_CLIENT_SECRET: Optional[str] = Field(
        default=None, description="ServiceNow OAuth client secret"
    )
    COHERE_API_KEY: Optional[str] = Field(
        default=None, description="Cohere API key for reranking"
    )
    AZURE_SPEECH_KEY: Optional[str] = Field(
        default=None, description="Azure Speech Services key"
    )

    # -- Bright Data (hackathon-provided web intelligence) -----------------

    BRIGHTDATA_API_KEY: Optional[str] = Field(
        default=None,
        description=(
            "Bright Data account API key. When absent the BrightDataClient operates "
            "in mock mode: fetch_url falls back to plain httpx GET, and SERP / "
            "Scraper APIs are disabled. Set this to enable full proxy-based "
            "web intelligence for the Iroko AI agent pipeline."
        ),
    )
    BRIGHTDATA_CUSTOMER_ID: Optional[str] = Field(
        default=None,
        description=(
            "Bright Data numeric customer/account ID. Required alongside "
            "BRIGHTDATA_API_KEY to construct proxy auth credentials "
            "(brd-customer-{id}-zone-{zone}). Find it in the Bright Data "
            "dashboard under Account Settings."
        ),
    )
    BRIGHTDATA_WEB_UNLOCKER_ENDPOINT: str = Field(
        default="https://brd.superproxy.io:22225",
        description=(
            "Bright Data Web Unlocker proxy host:port. Routes requests through "
            "the residential proxy network to bypass JS rendering gates and "
            "Cloudflare challenges on ncc.gov.ng and African telco sources."
        ),
    )
    BRIGHTDATA_SERP_API_ENDPOINT: str = Field(
        default="https://api.brightdata.com/serp",
        description=(
            "Bright Data SERP API base URL. Used by fetch_competitor_signals() "
            "and fetch_market_intel_signals() to issue structured Google/Bing "
            "SERP queries without a browser instance."
        ),
    )
    BRIGHTDATA_ZONE: str = Field(
        default="residential",
        description=(
            "Bright Data proxy zone name. Must match the zone created in your "
            "Bright Data dashboard (e.g. 'residential', 'datacenter', 'isp'). "
            "Used to build the proxy auth username."
        ),
    )
    BRIGHTDATA_PROXY_PASSWORD: Optional[str] = Field(
        default=None,
        description=(
            "Bright Data proxy zone password (specifically for Web Unlocker proxy auth). "
            "If not set, falls back to BRIGHTDATA_API_KEY."
        ),
    )
    BRIGHTDATA_SERP_ZONE: str = Field(
        default="serp_api1",
        description="Bright Data SERP API zone name (e.g. 'serp_api1').",
    )
    BRIGHTDATA_SCRAPING_BROWSER_ZONE: str = Field(
        default="scraping_browser1",
        description="Bright Data Scraping Browser zone name (e.g. 'scraping_browser1').",
    )
    BRIGHTDATA_MCP_SERVER_URL: Optional[str] = Field(
        default=None,
        description=(
            "Optional Bright Data MCP (Model Context Protocol) server URL. "
            "When set, Semantic Kernel agents can invoke live web fetches "
            "as native tool calls mid-reasoning without round-tripping to "
            "the FastAPI layer. Requires the MCP Server add-on to be enabled "
            "in your Bright Data account."
        ),
    )
    BRIGHTDATA_SCRAPER_DATASET_ID: Optional[str] = Field(
        default=None,
        description=(
            "Bright Data Web Scraper API dataset ID (Datasets v3). Used by "
            "scrape_structured() for schema-driven extraction from procurement "
            "portals and regulatory gazette PDFs. Falls back to Web Unlocker "
            "+ raw HTML when absent."
        ),
    )

    # -- Web Intelligence Pipeline Tuning ----------------------------------

    WEB_INTEL_REFRESH_INTERVAL_SECONDS: int = Field(
        default=300,
        description=(
            "How often (in seconds) the background signal poller refreshes "
            "live web intelligence data across all 5 domains. Default 300 "
            "(5 minutes). Reduce for demos; raise for production to stay "
            "within Bright Data quota."
        ),
    )
    AUDIT_TRAIL_MAX_ENTRIES: int = Field(
        default=10_000,
        description=(
            "Maximum number of hash-chained audit trail entries retained in "
            "the database. Oldest entries are pruned automatically when this "
            "limit is reached. Default 10,000."
        ),
    )
    NCC_LIVE_RULES_ENABLED: bool = Field(
        default=True,
        description=(
            "When True, ncc_live_rules_service.compile_live_enforcement_rules() "
            "fetches the latest NCC enforcement bulletins via Bright Data on "
            "each regulatory scan. Set to False to use the cached corpus only "
            "(useful when offline or running against Bright Data quota limits)."
        ),
    )
    SIGNAL_GRAPH_RISK_THRESHOLD: float = Field(
        default=0.6,
        description=(
            "Minimum compound risk score (0.0–1.0) for the SignalGraphService "
            "to surface an entity as a high-risk compound threat. Entities whose "
            "NetworkX-computed compound_risk_score falls below this threshold "
            "are excluded from get_high_risk_entities() output. Default 0.6."
        ),
    )

    # -- Validators --------------------------------------------------------

    @field_validator("SECRET_KEY")
    @classmethod
    def secret_key_not_insecure(cls, v: str) -> str:
        if v == "atlas-secret-key-change-in-production":
            raise ValueError(
                "SECRET_KEY is set to the insecure default. "
                "Generate a real key with: python -c \"import secrets; print(secrets.token_hex(64))\""
            )
        if len(v) < 32:
            raise ValueError("SECRET_KEY must be at least 32 characters long.")
        return v

    @field_validator(
        "AZURE_CLIENT_ID", "AZURE_CLIENT_SECRET", "AZURE_TENANT_ID",
        "AZURE_KEYVAULT_URL", "AZURE_OPENAI_ENDPOINT", "AZURE_OPENAI_API_KEY",
        "AZURE_SEARCH_ENDPOINT", "AZURE_SEARCH_API_KEY",
        "AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT", "AZURE_DOCUMENT_INTELLIGENCE_KEY",
        "AZURE_STORAGE_CONNECTION_STRING",
        "COSMOS_GREMLIN_ENDPOINT", "COSMOS_PRIMARY_KEY",
        "ACS_CONNECTION_STRING",
    )
    @classmethod
    def required_not_blank(cls, v: str, info) -> str:
        if not v or not v.strip():
            raise ValueError(f"{info.field_name} is required and cannot be blank.")
        return v.strip()

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True
        extra = "ignore"


# -- Loader ----------------------------------------------------------------

_settings: Optional[AppSettings] = None


def get_settings() -> AppSettings:
    """Return the cached settings singleton."""
    global _settings
    if _settings is None:
        raise RuntimeError("Settings not loaded yet. Call validate_environment() first.")
    return _settings


def validate_environment() -> AppSettings:
    """
    Validate all environment variables and return the settings object.
    Prints a clear error report and exits if any required variable is missing.
    Call this ONCE at startup, after loading .env and Key Vault.
    """
    global _settings

    try:
        _settings = AppSettings()
    except Exception as e:
        _print_validation_failure(e)
        sys.exit(1)

    # Warn about optional variables that are not set
    _warn_optional_missing(_settings)

    logger.info("[OK] Environment validated -- all required variables are set.")
    return _settings


def _print_validation_failure(error: Exception):
    """Print a human-readable error report for missing/invalid env vars."""
    lines = [
        "",
        "=" * 72,
        "  IROKO AI -- ENVIRONMENT VALIDATION FAILED",
        "=" * 72,
        "",
        "  The application cannot start because required environment",
        "  variables are missing or invalid.",
        "",
    ]

    if hasattr(error, "errors"):
        for err in error.errors():
            field = ".".join(str(loc) for loc in err.get("loc", []))
            msg = err.get("msg", "")
            lines.append(f"  [X]  {field}")
            lines.append(f"       {msg}")
            lines.append("")
    else:
        lines.append(f"  [X]  {error}")
        lines.append("")

    lines.extend([
        "  How to fix:",
        "  ---------------------------------------------------------",
        "  1. Copy .env.example to .env  (if not done already)",
        "  2. Fill in every required value in .env",
        "  3. Or ensure Azure Key Vault contains the missing secrets",
        "",
        "  Required variables can also be set directly in the shell:",
        "    export AZURE_OPENAI_ENDPOINT=https://...",
        "",
        "=" * 72,
        "",
    ])

    sys.stderr.write("\n".join(lines) + "\n")


def _warn_optional_missing(settings: AppSettings):
    """Log warnings for optional but recommended variables."""
    warnings = []

    if not settings.SLACK_CLIENT_ID or not settings.SLACK_CLIENT_SECRET:
        warnings.append("SLACK_CLIENT_ID / SLACK_CLIENT_SECRET -- Slack connector disabled")
    if not settings.SERVICENOW_CLIENT_ID or not settings.SERVICENOW_CLIENT_SECRET:
        warnings.append("SERVICENOW_CLIENT_ID / SERVICENOW_CLIENT_SECRET -- ServiceNow connector disabled")
    if not settings.COHERE_API_KEY:
        warnings.append("COHERE_API_KEY -- Cohere reranking disabled")
    if not settings.AZURE_SPEECH_KEY:
        warnings.append("AZURE_SPEECH_KEY -- Azure Speech Services disabled")
    if not settings.BRIGHTDATA_API_KEY or not settings.BRIGHTDATA_CUSTOMER_ID:
        warnings.append(
            "BRIGHTDATA_API_KEY / BRIGHTDATA_CUSTOMER_ID -- Bright Data web intelligence disabled; "
            "BrightDataClient will run in mock mode (plain httpx GET, no SERP/Scraper APIs). "
            "Both BRIGHTDATA_API_KEY and BRIGHTDATA_CUSTOMER_ID are required to enable full proxy-based scraping."
        )

    if warnings:
        logger.warning("Optional environment variables not set:")
        for w in warnings:
            logger.warning(f"  [!]  {w}")


# ==============================================================================
# BrightDataSettings — Bright Data product surface configuration
# ==============================================================================
# These are derived from AppSettings fields. Use as a convenience accessor
# when a service only needs Bright Data config, not the full AppSettings.
#
# Usage:
#   from services.settings import get_brightdata_settings
#   bd = get_brightdata_settings()
#   print(bd.api_key, bd.zone)

from dataclasses import dataclass


@dataclass(frozen=True)
class BrightDataSettings:
    """Read-only view of all Bright Data configuration fields."""
    api_key: Optional[str]
    customer_id: Optional[str]
    web_unlocker_endpoint: str
    serp_api_endpoint: str
    zone: str
    mcp_server_url: Optional[str]
    scraper_dataset_id: Optional[str]
    proxy_password: Optional[str]
    serp_zone: str
    scraping_browser_zone: str

    @property
    def mock_mode(self) -> bool:
        """True when API key or customer ID is absent — client runs in mock mode."""
        return not self.api_key or not self.customer_id

    @property
    def proxy_username(self) -> str:
        """Bright Data proxy auth username string."""
        return f"brd-customer-{self.customer_id}-zone-{self.zone}"

    @classmethod
    def from_app_settings(cls, s: AppSettings) -> "BrightDataSettings":
        return cls(
            api_key=s.BRIGHTDATA_API_KEY,
            customer_id=s.BRIGHTDATA_CUSTOMER_ID,
            web_unlocker_endpoint=s.BRIGHTDATA_WEB_UNLOCKER_ENDPOINT,
            serp_api_endpoint=s.BRIGHTDATA_SERP_API_ENDPOINT,
            zone=s.BRIGHTDATA_ZONE,
            mcp_server_url=s.BRIGHTDATA_MCP_SERVER_URL,
            scraper_dataset_id=s.BRIGHTDATA_SCRAPER_DATASET_ID,
            proxy_password=s.BRIGHTDATA_PROXY_PASSWORD,
            serp_zone=s.BRIGHTDATA_SERP_ZONE,
            scraping_browser_zone=s.BRIGHTDATA_SCRAPING_BROWSER_ZONE,
        )


@dataclass(frozen=True)
class WebIntelSettings:
    """Read-only view of web intelligence pipeline tuning fields."""
    refresh_interval_seconds: int
    audit_trail_max_entries: int
    ncc_live_rules_enabled: bool
    signal_graph_risk_threshold: float

    @classmethod
    def from_app_settings(cls, s: AppSettings) -> "WebIntelSettings":
        return cls(
            refresh_interval_seconds=s.WEB_INTEL_REFRESH_INTERVAL_SECONDS,
            audit_trail_max_entries=s.AUDIT_TRAIL_MAX_ENTRIES,
            ncc_live_rules_enabled=s.NCC_LIVE_RULES_ENABLED,
            signal_graph_risk_threshold=s.SIGNAL_GRAPH_RISK_THRESHOLD,
        )


def get_brightdata_settings() -> BrightDataSettings:
    """Return Bright Data config derived from the current AppSettings singleton."""
    return BrightDataSettings.from_app_settings(get_settings())


def get_web_intel_settings() -> WebIntelSettings:
    """Return web intelligence tuning config derived from the current AppSettings singleton."""
    return WebIntelSettings.from_app_settings(get_settings())
