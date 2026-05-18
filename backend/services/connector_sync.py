"""
Connector Auto-Sync Service
Background scheduler that periodically checks all connected sources for new
or updated content and imports it into the Atlas document pipeline.

Supports: SharePoint, OneDrive, Microsoft Teams, Slack, ServiceNow.
"""
import os
import re
import asyncio
import logging
import json
from datetime import datetime, timedelta
from typing import Optional

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

logger = logging.getLogger(__name__)

UPLOAD_DIR = os.path.join(os.path.dirname(__file__), "..", "tmp_sync_downloads")
os.makedirs(UPLOAD_DIR, exist_ok=True)

# Supported file extensions for auto-import
SYNCABLE_EXTENSIONS = {"pdf", "docx", "xlsx", "txt", "md", "csv"}

# In-memory store for sync cursors (per connector)
_sync_cursors: dict[str, dict] = {}

_scheduler: Optional[AsyncIOScheduler] = None


def get_scheduler() -> AsyncIOScheduler:
    global _scheduler
    if _scheduler is None:
        _scheduler = AsyncIOScheduler()
    return _scheduler


def start_sync_scheduler():
    """Start the background scheduler. Called once at app startup."""
    scheduler = get_scheduler()
    if scheduler.running:
        return

    # Master tick — every 5 minutes, checks which connectors need syncing
    scheduler.add_job(
        _sync_tick,
        IntervalTrigger(minutes=5),
        id="connector_sync_tick",
        replace_existing=True,
        max_instances=1,
    )
    scheduler.start()
    logger.info("Connector auto-sync scheduler started (5-minute tick).")


def stop_sync_scheduler():
    """Gracefully shut down the scheduler."""
    global _scheduler
    if _scheduler and _scheduler.running:
        _scheduler.shutdown(wait=False)
        logger.info("Connector auto-sync scheduler stopped.")
    _scheduler = None


async def _sync_tick():
    """
    Master tick — find all active connectors with auto_sync enabled
    that are due for a sync, and dispatch to the correct handler.
    """
    from models.database import SessionLocal, Connector

    db = SessionLocal()
    try:
        connectors = (
            db.query(Connector)
            .filter(Connector.status == "active", Connector.auto_sync == True)
            .all()
        )

        now = datetime.utcnow()
        for conn in connectors:
            # Check if enough time has passed since last sync
            if conn.last_synced_at:
                elapsed = (now - conn.last_synced_at).total_seconds() / 60
                if elapsed < conn.sync_interval_minutes:
                    continue

            logger.info(f"Auto-sync starting for connector '{conn.display_name}' ({conn.id})")
            try:
                await _dispatch_sync(conn, db)
            except Exception as e:
                logger.error(f"Auto-sync failed for connector {conn.id}: {e}")
                if "invalid_grant" in str(e).lower() or "expired" in str(e).lower():
                    conn.status = "expired"
                    db.commit()
    finally:
        db.close()


async def _dispatch_sync(connector, db):
    """Route to the correct sync handler based on connector type."""
    ctype = connector.connector_type
    if ctype in ("sharepoint", "onedrive"):
        await _sync_microsoft_drive(connector, db)
    elif ctype == "microsoft_teams":
        await _sync_teams(connector, db)
    elif ctype == "slack":
        await _sync_slack(connector, db)
    elif ctype == "servicenow":
        await _sync_servicenow(connector, db)
    else:
        logger.warning(f"Unknown connector type: {ctype}")


# ── Shared Helpers ────────────────────────────────────────────────────────────

CONTENT_TYPE_MAP = {
    "pdf": "application/pdf",
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "txt": "text/plain",
    "csv": "text/csv",
    "md": "text/markdown",
}


