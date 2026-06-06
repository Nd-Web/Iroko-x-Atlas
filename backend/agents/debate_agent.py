"""
agents/debate_agent.py — Adversarial Sub-Agent Debate for Iroko AI.
=====================================================================
Implements the Diligence pattern: when a vendor risk signal is flagged,
two adversarial sub-agents debate whether it represents a genuine threat or
noise, and a senior reconciler scores both arguments to set final confidence.

Flow
----
                        ┌─────────────────┐
                        │   debate_signal  │
                        └────────┬────────┘
               asyncio.gather    │
           ┌─────────────────────┴─────────────────────┐
           ▼                                           ▼
    argue_threat()                              argue_noise()
  "Make the strongest                       "Make the strongest
   case this IS a threat"                    case this is noise"
           │                                           │
           └─────────────────────┬─────────────────────┘
                                 ▼
                           reconcile()
                  "Senior officer reads both sides,
                   returns confidence + verdict"
                                 │
                                 ▼
                    {"final_confidence": float,
                     "final_verdict": str, ...}

All three LLM calls are independent and purpose-prompted so they cannot
simply agree with each other — the threat analyst is instructed to argue
FOR the threat; the skeptic is instructed to argue AGAINST it.

Usage::

    from agents.debate_agent import debate_agent

    result = await debate_agent.debate_signal(
        signal={
            "title": "Huawei Nigeria executive arrested for bribery",
            "description": "Senior Huawei Nigeria director detained by EFCC ...",
        },
        context="Huawei is our primary RAN vendor for the South-West cluster.",
    )
    print(result["final_verdict"], result["final_confidence"])
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
from typing import Any

from agents.base_agent import BaseAgent

logger = logging.getLogger(__name__)

# ── LLM constants ─────────────────────────────────────────────────────────────

_DEBATE_TEMPERATURE  = 0.4   # slight creativity — better arguments
_TRIAGE_TEMPERATURE  = 0.2   # reconciler should be more deterministic
_MAX_TOKENS_ARGUE    = 600
_MAX_TOKENS_RECONCILE = 400

# ── JSON extraction helper ────────────────────────────────────────────────────

_JSON_FENCE_RE = re.compile(r"```(?:json)?(.*?)```", re.DOTALL)


def _extract_json(raw: str) -> dict:
    """
    Extract and parse the first JSON object from an LLM response string.

    Strips markdown fences if present, then attempts ``json.loads`` on the
    cleaned text.  Returns an empty dict on any parse failure.
    """
    # Try to strip a markdown fence first
    fence_match = _JSON_FENCE_RE.search(raw)
    text = fence_match.group(1).strip() if fence_match else raw.strip()

    # Find the first {...} block in case there is surrounding prose
    brace_start = text.find("{")
    brace_end   = text.rfind("}")
    if brace_start != -1 and brace_end != -1:
        text = text[brace_start : brace_end + 1]

    try:
        return json.loads(text)
    except (json.JSONDecodeError, ValueError):
        return {}


# ── Agent ─────────────────────────────────────────────────────────────────────


class ThreatDebateAgent(BaseAgent):
    """
    Adversarial debate agent that stress-tests vendor risk signals before
    committing to a final confidence score and verdict.

    Inherits ``_log_trace`` and ``_with_retry`` from ``BaseAgent``.
    """

    # ── 1. Argue THREAT ───────────────────────────────────────────────────────

    async def argue_threat(
        self,
        signal: dict[str, Any],
        context: str = "",
    ) -> dict[str, Any]:
        """
        LLM sub-agent that argues the signal IS a genuine threat.

        The agent is prompted to make the *strongest possible* affirmative
        case with three concrete, specific reasons.

        Parameters
        ----------
        signal : dict
            Signal dict with at least ``"title"`` and ``"description"`` keys.
        context : str, optional
            Additional domain context (e.g. vendor relationship details).

        Returns
        -------
        dict
            ::

                {
                    "position":         "THREAT",
                    "arguments":        list[str],          # 3 concrete reasons
                    "severity_estimate": "HIGH"|"MEDIUM"|"LOW",
                }

            Falls back to a default dict with empty arguments on LLM/parse
            failure so the debate can continue.
        """
        title       = signal.get("title", "")
        description = signal.get("description", signal.get("snippet", ""))

        prompt = (
            f"You are a risk analyst. Make the strongest possible case that this signal "
            f"represents a genuine threat: {title} — {description}. "
            f"Context: {context}. "
            "Give 3 specific reasons. Be concrete. "
            'Return JSON only: {"position": "THREAT", "arguments": ["reason1", "reason2", "reason3"], '
            '"severity_estimate": "HIGH"|"MEDIUM"|"LOW"}'
        )

        self._log_trace(
            "DebateAgent", "argue_threat",
            f"Building threat case for: {title[:80]}",
        )

        default: dict[str, Any] = {
            "position":          "THREAT",
            "arguments":         ["Insufficient LLM response — manual review required."],
            "severity_estimate": "MEDIUM",
        }

        try:
            from agents.kernel import llm_complete
            raw = await llm_complete(
                prompt,
                max_tokens=_MAX_TOKENS_ARGUE,
                temperature=_DEBATE_TEMPERATURE,
                system_prompt=(
                    "You are a diligent risk analyst building the strongest affirmative "
                    "threat case. Return valid JSON only — no prose, no markdown fences."
                ),
            )
            parsed = _extract_json(raw)
            if not parsed:
                logger.warning("[DebateAgent] argue_threat: JSON parse failed — using default")
                return default

            return {
                "position":          "THREAT",
                "arguments":         list(parsed.get("arguments", default["arguments"])),
                "severity_estimate": str(parsed.get("severity_estimate", "MEDIUM")).upper(),
            }

        except Exception as exc:
            logger.warning("[DebateAgent] argue_threat LLM call failed: %s", exc)
            return default

    # ── 2. Argue NOISE ────────────────────────────────────────────────────────

    async def argue_noise(
        self,
        signal: dict[str, Any],
        context: str = "",
    ) -> dict[str, Any]:
        """
        LLM sub-agent that argues the signal is noise / a false positive.

        The agent is prompted to be maximally skeptical and surface three
        concrete counter-arguments that would dismiss the signal.

        Parameters
        ----------
        signal : dict
            Signal dict with at least ``"title"`` and ``"description"`` keys.
        context : str, optional
            Additional domain context.

        Returns
        -------
        dict
            ::

                {
                    "position":          "NOISE",
                    "arguments":         list[str],   # 3 counter-arguments
                    "noise_probability": float,        # 0.0–1.0
                }

            Falls back to a safe default on LLM/parse failure.
        """
        title       = signal.get("title", "")
        description = signal.get("description", signal.get("snippet", ""))

        prompt = (
            f"You are a skeptical analyst. Make the strongest case that this signal "
            f"is NOT a real threat: {title} — {description}. "
            f"Context: {context}. "
            "Give 3 specific counter-arguments explaining why this is likely noise or a false positive. "
            'Return JSON only: {"position": "NOISE", "arguments": ["counter1", "counter2", "counter3"], '
            '"noise_probability": 0.0}'
        )

        self._log_trace(
            "DebateAgent", "argue_noise",
            f"Building noise case for: {title[:80]}",
        )

        default: dict[str, Any] = {
            "position":          "NOISE",
            "arguments":         ["Insufficient LLM response — manual review required."],
            "noise_probability": 0.5,
        }

        try:
            from agents.kernel import llm_complete
            raw = await llm_complete(
                prompt,
                max_tokens=_MAX_TOKENS_ARGUE,
                temperature=_DEBATE_TEMPERATURE,
                system_prompt=(
                    "You are a rigorous skeptical analyst challenging threat claims. "
                    "Return valid JSON only — no prose, no markdown fences."
                ),
            )
            parsed = _extract_json(raw)
            if not parsed:
                logger.warning("[DebateAgent] argue_noise: JSON parse failed — using default")
                return default

            raw_prob = parsed.get("noise_probability", 0.5)
            try:
                noise_prob = float(raw_prob)
                noise_prob = max(0.0, min(1.0, noise_prob))
            except (TypeError, ValueError):
                noise_prob = 0.5

            return {
                "position":          "NOISE",
                "arguments":         list(parsed.get("arguments", default["arguments"])),
                "noise_probability": round(noise_prob, 4),
            }

        except Exception as exc:
            logger.warning("[DebateAgent] argue_noise LLM call failed: %s", exc)
            return default

    # ── 3. Reconcile ──────────────────────────────────────────────────────────

    async def reconcile(
        self,
        threat_case: dict[str, Any],
        noise_case:  dict[str, Any],
        signal:      dict[str, Any],
    ) -> dict[str, Any]:
        """
        Senior reconciler that weighs both arguments and issues a final verdict.

        The reconciler is presented with the threat analyst's arguments and the
        skeptic's counter-arguments, and asked to rate confidence that the signal
        is a genuine threat requiring action.

        Parameters
        ----------
        threat_case : dict
            Output of ``argue_threat``.
        noise_case : dict
            Output of ``argue_noise``.
        signal : dict
            Original signal dict (for title context in the trace).

        Returns
        -------
        dict
            ::

                {
                    "confidence": float,                  # 0.0–1.0
                    "verdict":    "GO"|"NO-GO"|"MONITOR",
                    "rationale":  str,
                }

            Falls back to a MONITOR verdict at 0.5 confidence on failure.
        """
        threat_args = "\n".join(
            f"  {i+1}. {arg}" for i, arg in enumerate(threat_case.get("arguments", []))
        )
        noise_args  = "\n".join(
            f"  {i+1}. {arg}" for i, arg in enumerate(noise_case.get("arguments", []))
        )
        severity    = threat_case.get("severity_estimate", "MEDIUM")
        noise_prob  = noise_case.get("noise_probability", 0.5)

        prompt = (
            "You are a senior risk officer adjudicating a threat debate. "
            "You have heard two analysts argue about a signal.\n\n"
            f"Threat analyst argued ({severity} severity estimate):\n{threat_args}\n\n"
            f"Skeptic argued (noise probability estimate: {noise_prob:.0%}):\n{noise_args}\n\n"
            "Rate your confidence (0–1) that this is a real threat requiring action. "
            "Return JSON only: "
            '{"confidence": 0.0, "verdict": "GO"|"NO-GO"|"MONITOR", "rationale": "one sentence"}'
        )

        self._log_trace(
            "DebateAgent", "reconcile",
            f"Reconciling debate for: {signal.get('title', '')[:80]}",
        )

        default: dict[str, Any] = {
            "confidence": 0.5,
            "verdict":    "MONITOR",
            "rationale":  "Reconciliation failed — defaulting to MONITOR for manual review.",
        }

        try:
            from agents.kernel import llm_complete
            raw = await llm_complete(
                prompt,
                max_tokens=_MAX_TOKENS_RECONCILE,
                temperature=_TRIAGE_TEMPERATURE,
                system_prompt=(
                    "You are a decisive senior risk officer who reads both sides of a debate "
                    "and issues a clear, evidence-based verdict. "
                    "Return valid JSON only — no prose, no markdown fences."
                ),
            )
            parsed = _extract_json(raw)
            if not parsed:
                logger.warning("[DebateAgent] reconcile: JSON parse failed — using default")
                return default

            raw_conf = parsed.get("confidence", 0.5)
            try:
                confidence = float(raw_conf)
                confidence = max(0.0, min(1.0, confidence))
            except (TypeError, ValueError):
                confidence = 0.5

            verdict = str(parsed.get("verdict", "MONITOR")).upper()
            if verdict not in ("GO", "NO-GO", "MONITOR"):
                verdict = "MONITOR"

            return {
                "confidence": round(confidence, 4),
                "verdict":    verdict,
                "rationale":  str(parsed.get("rationale", default["rationale"])),
            }

        except Exception as exc:
            logger.warning("[DebateAgent] reconcile LLM call failed: %s", exc)
            return default

    # ── 4. Orchestrate the full debate ────────────────────────────────────────

    async def debate_signal(
        self,
        signal:  dict[str, Any],
        context: str = "",
    ) -> dict[str, Any]:
        """
        Orchestrate the full adversarial debate for a single vendor risk signal.

        ``argue_threat`` and ``argue_noise`` run **in parallel** via
        ``asyncio.gather``.  Their outputs feed ``reconcile``, which issues the
        final confidence score and verdict.  All three steps are logged to
        ``self.trace`` via ``_log_trace``.

        Parameters
        ----------
        signal : dict
            Vendor risk signal dict.  Expected keys: ``"title"``, ``"description"``
            (or ``"snippet"``).  Extra keys are preserved in the output.
        context : str, optional
            Domain context string injected into all three prompts (e.g. vendor
            relationship details, contract value, region).

        Returns
        -------
        dict
            ::

                {
                    "signal":          dict,    # original signal (unmodified)
                    "threat_case":     dict,    # argue_threat() output
                    "noise_case":      dict,    # argue_noise() output
                    "reconciliation":  dict,    # reconcile() output
                    "final_confidence": float,  # reconciliation["confidence"]
                    "final_verdict":   str,     # reconciliation["verdict"]
                }
        """
        title = signal.get("title", "<untitled signal>")

        self._log_trace(
            "DebateAgent", "debate_signal",
            f"Starting adversarial debate for signal: {title[:100]}",
        )

        # ── Parallel debate ───────────────────────────────────────────────────
        threat_case, noise_case = await asyncio.gather(
            self.argue_threat(signal, context=context),
            self.argue_noise(signal, context=context),
        )

        # ── Reconciliation ────────────────────────────────────────────────────
        reconciliation = await self.reconcile(threat_case, noise_case, signal)

        self._log_trace(
            "DebateAgent", "debate_signal",
            (
                f"Debate complete for '{title[:60]}': "
                f"verdict={reconciliation['verdict']} "
                f"confidence={reconciliation['confidence']:.2f} — "
                f"{reconciliation['rationale'][:120]}"
            ),
        )

        return {
            "signal":           signal,
            "threat_case":      threat_case,
            "noise_case":       noise_case,
            "reconciliation":   reconciliation,
            "final_confidence": reconciliation["confidence"],
            "final_verdict":    reconciliation["verdict"],
        }


# ── Module-level singleton ────────────────────────────────────────────────────

debate_agent = ThreatDebateAgent()
"""
Shared ``ThreatDebateAgent`` singleton.

Usage in agents and routes::

    from agents.debate_agent import debate_agent

    result = await debate_agent.debate_signal(
        signal={
            "title":       "Ericsson Nigeria fined for spectrum violations",
            "description": "NCC issued a ₦2bn fine to Ericsson Nigeria ...",
        },
        context="Ericsson supplies core network equipment for our Lagos cluster.",
    )
    if result["final_verdict"] == "NO-GO":
        # escalate immediately
        ...
"""
