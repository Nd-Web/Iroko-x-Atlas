"""
core/config.py — Pydantic BaseSettings for Iroko AI.

Loads all required and optional environment variables from .env and exports
a `settings` singleton for use across the application.

This module intentionally mirrors (and is compatible with) the comprehensive
settings in services/settings.py but provides a lighter, import-friendly
interface for core/ and agents/ modules that just need config values.
"""

import os
from typing import Optional
from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Central configuration loaded from environment variables."""

    # ── Critical ──────────────────────────────────────────────────────────────

    DATABASE_URL: str = Field(
        default="sqlite:///./atlas.db",
        description="SQLAlchemy database connection string",
    )
    SECRET_KEY: str = Field(
        default="atlas-secret-key-change-in-production",
        description="JWT signing key",
    )
    ALGORITHM: str = Field(
        default="HS256",
        description="JWT hashing algorithm",
    )
    ACCESS_TOKEN_EXPIRE_MINUTES: int = Field(
        default=30,
        description="Access token TTL in minutes",
    )

    # ── Azure OpenAI ──────────────────────────────────────────────────────────

    AZURE_OPENAI_ENDPOINT: str = Field(
        default="",
        description="Azure OpenAI service endpoint",
    )
    AZURE_OPENAI_API_KEY: str = Field(
        default="",
        description="Azure OpenAI API key",
    )
    AZURE_OPENAI_DEPLOYMENT: str = Field(
        default="gpt-4o",
        description="Azure OpenAI GPT-4o deployment name",
    )
    AZURE_OPENAI_EMBEDDING_DEPLOYMENT: str = Field(
        default="text-embedding-3-large",
        description="Azure OpenAI embedding model deployment name",
    )
    AZURE_OPENAI_API_VERSION: str = Field(
        default="2025-01-01-preview",
        description="Azure OpenAI API version",
    )

    # ── Azure AI Search ───────────────────────────────────────────────────────

    AZURE_SEARCH_ENDPOINT: str = Field(
        default="",
        description="Azure AI Search service endpoint",
    )
    AZURE_SEARCH_KEY: str = Field(
        default="",
        description="Azure AI Search admin API key",
    )
    AZURE_SEARCH_INDEX: str = Field(
        default="iroko-chunks",
        description="Azure AI Search index name",
    )

    # ── Azure Blob Storage ────────────────────────────────────────────────────

    AZURE_BLOB_CONNECTION_STRING: str = Field(
        default="",
        description="Azure Blob Storage connection string",
    )
    AZURE_BLOB_CONTAINER: str = Field(
        default="raw-documents",
        description="Blob container name for document storage",
    )

    # ── Cosmos DB ─────────────────────────────────────────────────────────────

    COSMOS_ENDPOINT: str = Field(
        default="",
        description="Cosmos DB Gremlin endpoint",
    )
    COSMOS_KEY: str = Field(
        default="",
        description="Cosmos DB primary key",
    )
    COSMOS_DATABASE: str = Field(
        default="iroko-graph-db",
        description="Cosmos DB database name",
    )

    # ── App ───────────────────────────────────────────────────────────────────

    FRONTEND_URL: str = Field(
        default="http://localhost:3000",
        description="Frontend URL for CORS and email links",
    )

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True
        extra = "ignore"


# ── Singleton ─────────────────────────────────────────────────────────────────

settings = Settings()