async def _ingest_file(
    dest_path: str,
    filename: str,
    ext: str,
    connector,
    db,
    source_item_id: str,
    department: str = "",
):
    """Shared: create Document, upload to blob, process, index."""
    from services.document_processor import process_document
    from services.blob_storage import upload_document as upload_to_blob
    from services.cosmos_graph import upsert_document_node
    from models.database import Document, generate_id

    doc_id = generate_id()
    file_size = os.path.getsize(dest_path)

    document = Document(
        id=doc_id,
        title=filename.rsplit(".", 1)[0] if "." in filename else filename,
        filename=filename,
        file_type=ext,
        file_size=file_size,
        department=department or None,
        tags=[],
        status="processing",
        uploaded_by_id=connector.user_id,
        source_connector_id=connector.id,
        source_item_id=source_item_id,
    )
    db.add(document)
    db.commit()

    blob_url = await upload_to_blob(
        file_path=dest_path,
        document_id=doc_id,
        filename=filename,
        content_type=CONTENT_TYPE_MAP.get(ext, "application/octet-stream"),
    )
    if blob_url:
        document.blob_url = blob_url

    try:
        result = await process_document(
            file_path=dest_path,
            document_id=doc_id,
            title=document.title,
            metadata={
                "department": department,
                "doc_type": ext,
                "file_type": ext,
                "source": f"connector:{connector.connector_type}",
                "filename": filename,
                "blob_url": blob_url or "",
                "classification": "internal",
                "language": "en",
                "region": "",
            },
        )
        document.status = "indexed" if result["success"] else "failed"
        document.chunk_count = result.get("chunk_count", 0)
        if not result["success"]:
            document.error_message = result.get("error", "Unknown error")
    except Exception as e:
        document.status = "failed"
        document.error_message = str(e)
        logger.error(f"Processing error for '{filename}': {e}")
    finally:
        try:
            os.remove(dest_path)
        except Exception:
            pass

    if document.status == "indexed":
        upsert_document_node(
            document_id=doc_id,
            title=document.title,
            doc_type=ext,
            department=department,
            blob_url=blob_url or "",
        )

    db.commit()
    return document


async def _ingest_text_content(
    text: str,
    title: str,
    source_label: str,
    connector,
    db,
    source_item_id: str,
    department: str = "",
):
    """Shared: create a .txt file from text content and ingest it."""
    from models.database import generate_id

    doc_id = generate_id()
    filename = re.sub(r'[^\w\s\-]', '', title)[:80].strip() + ".txt"
    dest_path = os.path.join(UPLOAD_DIR, f"{doc_id}.txt")

    with open(dest_path, "w", encoding="utf-8") as f:
        f.write(f"Source: {source_label}\n")
        f.write(f"Title: {title}\n")
        f.write(f"{'=' * 60}\n\n")
        f.write(text)

    return await _ingest_file(
        dest_path=dest_path,
        filename=filename,
        ext="txt",
        connector=connector,
        db=db,
        source_item_id=source_item_id,
        department=department,
    )


def _already_imported(connector_id: str, source_item_id: str, db) -> bool:
    from models.database import Document
    return db.query(Document).filter(
        Document.source_connector_id == connector_id,
        Document.source_item_id == source_item_id,
    ).first() is not None


# ── Microsoft Drive Sync (SharePoint / OneDrive) ─────────────────────────────

async def _sync_microsoft_drive(connector, db):
    from services.token_encryption import decrypt_token, encrypt_token
    from services import microsoft_graph as graph
    from models.database import generate_id

    refresh_token = decrypt_token(connector.encrypted_refresh_token)
    try:
        tokens = await graph.refresh_access_token(refresh_token)
    except Exception as e:
        logger.error(f"Token refresh failed for connector {connector.id}: {e}")
        connector.status = "expired"
        db.commit()
        raise

    access_token = tokens["access_token"]
    if tokens["refresh_token"] != refresh_token:
        connector.encrypted_refresh_token = encrypt_token(tokens["refresh_token"])

    drive_id = connector.drive_id
    if not drive_id:
        logger.warning(f"Connector {connector.id} has no drive_id — skipping sync.")
        return

    # Delta query
    cursors = _sync_cursors.get(connector.id, {})
    delta_link = cursors.get("delta_link")
    changed_items, next_delta = await graph.get_drive_delta(
        access_token=access_token, drive_id=drive_id, delta_link=delta_link,
    )
    _sync_cursors[connector.id] = {"delta_link": next_delta}

    imported = 0
    for item in changed_items:
        if item["item_type"] != "file" or item.get("deleted"):
            continue

        name = item.get("name", "")
        ext = name.rsplit(".", 1)[-1].lower() if "." in name else ""
        if ext not in SYNCABLE_EXTENSIONS:
            continue

        item_id = item["id"]
        if _already_imported(connector.id, item_id, db):
            continue

        dest_path = os.path.join(UPLOAD_DIR, f"{generate_id()}.{ext}")
        try:
            await graph.download_drive_item(access_token, drive_id, item_id, dest_path)
            await _ingest_file(dest_path, name, ext, connector, db, item_id)
            imported += 1
        except Exception as e:
            logger.error(f"Drive sync download failed for '{name}': {e}")

    connector.last_synced_at = datetime.utcnow()
    db.commit()
    logger.info(f"Drive sync complete for '{connector.display_name}': {imported} imported")


