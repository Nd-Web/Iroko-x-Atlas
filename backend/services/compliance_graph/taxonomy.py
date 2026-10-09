"""
Regulatory vocabulary for the compliance graph, kept as reviewable constants.

Every mapping here is a regulatory judgement, so it lives in code review rather
than in a model prompt. The owner signs off changes; tests pin the behaviour.

  * CATEGORIES      licence categories (leaves) and the groups they belong to.
  * ADDRESSEE_TERMS how circulars name their addressees. `explicit` terms make
                    applicability "stated in source"; the rest only suggest it.
  * TOPICS          the shared vocabulary that lets a policy clause and a
                    regulation be compared even when their wording differs.
  * ACTS            statutes instruments commonly cite.
  * RETURN_GROUPS   which licences each regulatory return in
                    services/regulatory_returns/catalog.py applies to.
"""

from __future__ import annotations

import difflib
import re
from dataclasses import dataclass

# ─── Licence categories ──────────────────────────────────────────────────────

GROUPS: dict[str, str] = {
    "mfb": "Microfinance banks",
    "ofi": "Other financial institutions (OFIs)",
    "banks": "Banks",
    "payments": "Payment service providers",
    "all_regulated": "All CBN-regulated institutions",
}

# code -> (label, sector, groups). MFB codes match catalog.LICENCE_CATEGORIES.
# OFIs are supervised by the CBN's OFI department and include MFBs; payment
# licensees are supervised separately and are deliberately NOT in "ofi".
CATEGORIES: dict[str, tuple[str, str, tuple[str, ...]]] = {
    "unit_tier1": ("Unit Microfinance Bank (Tier 1)", "mfb", ("mfb", "ofi", "all_regulated")),
    "unit_tier2": ("Unit Microfinance Bank (Tier 2)", "mfb", ("mfb", "ofi", "all_regulated")),
    "state": ("State Microfinance Bank", "mfb", ("mfb", "ofi", "all_regulated")),
    "national": ("National Microfinance Bank", "mfb", ("mfb", "ofi", "all_regulated")),
    "pmb": ("Primary Mortgage Bank", "ofi", ("ofi", "all_regulated")),
    "finance_company": ("Finance Company", "ofi", ("ofi", "all_regulated")),
    "bdc": ("Bureau De Change", "ofi", ("ofi", "all_regulated")),
    "dfi": ("Development Finance Institution", "ofi", ("ofi", "all_regulated")),
    "dmb": ("Deposit Money Bank (commercial, merchant or non-interest)", "banks", ("banks", "all_regulated")),
    "psb": ("Payment Service Bank", "payments", ("payments", "banks", "all_regulated")),
    "mmo": ("Mobile Money Operator", "payments", ("payments", "all_regulated")),
    "switching_processing": ("Switching and Processing", "payments", ("payments", "all_regulated")),
    "pssp": ("Payment Solution Service Provider", "payments", ("payments", "all_regulated")),
    "ptsp": ("Payment Terminal Service Provider", "payments", ("payments", "all_regulated")),
    "super_agent": ("Super-Agent", "payments", ("payments", "all_regulated")),
    "imto": ("International Money Transfer Operator", "payments", ("payments", "all_regulated")),
}

# Licences a pilot workspace may declare (the others exist so a circular
# addressed only to, say, Bureaux De Change resolves to "not among the stated
# addressees" instead of "not established").
DECLARABLE = ("unit_tier1", "unit_tier2", "state", "national", "psb", "mmo",
              "switching_processing", "pssp", "ptsp", "super_agent", "imto")


def leaves(codes) -> set[str]:
    """Expand group and leaf codes to leaf codes."""
    out: set[str] = set()
    for code in codes or ():
        if code in CATEGORIES:
            out.add(code)
        elif code in GROUPS:
            out.update(leaf for leaf, (_l, _s, groups) in CATEGORIES.items() if code in groups)
    return out


def label(code: str) -> str:
    if code in CATEGORIES:
        return CATEGORIES[code][0]
    return GROUPS.get(code, code)


def valid_codes(codes) -> list[str]:
    return [c for c in dict.fromkeys(codes or ()) if c in CATEGORIES or c in GROUPS]


# ─── Addressee terms ─────────────────────────────────────────────────────────


