"""
services/verdict_engine.py — Standardised GO / NO-GO / MONITOR verdict engine for Iroko AI.
============================================================================================
Every Iroko AI agent output is collapsed into one of three compliance verdicts before it
is surfaced to the user or written to the audit trail.

Verdict hierarchy (most → least restrictive):
    NO-GO   — compliance violation or very low confidence: escalate immediately.
    MONITOR — borderline or uncertain: flag for human review.
    GO      — confident, compliant, adequately signalled: proceed.

Architecture (inspired by ComplianceOS ``ClassifierVerdict`` pattern):
  - ``VerdictOutput``    — Pydantic model for FastAPI response typing.
  - ``VerdictEngine``    — Synchronous computation and formatting service.
      ├── ``compute_verdict``            pure rule evaluation
      ├── ``generate_recommended_actions`` context-aware action strings
      └── ``format_verdict_output``      full standardised output dict

Design constraints:
  - All public methods are synchronous (verdict computation is CPU-bound).
  - ``AuditService`` is NOT called here directly — callers log after calling
    this engine so they can provide their own db session.
  - Full type hints throughout.

Usage::

    from services.verdict_engine import verdict_engine

    verdict = verdict_engine.compute_verdict(
        confidence=0.82,
        compliance_result={"verdict": "GO", "compliant": True, "violations": []},
        signal_strength=4,
    )
    output = verdict_engine.format_verdict_output(
        finding={"summary": "Fintech lending exposure above CBN threshold — Q3 review due in 5 days."},
        verdict=verdict,
        sources=[{"title": "CBN Microfinance Policy Framework 2022", "url": "https://cbn.gov.ng/..."}],
        ncc_refs=["CBN-MFB-001"],
    )
    # → VerdictOutput-shaped dict ready for FastAPI response
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, List, Optional

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

# ── Verdict constants ─────────────────────────────────────────────────────────

_GO      = "GO"
_MONITOR = "MONITOR"
_NO_GO   = "NO-GO"

# Visual identity for each verdict (used in frontend rendering)
_VERDICT_COLOR: dict[str, str] = {
    _GO:      "#22c55e",   # green-500
    _MONITOR: "#f59e0b",   # amber-400
    _NO_GO:   "#ef4444",   # red-500
}

_VERDICT_LABEL: dict[str, str] = {
    _GO:      "✅ GO — Proceed with confidence",
    _MONITOR: "⚠️ MONITOR — Watch closely",
    _NO_GO:   "🚫 NO-GO — Action required",
}


# ── Pydantic output model ─────────────────────────────────────────────────────


class SourceRef(BaseModel):
    """A single evidence source linked from the verdict output."""
    title: str = Field(description="Display title of the source document or page.")
    url: str   = Field(description="URL of the source. May be empty string if unavailable.")


class VerdictOutput(BaseModel):
    """
    Standardised Iroko AI verdict output — used as FastAPI response model.

    Attributes
    ----------
    verdict : str
        One of ``"GO"``, ``"NO-GO"``, ``"MONITOR"``.
    verdict_color : str
        Hex colour for frontend badge rendering.
    verdict_label : str
        Human-readable label with emoji prefix.
    summary : str
        Agent finding or decision summary.
    confidence_score : float
        Agent confidence in the underlying finding (0.0–1.0).
    sources : list[SourceRef]
        Evidence sources that informed the finding.
    ncc_references : list[str]
        CBN/SEC regulation IDs referenced (e.g. ``["CBN-MFB-001", "CBN-PSB-002"]``).
    recommended_actions : list[str]
        Three contextual action strings generated from the verdict + finding.
    downloadable_brief : bool
        Flag indicating that a PDF compliance brief can be generated for this output.
    generated_at : str
        ISO-8601 UTC timestamp of when this verdict was produced.
    compliant : bool
        Whether the finding passed compliance checks.
    violations : list[dict]
        List of compliance violations if any.
    """
    verdict:              str              = Field(description="GO | NO-GO | MONITOR")
    verdict_color:        str              = Field(description="Hex colour for badge.")
    verdict_label:        str              = Field(description="Human-readable verdict label.")
    summary:              str              = Field(default="", description="Agent finding summary.")
    confidence_score:     float            = Field(default=0.0, ge=0.0, le=1.0)
    sources:              List[SourceRef]  = Field(default_factory=list)
    ncc_references:       List[str]        = Field(default_factory=list)
    ncc_refs:             List[str]        = Field(default_factory=list)
    recommended_actions:  List[str]        = Field(default_factory=list)
    downloadable_brief:   bool             = Field(default=True)
    generated_at:         str              = Field(default="")
    compliant:            bool             = Field(default=True)
    violations:           List[dict]       = Field(default_factory=list)

    model_config = {"populate_by_name": True}


# ── Verdict engine ────────────────────────────────────────────────────────────


class VerdictEngine:
    """
    Synchronous engine that standardises all Iroko AI agent outputs into
    GO / NO-GO / MONITOR verdicts and formats them for API responses.

    All methods are pure / synchronous — async is not needed for rule
    evaluation and formatting. Callers that need to persist the verdict
    should call ``AuditService.log_decision()`` with the returned verdict
    string after this engine returns.
    """

    # ── 1. Compute verdict ────────────────────────────────────────────────────

    def compute_verdict(
        self,
        confidence: float,
        compliance_result: dict[str, Any],
        signal_strength: int,
    ) -> str:
        """
        Evaluate confidence, compliance, and signal strength into a single verdict.

        Rule evaluation order (first rule that matches wins):

        1. **Hard NO-GO**: ``compliance_result["verdict"] == "NO-GO"``
           → always ``"NO-GO"`` regardless of confidence or signal strength.
           Regulatory violations are non-negotiable.

        2. **GO**: ``confidence >= 0.75`` **AND** ``compliance_result["compliant"]``
           **AND** ``signal_strength >= 3``
           → ``"GO"`` — confident, compliant, adequately corroborated.

        3. **MONITOR**: ``confidence >= 0.50`` **AND** ``compliance_result["compliant"]``
           → ``"MONITOR"`` — acceptable confidence but borderline; flag for review.

        4. **Default**: all other cases → ``"NO-GO"``.

        Parameters
        ----------
        confidence : float
            Agent confidence score in the underlying finding (0.0–1.0).
        compliance_result : dict
            Output of ``NCCLiveRulesService.check_decision_against_rules()``
            or equivalent. Must contain keys:
              ``"verdict"`` (str: "GO"|"NO-GO"|"MONITOR") and
              ``"compliant"`` (bool).
        signal_strength : int
            Number of corroborating data signals (e.g. matching SERP results,
            web intelligence hits, cross-referencing sources). Ranges: 0–10+.

        Returns
        -------
        str
            ``"GO"``, ``"NO-GO"``, or ``"MONITOR"``.
        """
        compliance_verdict = compliance_result.get("verdict", _MONITOR)
        compliant          = bool(compliance_result.get("compliant", False))

        # Rule 1: hard NO-GO from compliance layer — always overrides
        if compliance_verdict == _NO_GO:
            logger.info(
                "[VerdictEngine] Rule 1 (hard NO-GO): compliance_result.verdict=NO-GO → NO-GO"
            )
            return _NO_GO

        # Rule 2: GO — all three gates pass
        if confidence >= 0.75 and compliant and signal_strength >= 3:
            logger.info(
                "[VerdictEngine] Rule 2 (GO): confidence=%.2f compliant=%s signal_strength=%d → GO",
                confidence, compliant, signal_strength,
            )
            return _GO

        # Rule 3: MONITOR — acceptable confidence, compliant, but weak signal
        if confidence >= 0.50 and compliant:
            logger.info(
                "[VerdictEngine] Rule 3 (MONITOR): confidence=%.2f compliant=%s → MONITOR",
                confidence, compliant,
            )
            return _MONITOR

        # Rule 4: default — all other cases
        logger.info(
            "[VerdictEngine] Rule 4 (default NO-GO): confidence=%.2f compliant=%s signal=%d → NO-GO",
            confidence, compliant, signal_strength,
        )
        return _NO_GO

    # ── 2. Generate recommended actions ──────────────────────────────────────

    def generate_recommended_actions(
        self,
        verdict: str,
        finding: dict[str, Any],
    ) -> list[str]:
        """
        Generate three contextual recommended action strings based on verdict
        and the content of the agent finding.

        Parameters
        ----------
        verdict : str
            ``"GO"``, ``"NO-GO"``, or ``"MONITOR"``.
        finding : dict
            Agent finding dict. May contain keys such as ``"summary"``,
            ``"action_type"``, ``"ncc_regulation_ref"``, ``"source_url"``.

        Returns
        -------
        list[str]
            Exactly three action strings (may be fewer if context is missing).
        """
        action_type = finding.get("action_type", "")
        ncc_ref     = finding.get("ncc_regulation_ref", "") or finding.get("ncc_ref", "")
        source_url  = finding.get("source_url", "")
        summary     = finding.get("summary", "")

        # Build context tokens for action personalisation
        _ref_clause    = f" (ref: {ncc_ref})" if ncc_ref else ""
        _source_clause = f" — review source: {source_url}" if source_url else ""

        if verdict == _GO:
            return [
                f"Proceed with the planned action{_ref_clause} — CBN compliance gate passed.",
                "Document this decision in the compliance log with a GO stamp for auditor review.",
                (
                    "Schedule a follow-up review in 30 days to confirm continued compliance "
                    "with any new CBN/SEC enforcement notices."
                ),
            ]

        if verdict == _MONITOR:
            escalation_note = (
                f"related to {action_type}" if action_type else "flagged by Iroko AI"
            )
            return [
                (
                    f"Place the decision {escalation_note} under enhanced monitoring — "
                    f"assign a compliance owner and set a 48-hour review deadline."
                ),
                (
                    f"Cross-check against the latest CBN/SEC enforcement register{_ref_clause} "
                    f"before proceeding{_source_clause}."
                ),
                (
                    "Escalate to the Regulatory Affairs team if signal confidence does not "
                    "improve after the next intelligence sweep. Do not proceed unilaterally."
                ),
            ]

        # NO-GO
        immediate_action = (
            f"Halt the planned action immediately — a CBN compliance violation has been "
            f"detected{_ref_clause}."
        )
        notify_action = (
            "Notify the Chief Compliance Officer and CBN/SEC Regulatory Affairs team within "
            "24 hours as required under applicable fintech licensing obligations."
        )
        remediation_action = (
            f"Initiate a formal regulatory risk assessment{_ref_clause} and document the "
            f"breach in the AuditTrail with a NO-GO verdict. "
            f"{'Attach evidence from: ' + source_url if source_url else 'Attach all available evidence.'}"
        )
        return [immediate_action, notify_action, remediation_action]

    # ── 3. Format full verdict output ─────────────────────────────────────────

    def format_verdict_output(
        self,
        finding: dict[str, Any],
        verdict: str,
        sources: list[dict[str, str]],
        ncc_refs: list[str],
        confidence_score: Optional[float] = None,
        compliant: bool = True,
        violations: Optional[list[dict]] = None,
    ) -> dict[str, Any]:
        """
        Format any agent finding into the standard Iroko AI output structure.

        Intended for direct use as a FastAPI response body (matches
        ``VerdictOutput`` schema) or as the ``output`` field of an
        ``AgentRun`` row.

        Parameters
        ----------
        finding : dict
            Agent finding. Must contain ``"summary"`` key; may also contain
            ``"confidence_score"``, ``"action_type"``, ``"ncc_regulation_ref"``,
            ``"source_url"``.
        verdict : str
            Pre-computed verdict from ``compute_verdict()``.
        sources : list[dict]
            List of ``{"title": str, "url": str}`` evidence sources.
        ncc_refs : list[str]
            NCC regulation ID strings to cite, e.g. ``["NCC-003", "NCC-001"]``.
        confidence_score : float, optional
            Override confidence score. Falls back to ``finding["confidence_score"]``
            or ``0.0``.
        compliant : bool
            Whether the finding passed compliance checks.
        violations : list[dict], optional
            List of compliance violations.

        Returns
        -------
        dict
            A ``VerdictOutput``-shaped dictionary. Validated against the
            Pydantic model but returned as a plain dict for JSON serialisation
            compatibility.
        """
        # Normalise verdict to allowed values
        if verdict not in (_GO, _MONITOR, _NO_GO):
            logger.warning(
                "[VerdictEngine] Unknown verdict '%s' — coercing to MONITOR", verdict
            )
            verdict = _MONITOR

        # Resolve confidence
        resolved_confidence: float = confidence_score if confidence_score is not None else float(
            finding.get("confidence_score", 0.0) or 0.0
        )

        # Normalise sources to SourceRef shape
        normalised_sources: list[dict[str, str]] = []
        for s in (sources or []):
            if isinstance(s, dict):
                normalised_sources.append({
                    "title": str(s.get("title", "")),
                    "url":   str(s.get("url", "")),
                })

        # Generate contextual recommended actions
        actions = self.generate_recommended_actions(verdict, finding)

        output: dict[str, Any] = {
            "verdict":             verdict,
            "verdict_color":       _VERDICT_COLOR.get(verdict, "#6b7280"),
            "verdict_label":       _VERDICT_LABEL.get(verdict, verdict),
            "summary":             finding.get("summary", ""),
            "confidence_score":    round(resolved_confidence, 4),
            "sources":             normalised_sources,
            "ncc_references":      list(ncc_refs or []),
            "ncc_refs":            list(ncc_refs or []),
            "recommended_actions": actions,
            "downloadable_brief":  True,
            "generated_at":        datetime.now(tz=timezone.utc).isoformat(),
            "compliant":           compliant,
            "violations":          violations or [],
        }

        logger.info(
            "[VerdictEngine] format_verdict_output: verdict=%s confidence=%.2f "
            "sources=%d ncc_refs=%s",
            verdict,
            resolved_confidence,
            len(normalised_sources),
            ncc_refs,
        )

        return output

    # ── 4. Convenience: compute + format in one call ──────────────────────────

    def evaluate(
        self,
        finding: dict[str, Any],
        compliance_result: dict[str, Any],
        sources: list[dict[str, str]],
        ncc_refs: list[str],
        confidence: Optional[float] = None,
        signal_strength: int = 0,
    ) -> dict[str, Any]:
        """
        Convenience method: ``compute_verdict`` + ``format_verdict_output`` in
        a single call.

        Parameters
        ----------
        finding : dict
            Agent finding dict (must include ``"summary"``).
        compliance_result : dict
            Output of ``NCCLiveRulesService.check_decision_against_rules()``.
        sources : list[dict]
            Evidence sources.
        ncc_refs : list[str]
            NCC regulation references.
        confidence : float, optional
            Confidence score override. Falls back to ``finding["confidence_score"]``.
        signal_strength : int
            Number of corroborating signals.

        Returns
        -------
        dict
            Full ``VerdictOutput``-shaped dict.
        """
        resolved_confidence: float = confidence if confidence is not None else float(
            finding.get("confidence_score", 0.0) or 0.0
        )

        verdict = self.compute_verdict(
            confidence=resolved_confidence,
            compliance_result=compliance_result,
            signal_strength=signal_strength,
        )

        compliant = compliance_result.get("compliant", True)
        violations = compliance_result.get("violations", [])

        return self.format_verdict_output(
            finding=finding,
            verdict=verdict,
            sources=sources,
            ncc_refs=ncc_refs,
            confidence_score=resolved_confidence,
            compliant=compliant,
            violations=violations,
        )


# ── Module-level singleton ────────────────────────────────────────────────────

verdict_engine = VerdictEngine()
"""
Shared ``VerdictEngine`` singleton.

Import and use directly in agents and API routes::

    from services.verdict_engine import verdict_engine, VerdictOutput

    verdict = verdict_engine.compute_verdict(confidence, compliance_result, signal_strength)
    output  = verdict_engine.format_verdict_output(finding, verdict, sources, ncc_refs)

    # FastAPI endpoint:
    @router.get("/analysis", response_model=VerdictOutput)
    async def analyse() -> dict:
        ...
        return verdict_engine.evaluate(finding, compliance_result, sources, ncc_refs)
"""
