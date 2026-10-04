"""
services/regulatory_returns/catalog.py

The regulatory returns a Nigerian microfinance bank renders, as Iroko generates
them. Each entry records the legal basis, deadline rule, recipient and the
inputs the generator needs, so the API, the calendar and the documents all read
from one definition.

Sources (researched October 2026):
  * CBN letter to MFBs/PMBs/DFIs on monthly FinA rendition (March 2024): due on
    or before the 5th day after month end; previous working day if the 5th is a
    weekend/public holiday; BOFIA 2020 s.24.
  * Revised Regulatory and Supervisory Guidelines for MFBs (2020), s.5.3 —
    monthly returns; categories and minimum capital (s.3, s.4.2.7).
  * Code of Corporate Governance for MFBs (CBN, Oct 2018, effective 1 Apr 2019):
    s.2.2–2.6 board rules, s.5.2.15 MD/CEO certification, s.5.3.3 whistle-
    blowing returns (semi-annual, 7 days), s.8.2 governance returns
    (semi-annual, 2 weeks), s.2.8.2 board appraisal (31 March).
  * Money Laundering (Prevention and Prohibition) Act 2022: s.7(2) STR within
    24 hours; s.11(1) CTR within 7 days above N5m (individual) / N10m (body
    corporate); s.8 five-year record keeping; s.19(1)(a) tipping-off offence.
  * NDIC Act 2023 s.17: deposit liabilities as at 31 December certified by the
    approved auditor, forwarded by 31 January; premium capped at 8/16 of 1%
    for deposit-taking OFIs.
  * Nigeria Data Protection Act 2023 + GAID 2025: annual Data Protection
    Compliance Audit Return by 31 March, filed through a licensed DPCO
    (2025 returns extended to 30 May 2026).
  * BOFIA / MFB guidelines: audited financial statements to the CBN for
    approval within four months of the financial year end.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

# ─── Form schema ──────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class Field:
    key: str
    label: str
    type: str  # text | textarea | date | number | money | select | multiselect | bool | table
    required: bool = False
    options: tuple[str, ...] = ()
    help: str = ""
    columns: tuple["Field", ...] = ()


def _f(key: str, label: str, type: str = "text", **kw: Any) -> Field:
    return Field(key=key, label=label, type=type, **kw)


LICENCE_CATEGORIES: dict[str, str] = {
    "unit_tier1": "Unit Microfinance Bank (Tier 1)",
    "unit_tier2": "Unit Microfinance Bank (Tier 2)",
    "state": "State Microfinance Bank",
    "national": "National Microfinance Bank",
}

# Minimum capital by licence category — Revised Regulatory and Supervisory
# Guidelines for MFBs (2020), s.4.2.7 (final thresholds after the phased dates).
MINIMUM_CAPITAL: dict[str, float] = {
    "unit_tier1": 200_000_000,
    "unit_tier2": 50_000_000,
    "state": 1_000_000_000,
    "national": 5_000_000_000,
}

# Institution particulars shared by every return. The frontend keeps these as
# the bank's profile so they are entered once.
PROFILE_FIELDS: tuple[Field, ...] = (
    _f("institution_name", "Institution name", required=True, help="As on the CBN licence, e.g. Acme Microfinance Bank Limited"),
    _f("licence_category", "Licence category", "select", required=True, options=tuple(LICENCE_CATEGORIES)),
    _f("cbn_licence_no", "CBN licence number"),
    _f("rc_number", "RC number"),
    _f("head_office_address", "Head office address", "textarea", required=True),
    _f("md_ceo_name", "MD/CEO name", required=True),
    _f("cco_name", "Chief Compliance Officer name", required=True),
    _f("cfo_name", "Head of Finance / CFO name"),
    _f("contact_email", "Official email"),
    _f("contact_phone", "Official phone"),
)

_BOARD_COLUMNS = (
    _f("name", "Director name", required=True),
    _f("role", "Role", "select", required=True, options=("Chairman", "MD/CEO", "Executive Director", "Non-Executive Director", "Independent Non-Executive Director")),
    _f("first_appointed", "First appointed", "date", required=True),
    _f("cbn_approved", "CBN approval received", "bool"),
    _f("board_meetings_held", "Board meetings held (while in office)", "number", required=True),
    _f("board_meetings_attended", "Board meetings attended", "number", required=True),
    _f("committees", "Committees (comma-separated)", help="e.g. Audit, Credit"),
)

_COMMITTEE_COLUMNS = (
    _f("name", "Committee", "select", required=True, options=("Board Risk Management Committee", "Board Audit Committee", "Board Risk & Audit Committee (combined)", "Board Governance & Nominations Committee", "Board Credit Committee", "Board Remuneration Committee")),
    _f("chair", "Chaired by", required=True),
    _f("chair_role", "Chair's role", "select", required=True, options=("Non-Executive Director", "Independent Non-Executive Director", "Executive Director", "MD/CEO", "Chairman")),
    _f("members", "Number of members", "number", required=True),
    _f("meetings_held", "Meetings held in period", "number", required=True),
    _f("charter_cbn_approved", "Charter approved by CBN", "bool"),
)

_FRAUD_COLUMNS = (
    _f("case_ref", "Case reference", required=True),
    _f("date_occurred", "Date occurred", "date", required=True),
    _f("date_discovered", "Date discovered", "date", required=True),
    _f("branch", "Branch / location", required=True),
    _f("category", "Category", "select", required=True, options=("Cash suppression / theft", "Forgery (cheque / document)", "Fraudulent withdrawal", "Card / ATM / POS fraud", "Internet / mobile banking fraud", "Loan fraud", "Account takeover / impersonation", "Insider abuse", "Other")),
    _f("description", "Description", "textarea", required=True),
    _f("amount_involved", "Amount involved (₦)", "money", required=True),
    _f("actual_loss", "Actual loss (₦)", "money", required=True),
    _f("amount_recovered", "Amount recovered (₦)", "money"),
    _f("staff_involved", "Staff involved (name, rank) or 'None'"),
    _f("reported_to_police", "Reported to police", "bool"),
    _f("status", "Status", "select", required=True, options=("Under investigation", "Closed — loss recovered", "Closed — loss written off", "Referred to law enforcement", "In court")),
    _f("action_taken", "Action taken", "textarea", required=True),
)

_STR_TXN_COLUMNS = (
    _f("date", "Date", "date", required=True),
    _f("type", "Type", "select", required=True, options=("Cash deposit", "Cash withdrawal", "Inward transfer", "Outward transfer", "Loan disbursement", "Loan repayment", "Other")),
    _f("amount", "Amount (₦)", "money", required=True),
    _f("counterparty", "Counterparty / source or destination"),
    _f("channel", "Channel / branch"),
    _f("narration", "Narration"),
)

# Due-rule kinds understood by calendar.py:
#   monthly_fina      — 5th day after month end, rolled back to a working day
#   semiannual_offset — `offset_days` after 30 June / 31 December
#   annual_fixed      — fixed `month`/`day` each year (for the prior year)
#   fy_offset_months  — `months` after the financial year end
#   event             — triggered by a transaction / incident


@dataclass(frozen=True)
class ReturnSpec:
    id: str
    title: str
    short_title: str
    regulator: str
    recipient: tuple[str, ...]
    cc: tuple[str, ...]
    channel: str
    frequency: str
    period_type: str  # month | half_year | year | event
    due_rule: dict[str, Any]
    due_text: str
    legal_basis: tuple[str, ...]
    sources: tuple[str, ...]
    summary: str
    outputs: tuple[str, ...]
    fields: tuple[Field, ...] = ()
    upload: str | None = None  # template id when the return needs a data upload
    generator: bool = True
    submission_notes: tuple[str, ...] = ()
    verification_notes: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


_CBN_OFISD = (
    "The Director",
    "Other Financial Institutions Supervision Department",
    "Central Bank of Nigeria",
    "Plot 33, Abubakar Tafawa Balewa Way, Central Business District",
    "Abuja",
)
_NDIC_SIID = (
    "The Director, Special Insured Institutions Department, Nigeria Deposit Insurance Corporation, Abuja",
)

RETURNS: tuple[ReturnSpec, ...] = (
    ReturnSpec(
        id="cbn-monthly-prudential",
        title="Monthly Prudential Returns (MMFBR 300, MMFBR 1000 and prudential schedules)",
        short_title="Monthly prudential returns",
        regulator="CBN",
        recipient=_CBN_OFISD,
        cc=_NDIC_SIID,
        channel="CBN FinA application (data); covering letter and certification to OFISD",
        frequency="Monthly",
        period_type="month",
        due_rule={"kind": "monthly_fina"},
        due_text="On or before the 5th day after month end; if the 5th is a weekend or public holiday, the previous working day.",
        legal_basis=(
            "Banks and Other Financial Institutions Act 2020, s.24",
            "Revised Regulatory and Supervisory Guidelines for MFBs (2020), s.5.3",
            "CBN letter to MFBs, PMBs and DFIs on monthly FinA rendition (March 2024)",
            "Code of Corporate Governance for MFBs (2018), s.5.2.15 (MD/CEO certification)",
        ),
        sources=(
            "https://www.cbn.gov.ng/supervision/mfbreturns.html",
            "https://nairametrics.com/2024/03/07/cbn-mandates-microfinance-mortgage-banks-and-dfis-to-submit-financial-returns-monthly-or-risk-sanctions/",
        ),
        summary="Statement of financial position (MMFBR 300), year-to-date profit or loss (MMFBR 1000), capital adequacy, liquidity, fixed-asset and minimum-capital tests, loan classification and provisioning, single-obligor and insider exposures, with MD/CEO certification.",
        outputs=("Covering letter, schedules and certification (.docx)", "Schedules workbook for FinA keying (.xlsx)"),
        upload="prudential",
        fields=(
            _f("risk_weighted_assets_override", "Risk-weighted assets override (₦)", "money", help="Leave blank to use Iroko's risk weights (0% cash/CBN/FGN securities, 20% bank balances and placements, 100% other assets). Enter your FinA figure to use it instead."),
            _f("qualifying_capital_override", "Qualifying capital override (₦)", "money", help="Leave blank to use total equity less intangible assets."),
        ),
        submission_notes=(
            "Key the MMFBR figures into the FinA master template (sheet names follow the form numbers, e.g. 300, 1000). The .xlsx schedule mirrors those figures for keying and reconciliation.",
            "MMFBR 1000 is cumulative for the financial year to date, not the current month alone.",
            "If a technical problem prevents rendition, email the CBN before the deadline with evidence of the problem.",
        ),
        verification_notes=(
            "Iroko's line items follow the MMFBR 300/1000 structure; align line codes with the current FinA master template before keying.",
            "Single-obligor (1% individual / 5% group, cooperative or corporate) and insider-lending (5% aggregate) limits are as published in the MFB guidelines; confirm against any later CBN circular.",
        ),
    ),
    ReturnSpec(
        id="cbn-fraud-forgeries",
        title="Monthly Return on Frauds and Forgeries",
        short_title="Frauds & forgeries return",
        regulator="CBN",
        recipient=_CBN_OFISD,
        cc=_NDIC_SIID,
        channel="With the monthly returns (FinA) and by letter to OFISD",
        frequency="Monthly",
        period_type="month",
        due_rule={"kind": "monthly_fina"},
        due_text="With the monthly returns — on or before the 5th day after month end. A nil return is rendered where there was no incident.",
        legal_basis=(
            "Revised Regulatory and Supervisory Guidelines for MFBs (2020), s.5.3 (monthly returns include frauds and forgeries)",
            "CBN OFID circular on rendition of returns by MFBs (2008)",
        ),
        sources=("https://cbn.gov.ng/OUT/CIRCULARS/OFID/2008/OFID-01-2008.PDF",),
        summary="Every fraud and forgery case discovered in the month — amount involved, actual loss, recoveries, staff involvement and action taken — or a nil return.",
        outputs=("Return letter with case schedule (.docx)", "Case schedule (.xlsx)"),
        fields=(
            _f("nil_return", "Nil return — no fraud or forgery in the month", "bool"),
            _f("incidents", "Fraud and forgery cases", "table", columns=_FRAUD_COLUMNS),
        ),
    ),
    ReturnSpec(
        id="cbn-cg-compliance",
        title="Semi-annual Return on Compliance with the Code of Corporate Governance",
        short_title="Corporate governance return",
        regulator="CBN",
        recipient=_CBN_OFISD,
        cc=(),
        channel="Letter to the Director, OFISD",
        frequency="Semi-annual (30 June and 31 December)",
        period_type="half_year",
        due_rule={"kind": "semiannual_offset", "offset_days": 14},
        due_text="Not later than 2 weeks after 30 June and 31 December (14 July and 14 January).",
        legal_basis=(
            "Code of Corporate Governance for MFBs in Nigeria (2018), s.8.2",
            "Code of Corporate Governance for MFBs in Nigeria (2018), ss.2.2–2.6, 5.2",
        ),
        sources=("https://corpgovnigeria.org/wp-content/uploads/2024/06/CODE-OF-CORPORATE-GOVERNANCE-FOR-MICROFINANCE-BANKS-IN-NIGERIA.pdf",),
        summary="Board size and mix, independent directors, separation of Chairman and MD/CEO, tenure limits, required committees and their chairs, quarterly meetings and attendance, with a requirement-by-requirement compliance matrix.",
        outputs=("Return letter with compliance matrix (.docx)", "Board and committee schedule (.xlsx)"),
        fields=(
            _f("board", "Board of directors", "table", required=True, columns=_BOARD_COLUMNS),
            _f("committees", "Board committees", "table", required=True, columns=_COMMITTEE_COLUMNS),
            _f("board_meetings_in_period", "Board meetings held in the half-year", "number", required=True),
            _f("external_auditor", "External auditor (firm)", required=True),
            _f("external_auditor_cbn_approved", "External auditor appointment approved by CBN", "bool"),
            _f("risk_officer_in_place", "Risk Officer in place, reporting to the risk committee", "bool"),
            _f("internal_auditor_in_place", "Internal Auditor in place, reporting to the audit committee", "bool"),
            _f("board_appraisal_date", "Date last annual board appraisal report was forwarded to CBN", "date"),
            _f("family_members_on_board", "More than two members of one family on the board", "bool"),
            _f("other_disclosures", "Other matters to disclose", "textarea"),
        ),
    ),
    ReturnSpec(
        id="cbn-whistleblowing",
        title="Semi-annual Return on Compliance with the Whistle-blowing Policy",
        short_title="Whistle-blowing return",
        regulator="CBN",
        recipient=_CBN_OFISD,
        cc=(),
        channel="Letter to the Director, OFISD",
        frequency="Semi-annual (30 June and 31 December)",
        period_type="half_year",
        due_rule={"kind": "semiannual_offset", "offset_days": 7},
        due_text="Not later than 7 days after 30 June and 31 December (7 July and 7 January).",
        legal_basis=("Code of Corporate Governance for MFBs in Nigeria (2018), s.5.3.3",),
        sources=("https://corpgovnigeria.org/wp-content/uploads/2024/06/CODE-OF-CORPORATE-GOVERNANCE-FOR-MICROFINANCE-BANKS-IN-NIGERIA.pdf",),
        summary="Whistle-blowing policy status, reporting channels, cases received, investigated and closed, and actions taken — or a nil return.",
        outputs=("Return letter (.docx)",),
        fields=(
            _f("policy_approval_date", "Date the Board approved the whistle-blowing policy", "date", required=True),
            _f("policy_on_website", "Policy published on the bank's website", "bool"),
            _f("channels", "Reporting channels", "textarea", required=True, help="e.g. dedicated email, hotline, CBN whistle-blowing portal, suggestion boxes"),
            _f("cases_received", "Cases received in the period", "number", required=True),
            _f("cases_investigated", "Cases investigated", "number", required=True),
            _f("cases_substantiated", "Cases substantiated", "number", required=True),
            _f("cases_closed", "Cases closed", "number", required=True),
            _f("cases_pending", "Cases pending at period end", "number", required=True),
            _f("case_summary", "Nature of cases and actions taken", "textarea"),
            _f("retaliation_complaints", "Complaints of retaliation against whistle-blowers", "number"),
            _f("staff_awareness", "Staff awareness / training in the period", "textarea"),
        ),
    ),
    ReturnSpec(
        id="nfiu-str",
        title="Suspicious Transaction Report (STR)",
        short_title="Suspicious transaction report",
        regulator="NFIU",
        recipient=("The Director/Chief Executive Officer", "Nigerian Financial Intelligence Unit", "Abuja"),
        cc=(),
        channel="NFIU goAML portal",
        frequency="Event-driven",
        period_type="event",
        due_rule={"kind": "event", "hours": 24},
        due_text="Within 24 hours of the transaction.",
        legal_basis=(
            "Money Laundering (Prevention and Prohibition) Act 2022, s.7(1)–(2)",
            "Money Laundering (Prevention and Prohibition) Act 2022, s.19(1)(a) (tipping-off offence)",
            "CBN AML/CFT/CPF Regulations 2022",
        ),
        sources=("https://placng.org/i/wp-content/uploads/2022/05/Money-Laundering-Prevention-and-Prohibition-Act-2022.pdf",),
        summary="Subject, account and transaction particulars, the statutory grounds for suspicion, the reasons in narrative form and the action taken — structured for entry into goAML and retention on file.",
        outputs=("STR report (.docx)",),
        fields=(
            _f("subject_name", "Subject name", required=True),
            _f("subject_type", "Subject type", "select", required=True, options=("Individual", "Body corporate")),
            _f("account_number", "Account number", required=True),
            _f("bvn_or_rc", "BVN / RC number"),
            _f("subject_address", "Address", "textarea"),
            _f("occupation_or_business", "Occupation / nature of business"),
            _f("relationship_start", "Customer since", "date"),
            _f("detection_datetime", "When the transaction was identified as suspicious", "text", required=True, help="Date and time, e.g. 2026-10-02 14:30"),
            _f("transactions", "Transactions", "table", required=True, columns=_STR_TXN_COLUMNS),
            _f("grounds", "Grounds (MLPPA 2022 s.7(1))", "multiselect", required=True, options=(
                "(a) Unjustifiable or unreasonable frequency",
                "(b) Unusual or unjustified complexity",
                "(c) No economic justification or lawful objective",
                "(d) Inconsistent with known pattern of the account",
                "(e) Believed to involve proceeds of crime, money laundering or terrorist financing",
            ), help="Select every ground that applies"),
            _f("reasons", "Reasons for suspicion", "textarea", required=True, help="Facts only: what was observed, why it departs from the customer's profile, what checks were made."),
            _f("action_taken", "Action taken", "textarea", required=True, help="e.g. enhanced due diligence, account placed on watch, funds held pending NFIU guidance"),
            _f("reporting_officer", "Reporting officer (name, designation)", required=True),
        ),
        submission_notes=(
            "Enter the report on goAML within 24 hours of the transaction and keep this document on the STR file.",
            "Do not inform the customer or any third party that a report has been or will be made — tipping off is an offence under s.19(1)(a).",
            "Keep the supporting records for at least five years (s.8).",
        ),
    ),
    ReturnSpec(
        id="nfiu-ctr",
        title="Currency Transaction Report (CTR)",
        short_title="Currency transaction report",
        regulator="NFIU",
        recipient=("The Director/Chief Executive Officer", "Nigerian Financial Intelligence Unit", "Abuja"),
        cc=(),
        channel="NFIU goAML portal",
        frequency="Event-driven (batch weekly to stay within 7 days)",
        period_type="event",
        due_rule={"kind": "event", "days": 7},
        due_text="Within 7 days of any single transaction, lodgment or transfer in excess of ₦5,000,000 (individual) or ₦10,000,000 (body corporate).",
        legal_basis=("Money Laundering (Prevention and Prohibition) Act 2022, s.11(1) and (3)",),
        sources=("https://placng.org/i/wp-content/uploads/2022/05/Money-Laundering-Prevention-and-Prohibition-Act-2022.pdf",),
        summary="Upload the period's transactions; Iroko selects those above the statutory thresholds, flags any already past the 7-day window and produces the CTR schedule and covering memo.",
        outputs=("CTR covering memo (.docx)", "CTR schedule (.xlsx)"),
        upload="ctr",
        fields=(
            _f("period_from", "Transactions from", "date", required=True),
            _f("period_to", "Transactions to", "date", required=True),
            _f("reporting_officer", "Reporting officer (name, designation)", required=True),
        ),
        submission_notes=(
            "File each qualifying transaction on goAML within 7 days. Late filing exposes the bank to a fine of ₦250,000–₦1,000,000 per day (s.11(3)).",
        ),
    ),
    ReturnSpec(
        id="ndic-deposit-certification",
        title="Certified Deposit Liabilities Return (Deposit Insurance Premium Assessment)",
        short_title="NDIC certified deposits return",
        regulator="NDIC",
        recipient=("The Managing Director/Chief Executive", "Nigeria Deposit Insurance Corporation", "Plot 447/448 Constitution Avenue, Central Business District", "Abuja"),
        cc=("The Director, Special Insured Institutions Department, NDIC",),
        channel="Letter to NDIC with the auditor's certificate",
        frequency="Annual",
        period_type="year",
        due_rule={"kind": "annual_fixed", "month": 1, "day": 31},
        due_text="On or before 31 January, for deposit liabilities as at 31 December of the preceding year.",
        legal_basis=("Nigeria Deposit Insurance Corporation Act 2023, s.17",),
        sources=("https://ndic.gov.ng/frequently-asked-questions/",),
        summary="Total deposit liabilities at 31 December, the exclusions allowed by the Act (insider deposits, deposits held as collateral against loans) and the assessable base, for certification by the approved auditor.",
        outputs=("Covering letter and deposit schedule (.docx)",),
        fields=(
            _f("demand_deposits", "Demand deposits at 31 Dec (₦)", "money", required=True),
            _f("savings_deposits", "Savings deposits at 31 Dec (₦)", "money", required=True),
            _f("time_deposits", "Time / term deposits at 31 Dec (₦)", "money", required=True),
            _f("other_deposits", "Other deposits at 31 Dec (₦)", "money"),
            _f("insider_deposits", "Less: insider deposits — staff and directors (₦)", "money", required=True),
            _f("collateral_deposits", "Less: deposits held as collateral against loans (₦)", "money", required=True),
            _f("auditor_name", "Approved auditor (firm)", required=True),
            _f("auditor_certificate_date", "Date of auditor's certificate", "date", required=True),
        ),
        verification_notes=(
            "Premium is shown at the statutory ceiling of 8/16 of 1% for deposit-taking OFIs; the NDIC demand notice determines the amount payable.",
        ),
    ),
    ReturnSpec(
        id="cbn-afs-submission",
        title="Submission of Audited Financial Statements for CBN Approval",
        short_title="Audited accounts submission",
        regulator="CBN",
        recipient=_CBN_OFISD,
        cc=(),
        channel="Letter to the Director, OFISD with the audited and abridged accounts",
        frequency="Annual",
        period_type="year",
        due_rule={"kind": "fy_offset_months", "months": 4},
        due_text="Within four months after the end of the financial year (30 April for a 31 December year end). Do not publish before CBN approval.",
        legal_basis=(
            "Banks and Other Financial Institutions Act 2020 (audited accounts to be approved by the CBN before publication)",
            "Revised Regulatory and Supervisory Guidelines for MFBs (2020)",
        ),
        sources=("https://nairametrics.com/2021/04/08/npf-microfinance-bank-delays-submission-of-2020-audited-financial-statements-to-nse/",),
        summary="Transmittal letter for the audited financial statements and the abridged version, with the enclosures the CBN reviews before approving publication.",
        outputs=("Transmittal letter (.docx)",),
        fields=(
            _f("auditor_name", "External auditor (firm)", required=True),
            _f("audit_report_date", "Date of the auditor's report", "date", required=True),
            _f("board_approval_date", "Date the Board approved the accounts", "date", required=True),
            _f("total_assets", "Total assets per audited accounts (₦)", "money", required=True),
            _f("profit_before_tax", "Profit / (loss) before tax (₦)", "money", required=True),
            _f("shareholders_funds", "Shareholders' funds (₦)", "money", required=True),
            _f("management_letter_enclosed", "Auditor's management letter enclosed", "bool"),
            _f("proposed_dividend", "Proposed dividend (₦, 0 if none)", "money"),
        ),
    ),
    ReturnSpec(
        id="ndpc-compliance-audit",
        title="Annual Data Protection Compliance Audit Return",
        short_title="NDPC compliance audit return",
        regulator="NDPC",
        recipient=("The National Commissioner", "Nigeria Data Protection Commission", "Abuja"),
        cc=(),
        channel="Filed with the NDPC through a licensed Data Protection Compliance Organisation (DPCO)",
        frequency="Annual",
        period_type="year",
        due_rule={"kind": "annual_fixed", "month": 3, "day": 31},
        due_text="By 31 March each year for the preceding calendar year (the NDPC extended the 2025 return to 30 May 2026).",
        legal_basis=(
            "Nigeria Data Protection Act 2023",
            "NDPC General Application and Implementation Directive (GAID) 2025",
        ),
        sources=(
            "https://oal.law/ndpc-extends-2025-data-protection-audit-return-deadline-to-30-may-2026/",
            "https://www.mondaq.com/nigeria/data-protection/1736914/data-protection-compliance-in-nigeria-audit-return-obligations-for-2026",
        ),
        summary="The bank's data-protection position for the year — DPO, processing inventory, lawful bases, DPIAs, breaches and 72-hour notifications, data-subject requests, transfers, processors, security and training — as the evidence pack for the DPCO's audit return.",
        outputs=("Compliance audit report for the DPCO (.docx)",),
        fields=(
            _f("dpco_name", "Licensed DPCO (firm)", required=True),
            _f("dpo_name", "Data Protection Officer", required=True),
            _f("data_subjects", "Approximate number of data subjects", "number", required=True),
            _f("data_categories", "Categories of personal data processed", "textarea", required=True, help="e.g. identity (BVN, NIN), contact, financial, biometric"),
            _f("lawful_bases", "Lawful bases relied on", "textarea", required=True),
            _f("dpias_conducted", "DPIAs conducted in the year", "number", required=True),
            _f("breaches", "Personal data breaches in the year", "number", required=True),
            _f("breaches_notified_72h", "Breaches notified to NDPC within 72 hours", "number", required=True),
            _f("dsr_received", "Data-subject requests received", "number", required=True),
            _f("dsr_resolved", "Data-subject requests resolved", "number", required=True),
            _f("cross_border_transfers", "Cross-border transfers and safeguards", "textarea"),
            _f("processors", "Data processors engaged and contracts in place", "textarea"),
            _f("security_measures", "Technical and organisational security measures", "textarea", required=True),
            _f("training", "Staff data-protection training in the year", "textarea"),
            _f("privacy_policy_url", "Privacy policy URL"),
        ),
        submission_notes=(
            "The return is filed by your licensed DPCO; this report is the bank's evidence pack for that audit.",
            "Late filing attracts a penalty of 50% of the applicable filing fee.",
        ),
    ),
    # Calendar-only obligations — tracked for deadlines, prepared by others.
    ReturnSpec(
        id="cbn-board-appraisal",
        title="Annual Board and Directors' Appraisal Report",
        short_title="Board appraisal report",
        regulator="CBN",
        recipient=_CBN_OFISD,
        cc=(),
        channel="Forwarded to the CBN by the independent consultant",
        frequency="Annual",
        period_type="year",
        due_rule={"kind": "annual_fixed", "month": 3, "day": 31},
        due_text="Not later than 31 March of the following year.",
        legal_basis=("Code of Corporate Governance for MFBs in Nigeria (2018), s.2.8.2",),
        sources=("https://corpgovnigeria.org/wp-content/uploads/2024/06/CODE-OF-CORPORATE-GOVERNANCE-FOR-MICROFINANCE-BANKS-IN-NIGERIA.pdf",),
        summary="Prepared and forwarded by an independent consultant; Iroko tracks the deadline only.",
        outputs=(),
        generator=False,
    ),
)

RETURNS_BY_ID: dict[str, ReturnSpec] = {r.id: r for r in RETURNS}


def catalog_dict() -> list[dict[str, Any]]:
    return [r.to_dict() for r in RETURNS]


def profile_schema() -> list[dict[str, Any]]:
    return [asdict(f) for f in PROFILE_FIELDS]


__all__ = [
    "Field",
    "ReturnSpec",
    "RETURNS",
    "RETURNS_BY_ID",
    "PROFILE_FIELDS",
    "LICENCE_CATEGORIES",
    "MINIMUM_CAPITAL",
    "catalog_dict",
    "profile_schema",
]
