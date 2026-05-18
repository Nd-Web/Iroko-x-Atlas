"""
Full database seed — Iroko AI / Atlas
======================================
Populates ALL tables with realistic MTN Nigeria operational data suitable
for a live hackathon demo.

Run from the backend directory:
    python -m scripts.seed_all
or against production:
    DATABASE_URL=postgresql://... python -m scripts.seed_all
"""
import sys
import os
import random
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

# Load Key Vault secrets so DATABASE_URL is available
try:
    from services.keyvault import load_secrets_from_keyvault
    load_secrets_from_keyvault()
except Exception:
    pass

from models.database import (
    SessionLocal, init_db,
    User, Document, Conversation, Message,
    Alert, AgentRun, AuditLog, OrgMemory, KnowledgeGap,
)
from models.network_models import (
    NetworkSite, NetworkIncident, VendorContract,
    ComplaintTicket, NetworkKPI,
)
from services.auth_utils import hash_password, generate_api_key


# ── Helpers ───────────────────────────────────────────────────────────────────

def ago(**kw):
    return datetime.utcnow() - timedelta(**kw)


def upsert(db, model, filter_kw, obj):
    existing = db.query(model).filter_by(**filter_kw).first()
    if not existing:
        db.add(obj)
    return existing or obj


# ── Users ─────────────────────────────────────────────────────────────────────

def seed_users(db):
    users = [
        User(
            email="admin@mtn.ng",
            full_name="Iroko AI Superadmin",
            hashed_password=hash_password("AtlasAdmin2026!"),
            organisation="MTN Nigeria",
            department="Technology",
            role="superadmin",
            is_active=True,
            api_key=generate_api_key(),
            created_at=ago(days=90),
            last_login=ago(hours=1),
        ),
        User(
            email="chukwuemeka.obi@mtn.ng",
            full_name="Chukwuemeka Obi",
            hashed_password=hash_password("Password2026!"),
            organisation="MTN Nigeria",
            department="Network Operations",
            role="admin",
            is_active=True,
            api_key=generate_api_key(),
            created_at=ago(days=60),
            last_login=ago(hours=3),
        ),
        User(
            email="adaeze.nwosu@mtn.ng",
            full_name="Adaeze Nwosu",
            hashed_password=hash_password("Password2026!"),
            organisation="MTN Nigeria",
            department="Legal/Regulatory",
            role="analyst",
            is_active=True,
            api_key=generate_api_key(),
            created_at=ago(days=45),
            last_login=ago(days=1),
        ),
        User(
            email="babatunde.afolabi@mtn.ng",
            full_name="Babatunde Afolabi",
            hashed_password=hash_password("Password2026!"),
            organisation="MTN Nigeria",
            department="Procurement",
            role="analyst",
            is_active=True,
            api_key=generate_api_key(),
            created_at=ago(days=30),
            last_login=ago(hours=8),
        ),
        User(
            email="ngozi.eze@mtn.ng",
            full_name="Ngozi Eze",
            hashed_password=hash_password("Password2026!"),
            organisation="MTN Nigeria",
            department="Customer Experience",
            role="viewer",
            is_active=True,
            api_key=generate_api_key(),
            created_at=ago(days=20),
            last_login=ago(days=2),
        ),
    ]
    created = 0
    for u in users:
        if not db.query(User).filter_by(email=u.email).first():
            db.add(u)
            created += 1
    db.commit()
    print(f"  ✓ {created} users (skipped {len(users)-created} existing)")
    return {u.email: db.query(User).filter_by(email=u.email).first() for u in users}


# ── Vendor Contracts ──────────────────────────────────────────────────────────

def seed_contracts(db):
    contracts = [
        VendorContract(
            contract_ref="IHS/MTN/IKJ/2024-001",
            title="TowerCo Tower Lease Agreement — IHS Nigeria (Ikeja Cluster)",
            vendor_name="IHS Nigeria Limited",
            vendor_type="towerco",
            scope="Tower lease and power management for 6 Ikeja cluster macro sites including diesel backup SLA",
            monthly_value_ngn=28_000_000,
            annual_value_ngn=336_000_000,
            commencement_date=datetime(2024, 7, 1),
            expiry_date=datetime(2026, 6, 30),
            renewal_notice_days=90,
            sla_uptime_pct=99.5,
            penalty_formula="2% fee reduction per 0.1% below SLA threshold, capped at 20%",
            penalty_cap_pct=20.0,
            department="Procurement",
            document_id="doc_002",
            sites_covered=["IKJ-001","IKJ-002","IKJ-003","IKJ-004","IKJ-005","IKJ-006"],
            status="active",
            days_to_expiry=57,
        ),
        VendorContract(
            contract_ref="ERIC/MTN/RAN/2026-001",
            title="Ericsson RAN Maintenance SLA — 2026",
            vendor_name="Ericsson Nigeria Limited",
            vendor_type="ran_vendor",
            scope="Corrective and preventive maintenance for 847 base stations nationwide, software upgrades included",
            monthly_value_ngn=15_000_000,
            annual_value_ngn=180_000_000,
            commencement_date=datetime(2026, 1, 1),
            expiry_date=datetime(2026, 12, 31),
            renewal_notice_days=90,
            sla_uptime_pct=99.5,
            sla_response_hours=4.0,
            penalty_formula="NGN 50,000 per hour beyond 4-hour response SLA",
            department="Procurement",
            document_id="doc_006",
            status="active",
            days_to_expiry=241,
        ),
        VendorContract(
            contract_ref="HUW/MTN/CORE/2025-001",
            title="Huawei Core Network Maintenance — 2025-2027",
            vendor_name="Huawei Technologies Nigeria",
            vendor_type="ran_vendor",
            scope="Core network (EPC/IMS) maintenance and software upgrades, 24/7 NOC support",
            monthly_value_ngn=22_000_000,
            annual_value_ngn=264_000_000,
            commencement_date=datetime(2025, 1, 1),
            expiry_date=datetime(2027, 12, 31),
            renewal_notice_days=120,
            sla_uptime_pct=99.9,
            sla_response_hours=2.0,
            penalty_formula="3% fee reduction per incident exceeding 2-hour response SLA",
            department="Procurement",
            status="active",
            days_to_expiry=606,
        ),
        VendorContract(
            contract_ref="ATC/MTN/LAG/2023-007",
            title="American Tower Corporation — Lagos Zone 2 Sites",
            vendor_name="American Tower Corporation",
            vendor_type="towerco",
            scope="Tower lease for 12 Lagos Zone 2 macro sites including security and access management",
            monthly_value_ngn=19_500_000,
            annual_value_ngn=234_000_000,
            commencement_date=datetime(2023, 4, 1),
            expiry_date=datetime(2026, 3, 31),
            renewal_notice_days=90,
            sla_uptime_pct=99.3,
            penalty_formula="1.5% fee reduction per 0.1% below SLA",
            department="Procurement",
            status="expiring",
            days_to_expiry=28,
        ),
        VendorContract(
            contract_ref="JB/MTN/FIBRE/KNO-KAD/2025-007",
            title="Julius Berger — Kano-Kaduna Fibre Route (Phase 1)",
            vendor_name="Julius Berger Nigeria Plc",
            vendor_type="fibre",
            scope="Civil works and cable laying for 287km Kano-Kaduna fibre route, ROW acquisition included",
            monthly_value_ngn=120_000_000,
            annual_value_ngn=1_440_000_000,
            commencement_date=datetime(2025, 10, 1),
            expiry_date=datetime(2026, 9, 30),
            renewal_notice_days=60,
            penalty_formula="0.5% of project value per week of delay beyond milestone",
            department="Network Operations",
            document_id="doc_007",
            status="active",
            days_to_expiry=149,
        ),
        VendorContract(
            contract_ref="ZENITH/MTN/EBU/2025-003",
            title="Zenith Bank Enterprise Connectivity SLA",
            vendor_name="Zenith Bank Plc",
            vendor_type="fibre",
            scope="Dedicated fibre and SD-WAN connectivity for 142 Zenith Bank branches nationwide",
            monthly_value_ngn=85_000_000,
            annual_value_ngn=1_020_000_000,
            commencement_date=datetime(2025, 3, 1),
            expiry_date=datetime(2027, 2, 28),
            renewal_notice_days=120,
            sla_uptime_pct=99.95,
            sla_response_hours=1.0,
            penalty_formula="NGN 100,000 per hour of downtime beyond 99.95% monthly uptime",
            department="Enterprise Business",
            document_id="doc_008",
            status="active",
            days_to_expiry=666,
        ),
    ]
    created = 0
    for c in contracts:
        if not db.query(VendorContract).filter_by(contract_ref=c.contract_ref).first():
            db.add(c)
            created += 1
    db.commit()
    print(f"  ✓ {created} vendor contracts (skipped {len(contracts)-created} existing)")


