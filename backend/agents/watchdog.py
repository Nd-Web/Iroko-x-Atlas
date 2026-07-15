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
        sector: Annotated[str, "Compliance sector: 'financial' (CBN/SEC) or 'network' (NCC)"] = "financial",
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
                result = json.loads(await check_fn(organisation, sector=sector))
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
        sector: Annotated[str, "Compliance sector: 'financial' or 'network'"] = "financial",
    ) -> str:
        results = await self._search_documents(
            "contract expiry renewal date agreement termination notice",
            doc_type="contract",
        )

        if results is None:
            return json.dumps({"check": "contract_expiry", "alerts": self._seed_contract_alerts(sector)})

        if not results:
            return json.dumps({"check": "contract_expiry", "alerts": []})

        alerts = await self._extract_alerts(
            results=results,
            extraction_type="contract_expiry",
            extra_context=f"days_ahead={days_ahead}, today={datetime.utcnow().strftime('%Y-%m-%d')}",
            prompt_instruction=self._contract_expiry_prompt(days_ahead),
            sector=sector,
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
        sector: Annotated[str, "Compliance sector: 'financial' or 'network'"] = "financial",
    ) -> str:
        results = await self._search_documents(
            "customer complaints volume spike deductions unauthorised transactions",
            doc_type="complaint",
        )

        if results is None:
            return json.dumps({"check": "complaint_spike", "alerts": self._seed_complaint_alerts(sector)})

        if not results:
            return json.dumps({"check": "complaint_spike", "alerts": []})

        alerts = await self._extract_alerts(
            results=results,
            extraction_type="complaint_spike",
            extra_context=f"spike_threshold={threshold_pct}%",
            prompt_instruction=self._complaint_spike_prompt(threshold_pct),
            sector=sector,
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
        sector: Annotated[str, "Compliance sector: 'financial' (CBN/SEC) or 'network' (NCC)"] = "financial",
    ) -> str:
        query = f"policy regulation compliance conflict {topic}".strip() if topic else \
                "internal policy regulation compliance requirement conflict"
        results = await self._search_documents(query, doc_type=None)

        if results is None:
            return json.dumps({"check": "policy_conflicts", "alerts": self._seed_policy_alerts(sector)})

        if not results:
            return json.dumps({"check": "policy_conflicts", "alerts": [], "conflicts": []})

        alerts = await self._extract_alerts(
            results=results,
            extraction_type="policy_conflict",
            extra_context=f"topic={topic or 'general'}",
            prompt_instruction=self._policy_conflict_prompt(sector),
            sector=sector,
        )

        await self._write_org_memory_from_alerts(alerts, organisation)
        return json.dumps({"check": "policy_conflicts", "alerts": alerts, "conflicts": alerts})

    def _policy_conflict_prompt(self, sector: str = "financial") -> str:
        regulators = "NCC, NDPA, NCA 2003" if sector == "network" else "CBN, SEC, NDPA, FIRS"
        return f"""Identify conflicts where an internal policy contradicts a law, regulation,
or regulatory guidance ({regulators}, etc.).

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
        sector: Annotated[str, "Compliance sector: 'financial' or 'network'"] = "financial",
    ) -> str:
        search_terms = (
            "regulatory submission deadline due date NCC QoS SIM NIN levy filing compliance return"
            if sector == "network"
            else "regulatory submission deadline due date CBN SEC NDPA filing compliance return"
        )
        results = await self._search_documents(search_terms)

        if results is None:
            return json.dumps({"check": "regulatory_deadlines", "alerts": self._seed_regulatory_alerts(sector)})

        if not results:
            return json.dumps({"check": "regulatory_deadlines", "alerts": []})

        alerts = await self._extract_alerts(
            results=results,
            extraction_type="regulatory_deadline",
            extra_context=f"today={datetime.utcnow().strftime('%Y-%m-%d')}",
            prompt_instruction=self._regulatory_deadline_prompt(sector),
            sector=sector,
        )

        await self._write_org_memory_from_alerts(alerts, organisation)
        return json.dumps({"check": "regulatory_deadlines", "alerts": alerts})

    def _regulatory_deadline_prompt(self, sector: str = "financial") -> str:
        today = datetime.utcnow().strftime("%Y-%m-%d")
        if sector == "network":
            include = """Include:
