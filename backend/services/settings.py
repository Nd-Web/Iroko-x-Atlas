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

    if warnings:
        logger.warning("Optional environment variables not set:")
        for w in warnings:
            logger.warning(f"  [!]  {w}")