# ── Microsoft Teams Sync ─────────────────────────────────────────────────────

async def _sync_teams(connector, db):
    from services.token_encryption import decrypt_token, encrypt_token
    from services import microsoft_graph as graph

    refresh_token = decrypt_token(connector.encrypted_refresh_token)
    try:
        tokens = await graph.refresh_access_token(refresh_token)
    except Exception as e:
        connector.status = "expired"
        db.commit()
        raise

    access_token = tokens["access_token"]
    if tokens["refresh_token"] != refresh_token:
        connector.encrypted_refresh_token = encrypt_token(tokens["refresh_token"])

    config = connector.extra_config or {}
    team_id = config.get("team_id")
    channel_ids = config.get("channel_ids", [])

    if not team_id:
        # Sync all teams/channels the user has access to
        teams = await graph.list_joined_teams(access_token)
        for team in teams:
            channels = await graph.list_team_channels(access_token, team["id"])
            for ch in channels:
                await _sync_teams_channel(
                    access_token, team["id"], ch["id"], ch["display_name"],
                    connector, db,
                )
    else:
        if not channel_ids:
            channels = await graph.list_team_channels(access_token, team_id)
            channel_ids = [ch["id"] for ch in channels]
        for ch_id in channel_ids:
            await _sync_teams_channel(access_token, team_id, ch_id, "", connector, db)

    connector.last_synced_at = datetime.utcnow()
    db.commit()
    logger.info(f"Teams sync complete for '{connector.display_name}'")


async def _sync_teams_channel(access_token, team_id, channel_id, channel_name, connector, db):
    from services import microsoft_graph as graph
    from models.database import generate_id

    messages = await graph.get_channel_messages(access_token, team_id, channel_id, top=50)

    imported = 0
    for msg in messages:
        msg_id = f"teams:{team_id}:{channel_id}:{msg['id']}"
        if _already_imported(connector.id, msg_id, db):
            continue

        text = msg.get("text", "")
        if not text or len(text.strip()) < 20:
            continue

        sender = msg.get("sender_name", "Unknown")
        created = msg.get("created_at", "")
        title = f"Teams message from {sender} in #{channel_name or channel_id}"

        await _ingest_text_content(
            text=f"From: {sender}\nDate: {created}\nChannel: {channel_name}\n\n{text}",
            title=title,
            source_label=f"Microsoft Teams / #{channel_name}",
            connector=connector,
            db=db,
            source_item_id=msg_id,
        )
        imported += 1

    # Also sync files in the channel's file tab
    drive_id = await graph.get_channel_files_drive(access_token, team_id, channel_id)
    if drive_id:
        items = await graph.list_drive_items(access_token, drive_id)
        for item in items:
            if item["item_type"] != "file":
                continue
            name = item.get("name", "")
            ext = name.rsplit(".", 1)[-1].lower() if "." in name else ""
            if ext not in SYNCABLE_EXTENSIONS:
                continue
            file_item_id = f"teams-file:{drive_id}:{item['id']}"
            if _already_imported(connector.id, file_item_id, db):
                continue
            dest_path = os.path.join(UPLOAD_DIR, f"{generate_id()}.{ext}")
            try:
                await graph.download_drive_item(access_token, drive_id, item["id"], dest_path)
                await _ingest_file(dest_path, name, ext, connector, db, file_item_id)
                imported += 1
            except Exception as e:
                logger.error(f"Teams file sync failed for '{name}': {e}")

    if imported > 0:
        logger.info(f"Teams channel sync: {imported} items from #{channel_name or channel_id}")


# ── Slack Sync ────────────────────────────────────────────────────────────────