# ── Network Sites ─────────────────────────────────────────────────────────────

def seed_sites(db):
    rows = [
        ("IKJ-001","Ikeja Tower 4471","macro","Ikeja","Lagos","Zone 7",6.5833,3.3500,"IHS Nigeria","Ericsson","IHS/MTN/IKJ/2024-001","ERIC/MTN/RAN/2026-001",3200,"4G","fibre","operational"),
        ("IKJ-002","Ikeja Oregun Road","macro","Ikeja","Lagos","Zone 7",6.5860,3.3480,"IHS Nigeria","Ericsson","IHS/MTN/IKJ/2024-001","ERIC/MTN/RAN/2026-001",2800,"4G","fibre","operational"),
        ("IKJ-003","Ikeja GRA North","macro","Ikeja","Lagos","Zone 7",6.5980,3.3420,"IHS Nigeria","Ericsson","IHS/MTN/IKJ/2024-001","ERIC/MTN/RAN/2026-001",2100,"4G","microwave","operational"),
        ("IKJ-004","Ikeja Along","macro","Ikeja","Lagos","Zone 7",6.5720,3.3560,"IHS Nigeria","Huawei","IHS/MTN/IKJ/2024-001","HUW/MTN/CORE/2025-001",1900,"4G/5G","fibre","degraded"),
        ("IKJ-005","Ikeja Computer Village","macro","Ikeja","Lagos","Zone 7",6.5800,3.3510,"IHS Nigeria","Ericsson","IHS/MTN/IKJ/2024-001","ERIC/MTN/RAN/2026-001",4100,"4G","fibre","operational"),
        ("IKJ-006","Ikeja Under Bridge","micro","Ikeja","Lagos","Zone 7",6.5740,3.3530,"IHS Nigeria","Huawei","IHS/MTN/IKJ/2024-001","HUW/MTN/CORE/2025-001",1400,"4G","fibre","operational"),
        ("LGI-001","Victoria Island Eko Hotel","macro","Lagos Island","Lagos","Zone 1",6.4281,3.4219,"ATC","Ericsson","ATC/MTN/LAG/2023-007","ERIC/MTN/RAN/2026-001",5200,"4G/5G","fibre","operational"),
        ("LGI-002","Lekki Phase 1","macro","Lagos Island","Lagos","Zone 1",6.4350,3.4780,"ATC","Huawei","ATC/MTN/LAG/2023-007","HUW/MTN/CORE/2025-001",4800,"4G/5G","fibre","operational"),
        ("LGI-003","Surulere National Stadium","macro","Surulere","Lagos","Zone 3",6.5040,3.3630,"IHS Nigeria","Ericsson","IHS/MTN/IKJ/2024-001","ERIC/MTN/RAN/2026-001",3600,"4G","fibre","operational"),
        ("LGI-004","Yaba College Road","macro","Yaba","Lagos","Zone 3",6.5075,3.3793,"ATC","Ericsson","ATC/MTN/LAG/2023-007","ERIC/MTN/RAN/2026-001",2900,"4G","fibre","operational"),
        ("ABJ-001","CBD Maitama","macro","Maitama","Abuja","FCT Central",9.0628,7.4887,"IHS Nigeria","Ericsson",None,"ERIC/MTN/RAN/2026-001",6100,"4G/5G","fibre","operational"),
        ("ABJ-002","Wuse Zone 4","macro","Wuse","Abuja","FCT Central",9.0634,7.4847,"IHS Nigeria","Huawei",None,"HUW/MTN/CORE/2025-001",4300,"4G","fibre","operational"),
        ("ABJ-003","Gwarinpa Estate","macro","Gwarinpa","Abuja","FCT North",9.1052,7.4148,"IHS Nigeria","Ericsson",None,"ERIC/MTN/RAN/2026-001",3800,"4G","microwave","operational"),
        ("KNO-001","Kano Sabon Gari","macro","Sabon Gari","Kano","Kano North",12.0022,8.5920,"IHS Nigeria","Huawei",None,"HUW/MTN/CORE/2025-001",5500,"3G/4G","fibre","operational"),
        ("KNO-002","Kano Kurmi Market","macro","Old City","Kano","Kano Central",11.9934,8.5335,"IHS Nigeria","Ericsson",None,"ERIC/MTN/RAN/2026-001",4100,"3G/4G","microwave","operational"),
        ("KNO-003","Kano Airport","macro","Nasarawa","Kano","Kano South",11.9944,8.5265,"ATC","Ericsson","ATC/MTN/LAG/2023-007","ERIC/MTN/RAN/2026-001",2200,"4G","fibre","operational"),
        ("KAD-001","Kaduna Central Business","macro","Kaduna Central","Kaduna","Kaduna Central",10.5272,7.4396,"IHS Nigeria","Huawei",None,"HUW/MTN/CORE/2025-001",4700,"3G/4G","fibre","operational"),
        ("KAD-002","Barnawa","macro","Barnawa","Kaduna","Kaduna South",10.4876,7.4234,"IHS Nigeria","Ericsson",None,"ERIC/MTN/RAN/2026-001",3100,"4G","microwave","operational"),
        ("PHC-001","GRA Phase 2","macro","GRA","Port Harcourt","Rivers Central",4.8156,7.0498,"ATC","Ericsson","ATC/MTN/LAG/2023-007","ERIC/MTN/RAN/2026-001",4900,"4G","fibre","operational"),
        ("PHC-002","Old Market Trans-Amadi","macro","Trans-Amadi","Port Harcourt","Rivers Central",4.8180,7.0231,"IHS Nigeria","Huawei",None,"HUW/MTN/CORE/2025-001",3700,"4G","fibre","operational"),
        ("PHC-003","Rumuola Flyover","macro","Rumuola","Port Harcourt","Rivers North",4.8420,7.0150,"IHS Nigeria","Ericsson",None,"ERIC/MTN/RAN/2026-001",2800,"4G","microwave","operational"),
        ("POP-KNO-01","Kano Metro POP","pop","Kano Metro","Kano","Kano North",12.0010,8.5900,None,"Huawei",None,"HUW/MTN/CORE/2025-001",0,"fibre","fibre","operational"),
        ("POP-KAD-01","Kaduna Metro POP","pop","Kaduna Metro","Kaduna","Kaduna Central",10.5260,7.4380,None,"Huawei",None,"HUW/MTN/CORE/2025-001",0,"fibre","fibre","operational"),
    ]

    site_objects = {}
    created = 0
    for row in rows:
        (code, name, stype, cluster, region, zone, lat, lon,
         tvend, rvend, tref, rref, subs, tech, bh, status) = row
        existing = db.query(NetworkSite).filter_by(site_code=code).first()
        if not existing:
            s = NetworkSite(
                site_code=code, name=name, site_type=stype,
                cluster=cluster, region=region, zone=zone,
                latitude=lat, longitude=lon,
                tower_vendor=tvend, ran_vendor=rvend,
                tower_lease_ref=tref, ran_sla_ref=rref,
                subscriber_count=subs, technology=tech, backhaul_type=bh,
                status=status,
            )
            db.add(s)
            created += 1
            site_objects[code] = s
        else:
            site_objects[code] = existing
    db.commit()
    print(f"  ✓ {created} network sites (skipped {len(rows)-created} existing)")
    return site_objects


