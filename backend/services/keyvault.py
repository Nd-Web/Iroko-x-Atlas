"""
Azure Key Vault secret loader.
Runs once at startup — populates os.environ from irokovault2026.
Uses DefaultAzureCredential, so set AZURE_CLIENT_ID / AZURE_CLIENT_SECRET /
AZURE_TENANT_ID for service-principal auth (no az login required).
"""
import os
import logging

logger = logging.getLogger(__name__)

VAULT_URL = os.getenv("AZURE_KEYVAULT_URL", "https://irokovault2026.vault.azure.net/")

# Key Vault secret name → environment variable name
SECRET_MAP = {
    "search-admin-key":                 "AZURE_SEARCH_API_KEY",
    "search-endpoint":                  "AZURE_SEARCH_ENDPOINT",
    "ai-services-key":                  "AZURE_OPENAI_API_KEY",
    "ai-services-endpoint":             "AZURE_OPENAI_ENDPOINT",
    "document-intelligence-key":        "AZURE_DOCUMENT_INTELLIGENCE_KEY",
    "document-intelligence-endpoint":   "AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT",
    "storage-connection-string":        "AZURE_STORAGE_CONNECTION_STRING",
    "cosmosdb-gremlin-endpoint":        "COSMOS_GREMLIN_ENDPOINT",
    "cosmosdb-primary-key":             "COSMOS_PRIMARY_KEY",
    "speech-key":                       "AZURE_SPEECH_KEY",
    "acs-connection-string":            "ACS_CONNECTION_STRING",
    "jwt-secret-key":                   "SECRET_KEY",
    # ── Slack connector ───────────────────────────────────────────────────
    "slack-client-id":                  "SLACK_CLIENT_ID",
    "slack-client-secret":              "SLACK_CLIENT_SECRET",
    "slack-signing-secret":             "SLACK_SIGNING_SECRET",
    "slack-verification-token":         "SLACK_VERIFICATION_TOKEN",
    # ── ServiceNow connector ──────────────────────────────────────────────
    "servicenow-client-id":             "SERVICENOW_CLIENT_ID",
    "servicenow-client-secret":         "SERVICENOW_CLIENT_SECRET",
    # ── Database ──────────────────────────────────────────────────────────
    "database-url":                     "DATABASE_URL",
}


def load_secrets_from_keyvault() -> int:
    """
    Pull all mapped secrets from Key Vault into os.environ.
    Any env var already set (e.g. from .env) takes precedence — Key Vault
    fills only the gaps, so local overrides still work.
    Returns number of secrets loaded.
    """
    try:
        from azure.identity import DefaultAzureCredential
        from azure.keyvault.secrets import SecretClient
    except ImportError:
        logger.warning(
            "azure-identity or azure-keyvault-secrets not installed — "
            "skipping Key Vault load. Run: pip install azure-identity azure-keyvault-secrets"
        )
        return 0

    try:
        credential = DefaultAzureCredential()
        client = SecretClient(vault_url=VAULT_URL, credential=credential)
    except Exception as e:
        logger.error(f"Key Vault: failed to create client — {e}")
        return 0

    loaded = 0
    for secret_name, env_var in SECRET_MAP.items():
        if os.getenv(env_var):
            logger.debug(f"Key Vault: skipping '{secret_name}' — {env_var} already set.")
            continue
        try:
            value = client.get_secret(secret_name).value
            if value:
                os.environ[env_var] = value
                loaded += 1
                logger.info(f"Key Vault: loaded {env_var}")
        except Exception as e:
            logger.warning(f"Key Vault: could not load '{secret_name}' — {e}")

    logger.info(f"Key Vault: {loaded} secret(s) loaded into environment.")
    return loaded
