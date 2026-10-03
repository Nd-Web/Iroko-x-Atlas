"""Compatibility facade: unverified static regulatory documents have been removed.

Regulatory Q&A retrieves approved extracted sources through Researcher.
Legacy callers must treat an empty reference set as missing evidence, not compliance.
"""

CBN_REGULATIONS: list[dict] = []
NCC_REGULATIONS = CBN_REGULATIONS
NDPC_REGULATIONS: list[dict] = []
NCC_TELECOM_REGULATIONS: list[dict] = []
FINTECH_COMPLIANCE_CHECKLIST: list[dict] = []
TELECOM_COMPLIANCE_CHECKLIST: list[dict] = []
Sector = str


def get_regulatory_context(query: str, sector: Sector = "financial") -> dict:
    return {"regulations": [], "compliance_checklist": [], "sector": sector,
            "total_matched": 0, "knowledge_gap": True}


def get_all_regulations(sector: Sector = "both") -> dict:
    return {"cbn": [], "ncc": [], "ndpc": [], "compliance_checklist": [],
            "sector": sector, "knowledge_gap": True}


def get_regulatory_summary_text(query: str, sector: Sector = "financial") -> str:
    return "No static regulatory reference is available. Retrieve accessible extracted source documents; do not infer compliance or penalty figures."