# ── Network Incidents ─────────────────────────────────────────────────────────

def seed_incidents(db, sites):
    anchor = sites.get("IKJ-001")
    ikj4   = sites.get("IKJ-004")
    kno1   = sites.get("KNO-001")
    phc1   = sites.get("PHC-001")

    incidents = [
        NetworkIncident(
            incident_ref="INC-2026-IKJ-0147",
            title="Ikeja Cluster Power Outage — AES Feeder Failure",
            description="Full outage across 6 Ikeja sites due to AES utility feeder failure and generator auto-transfer relay malfunction at IKJ-001.",
            site_id=anchor.id if anchor else None,
            cluster="Ikeja", region="Lagos",
            affected_sites_count=6, affected_subscribers=18000,
            severity="critical", status="resolved", priority="P1",
            root_cause_category="power",
            root_cause_detail="AES utility feeder failure on Zone 7 ring; generator auto-transfer relay at IKJ-001 did not engage within 30s, causing cascade power loss. Generator fuel level was also below SLA minimum (18% vs 50% required).",
            rca_document_id="doc_001",
            sla_breached=True, sla_exposure_ngn=2_660_000,
            vendor_sla_breached=True,
            started_at=datetime(2026, 2, 14, 2, 14),
            detected_at=datetime(2026, 2, 14, 2, 17),
            acknowledged_at=datetime(2026, 2, 14, 2, 45),
            resolved_at=datetime(2026, 2, 14, 6, 23),
            duration_hours=4.15,
            assigned_team="NOC", escalation_level=2,
        ),
        NetworkIncident(
            incident_ref="INC-2026-IKJ-0201",
            title="IKJ-004 Sector B Antenna Tilt Fault — Degraded Coverage",
            description="Sector B antenna at IKJ-004 showing persistent tilt fault after recent maintenance visit. Coverage degraded by ~35% in southern footprint.",
            site_id=ikj4.id if ikj4 else None,
            cluster="Ikeja", region="Lagos",
            affected_sites_count=1, affected_subscribers=650,
            severity="major", status="investigating", priority="P2",
            root_cause_category="equipment",
            root_cause_detail="Antenna tilt actuator failure suspected. Actuator firmware version mismatch detected after last software push. Field team dispatch scheduled for 08:00.",
            sla_breached=False, sla_exposure_ngn=0,
            vendor_sla_breached=False,
            started_at=ago(hours=6),
            detected_at=ago(hours=5, minutes=50),
            acknowledged_at=ago(hours=5, minutes=20),
            assigned_team="RAN Support", escalation_level=1,
        ),
        NetworkIncident(
            incident_ref="INC-2026-KNO-0088",
            title="Kano-Kaduna Fibre Cut — ROW Excavation at Km 142",
            description="Fibre cut at Km 142 of the Kano-Kaduna route caused by KEDCO road excavation crew. Traffic rerouted via microwave backup — capacity reduced 60%.",
            site_id=None,
            cluster="Kano Metro", region="Kano",
            affected_sites_count=4, affected_subscribers=8200,
            severity="major", status="open", priority="P2",
            root_cause_category="fibre_cut",
            root_cause_detail="Third-party KEDCO excavation crew cut main fibre conduit at Km 142 (Zaria bypass). Coordinates: 11.1095°N, 7.7227°E. Splicing team ETA 8 hours.",
            sla_breached=False, sla_exposure_ngn=0,
            vendor_sla_breached=False,
            started_at=ago(hours=3),
            detected_at=ago(hours=2, minutes=55),
            acknowledged_at=ago(hours=2, minutes=30),
            assigned_team="Field Eng", escalation_level=1,
        ),
        NetworkIncident(
            incident_ref="INC-2026-PHC-0034",
            title="Port Harcourt GRA — Vandalism at PHC-001",
            description="Battery theft at PHC-001 GRA Phase 2 site. Site went down after utility power cut; batteries unavailable. Site offline for 2.3 hours.",
            site_id=phc1.id if phc1 else None,
            cluster="GRA", region="Port Harcourt",
            affected_sites_count=1, affected_subscribers=4900,
            severity="critical", status="resolved", priority="P1",
            root_cause_category="vandalism",
            root_cause_detail="All 8 VRLA batteries stolen overnight. Security contractor (Halogen) response time was 47 minutes — breach of 30-minute SLA. Police report filed: RPF/2026/PHC/00441.",
            sla_breached=True, sla_exposure_ngn=980_000,
            vendor_sla_breached=True,
            started_at=ago(days=5, hours=3),
            detected_at=ago(days=5, hours=2, minutes=50),
            acknowledged_at=ago(days=5, hours=2, minutes=20),
            resolved_at=ago(days=5),
            duration_hours=2.3,
            assigned_team="Field Eng", escalation_level=1,
        ),
        NetworkIncident(
            incident_ref="INC-2026-ABJ-0119",
            title="Abuja CBD — Maitama Site Software Fault Post-Upgrade",
            description="ABJ-001 Maitama went into alarm state following Ericsson ENM software upgrade. OSS showed repeated RRC setup failures. Rollback initiated.",
            site_id=sites.get("ABJ-001").id if sites.get("ABJ-001") else None,
            cluster="Maitama", region="Abuja",
            affected_sites_count=1, affected_subscribers=6100,
            severity="major", status="resolved", priority="P2",
            root_cause_category="software",
            root_cause_detail="Ericsson ENM R22A patch 14 introduced a regression in RRC setup handling for VoLTE calls. Rollback to R22A patch 12 resolved the issue. Ericsson TAC notified.",
            sla_breached=False, sla_exposure_ngn=0,
            vendor_sla_breached=False,
            started_at=ago(days=12, hours=14),
            detected_at=ago(days=12, hours=13, minutes=45),
            acknowledged_at=ago(days=12, hours=13, minutes=15),
            resolved_at=ago(days=12, hours=10),
            duration_hours=4.0,
            assigned_team="RAN Support", escalation_level=1,
        ),
    ]

    created = 0
    for inc in incidents:
        if not db.query(NetworkIncident).filter_by(incident_ref=inc.incident_ref).first():
            db.add(inc)
            created += 1
    db.commit()
    print(f"  ✓ {created} network incidents (skipped {len(incidents)-created} existing)")

    # Link some complaints to the major Ikeja incident
    ikj_inc = db.query(NetworkIncident).filter_by(incident_ref="INC-2026-IKJ-0147").first()
    return ikj_inc


