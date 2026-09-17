"""
Seed Azure AI Search — push realistic document chunks for the 8 seed documents.

The corpus covers a CBN/SEC-regulated Nigerian microfinance bank / fintech and is
written to answer the demo questions in services/demo_seed.py (capital adequacy,
prudential returns, AML/CFT and SAR filing, single-obligor limits, NDPA Article 24
and data localization, loan-deduction complaints, core banking migration).

Re-running is safe: each document's existing chunks are deleted first, so a
rewrite that produces fewer chunks never leaves stale ones behind.

Run from the backend directory:
    python -m scripts.seed_search
or with explicit DATABASE_URL:
    DATABASE_URL=postgresql://... python -m scripts.seed_search
"""
import sys, os, asyncio
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
# override=True so .env wins over any stale machine-wide Azure vars — otherwise
# chunks can be embedded with the wrong model and silently mismatch the index.
load_dotenv(override=True)

try:
    from services.keyvault import load_secrets_from_keyvault
    load_secrets_from_keyvault()
except Exception:
    pass


DOCUMENTS = [
    {
        "id": "doc_001",
        "title": "Loan Portal Outage RCA Q1 2026",
        "department": "IT Operations",
        "content": """Loan Portal Outage RCA Q1 2026

ROOT CAUSE ANALYSIS REPORT

Document Reference: ITO/RCA/LP/2026-001
Prepared By: Chukwuemeka Obi, Technology Operations
Date: 15 February 2026
Severity: P1 — Customer-Affecting Outage

EXECUTIVE SUMMARY

On 14 February 2026, between 23:47 and 04:12 WAT, the customer loan origination
portal and the USSD lending channel were unavailable for 4 hours 25 minutes,
affecting approximately 87,000 active borrowers. 11,400 loan applications and
6,200 repayment postings failed during the window. Estimated revenue impact is
NGN 12,400,000 in deferred interest income, with a further NGN 3,100,000 in
goodwill credits issued to affected customers.

Channel availability for the month fell to 99.1%, below the 99.5% internal
service standard but above the CBN Consumer Protection Framework expectation of
prompt restoration and customer notification.

INCIDENT TIMELINE

23:47 WAT — First alarm: loan-portal API latency breach (p95 > 8s)
23:51 WAT — USSD lending short code 3 timeouts; NOC initiates P1 procedure
00:05 WAT — Database connection pool exhaustion confirmed on LOS primary
00:22 WAT — Failover to standby node attempted; standby rejects connections
01:10 WAT — Core banking interface queue backs up to 41,000 messages
01:45 WAT — Vendor (core banking provider) escalated under Severity 1 SLA
02:30 WAT — Connection pool limits raised; standby node returned to service
03:15 WAT — Loan portal restored; queued messages begin draining
04:12 WAT — All channels confirmed operational; queue fully drained

ROOT CAUSE

A configuration change deployed on 13 February raised the batch repayment job's
concurrency from 20 to 120 worker threads without a corresponding increase to
the loan origination system (LOS) database connection pool, which remained
capped at 100 connections. The Valentine's Day evening repayment peak exhausted
the pool, starving the interactive loan portal of connections.

The standby node rejected failover because its connection pool configuration had
drifted from primary following a November 2025 patch that was never applied to
the standby.

CONTRIBUTING FACTORS

1. Change advisory board approved the concurrency change without a capacity review
2. Standby node configuration drift undetected since November 2025 (no config audit)
3. Connection pool saturation alerting threshold set at 100% rather than 80%
4. Escalation delay: NOC-to-vendor escalation exceeded the 10-minute SLA by 8 minutes

CUSTOMER AND REGULATORY IMPACT

Complaint volume for the week rose 310% against the trailing 4-week average.
CSAT for the loan channel dropped from 78% to 61% for February, recovering to
74% by the first week of March. Under the CBN Consumer Protection Framework the
Bank notified affected customers within 24 hours and logged the incident in the
complaints register. The incident did not meet the NDPA section 34 threshold for
NDPC notification: no personal data was disclosed, altered, or lost — this was an
availability incident only, confirmed by the Data Protection Officer on 15 February.

REMEDIATION

1. Connection pool sizing tied to batch concurrency in deployment templates — due 28 Feb 2026
2. Automated configuration drift detection across primary and standby — due 15 Mar 2026
3. Pool saturation alert threshold lowered to 80% — completed 16 Feb 2026
4. Capacity review mandatory for concurrency changes at CAB — completed 20 Feb 2026
5. Vendor escalation path rehearsed quarterly — first drill due 31 Mar 2026

SLA EXPOSURE

The core banking vendor breached the Severity 1 response SLA (30 minutes
contractual, 47 minutes actual). Service credit claimable under Schedule 4 of the
core banking agreement is 5% of the quarterly support fee, approximately
NGN 4,200,000. Claim lodged 18 February 2026, pending vendor acknowledgement.
""",
    },
    {
        "id": "doc_002",
        "title": "Core Banking Vendor Agreement 2026",
        "department": "Procurement",
        "content": """Core Banking Vendor Agreement 2026

MASTER SERVICES AGREEMENT — CORE BANKING PLATFORM

Agreement Reference: PROC/CBS/2024-017
Parties: African Fintech Platform Microfinance Bank Limited ("the Bank") and
         Meridian Core Systems Limited ("the Vendor")
Effective Date: 1 July 2024
Initial Term: 36 months, expiring 30 June 2027
Contract Value: NGN 1,850,000,000 over the initial term

KEY COMMERCIAL TERMS

Annual licence and support fee: NGN 336,000,000 payable quarterly in advance
Implementation and migration fee: NGN 480,000,000 (milestone-based)
Change request day rate: NGN 420,000 per consultant day
Annual uplift: capped at Nigerian CPI or 8%, whichever is lower

RENEWAL AND EXPIRY SCHEDULE

The following engagements sit under this master agreement. Renewal dates drive
the 90-day procurement review cycle.

Schedule 1 — Core banking licence: expires 30 June 2027 (auto-renews 12 months
  unless terminated with 180 days notice; notice deadline 1 January 2027)
Schedule 2 — Disaster recovery hosting: expires 31 May 2026 (RENEWAL DUE — within
  90 days; procurement review required by 28 February 2026)
Schedule 3 — Payment switch integration: expires 30 April 2026 (RENEWAL DUE —
  within 90 days; procurement review overdue as of 1 February 2026)
Schedule 4 — Support and maintenance: co-terminus with Schedule 1
Schedule 5 — Data centre colocation (Lagos): expires 15 June 2026 (RENEWAL DUE —
  within 90 days)

Four schedules fall due within the next 90 days, representing NGN 214,000,000 of
annual contracted spend. Procurement policy requires a competitive review or a
documented single-source justification at least 60 days before each expiry.

SERVICE LEVELS (SCHEDULE 4)

Platform availability: 99.9% measured monthly, excluding agreed maintenance
Severity 1 response: 30 minutes, 24x7
Severity 1 resolution target: 4 hours
Severity 2 response: 2 hours during business hours
Mean time to restore (MTTR), Severity 1: 4 hours contractual ceiling
Planned maintenance window: Sundays 00:00–04:00 WAT, maximum 2 per month

SERVICE CREDITS

Availability 99.5%–99.9%: 2% of quarterly support fee
Availability 99.0%–99.5%: 5% of quarterly support fee
Availability below 99.0%: 10% of quarterly support fee plus right to terminate
  the affected schedule on 30 days notice
Severity 1 response breach: 5% of quarterly support fee per occurrence

REGULATORY AND OUTSOURCING OBLIGATIONS

The Vendor acknowledges the Bank is licensed and supervised by the Central Bank
of Nigeria. Under the CBN Guidelines on Outsourcing and BOFIA 2020, the Bank
remains fully responsible to the CBN for outsourced functions. Accordingly:

1. The CBN and its examiners have a contractual right of access to Vendor systems,
   records, and premises relating to the Bank's data (Clause 14.2)
2. The Vendor must notify the Bank within 12 hours of any security incident
   affecting the Bank's data, enabling the Bank to meet the NDPA section 34
   72-hour NDPC notification deadline (Clause 14.5)
3. Customer and KYC data must be hosted within Nigeria; any cross-border transfer
   requires prior written approval from the Bank's Data Protection Officer and a
   lawful transfer basis under NDPA section 41 (Clause 14.7)
4. The Vendor may not subcontract processing of customer data without prior
   written consent (Clause 14.9)
5. Exit assistance of up to 6 months at agreed rates, with full data return in a
   machine-readable format and certified deletion thereafter (Clause 21)

TERMINATION

For convenience: 180 days written notice, with early termination charge equal to
  50% of the remaining licence fees for the then-current term
For cause: 30 days written notice on material unremedied breach
Regulatory termination: immediate, if the CBN directs the Bank to terminate or
  the Vendor loses a licence or certification material to the service, with no
  early termination charge payable
""",
    },
    {
        "id": "doc_003",
        "title": "Customer Complaints Loan Deductions Q1 2026",
        "department": "Customer Experience",
        "content": """Customer Complaints Loan Deductions Q1 2026

QUARTERLY COMPLAINTS ANALYSIS

Document Reference: CX/COMP/2026-Q1
Prepared By: Adaeze Nwankwo, Head of Customer Experience
Date: 5 April 2026
Distribution: MANCO, Compliance, CBN Consumer Protection returns file

EXECUTIVE SUMMARY

Total complaints received in Q1 2026: 14,207 (Q4 2025: 9,880) — a 43.8% increase.
Loan deduction disputes account for 6,842 complaints (48.2% of the total) and are
the single largest driver of the quarter-on-quarter rise.

Resolution within the CBN-mandated timeline was achieved on 91.4% of complaints,
below the 95% internal target and below the 98% achieved in Q4 2025.

COMPLAINT CATEGORIES

Loan deduction disputes: 6,842 (48.2%)
Failed or duplicated repayment postings: 2,914 (20.5%)
Loan portal and USSD unavailability: 1,861 (13.1%)
Interest and fee disputes: 1,402 (9.9%)
KYC and account access: 788 (5.5%)
Other: 400 (2.8%)

LOAN DEDUCTION DISPUTES — ROOT CAUSE BREAKDOWN

Duplicate deduction following retry logic: 2,610 (38.1%)
Deduction after loan fully repaid: 1,744 (25.5%)
Deduction amount exceeds agreed instalment: 1,201 (17.6%)
Deduction on a rescheduled or restructured loan: 803 (11.7%)
Disputed authorisation (customer denies mandate): 484 (7.1%)

The 484 disputed-authorisation cases carry the highest regulatory risk. Under the
CBN Consumer Protection Framework and the Guide to Charges by Banks and Other
Financial Institutions, a deduction without a valid, auditable customer mandate is
an unauthorised debit requiring refund within 48 hours of the complaint plus
payment of any accrued interest to the customer.

POLICY CONFLICT — REFUND TIMELINE

Internal Complaints Handling Policy v3.1, section 6.4, currently allows the
disputes team up to 5 working days to refund a disputed deduction, on the basis
that the mandate audit trail must first be retrieved from the core banking
platform.

This directly contradicts the CBN Consumer Protection Framework, which requires
an unauthorised debit to be reversed within 48 hours of the customer's complaint.
The internal policy therefore authorises a timeline that is itself a breach of
the regulation, and staff following the policy as written will put the Bank in
default. Legal and Compliance raised this on 22 February 2026; the policy has not
yet been amended and remains in force as at the date of this report.

Estimated exposure: 484 disputed-authorisation cases in the quarter, of which 297
were refunded outside the 48-hour regulatory window while remaining inside the
5-day internal window.

MONTH-ON-MONTH TREND

January 2026: 3,118 complaints, 1,244 loan deduction disputes
February 2026: 6,904 complaints, 3,802 loan deduction disputes (loan portal
  outage of 14 February drove a 310% weekly spike; 2,411 complaints trace
  directly to the failed repayment postings during that incident)
March 2026: 4,185 complaints, 1,796 loan deduction disputes

The February peak is incident-driven and is expected to normalise. However, the
March baseline of 1,796 remains 44% above the Q4 2025 monthly average of 1,247,
indicating a structural issue in retry logic independent of the outage.

CSAT AND NPS

Overall CSAT: Q1 2026 68% (Q4 2025 79%)
Loan channel CSAT: February low of 61%, recovering to 74% by early March
NPS: Q1 2026 +11 (Q4 2025 +28)
Average time to resolution: 3.8 days (Q4 2025: 2.1 days)

REGULATORY EXPOSURE

Complaints unresolved beyond the CBN timeline: 1,222 (8.6%)
Cases escalated to the CBN Consumer Protection Department: 47
Refunds processed in the quarter: NGN 84,300,000
Provision held for disputed deductions pending investigation: NGN 31,000,000

Failure to resolve within the mandated timeline exposes the Bank to CBN
sanction. Repeated unauthorised debits may also attract a directive to refund all
affected customers irrespective of whether they complained, which on current
volumes would carry an estimated exposure of NGN 240,000,000.

REMEDIATION

1. Idempotency keys on all repayment retries to eliminate duplicate deductions —
   due 30 April 2026
2. Automated stop on any deduction against a loan with zero outstanding balance —
   completed 12 March 2026
3. Mandate audit trail surfaced in the agent console for dispute handling —
   due 31 May 2026
4. Additional 25 complaint handlers onboarded to restore resolution timelines —
   completed 1 April 2026
""",
    },
    {
        "id": "doc_004",
        "title": "CBN Prudential Return Q4 2025",
        "department": "Legal/Regulatory",
        "content": """CBN Prudential Return Q4 2025

CENTRAL BANK OF NIGERIA — QUARTERLY PRUDENTIAL RETURN

Document Reference: REG/CBN/PRU/2025-Q4
Institution: African Fintech Platform Microfinance Bank Limited (National MFB)
Reporting Period: 1 October – 31 December 2025
Submission Date: 28 January 2026
Prepared By: Finance and Regulatory Reporting
Regulatory Basis: CBN Revised Regulatory and Supervisory Guidelines for
  Microfinance Banks 2022; BOFIA 2020

CAPITAL ADEQUACY

Minimum regulatory requirement (national MFB): 10% of risk-weighted assets
Reported Capital Adequacy Ratio (CAR): 14.2%
Prior quarter (Q3 2025) CAR: 15.8%
Shareholders' funds unimpaired by losses: NGN 6,420,000,000
Total risk-weighted assets: NGN 45,210,000,000
Minimum paid-up capital requirement (national MFB): NGN 5,000,000,000
Paid-up capital: NGN 5,000,000,000 — COMPLIANT

CAR remains above the 10% regulatory minimum with a 4.2 percentage point buffer.
The 1.6 point quarter-on-quarter decline is driven by 18% growth in the loan book
without a matching capital injection. On the current trajectory CAR is projected
at 12.4% by Q2 2026 and 10.9% by Q4 2026, which would leave less than a
1 percentage point buffer. Management action is required during 2026.

LIQUIDITY

Minimum regulatory liquidity ratio (MFB): 20%
Reported liquidity ratio (bank-wide): 27.3%
Prior quarter: 31.1%

BRANCH-LEVEL LIQUIDITY POSITION

The following branches reported liquidity below the 20% regulatory minimum at
quarter end and are the subject of a remediation directive from Treasury:

Aba branch: 17.8% — BELOW MINIMUM
Onitsha branch: 18.4% — BELOW MINIMUM
Kano branch: 19.1% — BELOW MINIMUM
Ibadan branch: 21.2% — compliant, on watch
Lagos Island branch: 24.6% — compliant
Abuja Central branch: 29.8% — compliant
Port Harcourt branch: 33.2% — compliant

Three branches are below the CBN minimum. Branch-level shortfalls do not breach
the bank-wide ratio but are reportable and attract supervisory attention where
they persist across two consecutive quarters. Aba and Onitsha were also below
minimum in Q3 2025, making this a second consecutive quarter and therefore a
reportable persistent breach requiring a written remediation plan to the CBN.

ASSET QUALITY

Portfolio at Risk (PAR 30): 6.8% (regulatory guidance: not more than 5%)
Non-performing loan ratio: 5.9% (prior quarter 4.4%)
Loan loss provision coverage: 82%
Total gross loans: NGN 38,900,000,000
Write-offs in the quarter: NGN 412,000,000

PAR 30 exceeds the 5% supervisory guidance for the second consecutive quarter.

SUBMISSION STATUS AND PENALTIES

Q4 2025 return: submitted 28 January 2026, within the 30-day deadline — ON TIME
Q1 2026 return: due 30 April 2026. Current readiness assessed at 70%; branch
  liquidity remediation plans and the updated PAR 30 analysis are outstanding.
  Regulatory reporting has flagged a delay risk if branch data is not received
  by 15 April 2026.

Late or inaccurate submission of prudential returns attracts a penalty under the
CBN Guidelines of NGN 50,000 per day for each day the return is outstanding, plus
potential sanction of the Managing Director and the Chief Compliance Officer for
persistent default. Rendition of false or misleading returns is an offence under
BOFIA 2020 carrying materially higher penalties.
""",
    },
    {
        "id": "doc_005",
        "title": "NDPA Article 24 Processing Record",
        "department": "Legal/Regulatory",
        "content": """NDPA Article 24 Processing Record

DATA PROTECTION PROCESSING RECORD
NIGERIA DATA PROTECTION ACT 2023 — SECTION 24 COMPLIANCE

Document Reference: DPO/ROPA/2026-001
Data Controller: African Fintech Platform Microfinance Bank Limited
Data Protection Officer: Ifeoma Adeyemi (appointed under NDPA section 29)
Last Reviewed: 10 January 2026
Next Review Due: 10 July 2026 (semi-annual)
Regulatory Basis: Nigeria Data Protection Act 2023; NDPC; former NDPR

PROCESSING ACTIVITY 1 — CUSTOMER ONBOARDING AND KYC

Purpose: Identity verification, KYC/CDD, account opening, regulatory reporting
Categories of data subject: Prospective and existing customers, loan guarantors
Categories of personal data: Full name, date of birth, residential address,
  phone number, email, Bank Verification Number (BVN), National Identification
  Number (NIN), photograph, signature specimen, means of identification
Special category data: Biometric data (fingerprint, facial image) — NDPA section 30
Lawful basis: Legal obligation (NDPA s25(1)(c)) — CBN AML/CFT/CPF Regulations 2022
  and BOFIA 2020 mandate customer due diligence. Consent is NOT relied upon for
  KYC, as the processing is legally required.
Retention: 5 years after the end of the customer relationship, per CBN AML/CFT
  record-keeping requirements
Recipients: NIBSS (BVN validation), NIMC (NIN validation), credit bureaux, NFIU,
  CBN, external auditors
Hosting location: Primary data centre Lagos, Nigeria. DR site Lagos, Nigeria.

PROCESSING ACTIVITY 2 — LOAN ORIGINATION AND CREDIT SCORING

Purpose: Creditworthiness assessment, loan decisioning, portfolio monitoring
Categories of personal data: Income data, employment details, bank statement
  transaction history, credit bureau records, device and behavioural telemetry
Lawful basis: Performance of a contract (NDPA s25(1)(b)) and legitimate interest
  for fraud prevention (s25(1)(f))
Automated decision-making: YES. The lending pipeline applies an automated credit
  score that can decline an application without human review.
  NDPA section 32 obligations apply: data subjects must be informed that an
  automated decision is being made, be given meaningful information about the
  logic involved, and have the right to request human review.
  STATUS: The customer-facing notice was updated on 8 January 2026 to disclose
  automated decisioning. The human-review request workflow is IMPLEMENTED but
  the average turnaround is 9 working days against a 5-day internal target —
  flagged as a medium audit finding.
Retention: 7 years after loan closure
Hosting location: Lagos, Nigeria

PROCESSING ACTIVITY 3 — TRANSACTION MONITORING AND AML SCREENING

Purpose: Detection of suspicious transactions, sanctions and PEP screening
Categories of personal data: Transaction records, counterparty details, device
  and location data, sanctions and PEP match results
Lawful basis: Legal obligation (NDPA s25(1)(c)) — CBN AML/CFT/CPF Regulations 2022
Recipients: NFIU (SAR/STR/CTR filings), CBN
Retention: 5 years from the date of the transaction or the end of the
  relationship, whichever is later
Hosting location: Lagos, Nigeria

CROSS-BORDER TRANSFER POSITION — NDPA SECTION 41

The Bank's standing position is that customer KYC data, BVN, NIN, and biometric
records are hosted exclusively within Nigeria.

NDPA section 41 permits transfer of personal data outside Nigeria only where one
of the following applies: the recipient country is subject to a law or binding
instrument affording an adequate level of protection; the transfer is covered by
appropriate safeguards such as binding corporate rules or standard contractual
clauses; or a specific derogation applies (explicit informed consent, contractual
necessity, vital interests, public interest, or legal claims).

The NDPC has not issued an adequacy determination in respect of the United States.
A transfer of Nigerian customer KYC or biometric data to a United States cloud
region would therefore require documented appropriate safeguards and a completed
transfer impact assessment, and could not proceed on adequacy alone. Biometric
data attracts the heightened protections of section 30 for sensitive personal data.

OPEN FINDING: The 2026 lending pipeline expansion proposes using a machine
learning feature store hosted in a United States region. The DPO has issued a
HOLD pending (a) a completed Data Protection Impact Assessment under section 28,
(b) executed standard contractual clauses with the processor, and (c) a
documented transfer impact assessment. As at 10 January 2026 none of the three
is complete. Proceeding without them would place the Bank in breach of section 41.

BREACH NOTIFICATION — NDPA SECTION 34

Personal data breaches likely to result in a risk to the rights and freedoms of
data subjects must be notified to the NDPC within 72 hours of becoming aware.
Where the risk is high, affected data subjects must also be notified without
undue delay.
Breaches recorded in the period: 1 (see below)
NDPC notifications made: 0

The loan portal outage of 14 February 2026 was assessed by the DPO and determined
NOT to be a personal data breach: no unauthorised access, disclosure, alteration,
or loss of personal data occurred. It was an availability incident affecting
service only. Assessment documented 15 February 2026.

DPIA REGISTER — NDPA SECTION 28

DPIA completed: Customer onboarding and BVN/NIN verification (March 2025)
DPIA completed: Transaction monitoring and sanctions screening (June 2025)
DPIA OUTSTANDING: Automated credit decisioning (required — high risk automated
  processing with legal or similarly significant effect). Target date 31 March 2026.
DPIA OUTSTANDING: US-hosted ML feature store (blocking the pipeline expansion).

AUDIT RISK SUMMARY

Two outstanding DPIAs, one of which blocks a planned 2026 initiative, and a
human-review turnaround exceeding internal targets. NDPA penalties for a data
controller of major importance reach the higher of NGN 10,000,000 or 2% of annual
gross revenue in the preceding financial year. On FY2025 gross revenue the 2%
measure would be approximately NGN 214,000,000.
""",
    },
    {
        "id": "doc_006",
        "title": "Core Banking Migration Programme Plan 2026",
        "department": "Technology Programme",
        "content": """Core Banking Migration Programme Plan 2026

PROGRAMME STATUS REPORT

Document Reference: PMO/CBM/2026-003
Programme: Migration from legacy core banking to Meridian Core v9
Report Date: 31 March 2026
Programme Director: Tunde Balogun
Status: AMBER — schedule risk on two critical-path workstreams

EXECUTIVE SUMMARY

The programme is 62% complete against a plan that assumed 71% by end of Q1 2026.
Go-live remains scheduled for 30 September 2026 but the critical path has eroded
from 6 weeks of float to 9 days. Two workstreams — data migration and payment
switch integration — are driving the slippage.

The programme board has been asked to approve either a 6-week go-live deferral to
15 November 2026, or additional vendor resource of NGN 96,000,000 to recover the
schedule while holding the September date.

WORKSTREAM STATUS

Infrastructure provisioning: COMPLETE (100%)
Core module configuration: ON TRACK (84%)
Data migration: AT RISK (48% against 70% planned)
Payment switch integration: AT RISK (39% against 65% planned)
Regulatory reporting rebuild: ON TRACK (72%)
User acceptance testing: NOT STARTED (planned start 15 June 2026)
Parallel run: NOT STARTED (planned 1 August – 15 September 2026)
Staff training: ON TRACK (58%)

DATA MIGRATION — SCHEDULE RISK

Migration of 2.4 million customer records and 11 years of transaction history is
behind plan. Three extraction cycles have completed; reconciliation on cycle 3
identified 41,200 records (1.7%) with data quality exceptions, principally
missing or malformed NIN values on accounts opened before 2019.

Under the CBN AML/CFT/CPF Regulations 2022 the Bank cannot migrate customer
records into the new platform with incomplete CDD data and continue to operate
those accounts unrestricted. The remediation options are to complete a
re-verification exercise on the affected 41,200 customers before go-live, or to
migrate the accounts in a restricted state pending re-verification.

Compliance has advised that migrating with incomplete CDD and leaving accounts
unrestricted would constitute a CDD failing and is not acceptable. The
re-verification exercise is estimated at 10 weeks and has not been funded.

PAYMENT SWITCH INTEGRATION — SCHEDULE AND CONTRACT RISK

The payment switch integration schedule (Schedule 3 of the core banking vendor
agreement) expires 30 April 2026, before the integration work completes. The
schedule must be extended or renewed to cover the migration period. Procurement
review for this schedule is overdue as of 1 February 2026.

Failure to renew before 30 April 2026 would suspend integration support during
the most schedule-critical phase of the programme.

REGULATORY CONSIDERATIONS

1. The CBN requires prior notification of a core banking system change of this
   scale. Notification was filed 12 January 2026; CBN acknowledgement received
   2 February 2026 with a request for the parallel run results before go-live.
2. Regulatory reporting must produce prudential returns from the new platform
   with results identical to the legacy platform for at least one full quarter of
   parallel running. The current plan provides six weeks of parallel run, which is
   less than one full quarter — this is a known gap and the CBN has asked for the
   results. Extending parallel running to a full quarter would itself require the
   November go-live date.
3. All customer data remains hosted in Nigeria throughout the migration. No
   migration data is processed outside Nigeria; the vendor's offshore support
   teams access only anonymised defect reproductions, per Clause 14.7 of the
   master agreement.

DELAY RISK ASSESSMENT

Probability of missing the 30 September 2026 go-live without intervention: HIGH (75%)
Principal drivers: data quality remediation on 41,200 records (unfunded, 10 weeks),
  payment switch schedule expiry (30 April 2026), and a parallel run period shorter
  than the CBN has indicated it expects.

RECOMMENDATION

The programme board is recommended to approve the deferral to 15 November 2026.
This accommodates the CDD re-verification exercise, allows a full-quarter parallel
run consistent with the CBN's stated expectation, and removes the need for
NGN 96,000,000 of schedule-recovery resource.
""",
    },
    {
        "id": "doc_007",
        "title": "AML CFT Quarterly Return and SAR Register Q1 2026",
        "department": "Compliance",
        "content": """AML CFT Quarterly Return and SAR Register Q1 2026

ANTI-MONEY LAUNDERING AND COUNTER-FINANCING OF TERRORISM
QUARTERLY REGULATORY RETURN

Document Reference: COMP/AML/2026-Q1
Institution: African Fintech Platform Microfinance Bank Limited
Reporting Period: 1 January – 31 March 2026
Chief Compliance Officer: Ngozi Eze
Regulatory Basis: CBN (AML/CFT/CPF) Regulations 2022; Money Laundering
  (Prevention and Prohibition) Act 2022; NFIU reporting obligations

EXECUTIVE SUMMARY

Transaction monitoring generated 4,118 alerts in the quarter, of which 612 were
escalated to investigation and 147 resulted in a Suspicious Transaction Report
filed with the NFIU. Currency Transaction Reports totalling 2,904 were filed.

The Bank met the NFIU filing deadline on 141 of 147 STRs. Six STRs were filed
outside the required window and are disclosed below as a self-reported breach.

SUSPICIOUS TRANSACTION REPORTING

Alerts generated: 4,118
Alerts closed as false positive: 3,506 (85.1%)
Escalated to investigation: 612
STRs filed with the NFIU: 147
STRs filed within the required timeline: 141 (95.9%)
STRs filed LATE: 6 — see breach disclosure below
Investigations open at quarter end: 38
Average investigation cycle time: 6.2 days (internal target 5 days)

STR FILINGS BY TYPICAL TYPOLOGY

Structuring / smurfing across agent network: 41
Rapid movement of funds inconsistent with customer profile: 33
Loan account used as a pass-through: 26
Suspected account takeover and mule activity: 22
PEP-related transactions lacking economic rationale: 14
Sanctions near-match escalations: 11

CURRENCY TRANSACTION REPORTS

CTRs filed: 2,904
Reporting thresholds applied: NGN 5,000,000 for individuals and NGN 10,000,000
  for body corporates, per the Money Laundering (Prevention and Prohibition)
  Act 2022
CTRs filed within timeline: 2,904 (100%)

BREACH DISCLOSURE — SIX LATE STR FILINGS

Six STRs relating to a single connected group of agent accounts were filed
between 4 and 9 days after the determination of suspicion, against the
requirement to report promptly and in any event within the timeline set by the
NFIU. The delay arose because the analyst assigned to the case left the
institution on 12 February 2026 and the cases were not reassigned; the gap was
detected during the monthly quality assurance review on 2 March 2026.

Root cause: no automated reassignment of open investigations on analyst
offboarding. Remediation: automated reassignment implemented 20 March 2026;
weekly ageing report on open investigations introduced 23 March 2026.

Self-disclosure to the NFIU was made on 6 March 2026.

PENALTY EXPOSURE

Failure to file a suspicious transaction report within the required timeline is a
contravention of the CBN (AML/CFT/CPF) Regulations 2022 and the Money Laundering
(Prevention and Prohibition) Act 2022. Sanctions available to the CBN include
monetary penalties on the institution, penalties on the principal officers
responsible, and in cases of persistent or systemic default, directives affecting
the institution's licence.

Late rendition of the AML/CFT quarterly return itself attracts a penalty under the
CBN Guidelines of NGN 50,000 per day for each day the return remains outstanding,
alongside possible sanction of the Chief Compliance Officer for persistent default.

The Q1 2026 return is due 30 April 2026. Current readiness: 92%. Outstanding items
are the sanctions screening coverage statistics and the final training completion
figures. No delay is currently forecast.

CUSTOMER DUE DILIGENCE

New customers onboarded in the quarter: 84,200
Enhanced due diligence applied (PEP, high risk): 3,940
Onboarding declined on CDD grounds: 1,214
Existing customers with incomplete CDD data: 41,200 — these are the pre-2019
  accounts with missing or malformed NIN values identified by the core banking
  migration data quality review. A re-verification exercise is required before
  these accounts can be migrated and operated unrestricted.

SANCTIONS SCREENING

Screening coverage: 100% of customers at onboarding and on every transaction
Lists applied: UN Consolidated List, Nigerian Sanctions List, OFAC, EU, UK HMT
Screening frequency for existing customers: daily delta screening
True matches confirmed in the quarter: 2 (both accounts frozen and reported)

TRAINING

Staff completing annual AML/CFT training: 1,284 of 1,340 (95.8%)
Board and senior management training completed: 100%
Target: 100% of staff by 30 June 2026
""",
    },
    {
        "id": "doc_008",
        "title": "Corporate Credit Exposure and Single Obligor Register",
        "department": "Credit Risk",
        "content": """Corporate Credit Exposure and Single Obligor Register

CREDIT CONCENTRATION AND SINGLE-OBLIGOR COMPLIANCE REGISTER

Document Reference: CR/SOL/2026-Q1
Institution: African Fintech Platform Microfinance Bank Limited (National MFB)
Position Date: 31 March 2026
Prepared By: Chidi Okonkwo, Head of Credit Risk
Regulatory Basis: CBN Revised Regulatory and Supervisory Guidelines for
  Microfinance Banks 2022; BOFIA 2020

SINGLE-OBLIGOR LIMIT

Shareholders' funds unimpaired by losses: NGN 6,420,000,000
Regulatory single-obligor limit for a national MFB: 1% of shareholders' funds
Maximum permitted exposure to a single obligor: NGN 64,200,000
Aggregate large-exposure ceiling: not more than 8x shareholders' funds

TOP TEN OBLIGOR EXPOSURES

1. Sahel Agro Processing Limited — NGN 71,400,000 — 1.11% — IN BREACH
2. Lagos Logistics Consolidated — NGN 63,900,000 — 0.99% — within limit, on watch
3. Delta Retail Distributors — NGN 61,200,000 — 0.95% — within limit, on watch
4. Kano Textiles Cooperative — NGN 58,600,000 — 0.91% — within limit
5. Enugu Medical Supplies Limited — NGN 54,100,000 — 0.84% — within limit
6. Rivers Marine Services — NGN 49,800,000 — 0.78% — within limit
7. Abuja Property Holdings — NGN 47,300,000 — 0.74% — within limit
8. Ibadan Foods Limited — NGN 44,900,000 — 0.70% — within limit
9. Jos Mining Supplies — NGN 41,600,000 — 0.65% — within limit
10. Warri Energy Services — NGN 38,200,000 — 0.60% — within limit

Aggregate top-ten exposure: NGN 531,000,000 (8.27% of shareholders' funds)

ACTIVE BREACH — SAHEL AGRO PROCESSING LIMITED

Exposure of NGN 71,400,000 exceeds the NGN 64,200,000 single-obligor limit by
NGN 7,200,000, equivalent to 11.2% above the permitted ceiling.

The breach arose on 18 March 2026 when a previously approved NGN 12,000,000
seasonal facility was drawn without the credit committee re-testing aggregate
exposure, which already included a NGN 59,400,000 term loan. The limit check in
the origination system tests facility-level rather than obligor-level exposure —
the same control gap identified in the 2025 internal audit (finding CR-2025-04,
still open).

Regulatory consequence: a breach of the single-obligor limit is a contravention
of the CBN MFB Guidelines and BOFIA 2020. It is reportable to the CBN in the
prudential return for the period in which it occurs. Available sanctions include
monetary penalty, a directive to regularise within a specified period, and
sanction of the approving officers. Where a breach is not regularised, the CBN may
require the excess to be deducted from capital, which on the current position
would reduce CAR by approximately 0.11 percentage points.

Remediation: the Bank has obtained a commitment from the obligor to repay
NGN 9,000,000 by 30 April 2026, which would return exposure to NGN 62,400,000
(0.97%) and restore compliance. The breach will be disclosed in the Q1 2026
prudential return due 30 April 2026.

CONCENTRATION BY SECTOR

Agriculture and agro-processing: NGN 8,940,000,000 (23.0% of gross loans)
Trade and distribution: NGN 7,780,000,000 (20.0%)
Manufacturing: NGN 5,835,000,000 (15.0%)
Transport and logistics: NGN 4,668,000,000 (12.0%)
Services: NGN 4,279,000,000 (11.0%)
Construction and real estate: NGN 3,501,000,000 (9.0%)
Consumer and salary-backed: NGN 3,112,000,000 (8.0%)
Other: NGN 785,000,000 (2.0%)

Agriculture and agro-processing at 23.0% exceeds the internal sector
concentration appetite of 20%. The concentration is seasonally correlated: a
poor harvest or an FX shock affecting input costs would stress this sector
simultaneously, and it contains the single obligor currently in breach.

GEOGRAPHIC CONCENTRATION

South West: 34.0%
South East: 22.0%
North West: 18.0%
South South: 14.0%
North Central: 9.0%
North East: 3.0%

WATCH LIST AND ASSET QUALITY

Obligors on the credit watch list: 23, aggregate exposure NGN 1,284,000,000
Portfolio at Risk (PAR 30): 6.8% against the 5% supervisory guidance
Non-performing loan ratio: 5.9%
Provision coverage: 82%

CONTROL FINDINGS

1. OPEN (CR-2025-04): origination system tests facility-level rather than
   obligor-level exposure. Directly caused the Sahel Agro breach. Fix scheduled
   into the core banking migration; interim manual aggregate check introduced
   20 March 2026.
2. OPEN: no automated alert when an obligor reaches 90% of the single-obligor
   limit. Two obligors currently sit above 95% with no systemic warning.
3. CLOSED: quarterly credit committee review of all exposures above 0.75% of
   shareholders' funds — implemented 15 January 2026.
""",
    },
]


