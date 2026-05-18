"""
Connectors Route — Manage SharePoint, OneDrive, Teams, Slack, ServiceNow connections.
OAuth2 flow, browse content, import documents, and control auto-sync.
"""
import os
import logging
from typing import Optional
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy import func
from sqlalchemy.orm import Session

from models.database import get_db, User, Document, Connector, generate_id
from models.schemas import (
    ConnectorCreateRequest, ConnectorUpdateRequest,
    ConnectorResponse, ConnectorListResponse,
    DriveItemResponse, BrowseResponse, SharePointSiteResponse,
    ImportFileRequest, ImportFileResult, ImportResponse,
    SlackChannelResponse, TeamsTeamResponse, TeamsChannelResponse,
    ServiceNowRecordResponse,
)
from services.auth_utils import get_current_user
from services.token_encryption import encrypt_token, decrypt_token
from services.document_processor import process_document
from services.blob_storage import upload_document as upload_to_blob
from services.cosmos_graph import upsert_document_node

router = APIRouter(prefix="/api/connectors", tags=["Connectors"])
logger = logging.getLogger(__name__)

UPLOAD_DIR = "/tmp/atlas_uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

# Types that use Microsoft Graph
MICROSOFT_TYPES = {"sharepoint", "onedrive", "microsoft_teams"}


# ── Helpers ───────────────────────────────────────────────────────────────────

async def _get_microsoft_token(connector: Connector) -> str:
    from services import microsoft_graph as graph
    refresh_token = decrypt_token(connector.encrypted_refresh_token)
    tokens = await graph.refresh_access_token(refresh_token)
    if tokens["refresh_token"] != refresh_token:
        connector.encrypted_refresh_token = encrypt_token(tokens["refresh_token"])
    return tokens["access_token"]


async def _get_servicenow_token(connector: Connector) -> str:
    from services import servicenow_client as snow
    instance_url = (connector.extra_config or {}).get("instance_url", "")
    refresh_token = decrypt_token(connector.encrypted_refresh_token)
    tokens = await snow.refresh_access_token(instance_url, refresh_token)
    if tokens["refresh_token"] != refresh_token:
        connector.encrypted_refresh_token = encrypt_token(tokens["refresh_token"])
    return tokens["access_token"]


def _get_connector_or_404(connector_id: str, user: User, db: Session) -> Connector:
    connector = db.query(Connector).filter(
        Connector.id == connector_id, Connector.user_id == user.id
    ).first()
    if not connector:
        raise HTTPException(status_code=404, detail="Connector not found")
    if connector.status == "expired":
        raise HTTPException(status_code=401, detail="Connector token expired — please re-authenticate.")
    return connector


# ── OAuth Flow ────────────────────────────────────────────────────────────────

@router.get("/auth-url")
async def get_auth_url(
    redirect_uri: str,
    connector_type: str = "onedrive",
    instance_url: Optional[str] = None,
    current_user: User = Depends(get_current_user),
):
    """Generate the OAuth2 authorization URL for any supported platform."""
    state = f"{current_user.id}:{connector_type}"

    if connector_type in MICROSOFT_TYPES:
        from services import microsoft_graph as graph
        url = graph.get_auth_url(redirect_uri=redirect_uri, state=state)
    elif connector_type == "slack":
        from services import slack_client as slack
        url = slack.get_auth_url(redirect_uri=redirect_uri, state=state)
    elif connector_type == "servicenow":
        if not instance_url:
            raise HTTPException(400, "instance_url is required for ServiceNow")
        from services import servicenow_client as snow
        url = snow.get_auth_url(instance_url, redirect_uri=redirect_uri, state=state)
    else:
        raise HTTPException(400, f"Unsupported connector type: {connector_type}")

    return {"auth_url": url, "state": state}