@dataclass(frozen=True)
class Term:
    name: str
    pattern: re.Pattern
    codes: tuple[str, ...]
    explicit: bool
    phrase: str  # canonical words, used for typo-tolerant matching


def _term(name, pattern, codes, explicit, phrase):
    return Term(name, re.compile(pattern, re.I), tuple(codes), explicit, phrase)


# Order matters: specific names first. Each match masks its text so a generic
# term ("banks") never re-matches inside a specific one ("microfinance banks").
ADDRESSEE_TERMS: tuple[Term, ...] = (
    _term("microfinance banks", r"\bmicro[\s-]*finance\s+banks?\b|\bMFBs?\b", ["mfb"], True, "microfinance banks"),
    _term("primary mortgage banks", r"\b(?:primary\s+)?mortgage\s+banks?\b|\bPMBs?\b", ["pmb"], True, "primary mortgage banks"),
    _term("payment service banks", r"\bpayment\s+service\s+banks?\b|\bPSBs?\b", ["psb"], True, "payment service banks"),
    _term("deposit money banks", r"\bdeposit\s+money\s+banks?\b|\bDMBs?\b|\b(?:commercial|merchant|non-interest)\s+banks?\b",
          ["dmb"], True, "deposit money banks"),
    _term("other financial institutions", r"\bother\s+financial\s+institutions?\b|\bOFIs?\b", ["ofi"], True,
          "other financial institutions"),
    _term("bureaux de change", r"\bbureaux?\s+de\s+change\b|\bBDCs?\b", ["bdc"], True, "bureaux de change"),
    _term("development finance institutions", r"\bdevelopment\s+finance\s+institutions?\b|\bDFIs?\b", ["dfi"], True,
          "development finance institutions"),
    _term("finance companies", r"\bfinance\s+compan(?:y|ies)\b", ["finance_company"], True, "finance companies"),
    _term("mobile money operators", r"\bmobile\s+money\s+operators?\b|\bMMOs?\b", ["mmo"], True, "mobile money operators"),
    _term("switching and processing", r"\bswitching\s+(?:and\s+processing\s+)?(?:compan(?:y|ies)|licensees?|operators?)\b",
          ["switching_processing"], True, "switching and processing companies"),
    _term("payment solution service providers", r"\bpayment\s+solutions?\s+service\s+providers?\b|\bPSSPs?\b", ["pssp"], True,
          "payment solution service providers"),
    _term("payment terminal service providers", r"\bpayment\s+terminal\s+service\s+providers?\b|\bPTSPs?\b", ["ptsp"], True,
          "payment terminal service providers"),
    _term("super-agents", r"\bsuper[\s-]*agents?\b", ["super_agent"], True, "super agents"),
    _term("international money transfer operators", r"\binternational\s+money\s+transfer\s+operators?\b|\bIMTOs?\b", ["imto"],
          True, "international money transfer operators"),
    _term("payment service providers", r"\bpayment\s+service\s+providers?\b|\bPSPs?\b", ["payments"], True,
          "payment service providers"),
    # Scope depends on each Act's definitions, so these only suggest.
    _term("financial institutions", r"\bfinancial\s+institutions?\b", ["all_regulated"], False, "financial institutions"),
    _term("banks", r"\bbanks?\b", ["dmb", "psb"], False, "banks"),
)


@dataclass(frozen=True)
class AddresseeMatch:
    term: str
    codes: tuple[str, ...]
    explicit: bool  # an exact match of an explicit term: "stated in source"
    span: str
    start: int
    end: int


def match_addressees(text: str) -> list[AddresseeMatch]:
    """Exact matches only. Specific names mask generic ones."""
    if not text:
        return []
    masked = text
    found: list[AddresseeMatch] = []
    for term in ADDRESSEE_TERMS:
        for m in term.pattern.finditer(masked):
            found.append(AddresseeMatch(term.name, term.codes, term.explicit, text[m.start():m.end()], m.start(), m.end()))
        masked = term.pattern.sub(lambda m: " " * (m.end() - m.start()), masked)
    return sorted(found, key=lambda a: a.start)