async def index_all():
    from services.document_processor import smart_chunk_document
    from services.azure_search import index_document_chunks, get_search_client

    print("\nIroko AI -- Seed Azure Search Index")
    print("=" * 45)

    # Chunk ids are f"{doc_id}_chunk_{n}", so a rewrite with fewer chunks than the
    # previous run would leave the tail chunks behind holding stale content.
    _purge_existing({d["id"] for d in DOCUMENTS}, get_search_client())

    total_chunks = 0
    for doc in DOCUMENTS:
        chunks = smart_chunk_document(
            text=doc["content"],
            document_id=doc["id"],
            title=doc["title"],
            department=doc["department"],
        )

        created_at = datetime.now().strftime("%Y-%m-%dT%H:%M:%SZ")
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


def _purge_existing(doc_ids: set, client) -> None:
    """Delete every existing chunk belonging to the documents we are about to seed."""
    if client is None:
        return
    stale = []
    for doc_id in sorted(doc_ids):
        try:
            hits = client.search(
                search_text="*",
                filter=f"doc_id eq '{doc_id}'",
                select=["id"],
                top=1000,
            )
            stale.extend({"id": h["id"]} for h in hits)
        except Exception as exc:
            print(f"  [warn] could not list existing chunks for {doc_id}: {exc}")
    if stale:
        client.delete_documents(documents=stale)
        print(f"  [purged] {len(stale)} existing chunks for {len(doc_ids)} documents")


if __name__ == "__main__":
    asyncio.run(index_all())