async def _sync_slack(connector, db):
    from services import slack_client as slack
    from services.token_encryption import decrypt_token
    from models.database import generate_id

    # Slack bot tokens don't expire, so we just decrypt and use directly
    access_token = decrypt_token(connector.encrypted_refresh_token)

    config = connector.extra_config or {}
    channel_ids = config.get("channel_ids", [])

    # If no specific channels configured, sync all public channels
    if not channel_ids:
        channels = await slack.list_channels(access_token, include_private=False)
        channel_ids = [ch["id"] for ch in channels]

    cursors = _sync_cursors.get(connector.id, {})

    for ch_id in channel_ids:
        oldest = cursors.get(f"slack_ch_{ch_id}")
        messages = await slack.get_channel_history(access_token, ch_id, oldest=oldest, limit=100)

        if messages:
            # Update cursor to latest message timestamp
            latest_ts = max(m["timestamp"] for m in messages)
            cursors[f"slack_ch_{ch_id}"] = latest_ts

        imported = 0
        for msg in messages:
            msg_id = f"slack:{ch_id}:{msg['id']}"
            if _already_imported(connector.id, msg_id, db):
                continue

            text = msg.get("text", "")
            if not text or len(text.strip()) < 20:
                continue

            await _ingest_text_content(
                text=text,
                title=f"Slack message in #{ch_id} ({msg['timestamp']})",
                source_label=f"Slack / #{ch_id}",
                connector=connector,
                db=db,
                source_item_id=msg_id,
            )
            imported += 1

            # Download attached files
            for f_info in msg.get("files", []):
                file_url = f_info.get("url_private_download", "")
                fname = f_info.get("name", "")
                fext = fname.rsplit(".", 1)[-1].lower() if "." in fname else ""
                if fext not in SYNCABLE_EXTENSIONS or not file_url:
                    continue
                file_item_id = f"slack-file:{f_info.get('id', '')}"
                if _already_imported(connector.id, file_item_id, db):
                    continue
                dest = os.path.join(UPLOAD_DIR, f"{generate_id()}.{fext}")
                try:
                    await slack.download_file(access_token, file_url, dest)
                    await _ingest_file(dest, fname, fext, connector, db, file_item_id)
                except Exception as e:
                    logger.error(f"Slack file download failed for '{fname}': {e}")

        if imported:
            logger.info(f"Slack sync: {imported} items from channel {ch_id}")

    _sync_cursors[connector.id] = cursors
    connector.last_synced_at = datetime.utcnow()
    db.commit()
    logger.info(f"Slack sync complete for '{connector.display_name}'")


# ── ServiceNow Sync ──────────────────────────────────────────────────────────

async def _sync_servicenow(connector, db):
    from services import servicenow_client as snow
    from services.token_encryption import decrypt_token, encrypt_token

    refresh_token = decrypt_token(connector.encrypted_refresh_token)
    config = connector.extra_config or {}
    instance_url = config.get("instance_url", "")

    if not instance_url:
        logger.warning(f"ServiceNow connector {connector.id} has no instance_url")
        return

    # Refresh the token
    try:
        tokens = await snow.refresh_access_token(instance_url, refresh_token)
    except Exception as e:
        connector.status = "expired"
        db.commit()
        raise

    access_token = tokens["access_token"]
    if tokens["refresh_token"] != refresh_token:
        connector.encrypted_refresh_token = encrypt_token(tokens["refresh_token"])

    # Which tables to sync
    tables = config.get("tables", ["incident", "kb_knowledge", "change_request"])

    # Determine "since" timestamp
    since = None
    if connector.last_synced_at:
        since = connector.last_synced_at.strftime("%Y-%m-%d %H:%M:%S")

    imported = 0
    for table in tables:
        try:
            if since:
                records = await snow.query_updated_since(instance_url, access_token, table, since)
            else:
                records = await snow.query_table(instance_url, access_token, table, limit=100)

            for rec in records:
                rec_id = f"snow:{table}:{rec['sys_id']}"
                if _already_imported(connector.id, rec_id, db):
                    continue

                # Build text from record fields
                number = rec.get("number", "")
                short_desc = rec.get("short_description", "")
                description = rec.get("description", "")
                state = rec.get("state", "")
                priority = rec.get("priority", "")
                assigned = rec.get("assigned_to", "")
                category = rec.get("category", "")
                created_on = rec.get("created_on", "")

                text = (
                    f"Record: {number}\n"
                    f"Type: {snow.SUPPORTED_TABLES.get(table, table)}\n"
                    f"Title: {short_desc}\n"
                    f"State: {state}\n"
                    f"Priority: {priority}\n"
                    f"Assigned To: {assigned}\n"
                    f"Category: {category}\n"
                    f"Created: {created_on}\n"
                    f"\n{description}"
                )

                # For knowledge articles, get the full text
                if table == "kb_knowledge":
                    try:
                        kb_text = await snow.get_knowledge_article_text(
                            instance_url, access_token, rec["sys_id"]
                        )
                        if kb_text:
                            # Strip HTML tags for plain text indexing
                            import re as _re
                            clean = _re.sub(r'<[^>]+>', ' ', kb_text)
                            clean = _re.sub(r'\s+', ' ', clean).strip()
                            text += f"\n\nArticle Body:\n{clean}"
                    except Exception:
                        pass

                await _ingest_text_content(
                    text=text,
                    title=f"{number} — {short_desc}" if number else short_desc,
                    source_label=f"ServiceNow / {snow.SUPPORTED_TABLES.get(table, table)}",
                    connector=connector,
                    db=db,
                    source_item_id=rec_id,
                )
                imported += 1

        except Exception as e:
            logger.error(f"ServiceNow sync error for table '{table}': {e}")

    connector.last_synced_at = datetime.utcnow()
    db.commit()
    logger.info(f"ServiceNow sync complete for '{connector.display_name}': {imported} imported")


