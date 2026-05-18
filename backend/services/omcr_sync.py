"""
OMC-R Connector Sync Service
=============================
Fetches live data from the OMC-R simulation (omcr-demo) and upserts it into
atlascore's NetworkSite, NetworkIncident and NetworkKPI tables.

The omcr-demo acts as a stand-in for a real Radio Access Network OSS/NMS feed.
This service proves the full integration path works end-to-end.

Configure via env var:
    OMCR_API_URL=https://iroko-omcr-demo.azurewebsites.net  (default)
"""
import os
import logging
from datetime import datetime, date
from typing import Any, Optional

import httpx
from sqlalchemy.orm import Session

from models.database import SessionLocal
from models.network_models import NetworkSite, NetworkIncident, NetworkKPI

logger = logging.getLogger(__name__)

OMCR_API_URL = os.getenv(
    "OMCR_API_URL", "https://iroko-omcr-demo.azurewebsites.net"
).rstrip("/")

# Track last sync result in memory for the status endpoint
_last_sync: dict[str, Any] = {
    "synced_at": None,
    "sites_upserted": 0,
    "incidents_upserted": 0,
    "incidents_resolved": 0,
    "kpis_upserted": 0,
    "error": None,
}


def get_last_sync() -> dict[str, Any]:
    return dict(_last_sync)


# ── HTTP fetch ────────────────────────────────────────────────────────────────

async def fetch_snapshot() -> dict[str, Any]:
    """Pull the latest snapshot from the omcr-demo API (no auth required)."""
    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.get(f"{OMCR_API_URL}/api/omcr/snapshot")
        if resp.status_code >= 400:
            logger.warning(f"OMCR unavailable (HTTP {resp.status_code}), skipping sync")
            return None
        return resp.json()


# ── Status mapping ────────────────────────────────────────────────────────────

_SITE_STATUS_MAP = {
    "active": "operational",
    "degraded": "degraded",
    "down": "down",
}

_INCIDENT_STATUS_MAP = {
    "active": "open",
    "acknowledged": "investigating",
    "cleared": "resolved",
}


# ── Upsert helpers ────────────────────────────────────────────────────────────

def _upsert_sites(db: Session, towers: list[dict]) -> int:
    """Upsert NetworkSite rows from omcr-demo tower data."""
    site_codes = [f"OMCR-{t['id']}" for t in towers]

    # Bulk-load all existing sites in one query to avoid N round-trips
    # and to prevent autoflush interference mid-loop.
    with db.no_autoflush:
        existing: dict[str, NetworkSite] = {
            s.site_code: s
            for s in db.query(NetworkSite).filter(
                NetworkSite.site_code.in_(site_codes)
            ).all()
        }

        for t in towers:
            site_code = f"OMCR-{t['id']}"
            mapped_status = _SITE_STATUS_MAP.get(t.get("status", "active"), "operational")
            site = existing.get(site_code)

            if site:
                site.status = mapped_status
                site.sector_count = t.get("sectors", 3)
            else:
                site = NetworkSite(
                    site_code=site_code,
                    name=t["name"],
                    site_type="macro",
                    cluster=t.get("city", ""),
                    region=t.get("state", "Nigeria"),
                    zone=t.get("location", ""),
                    status=mapped_status,
                    sector_count=t.get("sectors", 3),
                    technology="4G",
                    ran_vendor="Ericsson",
                )
                db.add(site)
                existing[site_code] = site

    db.flush()
    return len(towers)


