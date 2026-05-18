"""
Iroko AI — Telecom Operations Data Models
==========================================
First-class representations of MTN Nigeria's operational entities.
These models enable the AI agents to query structured telecom data
alongside unstructured document search.

Entities:
  - NetworkSite      — towers, base stations, POPs
  - NetworkIncident  — outages, alarms, RCAs
  - VendorContract   — parsed SLA terms, penalty formulas
  - ComplaintTicket   — customer complaints with resolution tracking
  - NetworkKPI       — time-series: availability, CSR, throughput
"""
from sqlalchemy import (
    Column, String, Integer, Float, Boolean, DateTime, Text, JSON,
    ForeignKey, Index,
)
from sqlalchemy.orm import relationship
from datetime import datetime

from models.database import Base, generate_id


# ─── Network Sites ───────────────────────────────────────────────────────────

class NetworkSite(Base):
    """
    A physical network site — tower, base station, POP, fibre node.
    Each site belongs to a cluster and is managed by a vendor.
    """
    __tablename__ = "network_sites"

    id = Column(String, primary_key=True, default=generate_id)
    site_code = Column(String, unique=True, nullable=False, index=True)  # e.g. IKJ-001
    name = Column(String, nullable=False)                                 # e.g. "Ikeja Tower 4471"
    site_type = Column(String, nullable=False, default="macro")           # macro | micro | indoor | pop | fibre_node
    cluster = Column(String, nullable=True, index=True)                   # e.g. "Ikeja"
    region = Column(String, nullable=True, index=True)                    # e.g. "Lagos"
    zone = Column(String, nullable=True)                                  # e.g. "Zone 7"
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)
    address = Column(String, nullable=True)

    # Vendor & contract
    tower_vendor = Column(String, nullable=True)                          # e.g. "IHS Nigeria"
    ran_vendor = Column(String, nullable=True)                            # e.g. "Ericsson"
    tower_lease_ref = Column(String, nullable=True)                       # contract reference
    ran_sla_ref = Column(String, nullable=True)                           # contract reference

    # Operational status
    status = Column(String, default="operational")                        # operational | degraded | down | maintenance
    last_alarm_at = Column(DateTime, nullable=True)
    last_alarm_severity = Column(String, nullable=True)                   # critical | major | minor | warning
    subscriber_count = Column(Integer, default=0)                         # approximate subscribers served

    # Capacity
    sector_count = Column(Integer, default=3)                             # number of sectors
    technology = Column(String, default="4G")                             # 2G | 3G | 4G | 5G | mixed
    backhaul_type = Column(String, nullable=True)                         # fibre | microwave | satellite

    # Metadata
    commissioned_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    incidents = relationship("NetworkIncident", back_populates="site")


# ─── Network Incidents ───────────────────────────────────────────────────────

class NetworkIncident(Base):
    """
    A network incident — outage, degradation, alarm event.
    Links to the affected site, any RCA documents, and related complaint tickets.
    """
    __tablename__ = "network_incidents"

    id = Column(String, primary_key=True, default=generate_id)
    incident_ref = Column(String, unique=True, nullable=False, index=True)  # e.g. INC-2026-IKJ-0147
    title = Column(String, nullable=False)
    description = Column(Text, nullable=True)

    # Affected site
    site_id = Column(String, ForeignKey("network_sites.id"), nullable=True)
    cluster = Column(String, nullable=True, index=True)
    region = Column(String, nullable=True, index=True)
    affected_sites_count = Column(Integer, default=1)
    affected_subscribers = Column(Integer, default=0)

    # Severity & status
    severity = Column(String, nullable=False, default="major")            # critical | major | minor | warning
    status = Column(String, nullable=False, default="open")               # open | investigating | resolved | closed
    priority = Column(String, nullable=True)                              # P1 | P2 | P3 | P4

    # Root cause
    root_cause_category = Column(String, nullable=True)                   # power | equipment | fibre_cut | software | vandalism | weather
    root_cause_detail = Column(Text, nullable=True)
    rca_document_id = Column(String, nullable=True)                       # link to RCA document in Atlas

    # Impact
    sla_breached = Column(Boolean, default=False)
    sla_exposure_ngn = Column(Float, default=0.0)                         # financial exposure in Naira
    vendor_sla_breached = Column(Boolean, default=False)

    # Timeline
    started_at = Column(DateTime, nullable=False)
    detected_at = Column(DateTime, nullable=True)
    acknowledged_at = Column(DateTime, nullable=True)
    resolved_at = Column(DateTime, nullable=True)
    duration_hours = Column(Float, nullable=True)

    # Assignment
    assigned_team = Column(String, nullable=True)                         # e.g. "NOC", "Field Eng", "RAN Support"
    assigned_to = Column(String, nullable=True)
    escalation_level = Column(Integer, default=0)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    site = relationship("NetworkSite", back_populates="incidents")
    complaint_tickets = relationship("ComplaintTicket", back_populates="linked_incident")

    __table_args__ = (
        Index("ix_incident_status_severity", "status", "severity"),
    )


# ─── Vendor Contracts ────────────────────────────────────────────────────────

