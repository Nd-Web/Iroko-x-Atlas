"""
services/boardroom_formatter.py — Executive language transformation for Agent 5 outputs.
"""
import logging
import json
from typing import Dict, Any

try:
    from agents.kernel import llm_complete
    LLM_AVAILABLE = True
except ImportError:
    LLM_AVAILABLE = False
    async def llm_complete(prompt, **kw): return ""

logger = logging.getLogger(__name__)

class BoardroomFormatter:
    """
    Transforms raw JSON outputs from Strategist (Agent 5) into executive-level
    language suitable for C-suite and boardroom presentations.
    """
    async def format_executive_summary(self, raw_result: Dict[str, Any], is_pidgin: bool = False) -> Dict[str, Any]:
        if not LLM_AVAILABLE:
            return raw_result
            
        answer = raw_result.get("answer", "")
        if not answer:
            return raw_result

        prompt = f"""You are the Boardroom Formatter for Iroko AI.
Your job is to rewrite the following agent analysis into a high-impact executive summary.
Focus on business impact, financial exposure, risk mitigation, and immediate actions.
Use a professional, authoritative tone suitable for the C-suite.

Original Analysis:
{answer}

Respond with only the rewritten executive text, using clear markdown formatting.
"""
        if is_pidgin:
            prompt += "\nIMPORTANT: The user requested Pidgin English. Maintain the executive tone but write in professional Nigerian Pidgin English."

        try:
            executive_answer = await llm_complete(
                prompt, 
                max_tokens=1500, 
                temperature=0.3,
                system_prompt="You are a senior executive communications director. Elevate the tone to C-suite level."
            )
            raw_result["executive_summary"] = executive_answer.strip()
            # Replace the main answer so the UI displays the formatted version directly
            raw_result["answer"] = executive_answer.strip()
            logger.info("[BoardroomFormatter] Successfully transformed answer into executive language.")
        except Exception as e:
            logger.warning(f"[BoardroomFormatter] Failed to format executive summary: {e}")
            
        return raw_result

boardroom_formatter = BoardroomFormatter()
