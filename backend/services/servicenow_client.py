"""
ServiceNow REST API Client
Handles OAuth2 authentication and fetching incidents, knowledge articles,
change requests, and attachments from a ServiceNow instance.
"""
import os
import logging
from typing import Optional, Dict, Any, List

import httpx

logger = logging.getLogger(__name__)

# ServiceNow OAuth2 endpoints are instance-specific:
#   https://<instance>.service-now.com/oauth_token.do
SERVICENOW_CLIENT_ID = os.getenv("SERVICENOW_CLIENT_ID", "")
SERVICENOW_CLIENT_SECRET = os.getenv("SERVICENOW_CLIENT_SECRET", "")


def _api_base(instance_url: str) -> str:
    """Normalise instance URL to API base."""
    url = instance_url.rstrip("/")
    if not url.startswith("https://"):
        url = f"https://{url}"
    return url


def get_auth_url(instance_url: str, redirect_uri: str, state: str = "") -> str:
    """Build ServiceNow OAuth2 authorization URL."""
    base = _api_base(instance_url)
    params = (
        f"response_type=code"
        f"&client_id={SERVICENOW_CLIENT_ID}"
        f"&redirect_uri={redirect_uri}"
    )
    if state:
        params += f"&state={state}"
    return f"{base}/oauth_auth.do?{params}"


async def exchange_auth_code(
    instance_url: str,
    code: str,
    redirect_uri: str,
) -> Dict[str, str]:
    """
    Exchange authorization code for access + refresh tokens.
    Returns: {"access_token": "...", "refresh_token": "...", "instance_url": "..."}
    """
    base = _api_base(instance_url)
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            f"{base}/oauth_token.do",
            data={
                "grant_type": "authorization_code",
                "client_id": SERVICENOW_CLIENT_ID,
                "client_secret": SERVICENOW_CLIENT_SECRET,
                "code": code,
                "redirect_uri": redirect_uri,
            },
        )
        resp.raise_for_status()
        body = resp.json()

    if "error" in body:
        raise ValueError(f"ServiceNow OAuth error: {body.get('error_description', body['error'])}")

    return {
        "access_token": body["access_token"],
        "refresh_token": body.get("refresh_token", ""),
        "instance_url": base,
    }


async def refresh_access_token(
    instance_url: str,
    refresh_token: str,
) -> Dict[str, str]:
    """Refresh an expired access token."""
    base = _api_base(instance_url)
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            f"{base}/oauth_token.do",
            data={
                "grant_type": "refresh_token",
                "client_id": SERVICENOW_CLIENT_ID,
                "client_secret": SERVICENOW_CLIENT_SECRET,
                "refresh_token": refresh_token,
            },
        )
        resp.raise_for_status()
        body = resp.json()

    if "error" in body:
        raise ValueError(f"ServiceNow refresh error: {body.get('error_description', body['error'])}")

    return {
        "access_token": body["access_token"],
        "refresh_token": body.get("refresh_token", refresh_token),
    }


def _auth_headers(access_token: str) -> Dict[str, str]:
    return {
        "Authorization": f"Bearer {access_token}",
        "Accept": "application/json",
        "Content-Type": "application/json",
    }


# ── Tables & Records ─────────────────────────────────────────────────────────

SUPPORTED_TABLES = {
    "incident": "Incidents",
    "kb_knowledge": "Knowledge Articles",
    "change_request": "Change Requests",
    "problem": "Problems",
    "sc_request": "Service Requests",
    "cmdb_ci": "Configuration Items",
}


async def list_tables(instance_url: str, access_token: str) -> List[Dict[str, str]]:
    """Return supported tables that can be browsed/synced."""
    return [
        {"table_name": k, "label": v}
        for k, v in SUPPORTED_TABLES.items()
    ]