class VendorContract(Base):
    """
    A parsed vendor contract with structured SLA terms.
    Enables the Watchdog to calculate real SLA exposure and flag expirations.
    """
    __tablename__ = "vendor_contracts"

    id = Column(String, primary_key=True, default=generate_id)
    contract_ref = Column(String, unique=True, nullable=False, index=True)  # e.g. IHS/MTN/IKJ/2024-001
    title = Column(String, nullable=False)
    vendor_name = Column(String, nullable=False, index=True)
    vendor_type = Column(String, nullable=True)                              # towerco | ran_vendor | fibre | power | facilities

    # Contract terms
    scope = Column(Text, nullable=True)                                      # what the contract covers
    monthly_value_ngn = Column(Float, default=0.0)
    annual_value_ngn = Column(Float, default=0.0)
    currency = Column(String, default="NGN")
    commencement_date = Column(DateTime, nullable=True)
    expiry_date = Column(DateTime, nullable=True, index=True)
    renewal_notice_days = Column(Integer, default=90)
    auto_renew = Column(Boolean, default=False)

    # SLA terms (parsed from contract)
    sla_uptime_pct = Column(Float, nullable=True)                            # e.g. 99.5
    sla_response_hours = Column(Float, nullable=True)                        # e.g. 4.0
    penalty_formula = Column(String, nullable=True)                          # e.g. "2% fee reduction per 0.1% below SLA"
    penalty_cap_pct = Column(Float, nullable=True)                           # max penalty as % of contract value

    # Linked data
    document_id = Column(String, nullable=True)                              # link to the contract document in Atlas
    sites_covered = Column(JSON, default=list)                               # list of site_codes covered
    department = Column(String, nullable=True)                               # e.g. "Procurement"

    # Status
    status = Column(String, default="active")                                # active | expiring | expired | terminated
    days_to_expiry = Column(Integer, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


# ─── Complaint Tickets ───────────────────────────────────────────────────────

class ComplaintTicket(Base):
    """
    A customer complaint ticket with category, resolution status,
    and optional linkage to a network incident.
    """
    __tablename__ = "complaint_tickets"

    id = Column(String, primary_key=True, default=generate_id)
    ticket_ref = Column(String, unique=True, nullable=False, index=True)  # e.g. CMP-2026-001234
    category = Column(String, nullable=False, index=True)                  # momo_deduction | data_billing | voice_quality | network_coverage | etc
    subcategory = Column(String, nullable=True)
    description = Column(Text, nullable=True)

    # Customer info (anonymised)
    customer_segment = Column(String, nullable=True)                       # consumer | enterprise | sme
    customer_region = Column(String, nullable=True, index=True)            # e.g. "Lagos"
    customer_zone = Column(String, nullable=True)

    # Status & resolution
    status = Column(String, default="open")                                # open | investigating | resolved | escalated | closed
    priority = Column(String, default="medium")                            # critical | high | medium | low
    resolution = Column(Text, nullable=True)
    resolution_category = Column(String, nullable=True)                    # refunded | explained | escalated | rejected
    refund_amount_ngn = Column(Float, default=0.0)
    disputed_amount_ngn = Column(Float, default=0.0)

    # Linked incident
    linked_incident_id = Column(String, ForeignKey("network_incidents.id"), nullable=True)
    linked_site_code = Column(String, nullable=True)

    # Timeline
    reported_at = Column(DateTime, default=datetime.utcnow)
    acknowledged_at = Column(DateTime, nullable=True)
    resolved_at = Column(DateTime, nullable=True)
    sla_response_hours = Column(Float, nullable=True)                      # time to first response
    sla_resolution_hours = Column(Float, nullable=True)                    # time to resolution

    # Source
    channel = Column(String, default="call_centre")                        # call_centre | app | social_media | email | walk_in
    source_document_id = Column(String, nullable=True)                     # link to complaint report doc

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    linked_incident = relationship("NetworkIncident", back_populates="complaint_tickets")

    __table_args__ = (
        Index("ix_complaint_category_region", "category", "customer_region"),
        Index("ix_complaint_status", "status"),
    )


# ─── Network KPIs (Time Series) ──────────────────────────────────────────────

class NetworkKPI(Base):
    """
    Time-series KPI data for network performance tracking.
    One row per site per day (or per cluster/region aggregate).
    """
    __tablename__ = "network_kpis"

    id = Column(String, primary_key=True, default=generate_id)
    date = Column(DateTime, nullable=False, index=True)
    granularity = Column(String, default="daily")                          # hourly | daily | weekly

    # Scope — one of these is set
    site_code = Column(String, nullable=True, index=True)
    cluster = Column(String, nullable=True, index=True)
    region = Column(String, nullable=True, index=True)
    scope_level = Column(String, default="site")                           # site | cluster | region | national

    # Network KPIs
    availability_pct = Column(Float, nullable=True)                        # e.g. 99.42
    call_setup_success_pct = Column(Float, nullable=True)                  # e.g. 97.3
    drop_call_rate_pct = Column(Float, nullable=True)                      # e.g. 0.8
    data_throughput_mbps = Column(Float, nullable=True)                    # average DL throughput
    latency_ms = Column(Float, nullable=True)                              # average latency

    # Traffic
    voice_traffic_erlang = Column(Float, nullable=True)
    data_traffic_gb = Column(Float, nullable=True)
    subscriber_count = Column(Integer, nullable=True)
    active_users = Column(Integer, nullable=True)

    # Customer experience
    csat_score = Column(Float, nullable=True)                              # 0-100
    nps_score = Column(Float, nullable=True)                               # -100 to +100
    complaint_count = Column(Integer, default=0)

    # Targets
    availability_target = Column(Float, default=99.5)
    csr_target = Column(Float, default=95.0)

    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index("ix_kpi_date_scope", "date", "scope_level", "site_code"),
    )