def _upsert_incidents(
    db: Session,
    alarms: list[dict],
    towers: list[dict],
) -> tuple[int, int]:
    """
    Upsert NetworkIncident rows from omcr-demo alarm data.
    Returns (upserted_count, resolved_count).

    Bulk pre-loads all site and incident rows before the loop so that
    per-alarm DB queries never trigger SQLAlchemy's autoflush mid-transaction
    (which would abort the PostgreSQL transaction and make subsequent SELECTs
    silently return empty, causing phantom INSERT conflicts on flush).
    """
    with db.no_autoflush:
        # ── 1. Build site lookup in bulk ──────────────────────────────────────
        site_codes = [f"OMCR-{t['id']}" for t in towers]
        site_by_code: dict[str, NetworkSite] = {
            s.site_code: s
            for s in db.query(NetworkSite).filter(
                NetworkSite.site_code.in_(site_codes)
            ).all()
        }
        # tower-id → NetworkSite.id
        site_lookup: dict[str, str] = {
            t["id"]: site_by_code[f"OMCR-{t['id']}"].id
            for t in towers
            if f"OMCR-{t['id']}" in site_by_code
        }

        # ── 2. Pre-load all existing OMCR incidents in one query ──────────────
        alarm_refs = {f"OMCR-{a['alarm_code']}" for a in alarms}
        existing_incidents: dict[str, NetworkIncident] = {
            inc.incident_ref: inc
            for inc in db.query(NetworkIncident).filter(
                NetworkIncident.incident_ref.in_(alarm_refs)
            ).all()
        }

        # ── 3. Upsert each alarm ──────────────────────────────────────────────
        current_refs: set[str] = set()
        upserted = 0

        for alarm in alarms:
            incident_ref = f"OMCR-{alarm['alarm_code']}"
            current_refs.add(incident_ref)

            mapped_status = _INCIDENT_STATUS_MAP.get(alarm.get("status", "active"), "open")
            site_id = site_lookup.get(alarm.get("network_element", ""))

            # Update last_alarm fields on the linked site (uses the already-loaded object)
            if site_id and alarm.get("severity") in ("critical", "major"):
                site = site_by_code.get(f"OMCR-{alarm.get('network_element', '')}")
                if site:
                    occurred = _parse_dt(alarm.get("last_occurrence"))
                    if occurred and (
                        site.last_alarm_at is None or occurred > site.last_alarm_at
                    ):
                        site.last_alarm_at = occurred
                        site.last_alarm_severity = alarm.get("severity")

            inc = existing_incidents.get(incident_ref)
            if inc:
                inc.status = mapped_status
                inc.severity = alarm.get("severity", inc.severity)
            else:
                inc = NetworkIncident(
                    incident_ref=incident_ref,
                    title=alarm["title"],
                    description=alarm.get("description", ""),
                    site_id=site_id,
                    cluster=alarm.get("network_element", ""),
                    region=alarm.get("location", "Nigeria"),
                    severity=alarm.get("severity", "major"),
                    status=mapped_status,
                    priority=_severity_to_priority(alarm.get("severity", "major")),
                    root_cause_category=alarm.get("category", "network"),
                    affected_sites_count=alarm.get("count", 1),
                    started_at=_parse_dt(alarm.get("first_occurrence")) or datetime.utcnow(),
                    assigned_team="NOC",
                )
                db.add(inc)
                existing_incidents[incident_ref] = inc

            upserted += 1

        # ── 4. Resolve incidents that have disappeared from the live feed ──────
        resolved = 0
        active_omcr = db.query(NetworkIncident).filter(
            NetworkIncident.incident_ref.like("OMCR-%"),
            NetworkIncident.status.in_(["open", "investigating"]),
        ).all()
        for inc in active_omcr:
            if inc.incident_ref not in current_refs:
                inc.status = "resolved"
                inc.resolved_at = datetime.utcnow()
                resolved += 1

    db.flush()
    return upserted, resolved


def _upsert_kpis(db: Session, kpis: list[dict]) -> int:
    """Insert/update a national-scope KPI snapshot for today."""
    today = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)

    row = (
        db.query(NetworkKPI)
        .filter(
            NetworkKPI.scope_level == "national",
            NetworkKPI.site_code == None,
            NetworkKPI.date == today,
        )
        .first()
    )

    kpi_map = {k["id"]: k["value"] for k in kpis}

    if row:
        _apply_kpi_values(row, kpi_map)
    else:
        row = NetworkKPI(
            date=today,
            scope_level="national",
            granularity="daily",
            availability_target=99.5,
            csr_target=95.0,
        )
        _apply_kpi_values(row, kpi_map)
        db.add(row)

    db.flush()
    return 1


def _apply_kpi_values(row: NetworkKPI, kpi_map: dict) -> None:
    row.availability_pct = kpi_map.get("avail")
    row.call_setup_success_pct = kpi_map.get("csr")
    row.drop_call_rate_pct = kpi_map.get("dcr")
    row.data_throughput_mbps = kpi_map.get("throughput")
    row.latency_ms = kpi_map.get("latency")


# ── Main sync entry point ─────────────────────────────────────────────────────

async def run_omcr_sync() -> dict[str, Any]:
    """
    Pull latest snapshot from omcr-demo and sync into atlascore DB.
    Safe to call repeatedly — all operations are upserts.
    """
    global _last_sync
    logger.info("OMC-R sync starting...")

    try:
        snapshot = await fetch_snapshot()
    except Exception as exc:
        error = f"Failed to fetch omcr snapshot: {exc}"
        logger.warning(error)
        _last_sync = {**_last_sync, "error": error, "synced_at": datetime.utcnow().isoformat()}
        return None

    if snapshot is None:
        return None

    towers = snapshot.get("towers", [])
    alarms = snapshot.get("alarms", [])
    kpis = snapshot.get("kpis", [])

    db = SessionLocal()
    try:
        sites_count = _upsert_sites(db, towers)
        inc_count, resolved_count = _upsert_incidents(db, alarms, towers)
        kpi_count = _upsert_kpis(db, kpis)
        db.commit()
    except Exception as exc:
        db.rollback()
        raise
    finally:
        db.close()

    result = {
        "synced_at": datetime.utcnow().isoformat(),
        "sites_upserted": sites_count,
        "incidents_upserted": inc_count,
        "incidents_resolved": resolved_count,
        "kpis_upserted": kpi_count,
        "error": None,
        "source": f"{OMCR_API_URL}/api/omcr/snapshot",
    }
    _last_sync = result
    logger.info(
        f"OMC-R sync complete — sites:{sites_count} incidents:{inc_count} "
        f"resolved:{resolved_count} kpis:{kpi_count}"
    )
    return result


# ── Helpers ───────────────────────────────────────────────────────────────────

def _parse_dt(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).replace(tzinfo=None)
    except ValueError:
        return None


def _severity_to_priority(severity: str) -> str:
    return {"critical": "P1", "major": "P2", "minor": "P3", "warning": "P3"}.get(
        severity, "P4"
    )

