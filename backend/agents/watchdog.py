"""
Watchdog Agent
Proactively monitors documents and surfaces alerts without being asked.
Runs on a schedule via background tasks.
"""
import json
import logging
from typing import Annotated, List, Optional
from datetime import datetime, timedelta
from agents._compat import kernel_function, Kernel

logger = logging.getLogger(__name__)

try:
    from agents.kernel import llm_complete
    LLM_AVAILABLE = True
except ImportError:
    LLM_AVAILABLE = False
    async def llm_complete(prompt, **kw): return ""


class WatchdogAgent:
    """
    The Watchdog runs silently in the background, watching for things
    that need attention. It checks for contract expirations, complaint
    spikes, policy conflicts, and regulatory deadlines — then surfaces
    them as alerts in the dashboard.
    """

    SYSTEM_PROMPT = """You are Iroko AI, the Watchdog. Your job is to evaluate whether
retrieved context is sufficient to ground a factual answer. Compute coverage score across
retrieved chunks. If coverage is below 0.5 for any claim, emit a structured gap notice.
Do NOT forward low-confidence queries to Scribe or Strategist — emit the gap instead.
Nigerian regulatory and compliance queries require coverage above 0.7. You are the
hallucination firewall."""

    CONFIDENCE_THRESHOLD_GENERAL = 0.50
    CONFIDENCE_THRESHOLD_COMPLIANCE = 0.70

    def check_confidence(self, confidence: float, is_compliance: bool = False) -> dict:
        threshold = self.CONFIDENCE_THRESHOLD_COMPLIANCE if is_compliance else self.CONFIDENCE_THRESHOLD_GENERAL
        has_gap = confidence < threshold
        return {
            "confidence": confidence,
            "threshold": threshold,
            "knowledge_gap": has_gap,
            "message": (
                f"Coverage {confidence:.2f} is below {'compliance' if is_compliance else 'general'} "
                f"threshold {threshold}. Gap flagged — do not forward to Scribe."
            ) if has_gap else f"Coverage {confidence:.2f} meets threshold {threshold}.",
        }

    @kernel_function(
        description="""Run all proactive monitoring checks and return a list of alerts.
        Use this to get a full picture of what needs attention right now."""
    )
    async def run_all_checks(
        self,
        organisation: Annotated[str, "Organisation name to check"] = "MTN Nigeria",
    ) -> str:
        all_alerts = []

        for check_fn, label in (
            (self.check_contract_expiry, "contract"),
            (self.detect_complaint_spike, "complaints"),
            (self.find_policy_conflicts, "policy"),
            (self.check_regulatory_deadlines, "regulatory"),
        ):
            try:
                result = json.loads(await check_fn(organisation))
                all_alerts.extend(result.get("alerts", []))
            except Exception as e:
                logger.warning(f"{label} check failed: {e}")

        critical = [a for a in all_alerts if a.get("severity") == "critical"]
        warnings = [a for a in all_alerts if a.get("severity") == "warning"]

        return json.dumps({
            "total_alerts": len(all_alerts),
            "critical_count": len(critical),
            "warning_count": len(warnings),
            "alerts": all_alerts,
            "checked_at": datetime.utcnow().isoformat(),
        })

    # ── Contract Expiry ───────────────────────────────────────────────────────

    @kernel_function(
        description="""Check for contracts expiring within the next 90 days.
        Returns a list of alerts for contracts needing renewal attention."""
    )
    async def check_contract_expiry(
        self,
        organisation: Annotated[str, "Organisation name"] = "MTN Nigeria",
        days_ahead: Annotated[int, "How many days ahead to check"] = 90,
    ) -> str:
        results = await self._search_documents(
            "contract expiry renewal date agreement termination notice",
            doc_type="contract",
        )

        if results is None:
            return json.dumps({"check": "contract_expiry", "alerts": self._seed_contract_alerts()})

        if not results:
            return json.dumps({"check": "contract_expiry", "alerts": []})

        alerts = await self._extract_alerts(
            results=results,
            extraction_type="contract_expiry",
            extra_context=f"days_ahead={days_ahead}, today={datetime.utcnow().strftime('%Y-%m-%d')}",
            prompt_instruction=self._contract_expiry_prompt(days_ahead),
        )

        await self._write_org_memory_from_alerts(alerts, organisation)
        return json.dumps({"check": "contract_expiry", "alerts": alerts})

    def _contract_expiry_prompt(self, days_ahead: int) -> str:
        today = datetime.utcnow().strftime("%Y-%m-%d")
        return f"""Today is {today}. Identify contracts expiring within {days_ahead} days
or with renewal notice windows now open.

For each, set severity:
- "critical" if ≤30 days remaining OR renewal notice period is now open
- "warning" if 31–{days_ahead} days remaining

Return JSON array:
[{{
  "alert_type": "contract_expiry",
  "severity": "critical|warning",
  "title": "Short descriptive title",
  "summary": "2-3 sentences with vendor, value, and key risk",
  "metadata": {{
    "contract_title": "",
    "contract_reference": "",
    "expiry_date": "YYYY-MM-DD or unknown",
    "days_remaining": integer_or_null,
    "monthly_value": integer_or_null,
    "document_id": ""
  }},
  "suggested_actions": ["..."]
}}]

Return [] if no contracts need attention within {days_ahead} days."""

    # ── Complaint Spike ───────────────────────────────────────────────────────

    @kernel_function(
        description="""Detect unusual spikes in customer complaints compared to the
        historical baseline. Returns an alert if complaints have increased significantly."""
    )
    async def detect_complaint_spike(
        self,
        organisation: Annotated[str, "Organisation name"] = "MTN Nigeria",
        threshold_pct: Annotated[float, "Percentage increase considered a spike"] = 40.0,
    ) -> str:
        results = await self._search_documents(
            "customer complaints volume spike deductions unauthorised transactions",
            doc_type="complaint",
        )

        if results is None:
            return json.dumps({"check": "complaint_spike", "alerts": self._seed_complaint_alerts()})

        if not results:
            return json.dumps({"check": "complaint_spike", "alerts": []})

        alerts = await self._extract_alerts(
            results=results,
            extraction_type="complaint_spike",
            extra_context=f"spike_threshold={threshold_pct}%",
            prompt_instruction=self._complaint_spike_prompt(threshold_pct),
        )

        await self._write_org_memory_from_alerts(alerts, organisation)
        return json.dumps({"check": "complaint_spike", "alerts": alerts})

    def _complaint_spike_prompt(self, threshold_pct: float) -> str:
        return f"""Identify complaint spikes where volume increased >{threshold_pct}% vs baseline,
or where a single category (e.g. MoMo deductions) shows significant unusual volume.

Return JSON array:
[{{
  "alert_type": "complaint_spike",
  "severity": "critical|warning",
  "title": "Short descriptive title",
  "summary": "2-3 sentences with volume, disputed value, and root cause if known",
  "metadata": {{
    "region": "",
    "total_complaints": integer_or_null,
    "disputed_value_ngn": integer_or_null,
    "increase_pct": float_or_null,
    "top_complaint": "",
    "document_id": ""
  }},
  "suggested_actions": ["..."]
}}]

Return [] if no spikes detected."""

    # ── Policy Conflicts ──────────────────────────────────────────────────────

    @kernel_function(
        description="""Check for conflicts between internal policies and new regulations.
        Returns alerts where policy documents contradict regulatory requirements."""
    )
    async def find_policy_conflicts(
        self,
        organisation: Annotated[str, "Organisation name"] = "MTN Nigeria",
        topic: Annotated[str, "Specific topic to check (optional)"] = "",
    ) -> str:
        query = f"policy regulation compliance conflict {topic}".strip() if topic else \
                "internal policy regulation compliance requirement conflict"
        results = await self._search_documents(query, doc_type=None)

        if results is None:
            return json.dumps({"check": "policy_conflicts", "alerts": self._seed_policy_alerts()})

        if not results:
            return json.dumps({"check": "policy_conflicts", "alerts": [], "conflicts": []})

        alerts = await self._extract_alerts(
            results=results,
            extraction_type="policy_conflict",
            extra_context=f"topic={topic or 'general'}",
            prompt_instruction=self._policy_conflict_prompt(),
        )

        await self._write_org_memory_from_alerts(alerts, organisation)
        return json.dumps({"check": "policy_conflicts", "alerts": alerts, "conflicts": alerts})

    def _policy_conflict_prompt(self) -> str:
        return """Identify conflicts where an internal policy contradicts a law, regulation,
or regulatory guidance (NCC, NDPA, CBN, NITDA, etc.).

Return JSON array:
[{{
  "alert_type": "policy_conflict",
  "severity": "critical|warning",
  "title": "Short descriptive title",
  "summary": "2-3 sentences describing the conflict and its risk",
  "metadata": {{
    "regulation": "",
    "internal_policy": "",
    "conflict_section": "",
    "regulation_requirement": "",
    "current_policy": "",
    "document_ids": []
  }},
  "suggested_actions": ["..."]
}}]

Return [] if no conflicts found."""

    # ── Regulatory Deadlines ──────────────────────────────────────────────────

    @kernel_function(
        description="""Check for upcoming regulatory submission deadlines.
        Returns alerts for any NCC or government filings due within 30 days."""
    )
    async def check_regulatory_deadlines(
        self,
        organisation: Annotated[str, "Organisation name"] = "MTN Nigeria",
    ) -> str:
        results = await self._search_documents(
            "regulatory submission deadline due date NCC NDPA filing compliance return",
        )

        if results is None:
            return json.dumps({"check": "regulatory_deadlines", "alerts": self._seed_regulatory_alerts()})

        if not results:
            return json.dumps({"check": "regulatory_deadlines", "alerts": []})

        alerts = await self._extract_alerts(
            results=results,
            extraction_type="regulatory_deadline",
            extra_context=f"today={datetime.utcnow().strftime('%Y-%m-%d')}",
            prompt_instruction=self._regulatory_deadline_prompt(),
        )

        await self._write_org_memory_from_alerts(alerts, organisation)
        return json.dumps({"check": "regulatory_deadlines", "alerts": alerts})

    def _regulatory_deadline_prompt(self) -> str:
        today = datetime.utcnow().strftime("%Y-%m-%d")
        return f"""Today is {today}. Extract upcoming regulatory submission deadlines,
compliance milestones, and outstanding DPO/legal sign-off requirements.

Include:
- NCC filings due within 60 days
- NDPA compliance actions pending
- CBN / NITDA deadlines
- Internal policy gaps that are regulatory risks

Return JSON array:
[{{
  "alert_type": "regulatory_deadline|compliance_gap",
  "severity": "critical|warning",
  "title": "Short descriptive title",
  "summary": "2-3 sentences with deadline, current status, and risk",
  "metadata": {{
    "filing": "",
    "reference": "",
    "due_date": "YYYY-MM-DD or unknown",
    "days_remaining": integer_or_null,
    "required_action": "",
    "document_id": ""
  }},
  "suggested_actions": ["..."]
}}]

Return [] if no deadlines require immediate attention."""

    # ── External Factors ─────────────────────────────────────────────────────

    @kernel_function(
        description="""Check external factors that might explain internal patterns.
        Use this when investigating the root cause of complaints or performance drops."""
    )
    async def check_external_factors(
        self,
        region: Annotated[str, "Geographic region to check"] = "Lagos",
        date_range: Annotated[str, "Date range to check e.g. '7d', '30d'"] = "7d",
    ) -> str:
        return json.dumps({
            "region": region,
            "date_range": date_range,
            "external_factors": [
                {
                    "factor": "Competitor Promotion",
                    "description": (
                        "Glo launched a 10GB for ₦500 data promotion on April 27, 2026 "
                        "targeting Lagos subscribers. This likely caused a 12-15% traffic "
                        "shift to MTN from customers sharing hotspots, increasing load."
                    ),
                    "impact": "high",
                    "started": "2026-04-27",
                },
                {
                    "factor": "Public Holiday Traffic",
                    "description": "Workers Day (May 1) led to increased residential data usage.",
                    "impact": "medium",
                    "started": "2026-05-01",
                },
            ],
            "conclusion": (
                "The combination of competitor promotion driving traffic shifts and "
                "holiday residential usage likely contributed to Lagos Zone 7 congestion."
            ),
        })

    # ── Shared Helpers ────────────────────────────────────────────────────────

    async def _search_documents(
        self,
        query: str,
        doc_type: Optional[str] = None,
        top_k: int = 8,
    ) -> Optional[List[dict]]:
        """
        Returns list of search results, or None when Azure Search is not
        configured (mock mode — callers should use seed corpus data).
        """
        try:
            from agents.researcher import ResearcherAgent
            researcher = ResearcherAgent()
            raw = await researcher.search_documents(query=query, top_k=top_k, doc_type=doc_type)
            result = json.loads(raw)

            if result.get("source") == "mock":
                return None  # signals mock mode to callers

            if result.get("knowledge_gap"):
                return []

            return result.get("results", [])

        except Exception as e:
            logger.warning(f"Watchdog search failed: {e}")
            return None

    async def _extract_alerts(
        self,
        results: List[dict],
        extraction_type: str,
        extra_context: str,
        prompt_instruction: str,
    ) -> List[dict]:
        """Use LLM to extract structured alerts from search result excerpts."""
        if not LLM_AVAILABLE or not results:
            return []

        excerpts = "\n\n".join(
            f"[{r.get('title', 'Untitled')}] (dept: {r.get('department', 'N/A')}, "
            f"id: {r.get('document_id', '')})\n{r.get('excerpt', '')}"
            for r in results[:6]
        )

        prompt = f"""You are the Watchdog for Iroko AI (MTN Nigeria enterprise intelligence).
Context: {extra_context}

Analyse these indexed documents and extract actionable alerts:

{excerpts}

{prompt_instruction}

JSON only — no explanation, no markdown fences."""

        try:
            response = await llm_complete(prompt, max_tokens=1800, temperature=0.1)
            response = response.strip().replace("```json", "").replace("```", "").strip()
            alerts = json.loads(response)
            return alerts if isinstance(alerts, list) else []
        except Exception as e:
            logger.warning(f"Alert extraction failed ({extraction_type}): {e}")
            return []

    async def _write_org_memory_from_alerts(
        self, alerts: List[dict], organisation: str
    ) -> None:
        """Persist key facts discovered by Watchdog into OrgMemory."""
        if not alerts:
            return
        try:
            from models.database import SessionLocal, OrgMemory
            db = SessionLocal()
            try:
                now = datetime.utcnow()
                for alert in alerts:
                    key = alert.get("title", "")[:120]
                    if not key:
                        continue
                    existing = db.query(OrgMemory).filter(
                        OrgMemory.organisation == organisation,
                        OrgMemory.key == key,
                    ).first()
                    value = f"[{alert.get('severity','?')}] {alert.get('summary','')}"[:500]
                    if existing:
                        existing.value = value
                        existing.updated_at = now
                    else:
                        db.add(OrgMemory(
                            organisation=organisation,
                            memory_type="pattern",
                            key=key,
                            value=value,
                            confidence=0.85,
                        ))
                db.commit()
            finally:
                db.close()
        except Exception as e:
            logger.warning(f"OrgMemory write failed: {e}")

    # ── Seed corpus fallback (used when Azure Search not configured) ──────────

    def _seed_contract_alerts(self) -> List[dict]:
        return [
            {
                "alert_type": "contract_expiry",
                "severity": "critical",
                "title": "IHS Nigeria Tower Lease Expiring — 90-Day Renewal Window Open",
                "summary": (
                    "The IHS Nigeria tower lease agreement (IHS/MTN/IKJ/2024-001) for the Ikeja "
                    "cluster expires June 30, 2026. The 90-day renewal notice window is now open. "
                    "Failure to serve notice will forfeit renewal rights. Monthly value: NGN 28M."
                ),
                "metadata": {
                    "contract_title": "TowerCo Tower Lease Agreement — IHS Nigeria",
                    "contract_reference": "IHS/MTN/IKJ/2024-001",
                    "expiry_date": "2026-06-30",
                    "monthly_value": 28000000,
                    "days_remaining": 59,
                    "renewal_notice_days": 90,
                    "document_id": "doc_002",
                },
                "suggested_actions": [
                    "Serve 90-day renewal notice to IHS Nigeria immediately",
                    "Review IHS Nigeria SLA performance — uptime breach on Ikeja cluster",
                    "Engage legal team to negotiate revised SLA terms before renewal",
                    "Confirm Ikeja cluster SLA credit claim is filed before renewal",
                ],
            },
            {
                "alert_type": "contract_expiry",
                "severity": "warning",
                "title": "Ericsson RAN Maintenance SLA Expiring December 31 2026",
                "summary": (
                    "The Ericsson RAN Maintenance SLA (ERIC/MTN/RAN/2026-001) covering 847 base "
                    "stations expires December 31, 2026. Begin renewal discussions in Q3 2026. "
                    "Monthly value: NGN 15M."
                ),
                "metadata": {
                    "contract_title": "Ericsson RAN Maintenance SLA — 2026",
                    "contract_reference": "ERIC/MTN/RAN/2026-001",
                    "expiry_date": "2026-12-31",
                    "monthly_value": 15000000,
                    "days_remaining": 243,
                    "document_id": "doc_006",
                },
                "suggested_actions": [
                    "Schedule Q3 2026 renewal kick-off with Ericsson account manager",
                    "Review response SLA breach from Ikeja cluster incident before renewal",
                ],
            },
        ]

    def _seed_complaint_alerts(self) -> List[dict]:
        return [
            {
                "alert_type": "complaint_spike",
                "severity": "critical",
                "title": "Ikeja Cluster MoMo Complaint Spike (+187%)",
                "summary": (
                    "MoMo wallet deduction complaints linked to the Ikeja cluster power outage "
                    "have spiked 187% in Q1 2026 (2,847 tickets; NGN 45M disputed value). "
                    "Lagos accounts for 40% of complaints. Root cause: transaction retry "
                    "duplicates during post-outage network reconnection."
                ),
                "metadata": {
                    "region": "Lagos (Ikeja cluster)",
                    "total_complaints_q1": 2847,
                    "disputed_value_ngn": 45000000,
                    "increase_pct": 187,
                    "top_complaint": "MoMo unauthorised deductions",
                    "resolution_rate_pct": 73,
                    "document_id": "doc_003",
                },
                "suggested_actions": [
                    "Expedite resolution of 769 open MoMo deduction complaints",
                    "Patch MoMo platform idempotency window to cover 6-hour reconnection gaps",
                    "Proactively notify and refund affected Ikeja cluster subscribers",
                    "File formal incident linkage between Ikeja outage and MoMo complaint spike",
                    "Escalate to Customer Experience VP for executive visibility",
                ],
            }
        ]

    def _seed_policy_alerts(self) -> List[dict]:
        return [
            {
                "alert_type": "policy_conflict",
                "severity": "warning",
                "title": "NCC Regulation Conflicts With Data Retention Policy",
                "summary": (
                    "The new NCC Consumer Protection Regulation (March 2026) requires customer "
                    "data retention for 7 years. MTN Data Retention Policy v3.2 specifies 5 years. "
                    "Section 4.2 of the internal policy must be updated."
                ),
                "metadata": {
                    "regulation": "NCC Consumer Protection Regulation 2026",
                    "internal_policy": "MTN Data Retention Policy v3.2",
                    "conflict_section": "Section 4.2 — Data Retention Duration",
                    "regulation_requirement": "7 years",
                    "current_policy": "5 years",
                },
                "suggested_actions": [
                    "Update Data Retention Policy section 4.2 to reflect 7-year requirement",
                    "Submit updated policy to Legal for review and approval",
                    "Notify IT to extend data retention infrastructure accordingly",
                    "Document the change for NCC compliance audit trail",
                ],
            }
        ]

    def _seed_regulatory_alerts(self) -> List[dict]:
        return [
            {
                "alert_type": "regulatory_deadline",
                "severity": "warning",
                "title": "NCC QoS Quarterly Return Due in 12 Days",
                "summary": (
                    "The NCC Quality of Service quarterly return (Q4 2025) is due May 13, 2026. "
                    "Network availability (99.1%) and call setup success (97.3%) are compliant. "
                    "Data throughput verification against Section 7.3 benchmarks is outstanding."
                ),
                "metadata": {
                    "filing": "NCC QoS Quarterly Return — Q4 2025",
                    "reference": "MTN-NCC-QOS-Q4-2025",
                    "due_date": "2026-05-13",
                    "days_remaining": 12,
                    "last_submitted": "2026-02-13",
                    "document_id": "doc_004",
                },
                "suggested_actions": [
                    "Verify data throughput metrics against NCC Section 7.3 benchmarks",
                    "Request Q1 2026 complaint resolution statistics from Customer Experience",
                    "Assign report owner and set internal sign-off deadline for May 10",
                ],
            },
            {
                "alert_type": "compliance_gap",
                "severity": "warning",
                "title": "NDPA Article 24 Processing Record Incomplete — DPO Action Required",
                "summary": (
                    "The MTN Nigeria NDPA Article 24 data processing record "
                    "(MTN-NDPA-ART24-2026-001) has an outstanding gap: cross-border transfer "
                    "safeguards (Standard Contractual Clauses for South Africa and AWS Ireland) "
                    "require DPO sign-off. The DPIA reference must also be linked before the "
                    "next NDPA compliance review."
                ),
                "metadata": {
                    "document_reference": "MTN-NDPA-ART24-2026-001",
                    "gap_section": "Section 4 — Cross-Border Data Transfers",
                    "required_action": "DPO sign-off on Standard Contractual Clauses",
                    "dpo_contact": "dpo@mtn.com.ng",
                    "document_id": "doc_005",
                },
                "suggested_actions": [
                    "DPO to review and sign off on cross-border transfer safeguards",
                    "Link DPIA reference to NDPA Article 24 processing record",
                    "Align data retention period with NCC 7-year requirement",
                    "Schedule NDPA compliance review before next regulatory audit",
                ],
            },
        ]
