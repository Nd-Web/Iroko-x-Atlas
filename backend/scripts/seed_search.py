"""
Seed Azure AI Search — push realistic document chunks for the 8 seed documents.

Run from the backend directory:
    python -m scripts.seed_search
or with explicit DATABASE_URL:
    DATABASE_URL=postgresql://... python -m scripts.seed_search
"""
import sys, os, asyncio
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

try:
    from services.keyvault import load_secrets_from_keyvault
    load_secrets_from_keyvault()
except Exception:
    pass


DOCUMENTS = [
    {
        "id": "doc_001",
        "title": "Ikeja Cluster RCA Power Outage Q1 2026",
        "department": "Network Operations",
        "content": """Ikeja Cluster RCA Power Outage Q1 2026

ROOT CAUSE ANALYSIS REPORT

Document Reference: NOC/RCA/IKJ/2026-001
Prepared By: Chukwuemeka Obi, Network Operations Centre
Date: 15 February 2026
Severity: P1 — Customer-Affecting Outage

EXECUTIVE SUMMARY

On 14 February 2026, between 23:47 and 04:12 WAT, a total of 14 base stations in the Ikeja
cluster experienced simultaneous power failure, affecting approximately 87,000 subscribers.
The outage lasted 4 hours 25 minutes, resulting in a revenue impact estimated at NGN 12,400,000.
Network availability for the affected cluster dropped to 78.3% during the incident window.

INCIDENT TIMELINE

23:47 WAT — First alarm received: IKJ-0471 (Ikeja Industrial Zone) power alarm
23:51 WAT — IKJ-0472, IKJ-0474 generate power alarms; NOC initiates P1 procedure
00:05 WAT — Field team dispatched from Oregun maintenance depot
00:22 WAT — 11 additional sites in Ikeja cluster cascade offline; suspected grid failure
01:10 WAT — MTN field engineer arrives at IKJ-0471; confirms transformer explosion
01:45 WAT — Generator fuel confirmed sufficient; bypass attempted, fails
02:30 WAT — Emergency generator from IHS Towers depot arrives at IKJ-0471
03:15 WAT — Primary site IKJ-0471 restored; cascade restoration begins
04:12 WAT — All 14 sites confirmed operational; cluster restored to 100%

ROOT CAUSE

A 500 KVA distribution transformer operated by IKEDC (Ikeja Electric Distribution Company)
feeding the Oregun Industrial feeder experienced a catastrophic winding failure following
sustained overload caused by the Valentine's Day evening peak demand. Voltage surge during
transformer failure caused cascading battery management system (BMS) trip across 14 sites
sharing the same feeder circuit through IHS infrastructure.

CONTRIBUTING FACTORS

1. IHS tower infrastructure shares single IKEDC feeder across 14-site cluster (SPOF risk)
2. Generator auto-start at 7 of 14 sites failed due to faulty relay (maintenance backlog)
3. Fuel monitoring alerts suppressed at IKJ-0472 and IKJ-0475 (configuration error)
4. Escalation delay: NOC-to-field team response exceeded 10-minute SLA by 8 minutes

IMPACT ASSESSMENT

Subscribers affected: 87,000 (GSM: 61,000 / Data: 26,000)
Revenue impact: NGN 12,400,000 (estimated based on Q1 ARPU data)
SLA breach with IHS Nigeria: 4 hours 25 minutes against 2-hour restoration SLA
NCC notification filed: 15 February 2026 — CISD/NOC/2026/IKJ/001

REMEDIATION ACTIONS

Immediate (completed):
- Generator relay replaced at 7 affected sites
- Fuel monitoring alert suppression cleared at IKJ-0472 and IKJ-0475
- IHS Nigeria notified of SLA breach; penalty clause invoked (Ref: IHS-MTN-SLA-2024, Clause 8.3)

Short-term (Q2 2026, Owner: Babatunde Afolabi — Procurement):
- Dual-feeder arrangement to be negotiated with IKEDC for Oregun Industrial Zone
- Generator auto-start testing to be added to monthly preventive maintenance checklist
- Standalone battery backup (minimum 8-hour) to be procured for top-10 revenue sites

Long-term (Q3 2026):
- Review all 23 IHS cluster configurations for single-point-of-failure feeder dependency
- Negotiate feeder redundancy SLA requirement into IHS contract renewal (expires May 2026)

LESSONS LEARNED

1. Single-feeder cluster configurations must be identified and remediated as P1 risk
2. Generator relay maintenance requires quarterly validation, not annual
3. NOC escalation tree must be reviewed to meet the 10-minute P1 field dispatch SLA

Approved: Chukwuemeka Obi, NOC Head — 16 February 2026
""",
    },
    {
        "id": "doc_002",
        "title": "TowerCo IHS Nigeria Tower Lease Agreement",
        "department": "Procurement",
        "content": """TowerCo IHS Nigeria Tower Lease Agreement

MASTER TOWER LEASE AGREEMENT

Reference: IHS/MTN/MLA/2021-001
Between: IHS Towers Nigeria Limited ("IHS") and MTN Nigeria Communications PLC ("MTN")
Effective Date: 15 May 2021
Expiry Date: 14 May 2026
Total Towers Under Agreement: 847

ARTICLE 1 — SCOPE OF AGREEMENT

IHS hereby grants to MTN a non-exclusive licence to co-locate telecommunications equipment
on 847 tower sites across Nigeria for the duration of this Agreement. Monthly lease fee is
NGN 45,000,000 per site cluster (23 cluster groups), totalling NGN 1,035,000,000 per month.

ARTICLE 2 — SLA AND AVAILABILITY COMMITMENTS

2.1 IHS guarantees 99.5% uptime per tower site per calendar month.
2.2 Generator fuel level must be maintained at minimum 50% capacity at all times.
2.3 Preventive maintenance must be completed monthly per site; reports submitted within 48 hours.
2.4 Maximum restoration time for P1 outages: 2 hours from NOC notification.
2.5 P2 outages: 8 hours. P3: 24 hours. Scheduled maintenance: 14 days' written notice required.

ARTICLE 3 — PENALTY CLAUSES

3.1 Failure to meet P1 restoration SLA (2 hours): NGN 500,000 per hour per affected site.
3.2 Monthly uptime below 99.5%: 5% credit against monthly invoice per affected site.
3.3 Fuel level breach (below 50%): NGN 250,000 per site per occurrence.
3.4 Failure to submit monthly maintenance report: NGN 100,000 per site per occurrence.

ARTICLE 4 — CONTRACT RENEWAL

4.1 Either party may elect to renew by providing 90 days' written notice before expiry.
4.2 Renewal notice due date: 13 February 2026 (90 days before 14 May 2026).
4.3 Failure to serve renewal notice defaults to month-to-month at 110% of current rate.
4.4 MTN retains right of first refusal on any new tower sites added by IHS in existing cluster zones.

ARTICLE 5 — EQUIPMENT AND ACCESS

5.1 MTN retains ownership of all equipment installed on IHS sites.
5.2 Access to sites for MTN field engineers must be granted within 2 hours of request (P1/P2).
5.3 IHS must maintain access logs and provide to MTN on request within 24 hours.

ARTICLE 6 — FORCE MAJEURE

Outages directly attributable to grid failure by DISCOs are exempt from penalty clauses
provided IHS demonstrates generator auto-start was functional and fuel was at required level.
Distribution company (DISCO) failure logs must be obtained and submitted within 72 hours.

ARTICLE 7 — DISPUTE RESOLUTION

Disputes shall first be referred to a joint technical committee (JTC) with 15-day resolution window.
Unresolved disputes proceed to arbitration under Lagos Court of Arbitration rules.

SCHEDULES

Schedule A — List of 847 tower sites by state and LGA (attached)
Schedule B — Monthly SLA reporting template
Schedule C — Penalty calculation methodology
Schedule D — Equipment inventory per site (baseline: May 2021)

Status Note (as at 1 May 2026): Contract expiry in 13 days. Renewal notice was due
13 February 2026 — 77 days overdue. Procurement team action required immediately.
""",
    },
    {
        "id": "doc_003",
        "title": "Customer Complaints MoMo Deductions Q1 2026",
        "department": "Customer Experience",
        "content": """Customer Complaints MoMo Deductions Q1 2026

CUSTOMER EXPERIENCE REPORT — MOBILE MONEY UNAUTHORISED DEDUCTIONS

Reference: CX/CRM/2026/Q1/MoMo
Period: January 1 – March 31, 2026
Prepared By: Ngozi Eze, Customer Experience Unit
Total Complaints Filed: 4,231

EXECUTIVE SUMMARY

Q1 2026 saw a significant spike in customer complaints related to MoMo (Mobile Money)
unauthorised deductions, constituting 34% of all CX complaints — up from 21% in Q4 2025.
Average complaint resolution time was 4.7 days against SLA target of 3 days.
Customer satisfaction score for complaint resolution: 61/100.

COMPLAINT CATEGORIES

Category 1 — Unauthorised Merchant Debits: 1,847 complaints (43.7%)
Customers report debits from unrecognised merchants following SIM swap or account compromise.
Average deduction: NGN 8,400. Total exposure: NGN 15,514,800.

Category 2 — Failed Transactions Debited: 1,102 complaints (26.1%)
Transaction failed at point of sale but amount deducted from MoMo wallet.
Typical reconciliation time: 2-5 business days.
Total exposure: NGN 9,256,800.

Category 3 — Duplicate Charges: 682 complaints (16.1%)
Same transaction charged twice; common in USSD sessions experiencing network lag.
Average duplicate amount: NGN 4,200.

Category 4 — Subscription Deductions Without Consent: 600 complaints (14.2%)
Third-party content providers billing via MoMo without confirmed customer opt-in.
NCC DO-NOT-DISTURB list non-compliance suspected in 3 vendor partners.

REGIONAL BREAKDOWN

Lagos: 1,891 complaints (44.7%) — highest volume, highest average transaction value
Kano: 612 complaints (14.5%)
Abuja: 487 complaints (11.5%)
Rivers: 398 complaints (9.4%)
Oyo: 311 complaints (7.4%)
Other states: 532 complaints (12.6%)

SLA COMPLIANCE

Complaints resolved within 3-day SLA: 2,687 (63.5%) — below 80% target
Complaints resolved within 5 days: 3,849 (91.0%)
Complaints escalated to CBN: 47 — all required written response within 5 business days
Regulatory fine risk (CBN Consumer Protection Framework): NGN 2,000,000 per breach above threshold

REFUNDS PROCESSED

Total refunds approved: 3,127 complaints
Total refund value: NGN 26,268,000
Refunds pending (30+ days): 394 complaints — escalation required

NCC COMPLIANCE NOTES

Per NCC Consumer Code of Practice 2022, MTN must resolve complaints within 5 business days.
CBN Mobile Money Regulations require MoMo operators to refund disputed transactions within
72 hours for amounts under NGN 50,000 pending investigation.

RECOMMENDATIONS

1. Implement real-time transaction anomaly detection for MoMo debits above NGN 5,000
2. Mandatory 2-FA for merchant initiations above NGN 10,000
3. Review and terminate 3 vendor partners suspected of NCC DND non-compliance
4. Increase CX team staffing by 12 FTEs to restore 3-day SLA compliance
""",
    },
    {
        "id": "doc_004",
        "title": "NCC QoS Quarterly Return Q4 2025",
        "department": "Legal/Regulatory",
        "content": """NCC QoS Quarterly Return Q4 2025

NIGERIAN COMMUNICATIONS COMMISSION
QUALITY OF SERVICE QUARTERLY RETURN

Operator: MTN Nigeria Communications PLC
Quarter: Q4 2025 (October 1 – December 31, 2025)
Filed: 15 January 2026
Reference: NCC/QoS/MTN/2025/Q4

SECTION A — NETWORK PERFORMANCE METRICS

A1. Voice Service Quality
Call Setup Success Rate (CSSR): 98.7% (Benchmark: 98.0% — COMPLIANT)
Call Drop Rate (CDR): 1.3% (Benchmark: 2.0% — COMPLIANT)
Standalone Dedicated Control Channel (SDCCH) Congestion: 0.8% (Benchmark: 1.0% — COMPLIANT)
Traffic Channel (TCH) Congestion: 1.1% (Benchmark: 2.0% — COMPLIANT)

A2. Data Service Quality
Packet Data Call Setup Success Rate: 96.2% (Benchmark: 95.0% — COMPLIANT)
Ping (Round Trip Time) < 100ms: 89.4% (Benchmark: 90.0% — NON-COMPLIANT — 0.6 percentage points)
Throughput 2Mbps floor on LTE: 87.3% (Benchmark: 85.0% — COMPLIANT)

A3. SMS Service Quality
SMS Delivery Success Rate: 99.1% (Benchmark: 99.0% — COMPLIANT)
SMS Delivery Time < 10s: 94.7% (Benchmark: 95.0% — NON-COMPLIANT — 0.3 percentage points)

A4. Coverage
2G Population Coverage: 94.8% (Benchmark: 90.0% — COMPLIANT)
3G Population Coverage: 88.3% (Benchmark: 80.0% — COMPLIANT)
4G Population Coverage: 76.1% (Benchmark: 70.0% — COMPLIANT)

SECTION B — COMPLAINT STATISTICS

Total complaints received Q4 2025: 12,847
Resolved within 5 business days: 11,203 (87.2%) — Benchmark 90.0% — NON-COMPLIANT
Complaints escalated to NCC: 312
Average resolution time: 4.1 days

SECTION C — NON-COMPLIANT METRICS — REGULATORY RISK ASSESSMENT

1. Ping RTT < 100ms: 89.4% vs 90.0% benchmark (0.6pp shortfall)
   Risk: NCC may issue informal directive. Repeated non-compliance triggers formal sanction.
   Remediation: Lagos and Abuja core network upgrade scheduled Q1 2026.

2. SMS Delivery Time < 10s: 94.7% vs 95.0% benchmark (0.3pp shortfall)
   Risk: Low — first occurrence; NCC typically allows 2 quarters to remediate.
   Remediation: SMSC hardware upgrade deferred to Q2 2026 pending CapEx approval.

3. Complaint Resolution within 5 days: 87.2% vs 90.0% benchmark (2.8pp shortfall)
   Risk: MODERATE — this is the second consecutive quarter of non-compliance.
   Remediation: CX team restructuring underway; target 90%+ by Q2 2026.
   NCC may issue formal warning and demand corrective action plan within 30 days.

SECTION D — REGULATORY CORRESPONDENCE

NCC query reference NCC/ENF/MTN/2025/0847 received 20 December 2025 regarding
complaint resolution compliance — response filed 8 January 2026.
Awaiting NCC determination.

SECTION E — NETWORK INFRASTRUCTURE STATISTICS

Total active base stations: 23,847
Sites with 4G capability: 18,204 (76.3%)
Sites with 5G NSA: 312 (1.3%)
Planned new sites Q1 2026: 847

Submitted by: Adaeze Nwosu, Director Regulatory Affairs
MTN Nigeria Communications PLC
""",
    },
    {
        "id": "doc_005",
        "title": "MTN NDPA Article 24 Processing Record",
        "department": "Legal/Regulatory",
        "content": """MTN NDPA Article 24 Processing Record

DATA PROTECTION PROCESSING RECORD
NIGERIA DATA PROTECTION ACT 2023 — ARTICLE 24 COMPLIANCE

Organisation: MTN Nigeria Communications PLC
Data Protection Officer: Adaeze Nwosu (adaeze.nwosu@mtn.ng)
Record Version: 3.1
Last Updated: 1 February 2026

ARTICLE 24 REQUIREMENT: RECORDS OF PROCESSING ACTIVITIES (ROPA)

Under Section 24 of the Nigeria Data Protection Act 2023 (NDPA), MTN Nigeria as a data
controller processing personal data of over 1 million data subjects is required to maintain
and make available on request a record of all processing activities.

PROCESSING ACTIVITY 1 — SUBSCRIBER REGISTRATION

Purpose: KYC verification, SIM registration as mandated by NCC
Legal Basis: Legal obligation (NCC SIM Registration Directive 2022)
Data Categories: Full name, NIN, date of birth, address, biometric (fingerprint)
Data Subjects: All new subscribers (~2.1 million new registrations per year)
Recipients: NCC (mandatory SIM registry), NIMC (NIN verification API)
Retention: 5 years post-subscription termination
Cross-border Transfer: None
Security Measures: AES-256 encryption at rest; TLS 1.3 in transit; access logging

PROCESSING ACTIVITY 2 — CALL DETAIL RECORDS (CDR)

Purpose: Billing, network optimisation, regulatory compliance
Legal Basis: Legitimate interests (billing); Legal obligation (NCC lawful intercept)
Data Categories: Calling/called numbers, duration, timestamps, cell tower IDs, IMEI
Data Subjects: All active subscribers (~76.5 million)
Recipients: NCC (on lawful request); Internal analytics team
Retention: 12 months per NCC directive; 36 months for billing disputes
Cross-border Transfer: Analytics aggregates only (anonymised) — transferred to MTN Group SA
Security Measures: Row-level security in CDR database; DBA access restricted to 4 named staff

PROCESSING ACTIVITY 3 — MOBILE MONEY (MOMO) TRANSACTIONS

Purpose: Payment processing, fraud detection, CBN compliance
Legal Basis: Contract (MoMo subscriber agreement); Legal obligation (CBN EMTS Guidelines)
Data Categories: Account number, BVN, transaction history, merchant data, geolocation at transaction
Data Subjects: MoMo subscribers (~14.2 million wallet holders)
Recipients: CBN (regulatory reporting); NIBSS (NIP transfers); acquiring banks
Retention: 7 years (FIRS requirement for financial records)
Cross-border Transfer: None — all MoMo data processed on MTN Nigeria owned/controlled infrastructure
Security Measures: PCI-DSS Level 1 certified infrastructure; tokenisation for BVN storage

PROCESSING ACTIVITY 4 — CUSTOMER COMPLAINTS AND FEEDBACK

Purpose: Complaint resolution, service improvement, NCC compliance
Legal Basis: Legal obligation (NCC Consumer Code); Legitimate interests
Data Categories: Name, contact, complaint details, call recordings, resolution notes
Data Subjects: Complaining subscribers
Recipients: NCC (on request for complaint adjudication)
Retention: 3 years from resolution
Cross-border Transfer: None

DATA SUBJECT RIGHTS — FULFILMENT STATISTICS (Q4 2025)

Access requests received: 47 — fulfilled within 72 hours: 44 (93.6%)
Erasure requests: 12 — fulfilled: 8; contested: 4 (CDR retention obligation)
Portability requests: 3 — fulfilled: 3

NDPC AUDIT STATUS: Last NDPC inspection April 2025 — no material findings.
Next compliance deadline: Annual ROPA submission due 31 March 2026.

DPO Certification: ISACA CDPSE, IAPP CIPP/E — renewal due June 2026.
""",
    },
    {
        "id": "doc_006",
        "title": "Ericsson RAN Maintenance SLA 2026",
        "department": "Procurement",
        "content": """Ericsson RAN Maintenance SLA 2026

ERICSSON RADIO ACCESS NETWORK MAINTENANCE SERVICE AGREEMENT

Agreement Reference: MTN-NG/ERICSSON/RAN/MSA/2026
Between: Ericsson Nigeria Limited ("Ericsson") and MTN Nigeria Communications PLC ("MTN")
Effective Date: 1 January 2026
Duration: 24 months (to 31 December 2027)
Total Contract Value: NGN 18,400,000,000 (NGN 18.4 billion)

SCOPE OF SERVICES

1. PREVENTIVE MAINTENANCE
Ericsson shall perform scheduled preventive maintenance on all 14,847 RAN nodes (comprising
3G NodeBs, 4G eNodeBs, and 5G gNodeBs) under this agreement.
Frequency: Monthly for macro sites; Quarterly for micro/pico sites.
Documentation: Maintenance completion certificates within 48 hours per site.

2. CORRECTIVE MAINTENANCE — FAULT RESOLUTION SLA

Priority 1 (Complete Service Loss): 4-hour restoration SLA nationwide.
Priority 2 (Partial Service Degradation >30%): 8-hour restoration SLA.
Priority 3 (Degradation <30% or non-service-affecting): 48-hour resolution.
Priority 4 (Minor/cosmetic): 10 business days.

Penalty for P1 SLA breach: NGN 1,200,000 per site per hour beyond SLA.
Penalty for P2 SLA breach: NGN 600,000 per site per hour beyond SLA.
Monthly penalty cap: 15% of monthly contract value.

3. SPARE PARTS MANAGEMENT

Ericsson maintains dedicated spare parts depot at Oregun, Lagos with minimum stock:
- RRU (Radio Remote Units): 50 units per band class (B1/B3/B7/B20/B28/n78)
- BBU (Baseband Units): 30 units per model variant
- Power modules: 100 units
- Antenna systems: 40 units
Parts delivery to site: within 2 hours for Lagos; 6 hours for other states.

4. SOFTWARE AND FIRMWARE MANAGEMENT

Ericsson is responsible for all RAN software upgrade planning and execution.
Software release advisory: 30 days' advance notice for each planned upgrade.
Change freeze periods: NCC filing deadlines (Q-end ±2 weeks); peak events (elections, national holidays).
Post-upgrade monitoring: 72-hour hypercare period with NOC co-presence.

5. PERFORMANCE REPORTING

Monthly performance report: due 5th of following month.
KPIs reported: CSSR, CDR, DCR, SDCCH Congestion, TCH Congestion, Data Throughput, Latency.
Format: Ericsson OSS export + MTN NOC dashboard integration.
Quarterly business review (QBR): joint meeting within 15 days of quarter end.

6. KEY PERFORMANCE INDICATORS — 2026 TARGETS

Call Setup Success Rate: 99.0% (stretch: 99.2%)
Call Drop Rate: <1.5% (stretch: <1.2%)
Data Availability (4G): 99.2%
Average Latency (4G): <45ms
5G gNB availability (312 sites): 98.5%

7. GOVERNANCE

MTN contract owner: Babatunde Afolabi, Head Procurement (babatunde.afolabi@mtn.ng)
Ericsson account director: TBA (Ericsson to nominate within 30 days)
Escalation path: Technical Lead → Account Director → VP Networks → CEO escalation within 6 hours of P1

8. PENALTIES BILLED Q1 2026

Penalty invoked for 14-February power outage cascade (IKJ cluster):
P1 SLA breach × 4 sites × 2.3 hours overage = NGN 11,040,000
Dispute raised by Ericsson: force majeure (grid failure) — under review at JTC level.
""",
    },
    {
        "id": "doc_007",
        "title": "Kano Kaduna Fibre Route BoQ",
        "department": "Network Operations",
        "content": """Kano Kaduna Fibre Route BoQ

BILL OF QUANTITIES — KANO-KADUNA FIBRE OPTIC BACKBONE ROUTE

Project Reference: MTN-NG/INFRA/FIBRE/KAN-KAD/2026
Client: MTN Nigeria Communications PLC
Prepared By: Network Infrastructure Planning Team
Date: 20 March 2026
Route Distance: 214 km (Kano CBD to Kaduna City Centre via Zaria bypass)
Tender Validity: 60 days from issue date

PROJECT OVERVIEW

This BoQ covers the deployment of a 144-fibre underground backbone route between Kano
and Kaduna to provide redundant high-capacity connectivity for the North-West Nigeria
cluster. Current sole-path connectivity via aerial fibre is vulnerable to weather events
and road construction interference. Target capacity: 400 Gbps per wavelength (DWDM).

SECTION 1 — CIVIL WORKS

Item 1.1 — Trenching (urban areas: 148 km at NGN 850,000/km)
Estimated Cost: NGN 125,800,000

Item 1.2 — Trenching (peri-urban/rural: 66 km at NGN 420,000/km)
Estimated Cost: NGN 27,720,000

Item 1.3 — Road crossing (tarmac bore: 47 crossings at NGN 1,200,000 each)
Estimated Cost: NGN 56,400,000

Item 1.4 — Bridge crossing installation (12 crossings at NGN 3,800,000 each)
Estimated Cost: NGN 45,600,000

Item 1.5 — Duct installation (HDPE 50mm × 4-way micro-duct: 214 km × 4 = 856 km)
Rate: NGN 180,000/km
Estimated Cost: NGN 154,080,000

Item 1.6 — Concrete protection slab (urban sections only: 148 km)
Rate: NGN 95,000/km
Estimated Cost: NGN 14,060,000

CIVIL WORKS SUBTOTAL: NGN 423,660,000

SECTION 2 — FIBRE OPTIC CABLE SUPPLY

Item 2.1 — 144-core G.652.D single-mode fibre cable (230 km including 8% wastage)
Rate: NGN 1,450,000/km
Estimated Cost: NGN 333,500,000

Item 2.2 — Figure-8 aerial fibre for 6 bridge crossings (4 km)
Rate: NGN 980,000/km
Estimated Cost: NGN 3,920,000

CABLE SUPPLY SUBTOTAL: NGN 337,420,000

SECTION 3 — SPLICING AND TERMINATION

Item 3.1 — Fusion splicing (estimated 3,440 splices at NGN 12,000 each)
Estimated Cost: NGN 41,280,000

Item 3.2 — Fibre splice closures (86 units at NGN 185,000 each)
Estimated Cost: NGN 15,910,000

Item 3.3 — Optical Distribution Frames (8 locations at NGN 4,200,000 each)
Estimated Cost: NGN 33,600,000

Item 3.4 — Patch panels and connectors (8 locations, lump sum)
Estimated Cost: NGN 12,400,000

SPLICING SUBTOTAL: NGN 103,190,000

SECTION 4 — ACTIVE EQUIPMENT (DWDM)

Item 4.1 — DWDM terminals (8 locations, 40-channel OADM)
Rate: NGN 68,000,000 per terminal
Estimated Cost: NGN 544,000,000

Item 4.2 — Optical amplifiers (EDFA, 6 sites)
Rate: NGN 28,000,000 each
Estimated Cost: NGN 168,000,000

ACTIVE EQUIPMENT SUBTOTAL: NGN 712,000,000

SECTION 5 — PERMITTING AND RIGHT-OF-WAY

Item 5.1 — Federal Roads (NiMet/FHA wayleave): NGN 18,500,000
Item 5.2 — State government wayleave (Kano/Kaduna): NGN 12,800,000
Item 5.3 — Local government levies (estimated 14 LGAs): NGN 8,400,000
Item 5.4 — NCC infrastructure deployment notification fee: NGN 4,200,000

PERMITTING SUBTOTAL: NGN 43,900,000

TOTAL PROJECT COST ESTIMATE: NGN 1,620,170,000 (approximately NGN 1.62 billion)
Contingency (10%): NGN 162,017,000
GRAND TOTAL: NGN 1,782,187,000

PROJECT TIMELINE: 18 months from contract award (Q3 2026 start; Q4 2027 completion)
Funding approval required: Q2 2026 CapEx committee
""",
    },
    {
        "id": "doc_008",
        "title": "Enterprise Customer SLA Register EBU",
        "department": "Enterprise Business",
        "content": """Enterprise Customer SLA Register EBU

MTN NIGERIA ENTERPRISE BUSINESS UNIT
SLA REGISTER — TIER 1 ENTERPRISE CUSTOMERS

Reference: EBU/SLA/REG/2026/Q1
Last Updated: 1 April 2026
Total Tier 1 Accounts: 23 customers
Compiled By: Enterprise Business Unit

CUSTOMER 1 — ZENITH BANK PLC

MTN Account Manager: Fatima Bello
Contract Value: NGN 2,400,000,000 per annum
Services: MPLS VPN (47 branches), Internet Bandwidth, Voice Trunking, Managed SD-WAN

Committed SLAs:
- Internet availability: 99.9% (< 8.7 hours downtime per year)
- MPLS latency Lagos-Abuja: < 25ms
- MPLS packet loss: < 0.1%
- Voice call completion rate: 99.5%
- Incident response P1: 15 minutes acknowledgement; 2-hour restoration
- Planned maintenance window: 02:00-05:00 WAT Sundays only; 14-day notice

Q1 2026 Performance vs SLA:
- Internet availability: 99.87% (below 99.9% target by 0.03pp — SLA credit due: NGN 7,200,000)
- MPLS latency: 23ms average — COMPLIANT
- Voice completion: 99.6% — COMPLIANT
- P1 incidents: 2 events; both restored within 2-hour SLA — COMPLIANT
Status: SLA credit NGN 7,200,000 to be applied to April invoice.

CUSTOMER 2 — FIRST BANK OF NIGERIA

MTN Account Manager: Emeka Duru
Contract Value: NGN 1,850,000,000 per annum
Services: MPLS VPN (112 branches), Dedicated Internet Access 10Gbps

Committed SLAs:
- Availability: 99.95%
- Latency Lagos core: < 20ms
- Incident response P1: 10-minute acknowledgement; 1-hour restoration

Q1 2026 Performance:
- Availability: 99.97% — COMPLIANT
- All P1 SLAs met — COMPLIANT

CUSTOMER 3 — DANGOTE GROUP

MTN Account Manager: Adaora Okonkwo
Contract Value: NGN 4,200,000,000 per annum (largest EBU account)
Services: MPLS VPN (200+ sites), 5G private network (Dangote Fertiliser Plant Lekki), IoT SIM (3,200 units)

Committed SLAs:
- 5G private network availability: 99.99% (< 52 minutes downtime per year)
- IoT data delivery: 99.5% of packets delivered within 5 seconds
- Dedicated NOC support: 24/7 hotline with < 2-minute pickup SLA

Q1 2026 Performance:
- 5G private network: 99.99% — COMPLIANT
- IoT delivery: 99.7% — COMPLIANT
- NOC pickup time average: 47 seconds — COMPLIANT

CUSTOMER 4 — GTCO (GUARANTY TRUST HOLDINGS)

Contract Value: NGN 1,600,000,000 per annum
Services: MPLS VPN (89 branches), Managed Security (firewall/DDoS), Bulk SMS

Q1 2026 Performance: All SLAs met. Upsell opportunity: SD-WAN upgrade discussions ongoing.

SLA REGISTER SUMMARY — Q1 2026

Total active Tier 1 contracts: 23
Customers with all SLAs met: 21 (91.3%)
Customers requiring SLA credit: 2 (Zenith Bank, UBA — minor availability shortfall)
Total SLA credits issued Q1 2026: NGN 14,800,000
Customer satisfaction survey (Q1): 81/100 (EBU benchmark: 80/100 — on target)
Renewals due within 90 days: 4 accounts (Zenith Bank, Access Bank, Airtel Business — competitor risk)
Contracts at risk: Zenith Bank (repeated availability shortfall; competitor pitch received)
Revenue at risk: NGN 2,400,000,000 (Zenith Bank contract value)

RECOMMENDED ACTIONS:
1. Account review meeting with Zenith Bank within 2 weeks; offer NGN 50M credit gesture
2. Technical review of Lagos-Abuja MPLS path causing the availability shortfall
3. Accelerate SD-WAN upsell to Access Bank before renewal date in July 2026
""",
    },
]


async def index_all():
    from services.document_processor import smart_chunk_document
    from services.azure_search import index_document_chunks

    print("\nIroko AI -- Seed Azure Search Index")
    print("=" * 45)

    total_chunks = 0
    for doc in DOCUMENTS:
        chunks = smart_chunk_document(
            text=doc["content"],
            document_id=doc["id"],
            title=doc["title"],
            department=doc["department"],
        )

        created_at = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
        ok = await index_document_chunks(
            document_id=doc["id"],
            title=doc["title"],
            chunks=chunks,
            metadata={
                "department":     doc["department"],
                "doc_type":       "document",
                "source":         doc["title"],
                "filename":       doc["title"] + ".txt",
                "classification": "internal",
                "language":       "en",
                "region":         "",
                "created_at":     created_at,
            },
        )
        status = "indexed" if ok else "FAILED"
        print(f"  [{status}] {doc['id']} — {doc['title']} ({len(chunks)} chunks)")
        if ok:
            total_chunks += len(chunks)

    print(f"\nDone. {total_chunks} chunks pushed to iroko-chunks index.")


if __name__ == "__main__":
    asyncio.run(index_all())
