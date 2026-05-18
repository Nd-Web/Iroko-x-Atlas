"""
Slack API Client
Handles OAuth2 token exchange, channel listing, message history,
and file downloads via the Slack Web API.
"""
import os
import logging
from typing import Optional, Dict, Any, List
from datetime import datetime

import httpx

logger = logging.getLogger(__name__)

SLACK_API_BASE = "https://slack.com/api"
SLACK_AUTH_URL = "https://slack.com/oauth/v2/authorize"
SLACK_TOKEN_URL = "https://slack.com/api/oauth.v2.access"

# Slack app credentials — set via env or Key Vault
SLACK_CLIENT_ID = os.getenv("SLACK_CLIENT_ID", "")
SLACK_CLIENT_SECRET = os.getenv("SLACK_CLIENT_SECRET", "")

# Bot token scopes for reading channels, messages, and files
SLACK_SCOPES = [
    "channels:read",
    "channels:history",
    "groups:read",
    "groups:history",
    "files:read",
    "users:read",
    "team:read",
]


def get_auth_url(redirect_uri: str, state: str = "") -> str:
    """Build the Slack OAuth2 authorization URL."""
    scope = ",".join(SLACK_SCOPES)
    params = (
        f"client_id={SLACK_CLIENT_ID}"
        f"&scope={scope}"
        f"&redirect_uri={redirect_uri}"
    )
    if state:
        params += f"&state={state}"
    return f"{SLACK_AUTH_URL}?{params}"


async def exchange_auth_code(
    code: str, redirect_uri: str
) -> Dict[str, str]:
    """
    Exchange an OAuth2 authorization code for a bot access token.
    Slack v2 OAuth returns a bot token (no refresh token by default).
    Returns: {"access_token": "xoxb-...", "team_id": "...", "team_name": "..."}
    """
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            SLACK_TOKEN_URL,
            data={
                "client_id": SLACK_CLIENT_ID,
                "client_secret": SLACK_CLIENT_SECRET,
                "code": code,
                "redirect_uri": redirect_uri,
            },
        )
        resp.raise_for_status()
        body = resp.json()

    if not body.get("ok"):
        raise ValueError(f"Slack OAuth error: {body.get('error', 'unknown')}")

    return {
        "access_token": body.get("access_token", ""),
        "team_id": body.get("team", {}).get("id", ""),
        "team_name": body.get("team", {}).get("name", ""),
        "bot_user_id": body.get("bot_user_id", ""),
    }


def _auth_headers(access_token: str) -> Dict[str, str]:
    return {"Authorization": f"Bearer {access_token}"}


# ── Workspace Info ────────────────────────────────────────────────────────────

async def get_team_info(access_token: str) -> Dict[str, Any]:
    """Get workspace (team) info."""
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.get(
            f"{SLACK_API_BASE}/team.info",
            headers=_auth_headers(access_token),
        )
        resp.raise_for_status()
        data = resp.json()
    if not data.get("ok"):
        raise ValueError(f"Slack API error: {data.get('error')}")
    return data.get("team", {})


# ── Channels ──────────────────────────────────────────────────────────────────

async def list_channels(
    access_token: str,
    include_private: bool = False,
    limit: int = 200,
) -> List[Dict[str, Any]]:
    """List public (and optionally private) channels."""
    types = "public_channel"
    if include_private:
        types = "public_channel,private_channel"

    channels = []
    cursor = None
    async with httpx.AsyncClient(timeout=30) as client:
        while True:
            params = {"types": types, "limit": min(limit, 200)}
            if cursor:
                params["cursor"] = cursor

            resp = await client.get(
                f"{SLACK_API_BASE}/conversations.list",
                headers=_auth_headers(access_token),
                params=params,
            )
            resp.raise_for_status()
            data = resp.json()

            if not data.get("ok"):
                raise ValueError(f"Slack API error: {data.get('error')}")

            for ch in data.get("channels", []):
                channels.append({
                    "id": ch.get("id", ""),
                    "name": ch.get("name", ""),
                    "is_private": ch.get("is_private", False),
                    "topic": (ch.get("topic") or {}).get("value", ""),
                    "member_count": ch.get("num_members", 0),
                })

            cursor = data.get("response_metadata", {}).get("next_cursor")
            if not cursor:
                break

    return channels