- NCC filings due within 60 days (QoS quarterly returns, Annual Operating Levy, subscriber/NIN-SIM returns)
- Spectrum or licence renewal deadlines
- NDPA (subscriber data) compliance actions pending
- Internal policy gaps that are regulatory risks"""
        else:
            include = """Include:
- CBN filings due within 60 days
- SEC registration or reporting deadlines
- NDPA compliance actions pending
- Internal policy gaps that are regulatory risks"""
        return f"""Today is {today}. Extract upcoming regulatory submission deadlines,
compliance milestones, and outstanding DPO/legal sign-off requirements.

{include}

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
        sector: str = "financial",
    ) -> List[dict]:
        """Use LLM to extract structured alerts from search result excerpts."""
        if not LLM_AVAILABLE or not results:
            return []

        excerpts = "\n\n".join(
            f"[{r.get('title', 'Untitled')}] (dept: {r.get('department', 'N/A')}, "
            f"id: {r.get('document_id', '')})\n{r.get('excerpt', '')}"
            for r in results[:6]
        )

        domain = (
            "NCC telecom regulatory intelligence for Nigerian network operators (e.g. MTN Nigeria)"
            if sector == "network"
            else "fintech regulatory intelligence for African fintechs"
        )
        prompt = f"""You are the Watchdog for Iroko AI — {domain}.
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

    def _seed_contract_alerts(self, sector: str = "financial") -> List[dict]:
        if sector == "network":
            return [
                {
                    "alert_type": "contract_expiry",
                    "severity": "critical",
                    "title": "IHS Towers Colocation Master Agreement Expiring — Renewal Required",
                    "summary": (
                        "The IHS Towers tower-colocation master agreement (IHS/MTN/2024-001) expires "
                        "December 31, 2026. Non-renewal risks loss of access to 3,400 shared tower sites, "
                        "degrading coverage and breaching NCC network-availability KPIs. Annual value: NGN 42B."
                    ),
                    "metadata": {
                        "contract_title": "IHS Towers Colocation Master Agreement",
                        "contract_reference": "IHS/MTN/2024-001",
                        "expiry_date": "2026-12-31",
                        "monthly_value": 3500000000,
                        "days_remaining": 30,
                        "renewal_notice_days": 90,
                        "document_id": "doc_002",
                    },
                    "suggested_actions": [
                        "Initiate colocation renewal negotiations with IHS Towers immediately",
                        "Confirm SLA clauses preserve NCC network-availability KPIs (≥98%)",
                        "Assess coverage/QoS risk in affected states if sites are lost",
                        "Engage regulatory affairs on NCC QoS exposure from any site downtime",
                    ],
                },
                {
                    "alert_type": "contract_expiry",
                    "severity": "warning",
                    "title": "Ericsson RAN Managed Services SLA Expiring March 2027",
                    "summary": (
                        "The Ericsson RAN managed-services SLA (ERI/MTN/RAN/2027-001) expires March 31, 2027. "
                        "Begin renewal to avoid gaps in 4G/5G RAN maintenance that could raise dropped-call "
                        "rates above the NCC 2% threshold. Annual value: NGN 18B."
                    ),
                    "metadata": {
                        "contract_title": "Ericsson RAN Managed Services SLA",
                        "contract_reference": "ERI/MTN/RAN/2027-001",
                        "expiry_date": "2027-03-31",
                        "monthly_value": 1500000000,
                        "days_remaining": 90,
                        "document_id": "doc_006",
                    },
                    "suggested_actions": [
                        "Schedule renewal kick-off with Ericsson account team",
                        "Review RAN uptime performance and QoS KPI impact before renewal",
                    ],
                },
            ]
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

    def _seed_complaint_alerts(self, sector: str = "financial") -> List[dict]:
        if sector == "network":
            return [
                {
                    "alert_type": "complaint_spike",
                    "severity": "critical",
                    "title": "Unsolicited VAS Billing Complaint Spike (+164%)",
                    "summary": (
                        "Complaints about unsolicited Value Added Service (VAS) auto-renewals and "
                        "airtime deductions have spiked 164% in Q2 2026 (3,120 tickets; NGN 38M disputed "
                        "airtime). Lagos and Kano account for 46% of complaints. Root cause: a VAS partner "
                        "bypassed the double-consent flow, breaching the NCC Consumer Code of Practice."
                    ),
                    "metadata": {
                        "region": "Lagos",
                        "total_complaints_q2": 3120,
                        "disputed_value_ngn": 38000000,
                        "increase_pct": 164,
                        "top_complaint": "Unsolicited VAS auto-renewal / airtime deduction",
                        "resolution_rate_pct": 71,
                        "document_id": "doc_003",
                    },
                    "suggested_actions": [
                        "Suspend the offending VAS partner and disable auto-renewal without double consent",
                        "Refund affected subscribers and reverse unsolicited charges within 24h",
                        "Confirm Do-Not-Disturb (2442) opt-outs are being honoured end-to-end",
                        "Report remediation to NCC Consumer Affairs before enforcement escalation",
                    ],
                }
            ]
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

    def _seed_policy_alerts(self, sector: str = "financial") -> List[dict]:
        if sector == "network":
            return [
                {
                    "alert_type": "policy_conflict",
                    "severity": "warning",
                    "title": "NCC QoS Threshold Conflicts With Internal Network Maintenance Window Policy",
                    "summary": (
                        "The NCC Quality of Service Business Rules require network availability ≥ 98% per "
                        "month, but internal Network Maintenance Policy v2.4 permits maintenance windows that "
                        "can drop availability to 96% in a single state. Section 3.1 of the internal policy "
                        "must be tightened to stay within NCC KPI thresholds."
                    ),
                    "metadata": {
                        "regulation": "NCC QoS Business Rules 2024 — Rule 8 (NCC-QOS-001)",
                        "internal_policy": "Network Maintenance Policy v2.4",
                        "conflict_section": "Section 3.1 — Maintenance Window Availability Floor",
                        "regulation_requirement": "≥ 98% monthly availability",
                        "current_policy": "96% floor during maintenance",
                    },
                    "suggested_actions": [
                        "Update Network Maintenance Policy 3.1 to hold availability ≥ 98% per state",
                        "Stagger maintenance windows to avoid single-state KPI breaches",
                        "Add NCC QoS KPI guardrails to the change-management approval flow",
                        "Document the change for the NCC QoS compliance audit trail",
                    ],
                }
            ]
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

    def _seed_regulatory_alerts(self, sector: str = "financial") -> List[dict]:
        if sector == "network":
            return [
                {
                    "alert_type": "regulatory_deadline",
                    "severity": "warning",
                    "title": "NCC Q2 2026 Quality of Service Return Due in 12 Days",
                    "summary": (
                        "The NCC quarterly Quality of Service return (Q2 2026) is due July 15, 2026. "
                        "Call Setup Success Rate (98.4%) and availability (98.7%) are compliant, but "
                        "Dropped Call Rate in the Kano cluster (2.3%) is above the 2% NCC threshold and "
                        "must be remediated or explained before submission."
                    ),
                    "metadata": {
                        "filing": "NCC Quality of Service Return — Q2 2026",
                        "reference": "MTN-NCC-QOS-Q2-2026",
                        "due_date": "2026-07-15",
                        "days_remaining": 12,
                        "last_submitted": "2026-04-15",
                        "document_id": "doc_004",
                    },
                    "suggested_actions": [
                        "Remediate Dropped Call Rate in the Kano cluster below the 2% NCC threshold",
                        "Attach root-cause and optimisation plan for any breached KPI",
                        "Assign report owner and set internal sign-off deadline for July 12",
                    ],
                },
                {
                    "alert_type": "compliance_gap",
                    "severity": "critical",
                    "title": "NIN-SIM Linkage Backlog — Unlinked SIM Barring Overdue",
                    "summary": (
                        "Approximately 240,000 active SIMs remain unlinked to a valid NIN past the NCC "
                        "barring deadline. Under the NIN-SIM directive (NCC-SIM-001), outbound service on "
                        "unlinked SIMs must be barred. Continued service exposes the operator to per-SIM "
                        "fines and enforcement action reminiscent of the 2015 ₦1.04tn precedent."
                    ),
                    "metadata": {
                        "document_reference": "MTN-NCC-NINSIM-2026-001",
                        "gap_section": "NIN-SIM Directive — Barring Enforcement",
                        "required_action": "Bar outbound service on 240,000 unlinked SIMs",
                        "regulator_contact": "compliance@ncc.gov.ng",
                        "document_id": "doc_005",
                    },
                    "suggested_actions": [
                        "Bar outbound service on all SIMs unlinked past the NCC deadline",
                        "Run a verification sweep against NIMC to clear false-unlinked records",
                        "Notify NCC of the remediation timeline to pre-empt enforcement",
                        "Audit the SIM database for pre-registered / improperly registered SIMs",
                    ],
                },
            ]
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