async def query_table(
    instance_url: str,
    access_token: str,
    table: str,
    query: str = "",
    fields: Optional[List[str]] = None,
    limit: int = 50,
    offset: int = 0,
    order_by: str = "sys_updated_on",
    order_dir: str = "desc",
) -> List[Dict[str, Any]]:
    """
    Query a ServiceNow table via the Table API.
    Returns a list of records.
    """
    base = _api_base(instance_url)
    params: Dict[str, Any] = {
        "sysparm_limit": limit,
        "sysparm_offset": offset,
        "sysparm_display_value": "true",
        "sysparm_order_by": f"{order_dir}:{order_by}" if order_dir == "desc" else order_by,
    }
    if query:
        params["sysparm_query"] = query
    if fields:
        params["sysparm_fields"] = ",".join(fields)

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(
            f"{base}/api/now/table/{table}",
            headers=_auth_headers(access_token),
            params=params,
        )
        resp.raise_for_status()
        data = resp.json()

    records = []
    for rec in data.get("result", []):
        records.append({
            "sys_id": rec.get("sys_id", ""),
            "number": rec.get("number", ""),
            "short_description": rec.get("short_description", ""),
            "description": rec.get("description", ""),
            "state": rec.get("state", ""),
            "priority": rec.get("priority", ""),
            "assigned_to": rec.get("assigned_to", ""),
            "created_on": rec.get("sys_created_on", ""),
            "updated_on": rec.get("sys_updated_on", ""),
            "category": rec.get("category", ""),
            "table": table,
        })
    return records


async def get_record(
    instance_url: str,
    access_token: str,
    table: str,
    sys_id: str,
) -> Dict[str, Any]:
    """Fetch a single record with all fields."""
    base = _api_base(instance_url)
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.get(
            f"{base}/api/now/table/{table}/{sys_id}",
            headers=_auth_headers(access_token),
            params={"sysparm_display_value": "true"},
        )
        resp.raise_for_status()
        data = resp.json()
    return data.get("result", {})


# ── Knowledge Articles (full text) ───────────────────────────────────────────

async def get_knowledge_article_text(
    instance_url: str,
    access_token: str,
    sys_id: str,
) -> str:
    """Get the full text content of a knowledge article."""
    record = await get_record(instance_url, access_token, "kb_knowledge", sys_id)
    # The 'text' field contains the HTML body; 'short_description' is the title
    return record.get("text", record.get("description", ""))


# ── Attachments ───────────────────────────────────────────────────────────────

async def list_attachments(
    instance_url: str,
    access_token: str,
    table: str,
    sys_id: str,
) -> List[Dict[str, Any]]:
    """List attachments on a specific record."""
    base = _api_base(instance_url)
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.get(
            f"{base}/api/now/attachment",
            headers=_auth_headers(access_token),
            params={
                "sysparm_query": f"table_name={table}^table_sys_id={sys_id}",
            },
        )
        resp.raise_for_status()
        data = resp.json()

    attachments = []
    for att in data.get("result", []):
        attachments.append({
            "sys_id": att.get("sys_id", ""),
            "file_name": att.get("file_name", ""),
            "content_type": att.get("content_type", ""),
            "size_bytes": int(att.get("size_bytes", 0)),
            "download_link": att.get("download_link", ""),
        })
    return attachments


async def download_attachment(
    instance_url: str,
    access_token: str,
    attachment_sys_id: str,
    dest_path: str,
) -> int:
    """Download an attachment to a local file."""
    base = _api_base(instance_url)
    total = 0
    async with httpx.AsyncClient(timeout=120) as client:
        async with client.stream(
            "GET",
            f"{base}/api/now/attachment/{attachment_sys_id}/file",
            headers={"Authorization": f"Bearer {access_token}"},
        ) as stream:
            stream.raise_for_status()
            with open(dest_path, "wb") as f:
                async for chunk in stream.aiter_bytes(chunk_size=65536):
                    f.write(chunk)
                    total += len(chunk)
    return total


# ── Incremental Query ────────────────────────────────────────────────────────

async def query_updated_since(
    instance_url: str,
    access_token: str,
    table: str,
    since_datetime: str,
    limit: int = 200,
) -> List[Dict[str, Any]]:
    """
    Query records updated since a given datetime string (format: YYYY-MM-DD HH:MM:SS).
    Used by auto-sync to detect changes.
    """
    query = f"sys_updated_on>{since_datetime}^ORDERBYsys_updated_on"
    return await query_table(
        instance_url=instance_url,
        access_token=access_token,
        table=table,
        query=query,
        limit=limit,
    )