# ── Morning Briefing ──────────────────────────────────────────────────────────

def schedule_morning_briefing():
    """
    Add a daily 06:00 WAT (05:00 UTC) briefing job to the existing scheduler.
    Must be called after start_sync_scheduler().
    """
    from apscheduler.triggers.cron import CronTrigger

    scheduler = get_scheduler()
    scheduler.add_job(
        _send_morning_briefing,
        CronTrigger(hour=5, minute=0, timezone="UTC"),
        id="morning_briefing_daily",
        replace_existing=True,
        max_instances=1,
    )
    logger.info("Morning briefing job scheduled (daily 06:00 WAT / 05:00 UTC).")


async def _send_morning_briefing():
    """
    Run all Watchdog checks and email a daily digest to admin/analyst users.
    Saves real alerts to DB before sending so the dashboard stays current.
    """
    from agents.watchdog import WatchdogAgent
    from models.database import SessionLocal, User, Alert, KnowledgeGap, AgentRun

    logger.info("Morning briefing job started.")

    wd = WatchdogAgent()
    try:
        checks_raw = await wd.run_all_checks()
        checks = json.loads(checks_raw)
    except Exception as e:
        logger.error(f"Morning briefing watchdog checks failed: {e}")
        return

    db = SessionLocal()
    try:
        # Persist any new alerts (deduplicating by title + org)
        for alert_data in checks.get("alerts", []):
            existing = db.query(Alert).filter(
                Alert.title == alert_data.get("title", ""),
                Alert.status.in_(["new", "acknowledged"]),
            ).first()
            if not existing:
                db.add(Alert(
                    title=alert_data.get("title", ""),
                    summary=alert_data.get("summary", ""),
                    severity=alert_data.get("severity", "warning"),
                    alert_type=alert_data.get("alert_type", "general"),
                    extra_metadata=alert_data.get("metadata", {}),
                    suggested_actions=alert_data.get("suggested_actions", []),
                    organisation="MTN Nigeria",
                ))
        db.commit()

        now = datetime.utcnow()
        yesterday = now - timedelta(hours=24)

        gaps = (
            db.query(KnowledgeGap)
            .filter(KnowledgeGap.created_at >= yesterday)
            .order_by(KnowledgeGap.confidence_score)
            .limit(5)
            .all()
        )
        queries_24h = db.query(AgentRun).filter(AgentRun.created_at >= yesterday).count()

        recipients = db.query(User).filter(
            User.is_active == True,
            User.role.in_(["superadmin", "admin", "analyst"]),
        ).all()

    finally:
        db.close()

    # Compose briefing payload
    alerts = checks.get("alerts", [])
    briefing = {
        "date": now.strftime("%Y-%m-%d"),
        "critical_count": checks.get("critical_count", 0),
        "warning_count": checks.get("warning_count", 0),
        "queries_24h": queries_24h,
        "top_alerts": [
            {"title": a["title"], "severity": a.get("severity", "?"), "summary": a.get("summary", "")}
            for a in alerts[:5]
        ],
        "top_gaps": [g.query[:80] for g in gaps],
    }

    for user in recipients:
        try:
            from services.email import send_morning_briefing_email
            await send_morning_briefing_email(
                recipient_email=user.email,
                recipient_name=user.full_name or user.email.split("@")[0],
                briefing=briefing,
            )
        except Exception as e:
            logger.error(f"Morning briefing email failed for {user.email}: {e}")

    logger.info(
        f"Morning briefing complete: {len(alerts)} alerts, "
        f"{len(gaps)} gaps, {len(recipients)} recipients."
    )


# ── Public API ────────────────────────────────────────────────────────────────

async def trigger_sync_now(connector_id: str):
    """Manually trigger an immediate sync for a specific connector."""
    from models.database import SessionLocal, Connector

    db = SessionLocal()
    try:
        connector = db.query(Connector).filter(Connector.id == connector_id).first()
        if not connector:
            raise ValueError(f"Connector {connector_id} not found")
        if connector.status != "active":
            raise ValueError(f"Connector {connector_id} is not active (status: {connector.status})")

        await _dispatch_sync(connector, db)
    finally:
        db.close()
