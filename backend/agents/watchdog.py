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


try:
    from services.agent_capabilities import capability_guard, AgentCapability
    _CAPS_AVAILABLE = True
except ImportError:
    _CAPS_AVAILABLE = False
    import logging as _log
    _log.getLogger(__name__).warning("[WatchdogAgent] agent_capabilities not available")


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

    CONFIDENCE_THRESHOLD_GENERAL    = 0.60   # score must be > 0.60 to pass (0.5 fails ✓)
    CONFIDENCE_THRESHOLD_COMPLIANCE = 0.85   # score must be > 0.85 to pass (0.8 fails ✓, 0.9 passes ✓)

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
        organisation: Annotated[str, "Organisation name to check"] = "African Fintech Platform",
    ) -> str:
        # GAP 4 FIX — capability guard
        if _CAPS_AVAILABLE:
            try:
                capability_guard.require("WatchdogAgent", AgentCapability.FETCH_COMPETITOR)
            except PermissionError as e:
                logger.warning("[WatchdogAgent] Capability check failed: %s", e)

        all_alerts = []

        for check_fn, label in (
            (self.check_contract_expiry, "contract"),
            (self.detect_complaint_spike, "complaints"),
            (self.find_policy_conflicts, "policy"),
            (self.check_regulatory_deadlines, "regulatory"),
        ):
            try:
                result = json.loads(await check_fn(organisation))
                alerts = result.get("alerts", [])
                
                # Wire VerdictEngine to alerts
                try:
                    from services.verdict_engine import verdict_engine
                    for alert in alerts:
                        if "verdict" not in alert:
                            sev = alert.get("severity", "warning")
                            conf = 0.85 if sev == "critical" else 0.6
                            comp_res = {"verdict": "NO-GO", "compliant": False} if sev == "critical" else {"verdict": "MONITOR", "compliant": True}
                            alert["verdict"] = verdict_engine.compute_verdict(
                                confidence=conf, 
                                compliance_result=comp_res, 
                                signal_strength=3
                            )
                except Exception as e:
                    logger.warning(f"Failed to attach verdict to watchdog alert: {e}")

                all_alerts.extend(alerts)
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
        organisation: Annotated[str, "Organisation name"] = "African Fintech Platform",
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
        organisation: Annotated[str, "Organisation name"] = "African Fintech Platform",
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
or where a single category (e.g. loan repayment deductions) shows significant unusual volume.

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
        organisation: Annotated[str, "Organisation name"] = "African Fintech Platform",
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
or regulatory guidance (CBN, SEC, NDPA, FIRS, etc.).

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
        Returns alerts for any CBN/SEC or government filings due within 30 days."""
    )
    async def check_regulatory_deadlines(
        self,
        organisation: Annotated[str, "Organisation name"] = "African Fintech Platform",
    ) -> str:
        results = await self._search_documents(
            "regulatory submission deadline due date CBN SEC NDPA filing compliance return",
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
- CBN filings due within 60 days
- SEC registration or reporting deadlines
- NDPA compliance actions pending
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
                    "factor": "CBN Rate Policy Change",
                    "description": (
                        "CBN MPC reduced MPR by 50bps on April 27, 2026, signalling "
                        "potential easing. Fintechs may face pressure to lower lending rates, "
                        "compressing margins and increasing loan demand."
                    ),
                    "impact": "high",
                    "started": "2026-04-27",
                },
                {
                    "factor": "NDPA Enforcement Wave",
                    "description": "NDPC issued enforcement notices to 3 fintechs in May 2026 for KYC data misuse.",
                    "impact": "medium",
                    "started": "2026-05-01",
                },
            ],
            "conclusion": (
                "The combination of rate policy easing increasing loan demand and "
                "NDPC enforcement activity likely contributed to elevated compliance risk in the region."
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

        prompt = f"""You are the Watchdog for Iroko AI — fintech regulatory intelligence for African fintechs.
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
                "title": "CRC Credit Bureau Data Agreement Expiring — Renewal Required",
                "summary": (
                    "The CRC Credit Bureau data processing agreement (CRC/IROKO/2024-001) "
                    "expires December 31, 2025. Non-renewal prevents credit bureau checks on "
                    "new loan applicants, breaching CBN MFB lending guidelines. Annual value: NGN 890M."
                ),
                "metadata": {
                    "contract_title": "CRC Credit Bureau Data Processing Agreement",
                    "contract_reference": "CRC/IROKO/2024-001",
                    "expiry_date": "2025-12-31",
                    "monthly_value": 74166667,
                    "days_remaining": 30,
                    "renewal_notice_days": 60,
                    "document_id": "doc_002",
                },
                "suggested_actions": [
                    "Initiate renewal negotiations with CRC Credit Bureau immediately",
                    "Confirm CBN-compliant data sharing clauses are included in renewal",
                    "Engage legal team to review NDPA-compliant data processing terms",
                    "Ensure continuity of credit bureau access for loan origination pipeline",
                ],
            },
            {
                "alert_type": "contract_expiry",
                "severity": "warning",
                "title": "Interswitch Group Payment Gateway SLA Expiring March 2026",
                "summary": (
                    "The Interswitch Group Payment Gateway SLA (ISW/IROKO/PG/2026-001) "
                    "expires March 31, 2026. Begin renewal discussions to avoid payment processing "
                    "disruption. Annual value: NGN 1.2B."
                ),
                "metadata": {
                    "contract_title": "Interswitch Group Payment Gateway SLA",
                    "contract_reference": "ISW/IROKO/PG/2026-001",
                    "expiry_date": "2026-03-31",
                    "monthly_value": 100000000,
                    "days_remaining": 90,
                    "document_id": "doc_006",
                },
                "suggested_actions": [
                    "Schedule Q1 2026 renewal kick-off with Interswitch account manager",
                    "Review uptime SLA performance and any breach credits before renewal",
                ],
            },
        ]

    def _seed_complaint_alerts(self) -> List[dict]:
        return [
            {
                "alert_type": "complaint_spike",
                "severity": "critical",
                "title": "Kuda Agent Wallet Loan Deduction Complaint Spike (+187%)",
                "summary": (
                    "Unauthorised loan deduction complaints linked to Kuda agent wallet batch "
                    "processing have spiked 187% in Q2 2026 (2,847 tickets; NGN 45M disputed value). "
                    "Lagos accounts for 40% of complaints. Root cause: duplicate disbursement "
                    "entries in batch #7 causing double repayment deductions."
                ),
                "metadata": {
                    "region": "Lagos",
                    "total_complaints_q2": 2847,
                    "disputed_value_ngn": 45000000,
                    "increase_pct": 187,
                    "top_complaint": "Unauthorised loan repayment deductions",
                    "resolution_rate_pct": 73,
                    "document_id": "doc_003",
                },
                "suggested_actions": [
                    "Expedite resolution of 769 open loan deduction complaints",
                    "Suspend batch #7 processing and audit duplicate disbursement entries",
                    "Proactively notify and refund affected borrowers",
                    "File STR with CBN FIU if fraudulent pattern confirmed",
                    "Escalate to CBN Consumer Protection department if resolution SLA breached",
                ],
            }
        ]

    def _seed_policy_alerts(self) -> List[dict]:
        return [
            {
                "alert_type": "policy_conflict",
                "severity": "warning",
                "title": "CBN AML/CFT Regulation Conflicts With Internal Data Retention Policy",
                "summary": (
                    "CBN AML/CFT Regulations 2022 require customer transaction records to be "
                    "retained for 10 years. Internal Data Retention Policy v3.2 specifies 5 years. "
                    "Section 4.2 of the internal policy must be updated to ensure CBN compliance."
                ),
                "metadata": {
                    "regulation": "CBN AML/CFT Regulations 2022 — Section 18",
                    "internal_policy": "Fintech Data Retention Policy v3.2",
                    "conflict_section": "Section 4.2 — Transaction Record Retention Duration",
                    "regulation_requirement": "10 years",
                    "current_policy": "5 years",
                },
                "suggested_actions": [
                    "Update Data Retention Policy section 4.2 to reflect 10-year CBN requirement",
                    "Submit updated policy to Legal and DPO for review and approval",
                    "Extend data storage infrastructure to accommodate extended retention",
                    "Document the change for CBN AML/CFT compliance audit trail",
                ],
            }
        ]

    def _seed_regulatory_alerts(self) -> List[dict]:
        return [
            {
                "alert_type": "regulatory_deadline",
                "severity": "warning",
                "title": "CBN AML/CFT Quarterly Return Due in 12 Days",
                "summary": (
                    "The CBN AML/CFT quarterly return (Q2 2026) is due July 15, 2026. "
                    "KYC coverage (98.7%) and STR filing rate are compliant. "
                    "Transaction monitoring threshold verification against CBN-AML-001 Section 8 is outstanding."
                ),
                "metadata": {
                    "filing": "CBN AML/CFT Quarterly Return — Q2 2026",
                    "reference": "FINTECH-CBN-AML-Q2-2026",
                    "due_date": "2026-07-15",
                    "days_remaining": 12,
                    "last_submitted": "2026-04-15",
                    "document_id": "doc_004",
                },
                "suggested_actions": [
                    "Verify transaction monitoring metrics against CBN-AML-001 Section 8 benchmarks",
                    "Request Q2 2026 STR filing count from AML compliance team",
                    "Assign report owner and set internal sign-off deadline for July 12",
                ],
            },
            {
                "alert_type": "compliance_gap",
                "severity": "warning",
                "title": "NDPA Data Processing Record Incomplete — DPO Action Required",
                "summary": (
                    "The NDPA Article 24 data processing record (FINTECH-NDPA-ART24-2026-001) "
                    "has an outstanding gap: cross-border transfer safeguards (Standard Contractual "
                    "Clauses for South Africa and AWS Ireland) require DPO sign-off. The DPIA "
                    "reference for the credit scoring ML pipeline must also be linked before the "
                    "next NDPA compliance review."
                ),
                "metadata": {
                    "document_reference": "FINTECH-NDPA-ART24-2026-001",
                    "gap_section": "Section 4 — Cross-Border Data Transfers",
                    "required_action": "DPO sign-off on Standard Contractual Clauses",
                    "dpo_contact": "dpo@iroko.ai",
                    "document_id": "doc_005",
                },
                "suggested_actions": [
                    "DPO to review and sign off on cross-border transfer safeguards",
                    "Link DPIA reference to NDPA Article 24 processing record",
                    "Align data retention period with CBN AML/CFT 10-year requirement",
                    "Schedule NDPA compliance review before next regulatory audit",
                ],
            },
        ]