@router.post("", response_model=ConnectorResponse, status_code=201)
async def create_connector(
    body: ConnectorCreateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Exchange an OAuth2 auth code to create a new connector."""
    ctype = body.connector_type.value
    display_name = body.display_name
    drive_id = None
    extra_config = body.extra_config or {}
    refresh_token_value = ""

    # ── Microsoft (SharePoint / OneDrive / Teams) ──
    if ctype in MICROSOFT_TYPES:
        from services import microsoft_graph as graph
        try:
            tokens = await graph.exchange_auth_code(body.auth_code, body.redirect_uri)
        except Exception as e:
            raise HTTPException(400, f"Microsoft OAuth failed: {e}")

        access_token = tokens["access_token"]
        refresh_token_value = tokens["refresh_token"]
        if not refresh_token_value:
            raise HTTPException(400, "No refresh token — ensure offline_access scope is granted.")

        try:
            profile = await graph.get_user_profile(access_token)
        except Exception:
            profile = {}

        user_name = profile.get("displayName", "User")

        if ctype == "onedrive":
            try:
                drive = await graph.get_user_default_drive(access_token)
                drive_id = drive.get("id")
            except Exception:
                pass
            display_name = display_name or f"{user_name}'s OneDrive"

        elif ctype == "sharepoint":
            if body.site_id:
                try:
                    d = await graph.get_site_default_drive(access_token, body.site_id)
                    drive_id = d.get("id")
                except Exception:
                    pass
            display_name = display_name or "SharePoint Connection"

        elif ctype == "microsoft_teams":
            display_name = display_name or f"{user_name}'s Teams"

    # ── Slack ──
    elif ctype == "slack":
        from services import slack_client as slack
        try:
            result = await slack.exchange_auth_code(body.auth_code, body.redirect_uri)
        except Exception as e:
            raise HTTPException(400, f"Slack OAuth failed: {e}")

        refresh_token_value = result["access_token"]  # Slack bot tokens don't expire
        extra_config["team_id"] = result.get("team_id", "")
        extra_config["team_name"] = result.get("team_name", "")
        display_name = display_name or f"Slack — {result.get('team_name', 'Workspace')}"

    # ── ServiceNow ──
    elif ctype == "servicenow":
        from services import servicenow_client as snow
        instance_url = extra_config.get("instance_url", "")
        if not instance_url:
            raise HTTPException(400, "extra_config.instance_url is required for ServiceNow")
        try:
            result = await snow.exchange_auth_code(instance_url, body.auth_code, body.redirect_uri)
        except Exception as e:
            raise HTTPException(400, f"ServiceNow OAuth failed: {e}")

        refresh_token_value = result["refresh_token"]
        extra_config["instance_url"] = result.get("instance_url", instance_url)
        if "tables" not in extra_config:
            extra_config["tables"] = ["incident", "kb_knowledge", "change_request"]
        display_name = display_name or "ServiceNow Connection"
    else:
        raise HTTPException(400, f"Unsupported connector type: {ctype}")

    connector = Connector(
        id=generate_id(),
        user_id=current_user.id,
        connector_type=ctype,
        display_name=display_name or "Connected Source",
        site_id=body.site_id,
        drive_id=drive_id,
        extra_config=extra_config,
        encrypted_refresh_token=encrypt_token(refresh_token_value),
        status="active",
        auto_sync=True,
        sync_interval_minutes=30,
    )
    db.add(connector)
    db.commit()
    db.refresh(connector)

    logger.info(f"Connector created: {connector.display_name} (type={ctype}, user={current_user.email})")
    return connector


# ── CRUD ──────────────────────────────────────────────────────────────────────

@router.get("", response_model=ConnectorListResponse)
async def list_connectors(
    current_user: User = Depends(get_current_user), db: Session = Depends(get_db),
):
    connectors = db.query(Connector).filter(
        Connector.user_id == current_user.id
    ).order_by(Connector.created_at.desc()).all()

    # Compute document counts in one query
    counts = dict(
        db.query(Document.source_connector_id, func.count(Document.id))
        .filter(Document.source_connector_id.in_([c.id for c in connectors]))
        .group_by(Document.source_connector_id)
        .all()
    ) if connectors else {}

    result = []
    for c in connectors:
        data = ConnectorResponse.model_validate(c)
        data.document_count = counts.get(c.id, 0)
        data.last_sync_at = c.last_synced_at
        result.append(data)

    return ConnectorListResponse(connectors=result, total=len(result))


@router.get("/{connector_id}", response_model=ConnectorResponse)
async def get_connector(
    connector_id: str, current_user: User = Depends(get_current_user), db: Session = Depends(get_db),
):
    c = db.query(Connector).filter(Connector.id == connector_id, Connector.user_id == current_user.id).first()
    if not c:
        raise HTTPException(404, "Connector not found")
    return c


@router.patch("/{connector_id}", response_model=ConnectorResponse)
async def update_connector(
    connector_id: str, body: ConnectorUpdateRequest,
    current_user: User = Depends(get_current_user), db: Session = Depends(get_db),
):
    connector = _get_connector_or_404(connector_id, current_user, db)
    if body.display_name is not None:
        connector.display_name = body.display_name
    if body.root_folder is not None:
        connector.root_folder = body.root_folder
    if body.auto_sync is not None:
        connector.auto_sync = body.auto_sync
    if body.sync_interval_minutes is not None:
        connector.sync_interval_minutes = max(5, body.sync_interval_minutes)
    if body.extra_config is not None:
        merged = connector.extra_config or {}
        merged.update(body.extra_config)
        connector.extra_config = merged
    if body.site_id is not None and connector.connector_type == "sharepoint":
        connector.site_id = body.site_id
        try:
            from services import microsoft_graph as graph
            token = await _get_microsoft_token(connector)
            d = await graph.get_site_default_drive(token, body.site_id)
            connector.drive_id = d.get("id")
        except Exception:
            pass
    if body.drive_id is not None:
        connector.drive_id = body.drive_id
    db.commit()
    db.refresh(connector)
    return connector


@router.delete("/{connector_id}")
async def delete_connector(
    connector_id: str, current_user: User = Depends(get_current_user), db: Session = Depends(get_db),
):
    c = db.query(Connector).filter(Connector.id == connector_id, Connector.user_id == current_user.id).first()
    if not c:
        raise HTTPException(404, "Connector not found")
    c.status = "revoked"
    c.auto_sync = False
    db.commit()
    return {"message": "Connector disconnected", "connector_id": connector_id}


# ── Platform-specific list endpoints ─────────────────────────────────────────

@router.get("/{connector_id}/sites", response_model=list[SharePointSiteResponse])
async def list_sites(
    connector_id: str, current_user: User = Depends(get_current_user), db: Session = Depends(get_db),
):
    """List SharePoint sites (sharepoint connectors only)."""
    from services import microsoft_graph as graph
    connector = _get_connector_or_404(connector_id, current_user, db)
    token = await _get_microsoft_token(connector)
    db.commit()
    return await graph.list_sharepoint_sites(token)


@router.get("/{connector_id}/teams", response_model=list[TeamsTeamResponse])
async def list_teams(
    connector_id: str, current_user: User = Depends(get_current_user), db: Session = Depends(get_db),
):
    """List joined Teams (microsoft_teams connectors)."""
    from services import microsoft_graph as graph
    connector = _get_connector_or_404(connector_id, current_user, db)
    token = await _get_microsoft_token(connector)
    db.commit()
    return await graph.list_joined_teams(token)


@router.get("/{connector_id}/teams/{team_id}/channels", response_model=list[TeamsChannelResponse])
async def list_channels(
    connector_id: str, team_id: str,
    current_user: User = Depends(get_current_user), db: Session = Depends(get_db),
):
    """List channels in a Team."""
    from services import microsoft_graph as graph
    connector = _get_connector_or_404(connector_id, current_user, db)
    token = await _get_microsoft_token(connector)
    db.commit()
    return await graph.list_team_channels(token, team_id)


@router.get("/{connector_id}/slack-channels", response_model=list[SlackChannelResponse])
async def list_slack_channels(
    connector_id: str, current_user: User = Depends(get_current_user), db: Session = Depends(get_db),
):
    """List Slack channels."""
    from services import slack_client as slack
    connector = _get_connector_or_404(connector_id, current_user, db)
    token = decrypt_token(connector.encrypted_refresh_token)
    return await slack.list_channels(token)


@router.get("/{connector_id}/servicenow-tables")
async def list_servicenow_tables(
    connector_id: str, current_user: User = Depends(get_current_user), db: Session = Depends(get_db),
):
    """List available ServiceNow tables."""
    from services import servicenow_client as snow
    connector = _get_connector_or_404(connector_id, current_user, db)
    instance_url = (connector.extra_config or {}).get("instance_url", "")
    token = await _get_servicenow_token(connector)
    db.commit()
    return await snow.list_tables(instance_url, token)


@router.get("/{connector_id}/servicenow-records", response_model=list[ServiceNowRecordResponse])
async def query_servicenow(
    connector_id: str, table: str = "incident", query: str = "",
    limit: int = 50, offset: int = 0,
    current_user: User = Depends(get_current_user), db: Session = Depends(get_db),
):
    """Query ServiceNow table records."""
    from services import servicenow_client as snow
    connector = _get_connector_or_404(connector_id, current_user, db)
    instance_url = (connector.extra_config or {}).get("instance_url", "")
    token = await _get_servicenow_token(connector)
    db.commit()
    return await snow.query_table(instance_url, token, table, query=query, limit=limit, offset=offset)


# ── Browse Files (SharePoint / OneDrive / Teams files) ────────────────────────

@router.get("/{connector_id}/browse", response_model=BrowseResponse)
async def browse_files(
    connector_id: str, path: Optional[str] = "/", folder_id: Optional[str] = None,
    current_user: User = Depends(get_current_user), db: Session = Depends(get_db),
):
    """Browse files in the connected drive."""
    from services import microsoft_graph as graph
    connector = _get_connector_or_404(connector_id, current_user, db)
    if not connector.drive_id:
        raise HTTPException(400, "No drive associated — set a SharePoint site or Teams channel first.")
    token = await _get_microsoft_token(connector)
    db.commit()
    items = await graph.list_drive_items(token, connector.drive_id, folder_id=folder_id, path=path)
    return BrowseResponse(
        connector_id=connector_id, path=path or "/",
        items=[DriveItemResponse(**{k: v for k, v in i.items() if k in DriveItemResponse.model_fields}) for i in items],
    )


# ── Import Files ──────────────────────────────────────────────────────────────

@router.post("/{connector_id}/import", response_model=ImportResponse)
async def import_files(
    connector_id: str, body: ImportFileRequest, background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user), db: Session = Depends(get_db),
):
    """Import selected files from the connected drive into Atlas."""
    from services import microsoft_graph as graph
    connector = _get_connector_or_404(connector_id, current_user, db)
    if not connector.drive_id:
        raise HTTPException(400, "No drive associated with this connector.")
    token = await _get_microsoft_token(connector)
    db.commit()

    results, imported, failed = [], 0, 0
    allowed = {"pdf", "docx", "xlsx", "txt", "md", "csv"}

    for item_id in body.item_ids:
        try:
            item = await graph.get_drive_item(token, connector.drive_id, item_id)
            if item["item_type"] == "folder":
                results.append(ImportFileResult(item_id=item_id, filename=item["name"], success=False, error="Cannot import folders"))
                failed += 1; continue

            filename = item["name"]
            ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
            if ext not in allowed:
                results.append(ImportFileResult(item_id=item_id, filename=filename, success=False, error=f"Unsupported: {ext}"))
                failed += 1; continue

            existing = db.query(Document).filter(Document.source_connector_id == connector_id, Document.source_item_id == item_id).first()
            if existing:
                results.append(ImportFileResult(item_id=item_id, filename=filename, document_id=existing.id, success=True, error="Already imported"))
                imported += 1; continue

            doc_id = generate_id()
            dest = os.path.join(UPLOAD_DIR, f"{doc_id}.{ext}")
            await graph.download_drive_item(token, connector.drive_id, item_id, dest)

            ct_map = {"pdf": "application/pdf", "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document", "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", "txt": "text/plain", "csv": "text/csv", "md": "text/markdown"}
            document = Document(id=doc_id, title=filename.rsplit(".", 1)[0], filename=filename, file_type=ext, file_size=os.path.getsize(dest), department=body.department, tags=body.tags, status="processing", uploaded_by_id=current_user.id, source_connector_id=connector_id, source_item_id=item_id)
            db.add(document); db.commit()

            blob_url = await upload_to_blob(dest, doc_id, filename, ct_map.get(ext, "application/octet-stream"))
            if blob_url: document.blob_url = blob_url

            try:
                result = await process_document(dest, doc_id, document.title, {"department": body.department or "", "doc_type": ext, "file_type": ext, "source": f"connector:{connector.connector_type}", "filename": filename, "blob_url": blob_url or "", "classification": "internal", "language": "en", "region": ""})
                document.status = "indexed" if result["success"] else "failed"
                document.chunk_count = result.get("chunk_count", 0)
                if not result["success"]: document.error_message = result.get("error", "Unknown")
            except Exception as e:
                document.status = "failed"; document.error_message = str(e)
            finally:
                try: os.remove(dest)
                except Exception: pass

            if document.status == "indexed":
                upsert_document_node(doc_id, document.title, ext, body.department or "", blob_url or "")
            db.commit()
            results.append(ImportFileResult(item_id=item_id, filename=filename, document_id=doc_id, success=True))
            imported += 1
        except Exception as e:
            logger.error(f"Import failed for {item_id}: {e}")
            results.append(ImportFileResult(item_id=item_id, filename="unknown", success=False, error=str(e)))
            failed += 1

    return ImportResponse(connector_id=connector_id, results=results, total_imported=imported, total_failed=failed)


# ── Sync Controls ────────────────────────────────────────────────────────────

@router.post("/{connector_id}/sync")
async def trigger_sync(
    connector_id: str, current_user: User = Depends(get_current_user), db: Session = Depends(get_db),
):
    """Trigger an immediate sync for any connector type."""
    _get_connector_or_404(connector_id, current_user, db)
    from services.connector_sync import trigger_sync_now
    try:
        await trigger_sync_now(connector_id)
        return {"message": "Sync completed", "connector_id": connector_id}
    except Exception as e:
        raise HTTPException(500, f"Sync failed: {e}")