# ── Complaint Tickets ─────────────────────────────────────────────────────────

def seed_complaints(db, ikj_incident):
    categories = [
        ("momo_deduction",    "Lagos",         "consumer",   850, 0.73),
        ("data_billing",      "Lagos",         "consumer",   420, 0.81),
        ("voice_quality",     "Lagos",         "consumer",   380, 0.75),
        ("network_coverage",  "Lagos",         "consumer",   310, 0.68),
        ("data_billing",      "Abuja",         "enterprise", 190, 0.88),
        ("momo_deduction",    "Kano",          "consumer",   290, 0.70),
        ("network_coverage",  "Port Harcourt", "consumer",   220, 0.72),
        ("voice_quality",     "Kaduna",        "consumer",   180, 0.77),
        ("momo_deduction",    "Abuja",         "consumer",   160, 0.85),
        ("data_billing",      "Port Harcourt", "consumer",   140, 0.80),
    ]

    ticket_count = 0
    ikj_inc_id = ikj_incident.id if ikj_incident else None

    for (cat, region, segment, volume, res_rate) in categories:
        per_batch = min(volume // 20, 15)
        for i in range(per_batch):
            ref = f"CMP-2026-{region[:3].upper()}-{ticket_count+1:05d}"
            if db.query(ComplaintTicket).filter_by(ticket_ref=ref).first():
                ticket_count += 1
                continue

            days_ago = random.randint(0, 45)
            reported = ago(days=days_ago, hours=random.randint(0, 23))
            resolved = random.random() < res_rate
            disputed = round(random.uniform(500, 45000), 2) if cat == "momo_deduction" else 0
            is_ikeja_complaint = (region == "Lagos" and cat == "network_coverage" and
                                   days_ago <= 2 and ikj_inc_id)

            db.add(ComplaintTicket(
                ticket_ref=ref,
                category=cat,
                subcategory={
                    "momo_deduction": "unauthorised_deduction",
                    "data_billing":   "overbilling",
                    "voice_quality":  "call_drops",
                    "network_coverage": "no_signal",
                }.get(cat),
                description=f"{cat.replace('_',' ').title()} complaint from {region} — {segment} customer",
                customer_segment=segment,
                customer_region=region,
                customer_zone=random.choice(["Zone 1","Zone 2","Zone 3","Zone 4"]),
                status="resolved" if resolved else ("escalated" if random.random() < 0.2 else "open"),
                priority="high" if cat == "momo_deduction" else ("medium" if cat == "data_billing" else "low"),
                disputed_amount_ngn=disputed,
                refund_amount_ngn=round(disputed * 0.9, 2) if (resolved and disputed) else 0,
                resolution_category="refunded" if (resolved and disputed) else ("explained" if resolved else None),
                channel=random.choice(["call_centre","app","social_media","email"]),
                reported_at=reported,
                resolved_at=reported + timedelta(hours=random.randint(2, 72)) if resolved else None,
                sla_response_hours=round(random.uniform(0.5, 6.0), 1),
                linked_incident_id=ikj_inc_id if is_ikeja_complaint else None,
            ))
            ticket_count += 1

    db.commit()
    print(f"  ✓ {ticket_count} complaint tickets")


# ── Network KPIs ──────────────────────────────────────────────────────────────

def seed_kpis(db):
    base_date = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=30)
    kpi_count = 0

    for day in range(31):
        d = base_date + timedelta(days=day)
        incident_day = (d.date() == datetime(2026, 2, 14).date())

        scopes = [
            ("national", None, None, None, 99.3, 97.1, 99.1, 96.8),
            ("region",   None, "Lagos",  None,  99.2, 96.8, 98.7, 96.1),
            ("region",   None, "Abuja",  None,  99.4, 97.2, 99.3, 97.0),
            ("region",   None, "Kano",   None,  99.0, 96.5, 98.8, 96.2),
            ("cluster",  None, "Lagos",  "Ikeja",    99.1, 96.5, 82.7, 88.2),
            ("cluster",  None, "Lagos",  "Lagos Island", 99.4, 97.0, 99.3, 96.9),
            ("site",     "IKJ-001", "Lagos", "Ikeja", 99.2, 97.0, 80.1, 87.4),
        ]

        for (slevel, scode, sregion, scluster, norm_av, norm_csr, inc_av, inc_csr) in scopes:
            exists = db.query(NetworkKPI).filter(
                NetworkKPI.date == d,
                NetworkKPI.scope_level == slevel,
                NetworkKPI.site_code == scode,
                NetworkKPI.region == sregion,
                NetworkKPI.cluster == scluster,
            ).first()
            if exists:
                continue

            avail = inc_av if incident_day else round(random.uniform(norm_av - 0.3, norm_av + 0.3), 2)
            csr   = inc_csr if incident_day else round(random.uniform(norm_csr - 0.5, norm_csr + 0.5), 2)
            subs  = {"national": None, "region": 24300, "cluster": 15500, "site": 3200}.get(slevel)

            db.add(NetworkKPI(
                date=d, granularity="daily",
                scope_level=slevel, site_code=scode, region=sregion, cluster=scluster,
                availability_pct=avail,
                call_setup_success_pct=csr,
                drop_call_rate_pct=12.4 if (incident_day and scluster == "Ikeja") else round(random.uniform(0.6, 1.6), 2),
                data_throughput_mbps=round(random.uniform(44, 68), 1),
                latency_ms=round(random.uniform(14, 35), 1),
                subscriber_count=subs,
                voice_traffic_erlang=round(random.uniform(120, 480), 1),
                data_traffic_gb=round(random.uniform(850, 2400), 0),
                complaint_count=312 if (incident_day and scluster == "Ikeja") else random.randint(8, 80),
                csat_score=41.2 if (incident_day and scluster == "Ikeja") else round(random.uniform(64, 76), 1),
                availability_target=99.5,
                csr_target=95.0,
            ))
            kpi_count += 1

    db.commit()
    print(f"  ✓ {kpi_count} KPI records (7 scopes × 31 days)")


