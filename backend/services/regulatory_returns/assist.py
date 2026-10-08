"""
services/regulatory_returns/assist.py

How Iroko gathers each answer before it asks the compliance officer anything.
For every field of every return this records, in order of preference:

  fact      a fact shared across returns (the external auditor is the same on
            the governance return, the NDIC return and the accounts letter)
  carry     start from the previous period's answer — boards, policies and
            officers rarely change between filings
  evidence  a search over the bank's own document library; the answer is only
            accepted with a verbatim quote from a named document
  default   a value Iroko can work out (the CCO as reporting officer, the last
            seven days for a CTR batch)
  ask       otherwise, one plain-English question, with one-click answers
            where the common answer is obvious

Anything Iroko fills is shown with its source and must be confirmed by the
officer before the return is generated.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True)
class Hint:
    ask: str = ""
    carry: bool = False
    evidence: str = ""
    fact: str = ""
    quick: tuple[tuple[str, Any], ...] = ()
    when: tuple[tuple[str, Any], ...] = ()  # ask only when these fields hold these values
    default: str = ""  # profile:<key> | cco_officer | days_ago:<n> | today


@dataclass(frozen=True)
class Dataset:
    kind: str  # trial_balance | loan_book | transactions
    label: str
    ask: str
    help: str
    required: bool = True


DATASETS: dict[str, tuple[Dataset, ...]] = {
    "cbn-monthly-prudential": (
        Dataset("trial_balance", "Trial balance",
                "Drop this month's trial balance exactly as your core banking system exports it.",
                "Excel or CSV, any layout. Iroko maps each GL account to the MMFBR line and remembers the mapping for next month."),
        Dataset("loan_book", "Loan book",
                "Drop the loan portfolio report as at month end.",
                "One row per loan, any layout. Iroko works out borrower type, days past due and insiders, and shows you what it inferred."),
    ),
    "nfiu-ctr": (
        Dataset("transactions", "Transactions",
                "Drop the cash transactions report for the period.",
                "Excel or CSV straight from core banking. Iroko picks out every transaction above the ₦5m / ₦10m thresholds."),
    ),
}

_YES_NO = (("Yes", True), ("No", False))

HINTS: dict[str, dict[str, Hint]] = {
    "cbn-monthly-prudential": {
        "risk_weighted_assets_override": Hint(carry=False),
        "qualifying_capital_override": Hint(carry=False),
    },
    "cbn-fraud-forgeries": {
        "nil_return": Hint(
            ask="Was any fraud or forgery — attempted or successful — discovered in {period}?",
            quick=(("No — file a nil return", True), ("Yes — I'll add the cases", False)),
        ),
        "incidents": Hint(ask="Add each case discovered in {period}.", when=(("nil_return", False),)),
    },
    "cbn-cg-compliance": {
        "board": Hint(ask="Who is on the board? Add every director with their role and appointment date.", carry=True, fact="board"),
        "committees": Hint(ask="Which board committees exist, and who chairs each?", carry=True, fact="committees"),
        # A count needs every set of minutes, not one quote — always asked.
        "board_meetings_in_period": Hint(ask="How many board meetings were held in the {period}?"),
        "external_auditor": Hint(ask="Which firm is the bank's external auditor?", carry=True, fact="external_auditor",
                                 evidence="external auditor appointment chartered accountants"),
        "external_auditor_cbn_approved": Hint(ask="Did the CBN approve the external auditor's appointment?", carry=True, quick=_YES_NO),
        "risk_officer_in_place": Hint(ask="Is there a Risk Officer reporting to the risk committee?", carry=True, quick=_YES_NO),
        "internal_auditor_in_place": Hint(ask="Is there an Internal Auditor reporting to the audit committee?", carry=True, quick=_YES_NO),
        "board_appraisal_date": Hint(ask="When did the independent consultant forward last year's board appraisal to the CBN?",
                                     evidence="board appraisal report independent consultant forwarded central bank"),
        "family_members_on_board": Hint(ask="Do more than two members of one family sit on the board?", carry=True,
                                        quick=(("No", False), ("Yes", True))),
        "other_disclosures": Hint(),
    },
    "cbn-whistleblowing": {
        "policy_approval_date": Hint(ask="When did the Board approve the whistle-blowing policy?", carry=True, fact="whistle_policy_date",
                                     evidence="whistle-blowing policy approved by the board"),
        "policy_on_website": Hint(ask="Is the whistle-blowing policy published on the bank's website?", carry=True, quick=_YES_NO),
        "channels": Hint(ask="How can staff and customers raise a concern?", carry=True, fact="whistle_channels",
                         evidence="whistle-blowing channels hotline email report concerns"),
        "cases_received": Hint(ask="How many whistle-blowing reports were received in the {period}?", quick=(("None", 0),)),
        "cases_investigated": Hint(ask="How many of them were investigated?", when=(("cases_received", "nonzero"),)),
        "cases_substantiated": Hint(ask="How many were substantiated?", when=(("cases_received", "nonzero"),)),
        "cases_closed": Hint(ask="How many are now closed?", when=(("cases_received", "nonzero"),)),
        "cases_pending": Hint(ask="How many are still open at the end of the period?", when=(("cases_received", "nonzero"),)),
        "case_summary": Hint(ask="Briefly, what were the reports about and what action was taken?", when=(("cases_received", "nonzero"),)),
        "retaliation_complaints": Hint(),
        "staff_awareness": Hint(carry=True),
    },
    "nfiu-str": {
        "reporting_officer": Hint(default="cco_officer"),
        "detection_datetime": Hint(ask="When was the activity identified as suspicious? (date and time)"),
        "subject_name": Hint(ask="Who is the subject of the report?"),
        "subject_type": Hint(ask="Is the subject an individual or a company?",
                             quick=(("Individual", "Individual"), ("Company", "Body corporate"))),
        "account_number": Hint(ask="What is the subject's account number?"),
        "transactions": Hint(ask="List the transactions that raised the suspicion."),
        "grounds": Hint(ask="Which grounds in Section 7(1) of the Act apply?"),
        "reasons": Hint(ask="In plain facts, what did you observe and why does it depart from the customer's profile?"),
        "action_taken": Hint(ask="What has the bank done so far?"),
    },
    "nfiu-ctr": {
        "period_from": Hint(default="days_ago:7"),
        "period_to": Hint(default="today"),
        "reporting_officer": Hint(default="cco_officer"),
    },
    "ndic-deposit-certification": {
        "demand_deposits": Hint(ask="Demand deposits at 31 December (₦)?"),
        "savings_deposits": Hint(ask="Savings deposits at 31 December (₦)?"),
        "time_deposits": Hint(ask="Time / term deposits at 31 December (₦)?"),
        "other_deposits": Hint(),
        "insider_deposits": Hint(ask="How much of that is held by staff and directors (₦)?", quick=(("None", 0),)),
        "collateral_deposits": Hint(ask="How much is held as cash collateral against loans (₦)?", quick=(("None", 0),)),
        "auditor_name": Hint(ask="Which approved auditor certified the deposits?", fact="external_auditor"),
        "auditor_certificate_date": Hint(ask="What date is on the auditor's certificate?"),
    },
    "cbn-afs-submission": {
        "auditor_name": Hint(ask="Which firm audited the accounts?", fact="external_auditor"),
        "audit_report_date": Hint(ask="What date is on the auditor's report?", evidence="independent auditor's report dated"),
        "board_approval_date": Hint(ask="On what date did the Board approve the accounts?",
                                    evidence="financial statements approved by the board of directors on"),
        "total_assets": Hint(ask="Total assets per the audited accounts (₦)?"),
        "profit_before_tax": Hint(ask="Profit or loss before tax per the audited accounts (₦)?"),
        "shareholders_funds": Hint(ask="Shareholders' funds per the audited accounts (₦)?"),
        "management_letter_enclosed": Hint(ask="Will you enclose the auditor's management letter?", quick=_YES_NO),
        "proposed_dividend": Hint(quick=(("No dividend", 0),)),
    },
    "ndpc-compliance-audit": {
        "dpco_name": Hint(ask="Which licensed DPCO is filing the audit return?", carry=True, fact="dpco_name",
                          evidence="data protection compliance organisation DPCO audit engagement"),
        "dpo_name": Hint(ask="Who is the bank's Data Protection Officer?", carry=True, fact="dpo_name",
                         evidence="data protection officer appointed"),
        "data_subjects": Hint(ask="Roughly how many customers and staff does the bank hold data on?"),
        "data_categories": Hint(ask="What categories of personal data does the bank process?", carry=True,
                                evidence="categories of personal data processed BVN NIN"),
        "lawful_bases": Hint(ask="Which lawful bases does the bank rely on?", carry=True, evidence="lawful basis for processing consent contract legal obligation"),
        "dpias_conducted": Hint(ask="How many data protection impact assessments were done this year?", quick=(("None", 0),)),
        "breaches": Hint(ask="How many personal data breaches occurred this year?", quick=(("None", 0),)),
        "breaches_notified_72h": Hint(ask="How many of those were notified to the NDPC within 72 hours?", when=(("breaches", "nonzero"),)),
        "dsr_received": Hint(ask="How many data-subject requests did customers make this year?", quick=(("None", 0),)),
        "dsr_resolved": Hint(ask="How many were resolved?", when=(("dsr_received", "nonzero"),)),
        "cross_border_transfers": Hint(carry=True),
        "processors": Hint(carry=True),
        "security_measures": Hint(ask="What security measures protect personal data?", carry=True,
                                  evidence="information security encryption access control measures personal data"),
        "training": Hint(carry=True),
        "privacy_policy_url": Hint(carry=True),
    },
}


def hint(return_id: str, key: str) -> Hint:
    return HINTS.get(return_id, {}).get(key, Hint())


def datasets(return_id: str) -> tuple[Dataset, ...]:
    return DATASETS.get(return_id, ())


def datasets_dict(return_id: str) -> list[dict]:
    return [asdict(d) for d in datasets(return_id)]