# ── Messages (History) ────────────────────────────────────────────────────────

async def get_channel_history(
    access_token: str,
    channel_id: str,
    oldest: Optional[str] = None,
    limit: int = 100,
) -> List[Dict[str, Any]]:
    """
    Get message history for a channel.
    `oldest` is a Slack timestamp (e.g. "1234567890.123456") — only messages
    after this timestamp are returned. Used for incremental sync.
    """
    messages = []
    cursor = None
    async with httpx.AsyncClient(timeout=30) as client:
        while True:
            params: Dict[str, Any] = {"channel": channel_id, "limit": min(limit, 100)}
            if oldest:
                params["oldest"] = oldest
            if cursor:
                params["cursor"] = cursor

            resp = await client.get(
                f"{SLACK_API_BASE}/conversations.history",
                headers=_auth_headers(access_token),
                params=params,
            )
            resp.raise_for_status()
            data = resp.json()

            if not data.get("ok"):
                raise ValueError(f"Slack API error: {data.get('error')}")

            for msg in data.get("messages", []):
                if msg.get("type") != "message":
                    continue
                messages.append({
                    "id": msg.get("ts", ""),
                    "text": msg.get("text", ""),
                    "user": msg.get("user", ""),
                    "timestamp": msg.get("ts", ""),
                    "has_files": bool(msg.get("files")),
                    "files": msg.get("files", []),
                })

            if not data.get("has_more"):
                break
            cursor = data.get("response_metadata", {}).get("next_cursor")
            if not cursor:
                break

    return messages


# ── Files ─────────────────────────────────────────────────────────────────────

async def list_files(
    access_token: str,
    channel_id: Optional[str] = None,
    ts_from: Optional[str] = None,
    limit: int = 100,
) -> List[Dict[str, Any]]:
    """List files shared in the workspace, optionally filtered by channel."""
    params: Dict[str, Any] = {"count": min(limit, 100)}
    if channel_id:
        params["channel"] = channel_id
    if ts_from:
        params["ts_from"] = ts_from

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(
            f"{SLACK_API_BASE}/files.list",
            headers=_auth_headers(access_token),
            params=params,
        )
        resp.raise_for_status()
        data = resp.json()

    if not data.get("ok"):
        raise ValueError(f"Slack API error: {data.get('error')}")

    files = []
    for f in data.get("files", []):
        files.append({
            "id": f.get("id", ""),
            "name": f.get("name", ""),
            "title": f.get("title", ""),
            "filetype": f.get("filetype", ""),
            "size": f.get("size", 0),
            "url_private_download": f.get("url_private_download", ""),
            "created": f.get("created", 0),
            "channels": f.get("channels", []),
        })
    return files


async def download_file(
    access_token: str,
    url_private_download: str,
    dest_path: str,
) -> int:
    """Download a Slack file using the bot token for auth."""
    total = 0
    async with httpx.AsyncClient(timeout=120) as client:
        async with client.stream(
            "GET",
            url_private_download,
            headers=_auth_headers(access_token),
        ) as stream:
            stream.raise_for_status()
            with open(dest_path, "wb") as f:
                async for chunk in stream.aiter_bytes(chunk_size=65536):
                    f.write(chunk)
                    total += len(chunk)
    return total


# ── Users ─────────────────────────────────────────────────────────────────────

async def get_user_info(access_token: str, user_id: str) -> Dict[str, Any]:
    """Get a Slack user's profile."""
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.get(
            f"{SLACK_API_BASE}/users.info",
            headers=_auth_headers(access_token),
            params={"user": user_id},
        )
        resp.raise_for_status()
        data = resp.json()
    if not data.get("ok"):
        return {"name": user_id}
    user = data.get("user", {})
    return {
        "id": user.get("id", ""),
        "name": user.get("real_name", user.get("name", "")),
        "display_name": user.get("profile", {}).get("display_name", ""),
    }