# ── Alerts ────────────────────────────────────────────────────────────────────

def seed_alerts(db, users):
    admin = users.get("admin@mtn.ng")
    noc   = users.get("chukwuemeka.obi@mtn.ng")

    alerts = [
        Alert(
            title="ATC Lagos Zone 2 Contract Expiring in 28 Days",
            summary="VendorContract ATC/MTN/LAG/2023-007 (American Tower Corporation — Lagos Zone 2, 12 sites) expires 2026-03-31. Renewal notice required 90 days before — already overdue. Monthly value: NGN 19.5M. Escalate to Procurement immediately.",
            severity="critical",
            status="new",
            alert_type="contract_expiry",
            extra_metadata={"contract_ref": "ATC/MTN/LAG/2023-007", "vendor": "American Tower Corporation", "days_to_expiry": 28, "sites_affected": 12, "monthly_value_ngn": 19500000},
            suggested_actions=["Escalate to VP Procurement", "Draft renewal letter", "Prepare BATNA for renegotiation", "Confirm site handover plan if not renewed"],
            related_document_ids=["doc_002"],
            organisation="MTN Nigeria",
            created_at=ago(hours=2),
        ),
        Alert(
            title="IHS Ikeja Cluster SLA Breach — February 2026 Outage",
            summary="INC-2026-IKJ-0147 (4.15h outage, 18,000 affected subscribers) confirms IHS Nigeria breached generator uptime SLA under IHS/MTN/IKJ/2024-001. Penalty clause triggered: NGN 2.66M exposure. Legal has 30 days from incident date to file penalty notice.",
            severity="critical",
            status="acknowledged",
            alert_type="sla_breach",
            extra_metadata={"incident_ref": "INC-2026-IKJ-0147", "vendor": "IHS Nigeria Limited", "exposure_ngn": 2660000, "penalty_formula": "2% fee reduction per 0.1% below SLA"},
            suggested_actions=["Calculate exact penalty under clause 12.3", "Issue formal notice to IHS within 30 days", "Request root cause report from IHS", "Review generator maintenance schedule"],
            draft_content="Dear IHS Nigeria Limited,\n\nRe: SLA Breach Notice — IHS/MTN/IKJ/2024-001\n\nWe write to formally notify you of an SLA breach recorded on 14 February 2026...",
            related_document_ids=["doc_001","doc_002"],
            organisation="MTN Nigeria",
            acknowledged_by=noc.id if noc else None,
            acknowledged_at=ago(hours=20),
            created_at=ago(days=1),
        ),
        Alert(
            title="MoMo Deduction Complaints Spike — Lagos +312% vs Q4 2025",
            summary="Complaint category 'momo_deduction' in Lagos has risen 312% quarter-on-quarter. Volume: 850 tickets in Q1 2026 vs 204 in Q4 2025. Disputed amount: NGN 28.4M. Pattern consistent with unauthorised API deductions — escalate to Mobile Money Operations.",
            severity="warning",
            status="new",
            alert_type="complaint_spike",
            extra_metadata={"category": "momo_deduction", "region": "Lagos", "count_q1_2026": 850, "count_q4_2025": 204, "pct_change": 312, "disputed_amount_ngn": 28400000},
            suggested_actions=["Audit MoMo API transaction logs", "Identify top 10 deduction sources", "Draft customer communication", "Engage NCC proactively before regulatory inquiry"],
            related_document_ids=["doc_003"],
            organisation="MTN Nigeria",
            created_at=ago(hours=6),
        ),
        Alert(
            title="NCC QoS Return Q1 2026 — Submission Due in 12 Days",
            summary="NCC QoS quarterly return for Q1 2026 must be submitted by 2026-04-14. Current Ikeja cluster availability (82.7% on 2026-02-14) is below the NCC minimum of 95%. Non-submission attracts a fine of NGN 5M per day. Legal team action required.",
            severity="warning",
            status="new",
            alert_type="regulatory_deadline",
            extra_metadata={"regulator": "NCC", "return_type": "QoS Quarterly", "quarter": "Q1 2026", "due_date": "2026-04-14", "days_remaining": 12, "daily_penalty_ngn": 5000000},
            suggested_actions=["Draft narrative explanation for Ikeja outage", "Prepare mitigation evidence", "Legal sign-off required before submission", "Request NOC data extracts"],
            related_document_ids=["doc_004"],
            organisation="MTN Nigeria",
            created_at=ago(hours=12),
        ),
        Alert(
            title="NDPA Article 24 Processing Record — Annual Review Overdue",
            summary="MTN Nigeria's NDPA Article 24 data processing record was last reviewed 2025-03-01. Annual review is overdue by 34 days. NITDA audit risk: failure to maintain current processing records attracts NGN 10M penalty under Section 48 NDPA 2023.",
            severity="warning",
            status="new",
            alert_type="compliance_gap",
            extra_metadata={"regulation": "NDPA 2023", "article": "Article 24", "last_reviewed": "2025-03-01", "days_overdue": 34, "penalty_ngn": 10000000},
            suggested_actions=["DPO to schedule immediate review", "Update data processing register", "File evidence of review with NITDA portal", "Check if any new data flows added since last review"],
            related_document_ids=["doc_005"],
            organisation="MTN Nigeria",
            created_at=ago(days=2),
        ),
        Alert(
            title="Kano-Kaduna Fibre Cut — SLA Milestone at Risk",
            summary="INC-2026-KNO-0088: Fibre cut at Km 142 of the Kano-Kaduna Julius Berger route. Repair ETA 8 hours. If Phase 1 milestone (Km 180) is missed by >7 days, penalty clause in JB/MTN/FIBRE/KNO-KAD/2025-007 activates: 0.5% of NGN 1.44B (= NGN 7.2M/week).",
            severity="info",
            status="new",
            alert_type="project_risk",
            extra_metadata={"contract_ref": "JB/MTN/FIBRE/KNO-KAD/2025-007", "incident_ref": "INC-2026-KNO-0088", "penalty_per_week_ngn": 7200000, "km_affected": 142},
            suggested_actions=["Monitor repair progress hourly", "Assess milestone impact", "Pre-notify Julius Berger PM if delay >24h", "Engage insurance for force majeure assessment"],
            organisation="MTN Nigeria",
            created_at=ago(hours=3),
        ),
    ]

    created = 0
    for a in alerts:
        if not db.query(Alert).filter_by(title=a.title).first():
            db.add(a)
            created += 1
    db.commit()
    print(f"  ✓ {created} alerts (skipped {len(alerts)-created} existing)")


