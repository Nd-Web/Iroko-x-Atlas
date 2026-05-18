"""
Scribe Agent
Drafts professional communications grounded in real MTN document context.
"""
import json
import logging
from datetime import date
from typing import Optional, Annotated
from agents._compat import kernel_function, Kernel

logger = logging.getLogger(__name__)


class ScribeAgent:
    """
    The Scribe is Atlas's writing specialist. Given context from other agents,
    it drafts emails, reports, memos, and summaries in MTN's brand voice.
    """

    MTN_VOICE = """MTN Nigeria Brand Voice:
    - Professional but warm and accessible
    - Clear and direct — avoid corporate jargon
    - Customer-focused — acknowledge impact before explaining action
    - Action-oriented — always end with clear next steps
    - Formal salutation and sign-off for external communications
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
        try:
            from agents.kernel import llm_complete
            prompt = f"""You are Iroko AI's Scribe agent. Draft a {tone} {recipient_type} email for MTN Nigeria.

Purpose: {purpose}
Context and facts to include: {context}
Recipient type: {recipient_type}
Tone: {tone}

MTN Nigeria brand voice: professional but warm, clear and direct, customer-focused, action-oriented, always end with clear next steps.

Return valid JSON:
{{"document_type": "Email", "subject": "...", "content": "..."}}"""

            response = await llm_complete(
                prompt,
                max_tokens=1200,
                temperature=0.4,
                system_prompt="You are Iroko AI's Scribe. Draft professional communications for MTN Nigeria grounded in the provided context. Return only valid JSON."
            )
            clean = response.strip().replace("```json", "").replace("```", "").strip()
            return clean if clean.startswith("{") else json.dumps({
                "document_type": "Email",
                "subject": purpose,
                "content": clean,
            })
        except Exception as e:
            logger.warning(f"Scribe LLM draft failed, using template fallback: {e}")
            # Fall back to existing template logic
            if "apolog" in purpose.lower() or "complaint" in context.lower():
                return self._draft_apology_email(context)
            elif "vendor" in recipient_type.lower() or "contract" in purpose.lower():
                return self._draft_vendor_email(context, purpose)
            elif "regulator" in recipient_type.lower() or "ncc" in context.lower():
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

MTN Nigeria brand voice: professional, clear, data-driven.
Include: Key Findings, Recommended Actions (immediate/short-term/long-term), Business Impact.

Return valid JSON:
{{"document_type": "Executive Summary", "audience": "{audience}", "content": "..."}}"""

            response = await llm_complete(
                prompt,
                max_tokens=1500,
                temperature=0.3,
                system_prompt="You are Iroko AI's Scribe. Create structured executive summaries for MTN Nigeria leadership. Return only valid JSON."
            )
            clean = response.strip().replace("```json", "").replace("```", "").strip()
            return clean if clean.startswith("{") else json.dumps({
                "document_type": "Executive Summary",
                "audience": audience,
                "content": clean,
            })
        except Exception as e:
            logger.warning(f"Scribe LLM executive summary failed, using template fallback: {e}")
            return json.dumps({
                "document_type": "Executive Summary",
                "audience": audience,
                "content": f"""EXECUTIVE SUMMARY
Generated by Iroko AI — {audience.title()} Brief

KEY FINDINGS
{findings}

RECOMMENDED ACTIONS
1. Immediate: Address the most critical issues identified above
2. Short-term (7 days): Implement preventive measures
3. Long-term: Review processes to prevent recurrence

BUSINESS IMPACT
This situation has direct implications for customer satisfaction scores,
NCC compliance standing, and competitive positioning in the Lagos market.

Prepared by: Iroko AI Intelligence Platform
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
            prompt = f"""You are Iroko AI's Scribe agent. Draft a formal internal memo for MTN Nigeria.

TO: {to_dept}
FROM: {from_dept}
SUBJECT: {subject}

Key points to cover:
{body}

MTN Nigeria brand voice: professional, clear, action-oriented.
Include proper memo formatting with date, classification, and sign-off block.

Return valid JSON:
{{"document_type": "Internal Memo", "content": "..."}}"""

            response = await llm_complete(
                prompt,
                max_tokens=1200,
                temperature=0.3,
                system_prompt="You are Iroko AI's Scribe. Draft formal internal memos for MTN Nigeria. Return only valid JSON."
            )
            clean = response.strip().replace("```json", "").replace("```", "").strip()
            return clean if clean.startswith("{") else json.dumps({
                "document_type": "Internal Memo",
                "content": clean,
            })
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
MTN Nigeria""",
            })

    # ── Email Templates ───────────────────────────────────────────────────

    def _draft_apology_email(self, context: str) -> str:
        return json.dumps({
            "document_type": "Customer Apology Email",
            "subject": "Important Update Regarding Your Recent MTN Experience",
            "content": """Dear Valued Customer,

We want to sincerely apologise for the service disruption you experienced recently 
in the Lagos Zone 7 area. We understand how important reliable connectivity is to you, 
and we take full responsibility for falling short of the standard you deserve.

What happened:
Our network in the Ikeja area experienced capacity constraints between 6pm-9pm 
over the past few days, caused by unusually high traffic volume combined with 
scheduled maintenance on one of our towers.

What we have done:
• Emergency maintenance was completed on Tower 4471 as of this morning
• Additional capacity has been allocated to the Lagos Zone 7 area
• We are monitoring the network closely to prevent recurrence

As a token of our appreciation for your patience, we are crediting your account 
with 2GB of free data, valid for 30 days.

We remain committed to providing you with the best network experience in Nigeria.

Warm regards,
MTN Nigeria Customer Experience Team
[customercare@mtn.ng | 180 | @MTNNigeria]""",
        })

    def _draft_vendor_email(self, context: str, purpose: str) -> str:
        return json.dumps({
            "document_type": "Vendor Communication",
            "subject": f"Re: Contract Discussion — {purpose}",
            "content": f"""Dear [Vendor Contact Name],

I hope this message finds you well. I am writing regarding our ongoing 
business relationship and the matters outlined in our current agreement.

{context}

We value our partnership and look forward to discussing this further. 
Please let us know your availability for a call this week.

Best regards,
[Your Name]
Procurement Department
MTN Nigeria
[procurement@mtn.ng]""",
        })

    def _draft_regulatory_email(self, context: str, purpose: str) -> str:
        return json.dumps({
            "document_type": "Regulatory Communication",
            "subject": f"MTN Nigeria — {purpose}",
            "content": f"""Dear NCC Regulatory Affairs Team,

MTN Nigeria Limited hereby submits the following communication in accordance 
with our regulatory obligations under the Nigerian Communications Act 2003.

{context}

MTN Nigeria remains committed to full compliance with all NCC directives 
and the highest standards of telecommunications service delivery.

Please do not hesitate to contact our Regulatory Affairs team for any 
additional information required.

Yours faithfully,
[Name]
Director, Regulatory Affairs
MTN Nigeria Limited""",
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