def fuzzy_addressees(text: str, threshold: float = 0.84) -> list[AddresseeMatch]:
    """Typo-tolerant matches ("Institutiions") for explicit terms. Never "stated"."""
    words = [(m.group(), m.start(), m.end()) for m in re.finditer(r"[A-Za-z][A-Za-z-]*", text or "")]
    out: list[AddresseeMatch] = []
    for term in ADDRESSEE_TERMS:
        if not term.explicit:
            continue
        size = len(term.phrase.split())
        target = term.phrase.lower()
        for i in range(0, max(0, len(words) - size + 1)):
            window = words[i:i + size]
            candidate = " ".join(w for w, _s, _e in window).lower()
            ratio = difflib.SequenceMatcher(None, candidate, target).ratio()
            if ratio >= threshold and candidate != target:
                start, end = window[0][1], window[-1][2]
                out.append(AddresseeMatch(term.name, term.codes, False, text[start:end], start, end))
    return out


# ─── Topics ──────────────────────────────────────────────────────────────────

TOPICS: dict[str, str] = {
    "kyc_cdd": "Customer due diligence and KYC",
    "aml_cft_reporting": "AML/CFT reporting (STR, CTR)",
    "sanctions": "Sanctions and terrorist designations",
    "record_keeping": "Record keeping",
    "data_protection": "Data protection and privacy",
    "consumer_protection": "Consumer protection and complaints",
    "fraud": "Fraud management and reporting",
    "it_cybersecurity": "IT and cybersecurity",
    "capital": "Capital adequacy",
    "liquidity": "Liquidity",
    "credit_risk": "Credit risk and lending",
    "governance": "Corporate governance and board",
    "risk_management": "Risk management",
    "regulatory_returns": "Regulatory returns and reporting",
    "financial_reporting": "Financial statements and audit",
    "bvn_identity": "BVN and identity verification",
    "agent_banking": "Agent banking",
    "e_money_limits": "E-money, wallets and transaction limits",
    "payments_operations": "Payment operations and settlement",
    "outsourcing": "Outsourcing and third parties",
    "whistleblowing": "Whistleblowing",
    "training": "Training and awareness",
    "business_continuity": "Business continuity",
    "licensing": "Licensing and approvals",
    "fees_disclosure": "Fees, charges and disclosures",
    "financial_inclusion": "Financial inclusion",
    "other": "Other",
}


def valid_topics(values) -> list[str]:
    return [v for v in dict.fromkeys(values or ()) if v in TOPICS][:4]


# ─── Acts ────────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class Act:
    code: str
    title: str
    pattern: re.Pattern


def _act(code, title, pattern):
    return Act(code, title, re.compile(pattern, re.I))


ACTS: tuple[Act, ...] = (
    _act("bofia_2020", "Banks and Other Financial Institutions Act 2020",
         r"\bBanks\s+and\s+Other\s+Financial\s+Institutions\s+Act\b(?:\s*\(BOFIA\))?(?:\s*,?\s*2020)?|\bBOFIA\b(?:\s*,?\s*2020)?"),
    _act("cbn_act_2007", "Central Bank of Nigeria Act 2007",
         r"\bCentral\s+Bank\s+of\s+Nigeria\s+Act\b(?:\s*,?\s*2007)?|\bCBN\s+Act\b(?:\s*,?\s*2007)?"),
    _act("mlppa_2022", "Money Laundering (Prevention and Prohibition) Act 2022",
         r"\bMoney\s+Laundering\s+\(?Prevention\s+and\s+Prohibition\)?\s+Act\b(?:\s*,?\s*2022)?|\bMLPPA\b"),
    _act("mlpa_2011", "Money Laundering (Prohibition) Act 2011",
         r"\bMoney\s+Laundering\s+\(?Prohibition\)?\s+Act\b(?:\s*,?\s*2011)?|\bMLPA\b(?:\s*,?\s*2011)?"),
    _act("ndpa_2023", "Nigeria Data Protection Act 2023",
         r"\bNigeria(?:n)?\s+Data\s+Protection\s+Act\b(?:\s*,?\s*2023)?|\bNDPA\b(?:\s*,?\s*2023)?"),
    _act("ndic_act_2023", "Nigeria Deposit Insurance Corporation Act 2023",
         r"\bNigeria\s+Deposit\s+Insurance\s+Corporation\s+Act\b(?:\s*,?\s*2023)?|\bNDIC\s+Act\b(?:\s*,?\s*2023)?"),
    _act("tppa_2022", "Terrorism (Prevention and Prohibition) Act 2022",
         r"\bTerrorism\s+\(Prevention\s+and\s+Prohibition\)\s+Act\b(?:\s*,?\s*2022)?|\bTPPA\b"),
    _act("cama_2020", "Companies and Allied Matters Act 2020",
         r"\bCompanies\s+and\s+Allied\s+Matters\s+Act\b(?:\s*,?\s*2020)?|\bCAMA\b(?:\s*,?\s*2020)?"),
    _act("isa_2025", "Investments and Securities Act 2025",
         r"\bInvestments\s+and\s+Securities\s+Act\b(?:\s*,?\s*2025)?|\bISA\s*,?\s*2025\b"),
)


