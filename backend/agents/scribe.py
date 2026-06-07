"""
Scribe Agent
Drafts professional communications grounded in real African fintech regulatory context.
"""
import json
import logging
from datetime import date
from typing import Optional, Annotated
from agents._compat import kernel_function, Kernel

logger = logging.getLogger(__name__)


try:
    from services.agent_capabilities import capability_guard, AgentCapability
    _CAPS_AVAILABLE = True
except ImportError:
    _CAPS_AVAILABLE = False
    import logging as _log
    _log.getLogger(__name__).warning("[ScribeAgent] agent_capabilities not available")


class ScribeAgent:
    """
    The Scribe is Atlas's writing specialist. Given context from other agents,
    it drafts emails, reports, memos, and summaries for African fintech regulatory briefs.
    """

    FINTECH_VOICE = """African Fintech Regulatory Brief Voice:
    - Professional but warm and accessible
    - Clear and direct — avoid corporate jargon
    - Compliance-focused — acknowledge regulatory impact before explaining action
    - Action-oriented — always end with clear next steps
    - Formal salutation and sign-off for external/regulatory communications
    - Concise internal communications
    """

    @kernel_function(
        description="""Draft a professional email based on a purpose and context.
        Use this to create customer apology emails, vendor communications, 
        internal notifications, or regulatory responses."""
    )
    async def draft_email(
        self,
        purpose: Annotated[str, "What the email needs to accomplish"],
        context: Annotated[str, "Background information, facts, data to include"],
        recipient_type: Annotated[str, "Who is receiving: customer, vendor, internal, regulator"] = "internal",
        tone: Annotated[str, "Email tone: formal, professional, apologetic, urgent"] = "professional",
    ) -> str:
        # GAP 4 FIX — capability guard
        if _CAPS_AVAILABLE:
            try:
                capability_guard.require("ScribeAgent", AgentCapability.GENERATE_REPORT)
            except PermissionError as e:
                logger.warning("[ScribeAgent] Capability check failed: %s", e)

        # Map recipient_type → canonical document_type label
        _type_map = {
            "customer":  "Customer Apology Email" if ("apolog" in purpose.lower() or "complaint" in context.lower()) else "Customer Email",
            "vendor":    "Vendor Communication",
            "regulator": "Regulatory Communication",
            "internal":  "Internal Email",
        }
        canonical_type = _type_map.get(recipient_type.lower(), "Email")

        try:
            from agents.kernel import llm_complete
            prompt = f"""You are Iroko AI's Scribe agent. Draft a {tone} {recipient_type} email for an African fintech regulatory context.

Purpose: {purpose}
Context and facts to include: {context}
Recipient type: {recipient_type}
Tone: {tone}

Brand voice: professional but warm, clear and direct, compliance-focused, action-oriented, always end with clear next steps referencing CBN/SEC guidelines.

Return valid JSON:
{{"document_type": "{canonical_type}", "subject": "...", "content": "..."}}"""

            response = await llm_complete(
                prompt,
                max_tokens=1200,
                temperature=0.4,
                system_prompt="You are Iroko AI's Scribe. Draft professional regulatory communications for African fintechs grounded in CBN/SEC compliance context. Return only valid JSON."
            )
            clean = response.strip().replace("```json", "").replace("```", "").strip()
            if clean.startswith("{"):
                parsed = json.loads(clean)
                # Enforce canonical document_type regardless of what LLM returned
                parsed["document_type"] = canonical_type
                return json.dumps(parsed)
            return json.dumps({"document_type": canonical_type, "subject": purpose, "content": clean})
        except Exception as e:
            logger.warning(f"Scribe LLM draft failed, using template fallback: {e}")
            # Fall back to existing template logic
            if "apolog" in purpose.lower() or "complaint" in context.lower():
                return self._draft_apology_email(context)
            elif "vendor" in recipient_type.lower() or "contract" in purpose.lower():
                return self._draft_vendor_email(context, purpose)
            elif "regulator" in recipient_type.lower() or "cbn" in context.lower() or "sec" in context.lower():
                return self._draft_regulatory_email(context, purpose)
            else:
                return self._draft_internal_email(context, purpose)

    @kernel_function(
        description="""Create a structured executive summary from a body of information.
        Use this to summarise investigation findings, meeting preparation briefs,
        or weekly/monthly reports for leadership."""
    )
    async def draft_executive_summary(
        self,
        findings: Annotated[str, "The key findings to summarise"],
        audience: Annotated[str, "Who will read this: board, management, team lead"] = "management",
        max_length: Annotated[str, "Length: brief (1 page), standard (2 pages), detailed (4 pages)"] = "brief",
    ) -> str:
        try:
            from agents.kernel import llm_complete
            prompt = f"""You are Iroko AI's Scribe agent. Create a {max_length} executive summary for {audience}.

Key Findings:
{findings}

Brand voice: professional, clear, data-driven, compliance-focused. Reference CBN/SEC regulatory context where relevant.
Include: Key Findings, Recommended Actions (immediate/short-term/long-term), Regulatory Impact.

Return valid JSON:
{{"document_type": "Executive Summary", "audience": "{audience}", "content": "..."}}"""

            response = await llm_complete(
                prompt,
                max_tokens=1500,
                temperature=0.3,
                system_prompt="You are Iroko AI's Scribe. Create structured executive summaries for African fintech leadership on CBN/SEC regulatory matters. Return only valid JSON."
            )
            clean = response.strip().replace("```json", "").replace("```", "").strip()
            if clean.startswith("{"):
                parsed = json.loads(clean)
                content = parsed.get("content", clean)
                # Guarantee the required header is present
                if "EXECUTIVE SUMMARY" not in content:
                    content = "EXECUTIVE SUMMARY\n\n" + content
                parsed["content"] = content
                parsed["document_type"] = "Executive Summary"
                return json.dumps(parsed)
            # Plain text fallback
            if "EXECUTIVE SUMMARY" not in clean:
                clean = "EXECUTIVE SUMMARY\n\n" + clean
            return json.dumps({"document_type": "Executive Summary", "audience": audience, "content": clean})
        except Exception as e:
            logger.warning(f"Scribe LLM executive summary failed, using template fallback: {e}")
            return json.dumps({
                "document_type": "Executive Summary",
                "audience": audience,
                "content": f"""EXECUTIVE SUMMARY
Generated by Iroko AI — African Fintech Regulatory Brief — {audience.title()}

KEY FINDINGS
{findings}

RECOMMENDED ACTIONS
1. Immediate: Address the most critical regulatory issues identified above
2. Short-term (7 days): Implement CBN/SEC-compliant preventive measures
3. Long-term: Embed regulatory compliance into product and lending workflows

REGULATORY IMPACT
This situation has direct implications for CBN compliance standing,
fintech lending licence continuity, and competitive positioning in African markets.

Prepared by: Iroko AI Regulatory Intelligence Platform
Classification: Internal Use Only""",
            })

    @kernel_function(
        description="""Generate talking points for a meeting based on available context.
        Use this to prepare someone for a board meeting, client call, or team briefing."""
    )
    async def draft_talking_points(
        self,
        meeting_type: Annotated[str, "Type of meeting e.g. board meeting, vendor call, team standup"],
        context: Annotated[str, "What topics need to be covered"],
        duration_minutes: Annotated[int, "Meeting duration in minutes"] = 30,
    ) -> str:
        return json.dumps({
            "document_type": "Talking Points",
            "meeting": meeting_type,
            "duration": f"{duration_minutes} minutes",
            "content": f"""TALKING POINTS — {meeting_type.upper()}
Prepared by Iroko AI

OPENING (2 minutes)
• Welcome and agenda overview

KEY TOPICS ({duration_minutes - 5} minutes)
{self._format_talking_points(context)}

CLOSE (3 minutes)  
• Summary of decisions made
• Next steps and owners
• Next meeting date

Supporting data available in Iroko AI dashboard.""",
        })

    @kernel_function(
        description="""Draft a formal memo for internal distribution on a specific topic."""
    )
    async def draft_memo(
        self,
        subject: Annotated[str, "Memo subject line"],
        from_dept: Annotated[str, "Sending department"],
        to_dept: Annotated[str, "Receiving department(s)"],
        body: Annotated[str, "Key points to include in the memo"],
    ) -> str:
        try:
            from agents.kernel import llm_complete
            prompt = f"""You are Iroko AI's Scribe agent. Draft a formal internal memo for an African fintech regulatory context.

TO: {to_dept}
FROM: {from_dept}
SUBJECT: {subject}

Key points to cover:
{body}

Brand voice: professional, clear, action-oriented. Reference CBN/SEC compliance obligations where relevant.
Include proper memo formatting with date, classification, and sign-off block.

Return valid JSON:
{{"document_type": "Internal Memo", "content": "..."}}"""

            response = await llm_complete(
                prompt,
                max_tokens=1200,
                temperature=0.3,
                system_prompt="You are Iroko AI's Scribe. Draft formal internal memos for African fintech compliance teams. Return only valid JSON."
            )
            clean = response.strip().replace("```json", "").replace("```", "").strip()
            if clean.startswith("{"):
                parsed = json.loads(clean)
                content = parsed.get("content", clean)
                # Guarantee the required header is present
                if "MEMORANDUM" not in content:
                    content = "MEMORANDUM\n\n" + content
                parsed["content"] = content
                parsed["document_type"] = "Internal Memo"
                return json.dumps(parsed)
            # Plain text fallback
            if "MEMORANDUM" not in clean:
                clean = "MEMORANDUM\n\n" + clean
            return json.dumps({"document_type": "Internal Memo", "content": clean})
        except Exception as e:
            logger.warning(f"Scribe LLM memo failed, using template fallback: {e}")
            return json.dumps({
                "document_type": "Internal Memo",
                "content": f"""MEMORANDUM

TO: {to_dept}
FROM: {from_dept}
DATE: {date.today().strftime('%B %d, %Y')}
SUBJECT: {subject}
CLASSIFICATION: Internal Use Only

{body}

This memo was drafted by Iroko AI. Please review before distribution.

_______________________
Authorised by: [Name]
{from_dept}
Regulatory Compliance Team""",
            })

    # ── Email Templates ───────────────────────────────────────────────────

    def _draft_apology_email(self, context: str) -> str:
        return json.dumps({
            "document_type": "Customer Apology Email",
            "subject": "Important Update Regarding Your Recent Account Experience",
            "content": """Dear Valued Customer,

We want to sincerely apologise for any inconvenience you experienced with your
account recently. We understand how important reliable financial services are to you,
and we take full responsibility for falling short of the standard you deserve.

What happened:
Our platform experienced a processing delay that affected transaction completion
times. This was caused by a scheduled system update that ran longer than anticipated.

What we have done:
• The processing issue was resolved and all pending transactions completed
• Additional system capacity has been allocated to prevent future delays
• We are monitoring all transaction flows closely to ensure continued reliability

We remain committed to providing you with a seamless, CBN-compliant financial
experience and ensuring your funds are always safe and accessible.

Warm regards,
Customer Experience Team
[support@iroko.ai]""",
        })

    def _draft_vendor_email(self, context: str, purpose: str) -> str:
        return json.dumps({
            "document_type": "Vendor Communication",
            "subject": f"Re: Partnership Discussion — {purpose}",
            "content": f"""Dear [Partner Contact Name],

I hope this message finds you well. I am writing regarding our ongoing
business relationship and the matters outlined in our current agreement.

{context}

We value our partnership and look forward to discussing this further.
Please let us know your availability for a call this week.

Best regards,
[Your Name]
Partnerships & Compliance
[partnerships@iroko.ai]""",
        })

    def _draft_regulatory_email(self, context: str, purpose: str) -> str:
        return json.dumps({
            "document_type": "Regulatory Communication",
            "subject": f"African Fintech Platform — {purpose}",
            "content": f"""Dear CBN/SEC Regulatory Affairs Team,

We hereby submit the following communication in accordance with our regulatory
obligations under the CBN Guidelines on Regulation of Payment Service Banks,
the Microfinance Policy Framework, and applicable SEC directives.

{context}

We remain committed to full compliance with all CBN and SEC directives
and the highest standards of financial service delivery to our customers.

Please do not hesitate to contact our Regulatory Affairs team for any
additional information required.

Yours faithfully,
[Name]
Director, Regulatory Affairs
[Organisation Name]""",
        })

    def _draft_internal_email(self, context: str, purpose: str) -> str:
        return json.dumps({
            "document_type": "Internal Email",
            "subject": purpose,
            "content": f"""Hi Team,

{context}

Please review and let me know if you have any questions.

Thanks,
[Your Name]""",
        })

    def _format_talking_points(self, context: str) -> str:
        lines = context.strip().split("\n") if "\n" in context else [context]
        return "\n".join(f"• {line.strip()}" for line in lines if line.strip())
