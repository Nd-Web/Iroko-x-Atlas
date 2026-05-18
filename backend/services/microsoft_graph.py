"""
Microsoft Graph API Client
Handles OAuth2 token exchange, OneDrive/SharePoint file browsing, downloads,
and Microsoft Teams channel/message access.
Uses the existing Azure AD app registration (AZURE_CLIENT_ID / AZURE_CLIENT_SECRET).
"""
import os
import logging
from typing import Optional, Dict, Any, List, Tuple
from datetime import datetime

import httpx

logger = logging.getLogger(__name__)

GRAPH_BASE = "https://graph.microsoft.com/v1.0"
AUTHORITY = "https://login.microsoftonline.com"

# Reuse the existing service principal
CLIENT_ID = os.getenv("AZURE_CLIENT_ID", "")
CLIENT_SECRET = os.getenv("AZURE_CLIENT_SECRET", "")
TENANT_ID = "common"  # must be 'common' to accept personal + any-tenant accounts

# Scopes required for file access + Teams
SCOPES = [
    "Files.Read.All",
    "Sites.Read.All",
    "User.Read",
    "Team.ReadBasic.All",
    "Channel.ReadBasic.All",
    "ChannelMessage.Read.All",
    "offline_access",
]


def get_auth_url(redirect_uri: str, state: str = "") -> str:
    """
    Build the Microsoft OAuth2 authorization URL.
    The frontend redirects the user here to grant consent.
    """
    scope = " ".join(SCOPES)
    params = (
        f"client_id={CLIENT_ID}"
        f"&response_type=code"
        f"&redirect_uri={redirect_uri}"
        f"&response_mode=query"
        f"&scope={scope}"
    )
    if state:
        params += f"&state={state}"
    return f"{AUTHORITY}/{TENANT_ID}/oauth2/v2.0/authorize?{params}"


async def exchange_auth_code(
    code: str,
    redirect_uri: str,
) -> Dict[str, str]:
    """
    Exchange an authorization code for access + refresh tokens.
    Returns: {"access_token": "...", "refresh_token": "..."}
    """
    token_url = f"{AUTHORITY}/{TENANT_ID}/oauth2/v2.0/token"
    data = {
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "code": code,
        "redirect_uri": redirect_uri,
        "grant_type": "authorization_code",
        "scope": " ".join(SCOPES),
    }
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(token_url, data=data)
        resp.raise_for_status()
        body = resp.json()

    return {
        "access_token": body["access_token"],
        "refresh_token": body.get("refresh_token", ""),
    }


async def refresh_access_token(refresh_token: str) -> Dict[str, str]:
    """
    Use a refresh token to obtain a new access + refresh token pair.
    Returns: {"access_token": "...", "refresh_token": "..."}
    """
    token_url = f"{AUTHORITY}/{TENANT_ID}/oauth2/v2.0/token"
    data = {
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "refresh_token": refresh_token,
        "grant_type": "refresh_token",
        "scope": " ".join(SCOPES),
    }
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(token_url, data=data)
        resp.raise_for_status()
        body = resp.json()

    return {
        "access_token": body["access_token"],
        "refresh_token": body.get("refresh_token", refresh_token),
    }


def _auth_headers(access_token: str) -> Dict[str, str]:
    return {"Authorization": f"Bearer {access_token}"}


# ── User Profile ──────────────────────────────────────────────────────────────

async def get_user_profile(access_token: str) -> Dict[str, Any]:
    """Get the authenticated user's display name and email."""
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.get(
            f"{GRAPH_BASE}/me",
            headers=_auth_headers(access_token),
            params={"$select": "displayName,mail,userPrincipalName"},
        )
        resp.raise_for_status()
        return resp.json()


# ── OneDrive ──────────────────────────────────────────────────────────────────

async def get_user_default_drive(access_token: str) -> Dict[str, Any]:
    """Get the user's default OneDrive drive metadata."""
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.get(
            f"{GRAPH_BASE}/me/drive",
            headers=_auth_headers(access_token),
        )
        resp.raise_for_status()
        return resp.json()


# ── SharePoint Sites ──────────────────────────────────────────────────────────

