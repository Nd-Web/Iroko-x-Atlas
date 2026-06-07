import asyncio
import httpx
import json
from main import app

async def main():
    payload = {
        "verdict": "MONITOR",
        "compliant": False,
        "confidence_score": 0.62,
        "violations": [
            {
                "regulation_id": "CBN-MFB-001",
                "section": "Capital Adequacy — Section 5.1",
                "reason": "The planned lending exposure exceeds the CBN single-obligor limit under the revised CBN MFB guidelines."
            }
        ],
        "recommended_actions": [
            "Halt the planned action immediately.",
            "Contact CBN/SEC Regulatory Affairs team."
        ],
        "ncc_refs": ["CBN-MFB-001"],
        "decision_text": "Kuda MFB plans to increase single-borrower loan limit by 12% effective Q3 2026, potentially breaching the CBN obligor cap.",
        "summary": "Compliance check: 1 violation detected.",
        "workspace_name": "African Fintech Platform"
    }

    # Use httpx.AsyncClient with the FastAPI app directly to bypass network ConnectErrors
    async with httpx.AsyncClient(app=app, base_url="http://test") as client:
        # Get login token
        login_res = await client.post(
            "/api/v1/auth/login",
            json={"email": "admin@iroko.ai", "password": "AtlasAdmin2026!"}
        )
        print("Login status:", login_res.status_code)
        token = login_res.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # Request compliance PDF
        pdf_res = await client.post(
            "/api/v1/intel/compliance-pdf",
            json=payload,
            headers=headers
        )
        print("PDF response status:", pdf_res.status_code)
        print("PDF response headers:", dict(pdf_res.headers))
        
        # Save pdf to file
        with open("test_compliance.pdf", "wb") as f:
            f.write(pdf_res.content)
        print("Saved test_compliance.pdf")

if __name__ == "__main__":
    asyncio.run(main())