# ── Conversations & Messages ──────────────────────────────────────────────────

def seed_conversations(db, users):
    noc_user  = users.get("chukwuemeka.obi@mtn.ng")
    legal     = users.get("adaeze.nwosu@mtn.ng")
    proc      = users.get("babatunde.afolabi@mtn.ng")

    convos = [
        {
            "user": noc_user,
            "title": "Ikeja Outage RCA Analysis",
            "messages": [
                ("user", "What happened during the Ikeja cluster outage on February 14?"),
                ("assistant", "**Ikeja Cluster Outage — 14 February 2026 (INC-2026-IKJ-0147)**\n\nA full outage affected all 6 Ikeja cluster sites from **02:14 to 06:23** (4 hours 9 minutes), impacting approximately **18,000 subscribers**.\n\n**Root Cause:** AES utility feeder failure on the Zone 7 ring. The generator auto-transfer relay at IKJ-001 failed to engage within the required 30 seconds, triggering a cascade power loss across all 6 sites. Additionally, generator fuel levels were at 18% — below the contractual minimum of 50% under IHS/MTN/IKJ/2024-001.\n\n**SLA Impact:** The 4.15-hour outage breached the 99.5% monthly uptime SLA with IHS Nigeria. Financial exposure: **NGN 2.66M** under the 2% fee reduction clause.\n\n**Corrective Actions Taken:**\n- Emergency refuelling completed by 04:00\n- Auto-transfer relay replaced at IKJ-001\n- IHS Nigeria issued site inspection mandate for all 6 cluster sites\n\n*Sources: Ikeja Cluster RCA Report Q1 2026, IHS Tower Lease Agreement*"),
                ("user", "What penalty can we claim from IHS?"),
                ("assistant", "Under **clause 12.3 of IHS/MTN/IKJ/2024-001**, MTN Nigeria can apply a **fee reduction of 2% per 0.1% below the 99.5% uptime SLA threshold**.\n\n**Calculation:**\n- Contracted SLA: 99.5% monthly uptime\n- Actual uptime for February 2026 (28 days): 4.15h downtime → **99.38% actual**\n- Shortfall: 0.12% below SLA\n- Penalty: 2% × 1.2 = **2.4% of monthly fee**\n- Monthly contract value: NGN 28,000,000\n- **Penalty amount: NGN 672,000**\n\nNote: The penalty cap is 20% of monthly fee (NGN 5.6M), so this calculation is well within the cap.\n\nMTN has **30 days from the incident date** (deadline: 16 March 2026) to issue the formal penalty notice. I recommend Legal review this urgently.\n\n*Sources: IHS Tower Lease Agreement, Ikeja RCA Report*"),
            ],
            "created_at": ago(days=3),
        },
        {
            "user": legal,
            "title": "NDPA Compliance Review",
            "messages": [
                ("user", "What are our obligations under Article 24 of the NDPA?"),
                ("assistant", "**MTN Nigeria's Obligations under NDPA 2023, Article 24**\n\nArticle 24 requires every data controller to **maintain a current record of all data processing activities**. This is the Data Processing Register.\n\n**Key Requirements:**\n1. **What to record:** Purpose of processing, categories of data subjects, categories of personal data, recipients of data, international transfer mechanisms, retention schedules, technical/organisational security measures\n2. **Who it applies to:** MTN Nigeria qualifies as a large-scale processor — full Article 24 obligations apply\n3. **Review frequency:** The register must be kept **accurate and up-to-date** — NITDA guidance recommends annual formal reviews\n4. **Availability:** Must be made available to NITDA on request within 48 hours\n\n**Current Status (from your records):** The processing record was last formally reviewed **1 March 2025** — now **34 days overdue**.\n\n**Penalty for non-compliance:** Section 48 NDPA 2023 — up to **NGN 10 million or 2% of annual gross revenue**, whichever is higher.\n\n*Source: MTN NDPA Article 24 Processing Record document*"),
            ],
            "created_at": ago(days=1),
        },
        {
            "user": proc,
            "title": "ATC Contract Renewal Strategy",
            "messages": [
                ("user", "The ATC Lagos Zone 2 contract expires in 28 days. What are our options?"),
                ("assistant", "**ATC/MTN/LAG/2023-007 — Renewal Analysis**\n\nWith 28 days to expiry (vs 90-day notice requirement in the contract), MTN is already in **breach of the renewal notice clause**. Here are your options:\n\n**Option 1 — Renew with ATC (Recommended)**\n- 12 sites, Lagos Zone 2 — strategically critical for LGI-001 (VI) and LGI-002 (Lekki) coverage\n- Current monthly value: NGN 19.5M. Expect 15-25% uplift in renegotiation given market rates\n- Leverage: ATC needs MTN's anchor tenancy. Use competitor quotes as BATNA\n\n**Option 2 — Transfer to IHS or Swap Tower**\n- IHS already manages Ikeja cluster (6 sites) — bundle could yield 8-12% discount\n- Risk: 90-day transition period → service gap unless emergency agreement in place\n- Cost: Civil works + downtime risk during transfer\n\n**Option 3 — Emergency Holdover (High Risk)**\n- Month-to-month occupancy at ATC discretion — rates typically 130-150% of contract rate\n- Avoid unless negotiations are actively progressing\n\n**My Recommendation:** Engage ATC VP today for a 6-month extension at current rates while full renewal is negotiated. This is common practice and protects network continuity.\n\n*Source: ATC Contract, Enterprise SLA Register*"),
            ],
            "created_at": ago(hours=5),
        },
    ]

    created = 0
    for cv in convos:
        u = cv["user"]
        if not u:
            continue
        existing = db.query(Conversation).filter_by(
            user_id=u.id, title=cv["title"]
        ).first()
        if existing:
            continue

        c = Conversation(user_id=u.id, title=cv["title"], created_at=cv["created_at"])
        db.add(c)
        db.flush()

        for i, (role, content) in enumerate(cv["messages"]):
            db.add(Message(
                conversation_id=c.id,
                role=role,
                content=content,
                citations=["doc_001","doc_002"] if role == "assistant" and i == 1 else [],
                agent_trace=["Researcher","Analyst","Strategist"] if role == "assistant" else [],
                created_at=cv["created_at"] + timedelta(minutes=i*2),
            ))
        created += 1

    db.commit()
    print(f"  ✓ {created} conversations with messages")