async def list_sharepoint_sites(access_token: str) -> List[Dict[str, Any]]:
    """List SharePoint sites the user has access to via search."""
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.get(
            f"{GRAPH_BASE}/sites",
            headers=_auth_headers(access_token),
            params={"search": "*", "$top": "50"},
        )
        resp.raise_for_status()
        data = resp.json()

    sites = []
    for s in data.get("value", []):
        sites.append({
            "site_id": s.get("id", ""),
            "name": s.get("name", ""),
            "display_name": s.get("displayName", s.get("name", "")),
            "web_url": s.get("webUrl", ""),
        })
    return sites


async def get_site_default_drive(access_token: str, site_id: str) -> Dict[str, Any]:
    """Get the default document library drive for a SharePoint site."""
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.get(
            f"{GRAPH_BASE}/sites/{site_id}/drive",
            headers=_auth_headers(access_token),
        )
        resp.raise_for_status()
        return resp.json()


# ── Drive Items (Browse) ─────────────────────────────────────────────────────

async def list_drive_items(
    access_token: str,
    drive_id: str,
    folder_id: Optional[str] = None,
    path: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """
    List files and folders in a drive.
    Use folder_id to list children of a specific folder,
    or path (e.g. "/Documents/Reports") for path-based browsing.
    If neither is given, lists the root.
    """
    if folder_id:
        url = f"{GRAPH_BASE}/drives/{drive_id}/items/{folder_id}/children"
    elif path and path != "/":
        clean_path = path.strip("/")
        url = f"{GRAPH_BASE}/drives/{drive_id}/root:/{clean_path}:/children"
    else:
        url = f"{GRAPH_BASE}/drives/{drive_id}/root/children"

    items = []
    async with httpx.AsyncClient(timeout=30) as client:
        while url:
            resp = await client.get(
                url,
                headers=_auth_headers(access_token),
                params={"$top": "200", "$orderby": "name"},
            )
            resp.raise_for_status()
            data = resp.json()

            for item in data.get("value", []):
                items.append(_parse_drive_item(item))

            url = data.get("@odata.nextLink")

    return items


async def get_drive_item(
    access_token: str,
    drive_id: str,
    item_id: str,
) -> Dict[str, Any]:
    """Get metadata for a single drive item."""
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.get(
            f"{GRAPH_BASE}/drives/{drive_id}/items/{item_id}",
            headers=_auth_headers(access_token),
        )
        resp.raise_for_status()
        return _parse_drive_item(resp.json())


async def download_drive_item(
    access_token: str,
    drive_id: str,
    item_id: str,
    dest_path: str,
) -> int:
    """
    Download a drive item to a local file path.
    Returns the number of bytes written.
    """
    # Get the download URL
    async with httpx.AsyncClient(timeout=15, follow_redirects=False) as client:
        resp = await client.get(
            f"{GRAPH_BASE}/drives/{drive_id}/items/{item_id}/content",
            headers=_auth_headers(access_token),
        )
        # Graph returns 302 redirect to the actual download URL
        if resp.status_code in (301, 302):
            download_url = resp.headers.get("Location", "")
        elif resp.status_code == 200:
            # Small files may return content directly
            with open(dest_path, "wb") as f:
                f.write(resp.content)
            return len(resp.content)
        else:
            resp.raise_for_status()

    # Stream the actual file download
    total = 0
    async with httpx.AsyncClient(timeout=120) as client:
        async with client.stream("GET", download_url) as stream:
            stream.raise_for_status()
            with open(dest_path, "wb") as f:
                async for chunk in stream.aiter_bytes(chunk_size=65536):
                    f.write(chunk)
                    total += len(chunk)
    return total


# ── Delta Query (for auto-sync) ──────────────────────────────────────────────

async def get_drive_delta(
    access_token: str,
    drive_id: str,
    delta_link: Optional[str] = None,
) -> Tuple[List[Dict[str, Any]], str]:
    """
    Use Graph delta query to get changed items since last sync.
    Returns (changed_items, next_delta_link).
    On first call pass delta_link=None to get the full initial state.
    """
    if delta_link:
        url = delta_link
    else:
        url = f"{GRAPH_BASE}/drives/{drive_id}/root/delta"

    items = []
    next_delta = ""
    async with httpx.AsyncClient(timeout=60) as client:
        while url:
            resp = await client.get(url, headers=_auth_headers(access_token))
            resp.raise_for_status()
            data = resp.json()

            for item in data.get("value", []):
                items.append(_parse_drive_item(item))

            # @odata.nextLink = more pages; @odata.deltaLink = checkpoint for next sync
            url = data.get("@odata.nextLink")
            if not url:
                next_delta = data.get("@odata.deltaLink", "")

    return items, next_delta


# ── Microsoft Teams ───────────────────────────────────────────────────────────

async def list_joined_teams(access_token: str) -> List[Dict[str, Any]]:
    """List Teams the authenticated user is a member of."""
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.get(
            f"{GRAPH_BASE}/me/joinedTeams",
            headers=_auth_headers(access_token),
            params={"$select": "id,displayName,description"},
        )
        resp.raise_for_status()
        data = resp.json()

    return [
        {
            "id": t.get("id", ""),
            "display_name": t.get("displayName", ""),
            "description": t.get("description", ""),
        }
        for t in data.get("value", [])
    ]


async def list_team_channels(
    access_token: str, team_id: str
) -> List[Dict[str, Any]]:
    """List channels in a Team."""
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.get(
            f"{GRAPH_BASE}/teams/{team_id}/channels",
            headers=_auth_headers(access_token),
            params={"$select": "id,displayName,description"},
        )
        resp.raise_for_status()
        data = resp.json()

    return [
        {
            "id": ch.get("id", ""),
            "team_id": team_id,
            "display_name": ch.get("displayName", ""),
            "description": ch.get("description", ""),
        }
        for ch in data.get("value", [])
    ]


async def get_channel_messages(
    access_token: str,
    team_id: str,
    channel_id: str,
    top: int = 50,
) -> List[Dict[str, Any]]:
    """
    Get recent messages from a Teams channel.
    Returns normalised message objects.
    """
    url = f"{GRAPH_BASE}/teams/{team_id}/channels/{channel_id}/messages"
    messages = []
    async with httpx.AsyncClient(timeout=30) as client:
        while url and len(messages) < top:
            resp = await client.get(
                url,
                headers=_auth_headers(access_token),
                params={"$top": str(min(top, 50))},
            )
            resp.raise_for_status()
            data = resp.json()

            for msg in data.get("value", []):
                body = msg.get("body", {})
                sender = msg.get("from", {}).get("user", {}) if msg.get("from") else {}
                attachments = msg.get("attachments", [])
                messages.append({
                    "id": msg.get("id", ""),
                    "text": body.get("content", ""),
                    "content_type": body.get("contentType", "text"),
                    "sender_name": sender.get("displayName", "Unknown"),
                    "created_at": msg.get("createdDateTime"),
                    "has_attachments": len(attachments) > 0,
                    "attachments": [
                        {
                            "id": a.get("id", ""),
                            "name": a.get("name", ""),
                            "content_type": a.get("contentType", ""),
                            "content_url": a.get("contentUrl", ""),
                        }
                        for a in attachments
                    ],
                })

            url = data.get("@odata.nextLink")

    return messages


async def get_channel_files_drive(
    access_token: str,
    team_id: str,
    channel_id: str,
) -> Optional[str]:
    """
    Get the drive ID for a Teams channel's SharePoint-backed file tab.
    Returns the drive ID or None.
    """
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(
                f"{GRAPH_BASE}/teams/{team_id}/channels/{channel_id}/filesFolder",
                headers=_auth_headers(access_token),
            )
            resp.raise_for_status()
            data = resp.json()
        return data.get("parentReference", {}).get("driveId")
    except Exception as e:
        logger.warning(f"Could not get channel files drive: {e}")
        return None


# ── Helpers ───────────────────────────────────────────────────────────────────

def _parse_drive_item(item: Dict[str, Any]) -> Dict[str, Any]:
    """Normalise a Graph driveItem into our schema."""
    is_folder = "folder" in item
    modified_raw = item.get("lastModifiedDateTime")
    modified_at = None
    if modified_raw:
        try:
            modified_at = datetime.fromisoformat(modified_raw.replace("Z", "+00:00"))
        except (ValueError, TypeError):
            pass

    return {
        "id": item.get("id", ""),
        "name": item.get("name", ""),
        "item_type": "folder" if is_folder else "file",
        "size": item.get("size"),
        "mime_type": item.get("file", {}).get("mimeType") if not is_folder else None,
        "modified_at": modified_at,
        "web_url": item.get("webUrl"),
        "download_url": item.get("@microsoft.graph.downloadUrl"),
        "parent_path": item.get("parentReference", {}).get("path", ""),
        "deleted": item.get("deleted") is not None,
    }
