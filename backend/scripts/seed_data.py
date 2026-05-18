"""
Seed script — uploads the 8 Iroko sample documents to Atlas.

Usage:
    python scripts/seed_data.py [--base-url http://localhost:8000]
"""
import sys
import argparse
import os
import requests

BASE_URL = "http://localhost:8000"

DOCUMENTS = [
    {
        "filename": "Ikeja_Cluster_RCA_Power_Outage_Q1_2026.txt",
        "department": "Network Operations",
        "doc_type": "report",
        "tags": ["rca", "ikeja", "outage", "noc", "q1-2026"],
    },
    {
        "filename": "TowerCo_IHS_Nigeria_Tower_Lease_Agreement.txt",
        "department": "Procurement",
        "doc_type": "contract",
        "tags": ["ihs", "towerco", "tower-lease", "ikeja", "vendor"],
    },
    {
        "filename": "Customer_Complaints_MoMo_Deductions_Q1_2026.txt",
        "department": "Customer Experience",
        "doc_type": "complaint",
        "tags": ["momo", "complaints", "deductions", "q1-2026", "lagos"],
    },
    {
        "filename": "NCC_QoS_Quarterly_Return_Q4_2025.txt",
        "department": "Legal/Regulatory",
        "doc_type": "policy",
        "tags": ["ncc", "qos", "regulatory", "quarterly-return", "q4-2025"],
    },
    {
        "filename": "MTN_NDPA_Article_24_Processing_Record.txt",
        "department": "Legal/Regulatory",
        "doc_type": "policy",
        "tags": ["ndpa", "data-protection", "article-24", "compliance", "dpo"],
    },
    {
        "filename": "Ericsson_RAN_Maintenance_SLA_2026.txt",
        "department": "Procurement",
        "doc_type": "contract",
        "tags": ["ericsson", "ran", "maintenance", "sla", "vendor"],
    },
    {
        "filename": "Kano_Kaduna_Fibre_Route_BoQ.txt",
        "department": "Network Operations",
        "doc_type": "report",
        "tags": ["fibre", "boq", "kano", "kaduna", "julius-berger", "rollout"],
    },
    {
        "filename": "Enterprise_Customer_SLA_Register_EBU.txt",
        "department": "Enterprise Business",
        "doc_type": "contract",
        "tags": ["enterprise", "sla", "ebu", "zenith-bank", "nnpc", "dangote"],
    },
]

SAMPLE_DOCS_DIR = os.path.join(os.path.dirname(__file__), "sample_docs")


def login(base_url: str) -> str:
    resp = requests.post(
        f"{base_url}/api/auth/login",
        json={"email": "admin@mtn.ng", "password": "AtlasAdmin2026!"},
        timeout=30,
    )
    resp.raise_for_status()
    token = resp.json().get("access_token")
    if not token:
        raise ValueError(f"No access_token in login response: {resp.json()}")
    print(f"  Authenticated as admin@mtn.ng")
    return token


def upload_document(base_url: str, token: str, doc_meta: dict) -> dict:
    filepath = os.path.join(SAMPLE_DOCS_DIR, doc_meta["filename"])
    if not os.path.exists(filepath):
        raise FileNotFoundError(f"Sample document not found: {filepath}")

    title = doc_meta["filename"].replace("_", " ").replace(".txt", "")

    with open(filepath, "rb") as f:
        resp = requests.post(
            f"{base_url}/api/documents",
            headers={"Authorization": f"Bearer {token}"},
            data={
                "title": title,
                "department": doc_meta["department"],
                "doc_type": doc_meta["doc_type"],
                "tags": str(doc_meta["tags"]).replace("'", '"'),
            },
            files={"file": (doc_meta["filename"], f, "text/plain")},
            timeout=60,
        )
    resp.raise_for_status()
    return resp.json()


def main():
    parser = argparse.ArgumentParser(description="Seed Atlas with Iroko sample documents")
    parser.add_argument("--base-url", default=BASE_URL, help="Atlas API base URL")
    args = parser.parse_args()

    base_url = args.base_url.rstrip("/")
    print(f"\nAtlas Seed Script — Iroko Document Corpus")
    print(f"Target: {base_url}\n")

    print("Step 1: Authenticating...")
    try:
        token = login(base_url)
    except Exception as e:
        print(f"  ERROR: Authentication failed — {e}")
        sys.exit(1)

    print(f"\nStep 2: Uploading {len(DOCUMENTS)} documents...\n")
    uploaded = 0
    for i, doc_meta in enumerate(DOCUMENTS, 1):
        print(f"  [{i}/{len(DOCUMENTS)}] {doc_meta['filename']}", end=" ... ", flush=True)
        try:
            result = upload_document(base_url, token, doc_meta)
            doc_id = result.get("id", "?")
            status = result.get("status", "?")
            print(f"OK (id={doc_id}, status={status})")
            uploaded += 1
        except Exception as e:
            print(f"FAILED — {e}")

    print(f"\nSeed complete — {uploaded} documents uploaded")
    if uploaded < len(DOCUMENTS):
        print(f"WARNING: {len(DOCUMENTS) - uploaded} document(s) failed to upload.")
        sys.exit(1)


if __name__ == "__main__":
    main()