# ── Agent Runs ────────────────────────────────────────────────────────────────

def seed_agent_runs(db):
    runs = [
        AgentRun(agent_type="researcher", input_query="Ikeja cluster power outage February 2026",
                 output="Found 3 relevant documents: RCA report, IHS contract, NOC incident log",
                 steps=[{"tool": "search", "query": "ikeja outage 2026", "hits": 3}],
                 duration_ms=842, token_count=1240, success=True, created_at=ago(days=3)),
        AgentRun(agent_type="analyst", input_query="Calculate IHS SLA penalty for Ikeja outage",
                 output="Penalty: NGN 672,000 under clause 12.3 (2.4% of monthly fee)",
                 steps=[{"tool": "extract_clauses", "doc": "IHS contract"}, {"tool": "calculate", "result": 672000}],
                 duration_ms=1240, token_count=1850, success=True, created_at=ago(days=3)),
        AgentRun(agent_type="watchdog", input_query="Check for expiring contracts next 90 days",
                 output="Found 1 critical: ATC/MTN/LAG/2023-007 expires 2026-03-31 (28 days)",
                 steps=[{"tool": "query_contracts", "filter": "expiry<90d", "matches": 1}],
                 duration_ms=420, token_count=680, success=True, created_at=ago(hours=2)),
        AgentRun(agent_type="scribe", input_query="Draft SLA breach notice to IHS Nigeria",
                 output="Draft letter generated — 420 words, formal tone, references clause 12.3",
                 steps=[{"tool": "draft_letter", "template": "sla_breach_notice"}],
                 duration_ms=2100, token_count=3200, success=True, created_at=ago(days=1)),
        AgentRun(agent_type="strategist", input_query="What is our exposure on the ATC contract if it lapses?",
                 output="Holdover risk: NGN 29.25M/month (150% of contract) plus coverage gap risk on 12 Lagos sites",
                 steps=[{"tool": "search"}, {"tool": "analyse"}, {"tool": "synthesise"}],
                 duration_ms=3840, token_count=4100, success=True, created_at=ago(hours=5)),
        AgentRun(agent_type="researcher", input_query="NCC QoS quarterly return requirements",
                 output="Found NCC QoS return document — Q1 2026 due 2026-04-14",
                 steps=[{"tool": "search", "query": "NCC QoS quarterly return", "hits": 1}],
                 duration_ms=610, token_count=920, success=True, created_at=ago(hours=12)),
    ]

    created = 0
    for r in runs:
        db.add(r)
        created += 1
    db.commit()
    print(f"  ✓ {created} agent run records")


# ── Org Memory ────────────────────────────────────────────────────────────────

def seed_org_memory(db):
    memories = [
        OrgMemory(organisation="MTN Nigeria", memory_type="fact",
                  key="primary_tower_vendor_ikeja",
                  value="IHS Nigeria Limited manages all 6 Ikeja cluster tower sites under contract IHS/MTN/IKJ/2024-001 (Jul 2024 – Jun 2026, NGN 336M/year)",
                  confidence=1.0),
        OrgMemory(organisation="MTN Nigeria", memory_type="fact",
                  key="ran_maintenance_vendor",
                  value="Ericsson Nigeria Limited handles corrective and preventive maintenance for 847 base stations nationwide under ERIC/MTN/RAN/2026-001",
                  confidence=1.0),
        OrgMemory(organisation="MTN Nigeria", memory_type="pattern",
                  key="momo_complaint_trend",
                  value="MoMo deduction complaints spike sharply in Q1 and Q3 — historically linked to unauthorised API calls from third-party platforms. Q1 2026 shows 312% increase vs Q4 2025.",
                  confidence=0.92),
        OrgMemory(organisation="MTN Nigeria", memory_type="preference",
                  key="contract_escalation_threshold",
                  value="Procurement team escalates contract renewals to VP level when value > NGN 100M/year or < 60 days remaining",
                  confidence=0.95),
        OrgMemory(organisation="MTN Nigeria", memory_type="fact",
                  key="ncc_qos_submission_cycle",
                  value="NCC QoS quarterly returns are due 14 days after each quarter end: Q1 → Apr 14, Q2 → Jul 14, Q3 → Oct 14, Q4 → Jan 14",
                  confidence=1.0),
        OrgMemory(organisation="MTN Nigeria", memory_type="pattern",
                  key="ikeja_power_risk",
                  value="Ikeja cluster has experienced 3 power-related incidents in the last 18 months — AES feeder reliability is below industry average. IHS generator fuel SLA compliance rate: 73%.",
                  confidence=0.88),
        OrgMemory(organisation="MTN Nigeria", memory_type="fact",
                  key="kano_kaduna_fibre_project",
                  value="Julius Berger Phase 1 fibre rollout covers 287km Kano-Kaduna route, expected completion Sep 2026. Current progress: Km 139 of 287. Penalty clause: 0.5% of NGN 1.44B per week delay.",
                  confidence=0.97),
    ]

    created = 0
    for m in memories:
        if not db.query(OrgMemory).filter_by(organisation=m.organisation, key=m.key).first():
            db.add(m)
            created += 1
    db.commit()
    print(f"  ✓ {created} org memory entries")


# ── Knowledge Gaps ────────────────────────────────────────────────────────────

def seed_knowledge_gaps(db):
    gaps = [
        KnowledgeGap(query="What is the MTTR target for Ericsson RAN faults under the 2026 SLA?", confidence_score=0.12, created_at=ago(days=2)),
        KnowledgeGap(query="What are the penalty clauses for the Huawei core network contract?", confidence_score=0.21, created_at=ago(days=4)),
        KnowledgeGap(query="NNPC enterprise SLA uptime requirements and penalty schedule", confidence_score=0.08, created_at=ago(days=6)),
        KnowledgeGap(query="NCC Type Approval requirements for 5G small cell equipment", confidence_score=0.15, created_at=ago(days=8)),
        KnowledgeGap(query="MTN Nigeria HR policy on field engineer overtime and hazard allowances", confidence_score=0.05, created_at=ago(days=10)),
    ]

    created = 0
    for g in gaps:
        db.add(g)
        created += 1
    db.commit()
    print(f"  ✓ {created} knowledge gap entries")


# ── Audit Logs ────────────────────────────────────────────────────────────────