@dataclass(frozen=True)
class ActMatch:
    code: str
    title: str
    span: str
    start: int
    end: int


def match_acts(text: str) -> list[ActMatch]:
    out = []
    for act in ACTS:
        for m in act.pattern.finditer(text or ""):
            out.append(ActMatch(act.code, act.title, m.group(), m.start(), m.end()))
    return sorted(out, key=lambda a: a.start)


def act_title(code: str) -> str:
    return next((a.title for a in ACTS if a.code == code), code)


# ─── Return applicability ────────────────────────────────────────────────────

# Every return in the catalog is an MFB return today. Wider scopes for NFIU
# STR/CTR, the NDPC audit and NDIC certification need the owner's sign-off,
# recorded here, before they apply to payment licences.
RETURN_GROUPS: dict[str, tuple[str, ...]] = {
    "cbn-monthly-prudential": ("mfb",),
    "cbn-fraud-forgeries": ("mfb",),
    "cbn-cg-compliance": ("mfb",),
    "cbn-whistleblowing": ("mfb",),
    "nfiu-str": ("mfb",),
    "nfiu-ctr": ("mfb",),
    "ndic-deposit-certification": ("mfb",),
    "cbn-afs-submission": ("mfb",),
    "ndpc-compliance-audit": ("mfb",),
    "cbn-board-appraisal": ("mfb",),
}
PROPOSED_WIDER_RETURN_GROUPS = {  # awaiting owner sign-off; not applied
    "nfiu-str": ("all_regulated",),
    "nfiu-ctr": ("all_regulated",),
    "ndpc-compliance-audit": ("all_regulated",),
    "ndic-deposit-certification": ("mfb", "psb", "dmb"),
}


def return_applies(return_id: str, categories) -> bool:
    """Whether a return applies to a workspace holding these licence categories.

    With no declared categories the returns stay visible (the returns module
    was built for MFBs and keeps working for them).
    """
    held = set(categories or ())
    if not held:
        return True
    return bool(leaves(RETURN_GROUPS.get(return_id, ("mfb",))) & leaves(held))


# Keywords that suggest a requirement is fulfilled through a known return.
RETURN_KEYWORDS: dict[str, tuple[str, ...]] = {
    "cbn-monthly-prudential": ("monthly returns", "prudential returns", "fina", "mmfbr"),
    "cbn-fraud-forgeries": ("fraud and forgeries", "fraud returns", "frauds and forgeries"),
    "cbn-cg-compliance": ("corporate governance returns", "governance returns", "code of corporate governance"),
    "cbn-whistleblowing": ("whistle-blowing", "whistleblowing"),
    "nfiu-str": ("suspicious transaction", "str"),
    "nfiu-ctr": ("currency transaction report", "ctr", "cash transaction"),
    "ndic-deposit-certification": ("deposit liabilities", "certified deposit"),
    "cbn-afs-submission": ("audited financial statements", "afs"),
    "ndpc-compliance-audit": ("data protection compliance audit", "compliance audit return"),
    "cbn-board-appraisal": ("board appraisal", "board evaluation"),
}


def suggest_returns(text: str) -> list[str]:
    low = (text or "").lower()
    out = []
    for return_id, words in RETURN_KEYWORDS.items():
        for word in words:
            if re.search(rf"\b{re.escape(word)}\b", low):
                out.append(return_id)
                break
    return out
