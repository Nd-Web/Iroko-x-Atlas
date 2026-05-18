"""
Seed Network Data — MTN Nigeria
================================
Populates the database with realistic telecom operational data
for demo and development purposes.

Run from the project root:
    python -m scripts.seed_network_data
"""
import sys
import os
from datetime import datetime, timedelta
import random

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

from models.database import SessionLocal, init_db
from models.network_models import (
    NetworkSite, NetworkIncident, VendorContract, ComplaintTicket, NetworkKPI,
)


def seed(db):
    print("Seeding MTN Nigeria network data...")

    # ── Vendor Contracts ─────────────────────────────────────────────────────
    contracts = [
        VendorContract(
            contract_ref="IHS/MTN/IKJ/2024-001",
            title="TowerCo Tower Lease Agreement — IHS Nigeria (Ikeja Cluster)",
            vendor_name="IHS Nigeria Limited",
            vendor_type="towerco",
            scope="Tower lease and power management for 6 Ikeja cluster macro sites",
            monthly_value_ngn=28_000_000,
            annual_value_ngn=336_000_000,
            commencement_date=datetime(2024, 7, 1),
            expiry_date=datetime(2026, 6, 30),
            renewal_notice_days=90,
            sla_uptime_pct=99.5,
            penalty_formula="2% fee reduction per 0.1% below SLA threshold",
            penalty_cap_pct=20.0,
            department="Procurement",
            document_id="doc_002",
            sites_covered=["IKJ-001","IKJ-002","IKJ-003","IKJ-004","IKJ-005","IKJ-006"],
            status="active",
        ),
        VendorContract(
            contract_ref="ERIC/MTN/RAN/2026-001",
            title="Ericsson RAN Maintenance SLA — 2026",
            vendor_name="Ericsson Nigeria Limited",
            vendor_type="ran_vendor",
            scope="Corrective and preventive maintenance for 847 base stations nationwide",
            monthly_value_ngn=15_000_000,
            annual_value_ngn=180_000_000,
            commencement_date=datetime(2026, 1, 1),
            expiry_date=datetime(2026, 12, 31),
            renewal_notice_days=90,
            sla_uptime_pct=99.5,
            sla_response_hours=4.0,
            penalty_formula="NGN 50,000 per hour beyond response SLA",
            department="Procurement",
            document_id="doc_006",
            status="active",
        ),
        VendorContract(
            contract_ref="HUW/MTN/CORE/2025-001",
            title="Huawei Core Network Maintenance — 2025-2027",
            vendor_name="Huawei Technologies Nigeria",
            vendor_type="ran_vendor",
            scope="Core network (EPC/IMS) maintenance and software upgrades",
            monthly_value_ngn=22_000_000,
            annual_value_ngn=264_000_000,
            commencement_date=datetime(2025, 1, 1),
            expiry_date=datetime(2027, 12, 31),
            renewal_notice_days=120,
            sla_uptime_pct=99.9,
            sla_response_hours=2.0,
            penalty_formula="3% fee reduction per incident exceeding response SLA",
            department="Procurement",
            status="active",
        ),
        VendorContract(
            contract_ref="ATC/MTN/LAG/2023-007",
            title="American Tower Corporation — Lagos Zone 2 Sites",
            vendor_name="American Tower Corporation",
            vendor_type="towerco",
            scope="Tower lease for 12 Lagos Zone 2 macro sites",
            monthly_value_ngn=19_500_000,
            annual_value_ngn=234_000_000,
            commencement_date=datetime(2023, 4, 1),
            expiry_date=datetime(2026, 3, 31),
            renewal_notice_days=90,
            sla_uptime_pct=99.3,
            penalty_formula="1.5% fee reduction per 0.1% below SLA",
            department="Procurement",
            status="expiring",
        ),
        VendorContract(
            contract_ref="JB/MTN/FIBRE/KNO-KAD/2025-007",
            title="Julius Berger — Kano-Kaduna Fibre Route (Phase 1)",
            vendor_name="Julius Berger Nigeria Plc",
            vendor_type="fibre",
            scope="Civil works and cable laying for 287km Kano-Kaduna fibre route",
            monthly_value_ngn=120_000_000,
            annual_value_ngn=1_440_000_000,
            commencement_date=datetime(2025, 10, 1),
            expiry_date=datetime(2026, 9, 30),
            renewal_notice_days=60,
            penalty_formula="0.5% of project value per week of delay beyond milestone",
            department="Network Operations",
            document_id="doc_007",
            status="active",
        ),
    ]
    for c in contracts:
        existing = db.query(VendorContract).filter_by(contract_ref=c.contract_ref).first()
        if not existing:
            db.add(c)
    db.commit()
    print(f"  ✓ {len(contracts)} vendor contracts")

    # ── Network Sites ────────────────────────────────────────────────────────
    sites_data = [
        # Ikeja cluster (Lagos)
        ("IKJ-001","Ikeja Tower 4471","macro","Ikeja","Lagos","Zone 7",6.5833,3.3500,"IHS Nigeria","Ericsson","IHS/MTN/IKJ/2024-001","ERIC/MTN/RAN/2026-001",3200,"4G","fibre","operational"),
        ("IKJ-002","Ikeja Oregun Road","macro","Ikeja","Lagos","Zone 7",6.5860,3.3480,"IHS Nigeria","Ericsson","IHS/MTN/IKJ/2024-001","ERIC/MTN/RAN/2026-001",2800,"4G","fibre","operational"),
        ("IKJ-003","Ikeja GRA North","macro","Ikeja","Lagos","Zone 7",6.5980,3.3420,"IHS Nigeria","Ericsson","IHS/MTN/IKJ/2024-001","ERIC/MTN/RAN/2026-001",2100,"4G","microwave","operational"),
        ("IKJ-004","Ikeja Along","macro","Ikeja","Lagos","Zone 7",6.5720,3.3560,"IHS Nigeria","Huawei","IHS/MTN/IKJ/2024-001","HUW/MTN/CORE/2025-001",1900,"4G/5G","fibre","degraded"),
        ("IKJ-005","Ikeja Computer Village","macro","Ikeja","Lagos","Zone 7",6.5800,3.3510,"IHS Nigeria","Ericsson","IHS/MTN/IKJ/2024-001","ERIC/MTN/RAN/2026-001",4100,"4G","fibre","operational"),
        ("IKJ-006","Ikeja Under Bridge","micro","Ikeja","Lagos","Zone 7",6.5740,3.3530,"IHS Nigeria","Huawei","IHS/MTN/IKJ/2024-001","HUW/MTN/CORE/2025-001",1400,"4G","fibre","operational"),
        # Lagos Island
        ("LGI-001","Victoria Island Eko Hotel","macro","Lagos Island","Lagos","Zone 1",6.4281,3.4219,"ATC","Ericsson","ATC/MTN/LAG/2023-007","ERIC/MTN/RAN/2026-001",5200,"4G/5G","fibre","operational"),
        ("LGI-002","Lekki Phase 1","macro","Lagos Island","Lagos","Zone 1",6.4350,3.4780,"ATC","Huawei","ATC/MTN/LAG/2023-007","HUW/MTN/CORE/2025-001",4800,"4G/5G","fibre","operational"),
        ("LGI-003","Surulere National Stadium","macro","Surulere","Lagos","Zone 3",6.5040,3.3630,"IHS Nigeria","Ericsson","IHS/MTN/IKJ/2024-001","ERIC/MTN/RAN/2026-001",3600,"4G","fibre","operational"),
        ("LGI-004","Yaba College Road","macro","Yaba","Lagos","Zone 3",6.5075,3.3793,"ATC","Ericsson","ATC/MTN/LAG/2023-007","ERIC/MTN/RAN/2026-001",2900,"4G","fibre","operational"),
        # Abuja
        ("ABJ-001","CBD Maitama","macro","Maitama","Abuja","FCT Central",9.0628,7.4887,"IHS Nigeria","Ericsson",None,"ERIC/MTN/RAN/2026-001",6100,"4G/5G","fibre","operational"),
        ("ABJ-002","Wuse Zone 4","macro","Wuse","Abuja","FCT Central",9.0634,7.4847,"IHS Nigeria","Huawei",None,"HUW/MTN/CORE/2025-001",4300,"4G","fibre","operational"),
        ("ABJ-003","Gwarinpa Estate","macro","Gwarinpa","Abuja","FCT North",9.1052,7.4148,"IHS Nigeria","Ericsson",None,"ERIC/MTN/RAN/2026-001",3800,"4G","microwave","operational"),
        # Kano
        ("KNO-001","Kano Sabon Gari","macro","Sabon Gari","Kano","Kano North",12.0022,8.5920,"IHS Nigeria","Huawei",None,"HUW/MTN/CORE/2025-001",5500,"3G/4G","fibre","operational"),
        ("KNO-002","Kano Kurmi Market","macro","Old City","Kano","Kano Central",11.9934,8.5335,"IHS Nigeria","Ericsson",None,"ERIC/MTN/RAN/2026-001",4100,"3G/4G","microwave","operational"),
        ("KNO-003","Kano Airport","macro","Nasarawa","Kano","Kano South",11.9944,8.5265,"ATC","Ericsson","ATC/MTN/LAG/2023-007","ERIC/MTN/RAN/2026-001",2200,"4G","fibre","operational"),
        # Kaduna
        ("KAD-001","Kaduna Central Business","macro","Kaduna Central","Kaduna","Kaduna Central",10.5272,7.4396,"IHS Nigeria","Huawei",None,"HUW/MTN/CORE/2025-001",4700,"3G/4G","fibre","operational"),
        ("KAD-002","Barnawa","macro","Barnawa","Kaduna","Kaduna South",10.4876,7.4234,"IHS Nigeria","Ericsson",None,"ERIC/MTN/RAN/2026-001",3100,"4G","microwave","operational"),
        # Port Harcourt
        ("PHC-001","GRA Phase 2","macro","GRA","Port Harcourt","Rivers Central",4.8156,7.0498,"ATC","Ericsson","ATC/MTN/LAG/2023-007","ERIC/MTN/RAN/2026-001",4900,"4G","fibre","operational"),
        ("PHC-002","Old Market Trans-Amadi","macro","Trans-Amadi","Port Harcourt","Rivers Central",4.8180,7.0231,"IHS Nigeria","Huawei",None,"HUW/MTN/CORE/2025-001",3700,"4G","fibre","operational"),
        # Fibre POPs
        ("POP-KNO-01","Kano Metro POP","pop","Kano Metro","Kano","Kano North",12.0010,8.5900,None,"Huawei",None,"HUW/MTN/CORE/2025-001",0,"fibre","fibre","operational"),
        ("POP-KAD-01","Kaduna Metro POP","pop","Kaduna Metro","Kaduna","Kaduna Central",10.5260,7.4380,None,"Huawei",None,"HUW/MTN/CORE/2025-001",0,"fibre","fibre","operational"),
    ]

    site_objects = {}
    for row in sites_data:
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
            site_objects[code] = s
        else:
            site_objects[code] = existing
    db.commit()
    print(f"  ✓ {len(sites_data)} network sites")

    # ── Network Incidents ────────────────────────────────────────────────────
    anchor = site_objects.get("IKJ-001")
    ikj4 = site_objects.get("IKJ-004")

    incidents_data = [
        dict(
            incident_ref="INC-2026-IKJ-0147",
            title="Ikeja Cluster Power Outage — AES Feeder Failure",
            description="Full outage across 6 Ikeja sites due to AES utility feeder failure and generator auto-transfer relay malfunction.",
            site_id=anchor.id if anchor else None,
            cluster="Ikeja", region="Lagos",
            affected_sites_count=6, affected_subscribers=18000,
            severity="critical", status="resolved", priority="P1",
            root_cause_category="power",
            root_cause_detail="AES utility feeder failure on Zone 7 ring; generator auto-transfer relay at IKJ-001 did not engage within 30 seconds, causing cascade power loss across all 6 cluster sites.",
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
        dict(
            incident_ref="INC-2026-IKJ-0201",
            title="IKJ-004 Sector B Antenna Tilt Fault — Degraded Coverage",
            description="Sector B antenna at IKJ-004 Ikeja Along showing persistent tilt fault after recent maintenance visit. Coverage degraded by ~35% in southern footprint.",
            site_id=ikj4.id if ikj4 else None,
            cluster="Ikeja", region="Lagos",
            affected_sites_count=1, affected_subscribers=650,
            severity="major", status="investigating", priority="P2",
            root_cause_category="equipment",
            root_cause_detail="Antenna tilt actuator failure suspected. Field team dispatch scheduled.",
            sla_breached=False, sla_exposure_ngn=0,
            vendor_sla_breached=False,
            started_at=datetime.utcnow() - timedelta(hours=6),
            detected_at=datetime.utcnow() - timedelta(hours=5, minutes=50),
            acknowledged_at=datetime.utcnow() - timedelta(hours=5, minutes=20),
            assigned_team="RAN Support", escalation_level=1,
        ),
        dict(
            incident_ref="INC-2026-KNO-0088",
            title="Kano-Kaduna Fibre Cut — ROW Excavation",
            description="Fibre cut at Km 142 of the Kano-Kaduna route caused by third-party road excavation. Traffic being rerouted via microwave backup. Capacity reduced by 60%.",
            site_id=None,
            cluster="Kano Metro", region="Kano",
            affected_sites_count=4, affected_subscribers=8200,
            severity="major", status="open", priority="P2",
            root_cause_category="fibre_cut",
            root_cause_detail="Third-party KEDCO excavation crew cut the fibre at Km 142 (Zaria bypass). Repair team dispatched. ETA 8 hours.",
            sla_breached=False, sla_exposure_ngn=0,
            vendor_sla_breached=False,
            started_at=datetime.utcnow() - timedelta(hours=3),
            detected_at=datetime.utcnow() - timedelta(hours=2, minutes=55),
            acknowledged_at=datetime.utcnow() - timedelta(hours=2, minutes=30),
            assigned_team="Field Eng", escalation_level=1,
        ),
    ]

    for inc_data in incidents_data:
        existing = db.query(NetworkIncident).filter_by(incident_ref=inc_data["incident_ref"]).first()
        if not existing:
            db.add(NetworkIncident(**inc_data))
    db.commit()
    print(f"  ✓ {len(incidents_data)} network incidents")

    # ── Complaint Tickets ────────────────────────────────────────────────────
    categories = [
        ("momo_deduction", "Lagos", "consumer", 850, 0.73),
        ("data_billing", "Lagos", "consumer", 420, 0.81),
        ("voice_quality", "Lagos", "consumer", 380, 0.75),
        ("network_coverage", "Lagos", "consumer", 310, 0.68),
        ("data_billing", "Abuja", "enterprise", 190, 0.88),
        ("momo_deduction", "Kano", "consumer", 290, 0.70),
        ("network_coverage", "Port Harcourt", "consumer", 220, 0.72),
        ("voice_quality", "Kaduna", "consumer", 180, 0.77),
    ]

    ticket_count = 0
    for (cat, region, segment, volume, res_rate) in categories:
        for i in range(min(volume // 20, 8)):  # sample ~8 per category
            ref = f"CMP-2026-{region[:3].upper()}-{ticket_count+1:05d}"
            existing = db.query(ComplaintTicket).filter_by(ticket_ref=ref).first()
            if not existing:
                days_ago = random.randint(0, 30)
                reported = datetime.utcnow() - timedelta(days=days_ago, hours=random.randint(0, 23))
                resolved = random.random() < res_rate
                disputed = round(random.uniform(500, 25000), 2) if cat == "momo_deduction" else 0
                db.add(ComplaintTicket(
                    ticket_ref=ref,
                    category=cat,
                    customer_segment=segment,
                    customer_region=region,
                    status="resolved" if resolved else ("escalated" if random.random() < 0.2 else "open"),
                    priority="high" if cat == "momo_deduction" else "medium",
                    disputed_amount_ngn=disputed,
                    refund_amount_ngn=round(disputed * 0.9, 2) if (resolved and disputed) else 0,
                    channel=random.choice(["call_centre", "app", "social_media"]),
                    reported_at=reported,
                    resolved_at=reported + timedelta(hours=random.randint(2, 72)) if resolved else None,
                ))
                ticket_count += 1
    db.commit()
    print(f"  ✓ {ticket_count} complaint tickets")

    # ── Network KPIs (30 days time series) ──────────────────────────────────
    base_date = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=30)
    kpi_count = 0

    for day in range(31):
        d = base_date + timedelta(days=day)
        incident_day = (d.date() == datetime(2026, 2, 14).date())

        # ── National ────────────────────────────────────────────────────────
        existing = db.query(NetworkKPI).filter(
            NetworkKPI.date == d, NetworkKPI.scope_level == "national"
        ).first()
        if not existing:
            avail = 99.1 if incident_day else round(random.uniform(99.3, 99.6), 2)
            csr   = 96.8 if incident_day else round(random.uniform(97.0, 97.8), 2)
            db.add(NetworkKPI(
                date=d, granularity="daily", scope_level="national",
                availability_pct=avail,
                call_setup_success_pct=csr,
                drop_call_rate_pct=round(random.uniform(0.6, 1.2), 2),
                data_throughput_mbps=round(random.uniform(48, 62), 1),
                latency_ms=round(random.uniform(18, 35), 1),
                complaint_count=random.randint(80, 140),
                csat_score=round(random.uniform(68, 76), 1),
                availability_target=99.5,
                csr_target=95.0,
            ))
            kpi_count += 1

        # ── Lagos Region — 10 sites, ~24,300 subscribers ────────────────────
        existing_lag = db.query(NetworkKPI).filter(
            NetworkKPI.date == d,
            NetworkKPI.scope_level == "region",
            NetworkKPI.region == "Lagos",
        ).first()
        if not existing_lag:
            lag_avail = 98.7 if incident_day else round(random.uniform(99.2, 99.5), 2)
            lag_csr   = 96.1 if incident_day else round(random.uniform(96.8, 97.5), 2)
            db.add(NetworkKPI(
                date=d, granularity="daily",
                scope_level="region", region="Lagos",
                availability_pct=lag_avail,
                call_setup_success_pct=lag_csr,
                drop_call_rate_pct=round(random.uniform(0.7, 1.4), 2),
                data_throughput_mbps=round(random.uniform(52, 68), 1),
                latency_ms=round(random.uniform(16, 30), 1),
                subscriber_count=24300,
                complaint_count=random.randint(40, 80),
                csat_score=round(random.uniform(66, 74), 1),
                availability_target=99.5,
                csr_target=95.0,
            ))
            kpi_count += 1

        # ── Ikeja Cluster — 6 sites, ~15,500 subscribers ────────────────────
        # 4.15h outage out of 24h = 82.7% availability on the incident day
        existing_ikj = db.query(NetworkKPI).filter(
            NetworkKPI.date == d,
            NetworkKPI.scope_level == "cluster",
            NetworkKPI.cluster == "Ikeja",
        ).first()
        if not existing_ikj:
            ikj_avail = 82.7 if incident_day else round(random.uniform(99.1, 99.6), 2)
            ikj_csr   = 88.2 if incident_day else round(random.uniform(96.5, 97.4), 2)
            db.add(NetworkKPI(
                date=d, granularity="daily",
                scope_level="cluster", cluster="Ikeja", region="Lagos",
                availability_pct=ikj_avail,
                call_setup_success_pct=ikj_csr,
                drop_call_rate_pct=12.4 if incident_day else round(random.uniform(0.8, 1.6), 2),
                data_throughput_mbps=round(random.uniform(44, 58), 1),
                latency_ms=round(random.uniform(14, 28), 1),
                subscriber_count=15500,
                complaint_count=312 if incident_day else random.randint(18, 45),
                csat_score=41.2 if incident_day else round(random.uniform(64, 73), 1),
                availability_target=99.5,
                csr_target=95.0,
            ))
            kpi_count += 1

    db.commit()
    print(f"  ✓ {kpi_count} KPI records (national + Lagos region + Ikeja cluster, 30-day)")


    print("\n✅ Seed complete. MTN Nigeria operational data loaded.")


if __name__ == "__main__":
    init_db()
    db = SessionLocal()
    try:
        seed(db)
    finally:
        db.close()