def seed_audit_logs(db, users):
    admin = users.get("admin@mtn.ng")
    noc   = users.get("chukwuemeka.obi@mtn.ng")
    legal = users.get("adaeze.nwosu@mtn.ng")

    logs = [
        AuditLog(user_id=admin.id if admin else None, action="user_created", resource="users", details={"email": "chukwuemeka.obi@mtn.ng", "role": "admin"}, ip_address="10.0.1.4", created_at=ago(days=60)),
        AuditLog(user_id=admin.id if admin else None, action="document_uploaded", resource="documents", details={"filename": "Ikeja_Cluster_RCA.txt", "department": "Network Operations"}, ip_address="10.0.1.4", created_at=ago(days=30)),
        AuditLog(user_id=noc.id if noc else None, action="document_searched", resource="search", details={"query": "Ikeja outage February 2026", "results": 3}, ip_address="10.0.1.7", created_at=ago(days=3)),
        AuditLog(user_id=legal.id if legal else None, action="document_viewed", resource="documents/doc_005", details={"title": "MTN NDPA Article 24 Processing Record"}, ip_address="10.0.1.12", created_at=ago(days=1)),
        AuditLog(user_id=noc.id if noc else None, action="alert_acknowledged", resource="alerts", details={"alert_type": "sla_breach", "contract": "IHS/MTN/IKJ/2024-001"}, ip_address="10.0.1.7", created_at=ago(hours=20)),
        AuditLog(user_id=admin.id if admin else None, action="connector_created", resource="connectors", details={"type": "sharepoint", "site": "MTN Nigeria Intranet"}, ip_address="10.0.1.4", created_at=ago(days=5)),
    ]

    for log in logs:
        db.add(log)
    db.commit()
    print(f"  ✓ {len(logs)} audit log entries")


# ── Documents (metadata only, no actual files) ────────────────────────────────

def seed_documents(db, users):
    admin = users.get("admin@mtn.ng")
    docs = [
        Document(id="doc_001", title="Ikeja Cluster RCA Power Outage Q1 2026", filename="Ikeja_Cluster_RCA_Power_Outage_Q1_2026.txt", file_type="txt", department="Network Operations", tags=["rca","ikeja","outage","noc"], status="indexed", chunk_count=12, uploaded_by_id=admin.id if admin else None, created_at=ago(days=30)),
        Document(id="doc_002", title="TowerCo IHS Nigeria Tower Lease Agreement", filename="TowerCo_IHS_Nigeria_Tower_Lease_Agreement.txt", file_type="txt", department="Procurement", tags=["ihs","towerco","tower-lease"], status="indexed", chunk_count=18, uploaded_by_id=admin.id if admin else None, created_at=ago(days=45)),
        Document(id="doc_003", title="Customer Complaints MoMo Deductions Q1 2026", filename="Customer_Complaints_MoMo_Deductions_Q1_2026.txt", file_type="txt", department="Customer Experience", tags=["momo","complaints","q1-2026"], status="indexed", chunk_count=9, uploaded_by_id=admin.id if admin else None, created_at=ago(days=20)),
        Document(id="doc_004", title="NCC QoS Quarterly Return Q4 2025", filename="NCC_QoS_Quarterly_Return_Q4_2025.txt", file_type="txt", department="Legal/Regulatory", tags=["ncc","qos","regulatory"], status="indexed", chunk_count=14, uploaded_by_id=admin.id if admin else None, created_at=ago(days=60)),
        Document(id="doc_005", title="MTN NDPA Article 24 Processing Record", filename="MTN_NDPA_Article_24_Processing_Record.txt", file_type="txt", department="Legal/Regulatory", tags=["ndpa","compliance","dpo"], status="indexed", chunk_count=11, uploaded_by_id=admin.id if admin else None, created_at=ago(days=400)),
        Document(id="doc_006", title="Ericsson RAN Maintenance SLA 2026", filename="Ericsson_RAN_Maintenance_SLA_2026.txt", file_type="txt", department="Procurement", tags=["ericsson","ran","sla"], status="indexed", chunk_count=22, uploaded_by_id=admin.id if admin else None, created_at=ago(days=120)),
        Document(id="doc_007", title="Kano Kaduna Fibre Route BoQ", filename="Kano_Kaduna_Fibre_Route_BoQ.txt", file_type="txt", department="Network Operations", tags=["fibre","boq","kano","kaduna"], status="indexed", chunk_count=16, uploaded_by_id=admin.id if admin else None, created_at=ago(days=90)),
        Document(id="doc_008", title="Enterprise Customer SLA Register EBU", filename="Enterprise_Customer_SLA_Register_EBU.txt", file_type="txt", department="Enterprise Business", tags=["enterprise","sla","ebu","zenith-bank"], status="indexed", chunk_count=20, uploaded_by_id=admin.id if admin else None, created_at=ago(days=30)),
    ]
    created = 0
    for d in docs:
        if not db.query(Document).filter_by(id=d.id).first():
            db.add(d)
            created += 1
    db.commit()
    print(f"  ✓ {created} document records (skipped {len(docs)-created} existing)")


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    print("\nIroko AI -- Full Database Seed")
    print("=" * 45)

    print("\nInitialising database schema...")
    init_db()
    print("  ✓ Schema ready\n")

    db = SessionLocal()
    try:
        print("Seeding users...")
        users = seed_users(db)

        print("Seeding documents (metadata)...")
        seed_documents(db, users)

        print("Seeding vendor contracts...")
        seed_contracts(db)

        print("Seeding network sites...")
        sites = seed_sites(db)

        print("Seeding network incidents...")
        ikj_incident = seed_incidents(db, sites)

        print("Seeding complaint tickets...")
        seed_complaints(db, ikj_incident)

        print("Seeding network KPIs...")
        seed_kpis(db)

        print("Seeding alerts...")
        seed_alerts(db, users)

        print("Seeding conversations & messages...")
        seed_conversations(db, users)

        print("Seeding agent run records...")
        seed_agent_runs(db)

        print("Seeding org memory...")
        seed_org_memory(db)

        print("Seeding knowledge gaps...")
        seed_knowledge_gaps(db)

        print("Seeding audit logs...")
        seed_audit_logs(db, users)

        print("\nSeed complete -- Iroko AI database is fully populated.")
        print("\n  Demo credentials:")
        print("    admin@mtn.ng           / AtlasAdmin2026!  (superadmin)")
        print("    chukwuemeka.obi@mtn.ng / Password2026!   (NOC admin)")
        print("    adaeze.nwosu@mtn.ng    / Password2026!   (Legal analyst)")
        print("    babatunde.afolabi@mtn.ng / Password2026! (Procurement analyst)")
        print("    ngozi.eze@mtn.ng       / Password2026!   (CX viewer)")

    except Exception as e:
        db.rollback()
        print(f"\nSeed FAILED: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
