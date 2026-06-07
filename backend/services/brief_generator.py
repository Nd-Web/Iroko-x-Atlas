# -*- coding: utf-8 -*-
"""
services/brief_generator.py — Professional PDF compliance brief generator for Iroko AI.
========================================================================================
Generates boardroom-quality, multi-page PDF reports as raw bytes.

Document types:
  1. ``generate_brief()``             — Detailed enterprise intelligence brief:
                                        Cover page, executive summary, CBN/SEC analysis,
                                        violations deep-dive, recommended actions,
                                        risk matrix, evidence sources, audit trail.
  2. ``generate_regulatory_digest()`` — Weekly regulatory digest from live CBN/SEC updates.

Design constraints:
  - Font: Helvetica only (always available in ReportLab, no external fonts needed).
  - Page: A4, multi-page with running headers/footers.
  - Emojis stripped from labels (Helvetica cannot render Unicode emoji).
  - All text passed through ``_esc()`` before entering Paragraph flowables.
  - Returns ``bytes`` only — never writes to disk.
"""

from __future__ import annotations

import io
import logging
import re
from datetime import datetime, timezone
from typing import Any, Optional
from xml.sax.saxutils import escape as _xml_escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT, TA_JUSTIFY
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm, mm
from reportlab.platypus import (
    HRFlowable,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
    PageBreak,
    KeepTogether,
)
from reportlab.platypus.flowables import HRFlowable
from reportlab.lib.utils import simpleSplit

logger = logging.getLogger(__name__)

# ── Brand colours ─────────────────────────────────────────────────────────────

_C_NAVY      = colors.HexColor("#0f172a")   # slate-900 — header bar
_C_BLUE      = colors.HexColor("#1d4ed8")   # brand blue
_C_BLUE_LITE = colors.HexColor("#3b7bf6")   # brand blue light
_C_GO        = colors.HexColor("#16a34a")   # green-600
_C_GO_BG     = colors.HexColor("#f0fdf4")   # green-50
_C_MONITOR   = colors.HexColor("#d97706")   # amber-600
_C_MONITOR_BG= colors.HexColor("#fffbeb")   # amber-50
_C_NO_GO     = colors.HexColor("#dc2626")   # red-600
_C_NO_GO_BG  = colors.HexColor("#fef2f2")   # red-50
_C_WHITE     = colors.white
_C_LIGHT     = colors.HexColor("#f8fafc")   # slate-50 — alternating rows
_C_BORDER    = colors.HexColor("#e2e8f0")   # slate-200 — table grid
_C_MUTED     = colors.HexColor("#64748b")   # slate-500 — captions/footer
_C_DARK_TEXT = colors.HexColor("#1e293b")   # slate-800 — body text
_C_SECTION   = colors.HexColor("#334155")   # slate-700 — section headings
_C_ACCENT    = colors.HexColor("#e0f2fe")   # sky-100 — info boxes
_C_ACCENT_BORDER = colors.HexColor("#7dd3fc") # sky-300

_VERDICT_COLOR_MAP: dict[str, Any] = {
    "GO":      _C_GO,
    "MONITOR": _C_MONITOR,
    "NO-GO":   _C_NO_GO,
}

_VERDICT_BG_MAP: dict[str, Any] = {
    "GO":      _C_GO_BG,
    "MONITOR": _C_MONITOR_BG,
    "NO-GO":   _C_NO_GO_BG,
}

_VERDICT_LABEL_MAP: dict[str, str] = {
    "GO":      "GO  --  Proceed with confidence",
    "MONITOR": "MONITOR  --  Flag for regulatory review",
    "NO-GO":   "NO-GO  --  Action required immediately",
}

# ── Internal helpers ──────────────────────────────────────────────────────────

def _esc(value: Any) -> str:
    """
    Escape any value for safe embedding in a ReportLab Paragraph XML context.
    Strips emoji / non-BMP characters that Helvetica cannot render, then
    XML-escapes ``<``, ``>``, ``&``.
    """
    text = str(value) if value is not None else ""
    text = re.sub(r"[^\u0000-\uFFFF]", "", text)
    text = re.sub(r"[\u2000-\u206F\u2700-\u27BF\uFE00-\uFE0F]", "", text)
    return _xml_escape(text)


def _now_display() -> str:
    """Return a human-readable UTC timestamp string."""
    return datetime.now(tz=timezone.utc).strftime("%d %B %Y  %H:%M UTC")


def _verdict_color(verdict: str) -> Any:
    return _VERDICT_COLOR_MAP.get(verdict.upper(), _C_MONITOR)


def _verdict_bg(verdict: str) -> Any:
    return _VERDICT_BG_MAP.get(verdict.upper(), _C_MONITOR_BG)


def _verdict_label(verdict: str) -> str:
    return _VERDICT_LABEL_MAP.get(verdict.upper(), verdict)


# ── CBN/SEC Regulation registry (variable name retained for backward compat) ──

_NCC_REGISTRY: dict[str, dict] = {
    "CBN-MFB-001": {
        "name":    "CBN MFB Guidelines 2022 — Capital Adequacy",
        "section": "Section 5.1",
        "penalty": "CBN administrative fine up to ₦2 billion (BOFIA 2020 s.12)",
        "detail":  (
            "All MFBs must maintain a minimum Capital Adequacy Ratio of 10% of risk-weighted assets. "
            "CAR breaches must be reported immediately to CBN — do not wait for the quarterly return cycle. "
            "CBN may direct recapitalisation, impose fines, or suspend directors for non-compliance."
        ),
    },
    "CBN-AML-001": {
        "name":    "CBN AML/CFT Regulations 2022",
        "section": "Sections 15 & 18",
        "penalty": "₦10M per STR violation; ₦100M+ for systemic failure",
        "detail":  (
            "Requires STR filing within 24 hours of detecting suspicious transactions. "
            "Quarterly AML/CFT returns due by the 15th of the month following each quarter. "
            "Failure to file or filing inaccurate returns constitutes a regulatory offence."
        ),
    },
    "CBN-PSB-001": {
        "name":    "CBN PSB Regulatory Framework 2020",
        "section": "Section 4 — Capital & Wallet Limits",
        "penalty": "CBN directive + ₦1-2bn undercapitalisation fine",
        "detail":  (
            "PSBs must maintain paid-up capital ≥ ₦5 billion. "
            "Customer wallet balances capped at ₦500,000 with ₦500,000 daily transaction limit. "
            "PSBs are fully liable for agent misconduct — agent fraud liability rests with the PSB."
        ),
    },
    "CBN-CAR-001": {
        "name":    "BOFIA 2020 — Prudential Enforcement",
        "section": "Section 12 (Sanctions) & Section 33 (Revocation)",
        "penalty": "Up to ₦2 billion per violation; licence revocation for systemic breach",
        "detail":  (
            "CBN may impose fines up to ₦2 billion on any licensed institution for non-compliance "
            "with any CBN directive, guideline, or regulation. Director disqualification and personal "
            "liability apply for governance failures. Licence revocation is available for systemic breach."
        ),
    },
    "CBN-ENF-001": {
        "name":    "CBN Consumer Protection Framework 2022",
        "section": "Section 3 — Complaint Resolution & Disclosure",
        "penalty": "₦1M/day unreversed deductions; ₦50-100M systemic failure",
        "detail":  (
            "All digital lenders must disclose APR and total repayment upfront. "
            "Complaints must be acknowledged in 24 hours and resolved within 7 business days. "
            "Unauthorised deductions must be reversed within 24 hours of customer report."
        ),
    },
    "SEC-001": {
        "name":    "SEC Fintech Regulatory Incubator Framework 2024",
        "section": "Section 2 — VASP Registration",
        "penalty": "₦50M fine + operations suspension for unregistered VASPs",
        "detail":  (
            "Digital asset service providers must register with SEC before offering services. "
            "Crowdfunding platforms: maximum raise ₦1 billion per issuer per year. "
            "Annual SEC renewal with updated AML/CFT compliance evidence required."
        ),
    },
}


def _ncc_detail(reg_id: str) -> dict:
    """Return full CBN/SEC regulation metadata for a given ID."""
    return _NCC_REGISTRY.get(reg_id, {
        "name":    "CBN/SEC Regulation",
        "section": "See CBN/SEC Enforcement Register",
        "penalty": "Review CBN/SEC enforcement register for penalty details",
        "detail":  "Consult the CBN (cbn.gov.ng) or SEC (sec.gov.ng) enforcement register for full details of this regulation and applicable penalties.",
    })


# ── Style factory ─────────────────────────────────────────────────────────────

def _build_styles() -> dict[str, ParagraphStyle]:
    """Build and return a reusable style dictionary."""
    base = getSampleStyleSheet()

    def ps(name: str, **kw) -> ParagraphStyle:
        return ParagraphStyle(name, parent=base["Normal"], **kw)

    return {
        # Cover
        "cover_title": ps(
            "CoverTitle",
            fontName="Helvetica-Bold",
            fontSize=28,
            leading=36,
            textColor=_C_WHITE,
            alignment=TA_CENTER,
            spaceAfter=8,
        ),
        "cover_sub": ps(
            "CoverSub",
            fontName="Helvetica",
            fontSize=13,
            leading=18,
            textColor=colors.HexColor("#cbd5e1"),
            alignment=TA_CENTER,
            spaceAfter=4,
        ),
        "cover_meta": ps(
            "CoverMeta",
            fontName="Helvetica",
            fontSize=10,
            textColor=colors.HexColor("#94a3b8"),
            alignment=TA_CENTER,
        ),
        # Document headers
        "doc_title": ps(
            "DocTitle",
            fontName="Helvetica-Bold",
            fontSize=20,
            leading=26,
            textColor=_C_NAVY,
            spaceAfter=4,
        ),
        "subtitle": ps(
            "Subtitle",
            fontName="Helvetica",
            fontSize=10,
            textColor=_C_MUTED,
            spaceAfter=10,
        ),
        "header_left": ps(
            "HeaderLeft",
            fontName="Helvetica-Bold",
            fontSize=9,
            textColor=_C_NAVY,
            alignment=TA_LEFT,
        ),
        "header_right": ps(
            "HeaderRight",
            fontName="Helvetica-Bold",
            fontSize=9,
            textColor=_C_MUTED,
            alignment=TA_RIGHT,
        ),
        # Section headings
        "section_h1": ps(
            "SectionH1",
            fontName="Helvetica-Bold",
            fontSize=14,
            leading=18,
            textColor=_C_NAVY,
            spaceBefore=18,
            spaceAfter=6,
        ),
        "section_h2": ps(
            "SectionH2",
            fontName="Helvetica-Bold",
            fontSize=11,
            leading=15,
            textColor=_C_SECTION,
            spaceBefore=12,
            spaceAfter=4,
        ),
        "section_h3": ps(
            "SectionH3",
            fontName="Helvetica-Bold",
            fontSize=10,
            leading=14,
            textColor=_C_DARK_TEXT,
            spaceBefore=8,
            spaceAfter=3,
        ),
        # Body text
        "body": ps(
            "Body",
            fontName="Helvetica",
            fontSize=9.5,
            leading=15,
            textColor=_C_DARK_TEXT,
            spaceAfter=6,
            alignment=TA_JUSTIFY,
        ),
        "body_small": ps(
            "BodySmall",
            fontName="Helvetica",
            fontSize=8.5,
            leading=13,
            textColor=_C_MUTED,
            spaceAfter=3,
        ),
        "body_italic": ps(
            "BodyItalic",
            fontName="Helvetica-Oblique",
            fontSize=9.5,
            leading=15,
            textColor=_C_SECTION,
            spaceAfter=6,
            leftIndent=12,
            rightIndent=12,
            alignment=TA_JUSTIFY,
        ),
        # Verdict
        "verdict_label": ps(
            "VerdictLabel",
            fontName="Helvetica-Bold",
            fontSize=18,
            textColor=_C_WHITE,
            alignment=TA_CENTER,
        ),
        "verdict_confidence": ps(
            "VerdictConfidence",
            fontName="Helvetica-Bold",
            fontSize=11,
            textColor=_C_WHITE,
            alignment=TA_CENTER,
        ),
        # Tables
        "table_header_text": ps(
            "TableHeaderText",
            fontName="Helvetica-Bold",
            fontSize=8,
            textColor=_C_WHITE,
        ),
        "table_cell": ps(
            "TableCell",
            fontName="Helvetica",
            fontSize=8.5,
            leading=12,
            textColor=_C_DARK_TEXT,
        ),
        "table_cell_mono": ps(
            "TableCellMono",
            fontName="Helvetica-Bold",
            fontSize=8,
            textColor=_C_BLUE,
        ),
        "table_cell_red": ps(
            "TableCellRed",
            fontName="Helvetica-Bold",
            fontSize=8.5,
            textColor=_C_NO_GO,
        ),
        # Action items
        "action_num": ps(
            "ActionNum",
            fontName="Helvetica-Bold",
            fontSize=9.5,
            textColor=_C_BLUE,
        ),
        "action_text": ps(
            "ActionText",
            fontName="Helvetica",
            fontSize=9.5,
            leading=14,
            textColor=_C_DARK_TEXT,
            spaceAfter=5,
            leftIndent=18,
        ),
        # Footer
        "footer": ps(
            "Footer",
            fontName="Helvetica",
            fontSize=7,
            textColor=_C_MUTED,
            alignment=TA_CENTER,
        ),
        "confidential_stamp": ps(
            "ConfidentialStamp",
            fontName="Helvetica-Bold",
            fontSize=8,
            textColor=_C_NO_GO,
            alignment=TA_RIGHT,
        ),
        # Info box
        "info_box_text": ps(
            "InfoBoxText",
            fontName="Helvetica",
            fontSize=9,
            leading=14,
            textColor=_C_DARK_TEXT,
        ),
    }


# ── Table style helpers ───────────────────────────────────────────────────────

def _dark_table_style(header_color: Any = _C_NAVY, zebra: bool = True) -> TableStyle:
    cmds = [
        ("BACKGROUND",    (0, 0), (-1, 0),  header_color),
        ("TEXTCOLOR",     (0, 0), (-1, 0),  _C_WHITE),
        ("FONTNAME",      (0, 0), (-1, 0),  "Helvetica-Bold"),
        ("FONTSIZE",      (0, 0), (-1, 0),  8),
        ("FONTNAME",      (0, 1), (-1, -1), "Helvetica"),
        ("FONTSIZE",      (0, 1), (-1, -1), 8.5),
        ("GRID",          (0, 0), (-1, -1), 0.35, _C_BORDER),
        ("VALIGN",        (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING",    (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LEFTPADDING",   (0, 0), (-1, -1), 7),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 7),
    ]
    if zebra:
        cmds.append(("ROWBACKGROUNDS", (0, 1), (-1, -1), [_C_WHITE, _C_LIGHT]))
    return TableStyle(cmds)


def _verdict_table_style(v_color: Any) -> TableStyle:
    return TableStyle([
        ("BACKGROUND",    (0, 0), (-1, -1), v_color),
        ("ALIGN",         (0, 0), (-1, -1), "CENTER"),
        ("VALIGN",        (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING",   (0, 0), (-1, -1), 16),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 16),
        ("TOPPADDING",    (0, 0), (-1, -1), 14),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 14),
    ])


# ── Page template helper ──────────────────────────────────────────────────────

def _make_page_callback(workspace: str, verdict: str):
    """Return an onFirstPage/onLaterPages callback that draws running headers/footers."""
    v_color = _verdict_color(verdict)

    def _draw(canvas, doc):
        w, h = A4
        canvas.saveState()
        # Top bar
        canvas.setFillColor(_C_NAVY)
        canvas.rect(0, h - 28, w, 28, fill=1, stroke=0)
        canvas.setFillColor(_C_WHITE)
        canvas.setFont("Helvetica-Bold", 8)
        canvas.drawString(18, h - 18, "IROKO AI  |  ENTERPRISE INTELLIGENCE")
        canvas.setFont("Helvetica", 8)
        canvas.drawRightString(w - 18, h - 18, f"CONFIDENTIAL  |  {_now_display()}")
        # Thin verdict colour accent line below header
        canvas.setFillColor(v_color)
        canvas.rect(0, h - 30, w, 2, fill=1, stroke=0)
        # Footer
        canvas.setFillColor(_C_MUTED)
        canvas.setFont("Helvetica", 7)
        canvas.drawString(18, 14, f"{workspace}  |  Iroko AI Enterprise Intelligence Platform")
        canvas.drawRightString(w - 18, 14, f"Page {doc.page}")
        canvas.setFillColor(_C_BORDER)
        canvas.rect(18, 22, w - 36, 0.5, fill=1, stroke=0)
        canvas.restoreState()

    return _draw


# ── Service class ─────────────────────────────────────────────────────────────

class ComplianceBriefGenerator:
    """
    Generates professional, multi-page PDF compliance briefs and regulatory
    digests for Iroko AI as raw bytes.

    All methods return ``bytes``. Nothing is written to disk.
    """

    # ── 1. Enterprise Intelligence Brief ─────────────────────────────────────

    def generate_brief(
        self,
        verdict_output: dict[str, Any],
        workspace_name: str = "African Fintech Platform",
        include_audit_trail: bool = False,
        audit_entries: Optional[list[dict]] = None,
    ) -> bytes:
        """
        Generate a professional multi-page PDF compliance brief.

        Page structure
        --------------
        1. Cover page          — Brand header, verdict callout, document meta
        2. Executive Summary   — Verdict banner, decision reviewed, key findings
        3. NCC Regulatory Analysis — Referenced regulations with full detail
        4. Violations Deep-Dive — Per-violation breakdown with implications
        5. Recommended Actions — Numbered priority action list
        6. Risk Assessment     — Risk matrix table
        7. Evidence Sources    — Cited URLs / documents
        8. Audit Trail         — Hash-chained log (optional)
        9. Disclaimer          — Confidentiality footer
        """
        buf = io.BytesIO()
        page_w, page_h = A4
        margin = 1.8 * cm

        verdict   = str(verdict_output.get("verdict", "MONITOR")).upper()
        v_color   = _verdict_color(verdict)
        v_bg      = _verdict_bg(verdict)
        v_label   = _verdict_label(verdict)
        confidence = float(verdict_output.get("confidence_score", 0.0))

        on_page = _make_page_callback(workspace_name, verdict)

        doc = SimpleDocTemplate(
            buf,
            pagesize=A4,
            leftMargin=margin,
            rightMargin=margin,
            topMargin=margin + 14,   # extra for top bar
            bottomMargin=margin,
            title="Iroko AI Enterprise Intelligence Brief",
            author="Iroko AI Platform",
            subject=f"Compliance Brief — {workspace_name}",
        )

        S = _build_styles()
        flow: list[Any] = []
        usable_w = page_w - 2 * margin

        generated_at = verdict_output.get("generated_at", _now_display())
        decision_text = verdict_output.get("decision_text", "")
        summary = verdict_output.get("summary", "")
        ncc_refs: list[str] = verdict_output.get("ncc_references", []) or []
        violations: list[dict] = verdict_output.get("violations", []) or []
        actions: list[str] = verdict_output.get("recommended_actions", []) or []
        sources: list[Any] = verdict_output.get("sources", []) or []

        # ── COVER PAGE ────────────────────────────────────────────────────────
        # Tall coloured cover block
        cover_bg_color = v_color

        cover_block = Table(
            [[Paragraph("IROKO AI", S["cover_sub"])],
             [Paragraph("Enterprise Intelligence Brief", S["cover_title"])],
             [Spacer(1, 4)],
             [Paragraph(_esc(workspace_name), S["cover_sub"])],
             [Spacer(1, 8)],
             [Paragraph(_esc(v_label), ParagraphStyle(
                "CoverVerdict",
                parent=S["cover_title"],
                fontSize=16,
                textColor=_C_WHITE,
             ))],
             [Spacer(1, 6)],
             [Paragraph(f"Confidence Score: {confidence:.0%}", S["cover_sub"])],
             [Spacer(1, 16)],
             [Paragraph(f"Generated: {_esc(str(generated_at))}", S["cover_meta"])],
             [Paragraph("CLASSIFICATION: CONFIDENTIAL — NOT FOR EXTERNAL DISTRIBUTION", S["cover_meta"])],
            ],
            colWidths=[usable_w],
        )
        cover_block.setStyle(TableStyle([
            ("BACKGROUND",    (0, 0), (-1, -1), cover_bg_color),
            ("ALIGN",         (0, 0), (-1, -1), "CENTER"),
            ("VALIGN",        (0, 0), (-1, -1), "MIDDLE"),
            ("TOPPADDING",    (0, 0), (-1, -1), 10),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
            ("LEFTPADDING",   (0, 0), (-1, -1), 20),
            ("RIGHTPADDING",  (0, 0), (-1, -1), 20),
        ]))
        flow.append(Spacer(1, 40))
        flow.append(cover_block)
        flow.append(Spacer(1, 20))

        # Cover metadata table
        meta_rows = [
            ["Document Type",    "CBN/SEC Compliance Intelligence Brief"],
            ["Prepared For",     _esc(workspace_name)],
            ["Prepared By",      "Iroko AI  |  Atlas Intelligence Engine"],
            ["Verdict",          _esc(v_label)],
            ["Confidence Score", f"{confidence:.0%}"],
            ["Violations Found", str(len(violations))],
            ["Actions Required", str(len(actions))],
            ["Generated At",     _esc(str(generated_at))],
            ["Classification",   "CONFIDENTIAL"],
        ]
        meta_table = Table(
            [[Paragraph(_esc(r[0]), S["table_header_text"]),
              Paragraph(_esc(r[1]), S["table_cell"])] for r in meta_rows],
            colWidths=[usable_w * 0.32, usable_w * 0.68],
        )
        meta_table.setStyle(TableStyle([
            ("BACKGROUND",    (0, 0), (0, -1), _C_NAVY),
            ("TEXTCOLOR",     (0, 0), (0, -1), _C_WHITE),
            ("BACKGROUND",    (1, 0), (1, -1), _C_WHITE),
            ("ROWBACKGROUNDS",(1, 0), (1, -1), [_C_WHITE, _C_LIGHT]),
            ("GRID",          (0, 0), (-1, -1), 0.35, _C_BORDER),
            ("VALIGN",        (0, 0), (-1, -1), "MIDDLE"),
            ("TOPPADDING",    (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ("LEFTPADDING",   (0, 0), (-1, -1), 8),
            ("RIGHTPADDING",  (0, 0), (-1, -1), 8),
        ]))
        flow.append(meta_table)
        flow.append(PageBreak())

        # ── SECTION 1: EXECUTIVE SUMMARY ──────────────────────────────────────
        flow.append(Paragraph("1.  Executive Summary", S["section_h1"]))
        flow.append(HRFlowable(width="100%", thickness=2, color=_C_NAVY, spaceAfter=10))

        # Verdict banner
        verdict_banner = Table(
            [[Paragraph(_esc(v_label), S["verdict_label"]),
              Paragraph(f"Confidence: {confidence:.0%}", S["verdict_confidence"])]],
            colWidths=[usable_w * 0.7, usable_w * 0.3],
            rowHeights=[48],
        )
        verdict_banner.setStyle(TableStyle([
            ("BACKGROUND",    (0, 0), (-1, -1), v_color),
            ("ALIGN",         (0, 0), (0, 0),   "LEFT"),
            ("ALIGN",         (1, 0), (1, 0),   "RIGHT"),
            ("VALIGN",        (0, 0), (-1, -1), "MIDDLE"),
            ("LEFTPADDING",   (0, 0), (-1, -1), 16),
            ("RIGHTPADDING",  (0, 0), (-1, -1), 16),
            ("TOPPADDING",    (0, 0), (-1, -1), 0),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
        ]))
        flow.append(verdict_banner)
        flow.append(Spacer(1, 12))

        # Key stats row
        stats = [
            ("Verdict",         _esc(verdict)),
            ("Confidence",      f"{confidence:.0%}"),
            ("Violations",      str(len(violations))),
            ("Regulation Refs",  str(len(ncc_refs))),
            ("Actions Required",str(len(actions))),
        ]
        stats_cells = [[Paragraph(s[0], S["body_small"]),
                         Paragraph(s[1], ParagraphStyle("StatVal", parent=S["section_h2"],
                             fontSize=14, textColor=v_color, spaceAfter=0))]
                        for s in stats]
        stats_table = Table(
            [stats_cells],
            colWidths=[usable_w / len(stats)] * len(stats),
        )
        stats_table.setStyle(TableStyle([
            ("BOX",          (0, 0), (-1, -1), 0.35, _C_BORDER),
            ("INNERGRID",    (0, 0), (-1, -1), 0.35, _C_BORDER),
            ("BACKGROUND",   (0, 0), (-1, -1), _C_LIGHT),
            ("VALIGN",       (0, 0), (-1, -1), "MIDDLE"),
            ("ALIGN",        (0, 0), (-1, -1), "CENTER"),
            ("TOPPADDING",   (0, 0), (-1, -1), 8),
            ("BOTTOMPADDING",(0, 0), (-1, -1), 8),
        ]))
        flow.append(stats_table)
        flow.append(Spacer(1, 14))

        # Summary narrative
        if summary:
            flow.append(Paragraph("Summary of Findings", S["section_h2"]))
            flow.append(Paragraph(_esc(summary), S["body"]))

        # Decision evaluated
        if decision_text:
            flow.append(Spacer(1, 6))
            flow.append(Paragraph("Decision Evaluated", S["section_h2"]))
            flow.append(Paragraph(
                f'"{_esc(decision_text)}"',
                S["body_italic"],
            ))

        # ── SECTION 2: NCC REGULATORY ANALYSIS ────────────────────────────────
        if ncc_refs or violations:
            flow.append(Spacer(1, 8))
            flow.append(Paragraph("2.  CBN/SEC Regulatory Analysis", S["section_h1"]))
            flow.append(HRFlowable(width="100%", thickness=2, color=_C_NAVY, spaceAfter=10))

            flow.append(Paragraph(
                "The following CBN/SEC regulations are relevant to the decision under review. "
                "Each regulation is evaluated against the proposed action, with applicable "
                "penalties and enforcement implications noted.",
                S["body"],
            ))
            flow.append(Spacer(1, 8))

            all_refs = list(dict.fromkeys(ncc_refs + [v.get("regulation_id", "") for v in violations if v.get("regulation_id")]))
            for ref in all_refs:
                if not ref:
                    continue
                meta = _ncc_detail(ref)
                # Regulation header box
                reg_header = Table(
                    [[Paragraph(_esc(ref), ParagraphStyle("RefID", parent=S["section_h2"],
                          fontSize=12, textColor=_C_WHITE, spaceAfter=0, spaceBefore=0)),
                      Paragraph(_esc(meta["name"]), ParagraphStyle("RefName", parent=S["body"],
                          textColor=colors.HexColor("#e2e8f0"), spaceAfter=0, alignment=TA_RIGHT))]],
                    colWidths=[usable_w * 0.25, usable_w * 0.75],
                    rowHeights=[28],
                )
                reg_header.setStyle(TableStyle([
                    ("BACKGROUND",    (0, 0), (-1, -1), _C_NAVY),
                    ("VALIGN",        (0, 0), (-1, -1), "MIDDLE"),
                    ("LEFTPADDING",   (0, 0), (-1, -1), 10),
                    ("RIGHTPADDING",  (0, 0), (-1, -1), 10),
                    ("TOPPADDING",    (0, 0), (-1, -1), 0),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
                ]))
                flow.append(KeepTogether([
                    reg_header,
                    Table(
                        [[Paragraph(_esc(meta.get("section", "")), S["table_cell_mono"]),
                          Paragraph(_esc(meta.get("penalty", "")), S["table_cell_red"])]],
                        colWidths=[usable_w * 0.5, usable_w * 0.5],
                    ),
                    Spacer(1, 4),
                    Paragraph(_esc(meta.get("detail", "")), S["body"]),
                    Spacer(1, 10),
                ]))

        # ── SECTION 3: VIOLATIONS DEEP-DIVE ───────────────────────────────────
        if violations:
            flow.append(Paragraph("3.  Violations Detected", S["section_h1"]))
            flow.append(HRFlowable(width="100%", thickness=2, color=_C_NO_GO, spaceAfter=10))

            flow.append(Paragraph(
                f"The compliance engine identified <b>{len(violations)}</b> violation(s) "
                f"against the current CBN/SEC regulatory corpus. Each violation is detailed below "
                f"with its applicable regulatory section and enforcement implications.",
                S["body"],
            ))
            flow.append(Spacer(1, 8))

            # Summary violations table
            viol_rows = [[
                Paragraph("Regulation", S["table_header_text"]),
                Paragraph("Section",    S["table_header_text"]),
                Paragraph("Reason",     S["table_header_text"]),
            ]]
            for v in violations:
                viol_rows.append([
                    Paragraph(_esc(v.get("regulation_id", "—")), S["table_cell_red"]),
                    Paragraph(_esc(v.get("section", "—")),       S["table_cell"]),
                    Paragraph(_esc(v.get("reason", "—")),        S["table_cell"]),
                ])
            viol_table = Table(
                viol_rows,
                colWidths=[usable_w * 0.16, usable_w * 0.16, usable_w * 0.68],
            )
            viol_table.setStyle(_dark_table_style(header_color=_C_NO_GO))
            flow.append(viol_table)
            flow.append(Spacer(1, 14))

            # Per-violation deep dive
            for i, v in enumerate(violations, start=1):
                reg_id = v.get("regulation_id", "N/A")
                section = v.get("section", "")
                reason = v.get("reason", "")
                meta = _ncc_detail(reg_id)

                block = KeepTogether([
                    Paragraph(
                        f"Violation {i}: {_esc(reg_id)}  —  {_esc(meta['name'])}",
                        S["section_h3"],
                    ),
                    Table(
                        [["Section:", _esc(section or meta.get("section", "—")),
                          "Penalty:", _esc(meta.get("penalty", "See register"))]],
                        colWidths=[usable_w * 0.12, usable_w * 0.38, usable_w * 0.12, usable_w * 0.38],
                    ),
                    Spacer(1, 4),
                    Paragraph(f"Finding: {_esc(reason)}", S["body"]),
                    Paragraph(
                        f"Regulatory Implication: {_esc(meta.get('detail', ''))}",
                        S["body_italic"],
                    ),
                    Spacer(1, 8),
                ])
                flow.append(block)

        # ── SECTION 4: RECOMMENDED ACTIONS ────────────────────────────────────
        if actions:
            flow.append(Paragraph("4.  Recommended Actions", S["section_h1"]))
            flow.append(HRFlowable(width="100%", thickness=2, color=_C_BLUE, spaceAfter=10))
            flow.append(Paragraph(
                "The following actions are recommended to remediate the identified "
                "compliance gaps and restore full CBN/SEC regulatory alignment. Actions are "
                "listed in order of priority.",
                S["body"],
            ))
            flow.append(Spacer(1, 8))

            for i, action in enumerate(actions, start=1):
                priority = "IMMEDIATE" if i == 1 else ("HIGH" if i <= 3 else "MEDIUM")
                p_color = _C_NO_GO if i == 1 else (_C_MONITOR if i <= 3 else _C_BLUE)
                action_block = Table(
                    [[Paragraph(str(i), ParagraphStyle("ANum", parent=S["section_h1"],
                          fontSize=16, textColor=_C_WHITE, alignment=TA_CENTER, spaceAfter=0, spaceBefore=0)),
                      Paragraph(f"<b>{priority}</b><br/>{_esc(action)}", S["body"])]],
                    colWidths=[usable_w * 0.08, usable_w * 0.92],
                )
                action_block.setStyle(TableStyle([
                    ("BACKGROUND",    (0, 0), (0, 0), p_color),
                    ("BACKGROUND",    (1, 0), (1, 0), _C_LIGHT),
                    ("VALIGN",        (0, 0), (-1, -1), "TOP"),
                    ("ALIGN",         (0, 0), (0, 0),   "CENTER"),
                    ("BOX",           (0, 0), (-1, -1), 0.35, _C_BORDER),
                    ("TOPPADDING",    (0, 0), (-1, -1), 8),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
                    ("LEFTPADDING",   (0, 0), (-1, -1), 8),
                    ("RIGHTPADDING",  (0, 0), (-1, -1), 8),
                    ("TOPPADDING",    (0, 0), (0, 0),   16),
                ]))
                flow.append(action_block)
                flow.append(Spacer(1, 4))
            flow.append(Spacer(1, 8))

        # ── SECTION 5: RISK ASSESSMENT ────────────────────────────────────────
        flow.append(Paragraph("5.  Risk Assessment Summary", S["section_h1"]))
        flow.append(HRFlowable(width="100%", thickness=2, color=_C_NAVY, spaceAfter=10))

        # Map verdict to risk level
        risk_map = {"NO-GO": "CRITICAL", "MONITOR": "HIGH", "GO": "LOW"}
        risk_level = risk_map.get(verdict, "MEDIUM")
        risk_color = {"CRITICAL": _C_NO_GO, "HIGH": _C_MONITOR, "LOW": _C_GO, "MEDIUM": _C_BLUE}.get(risk_level, _C_BLUE)

        risk_matrix = [
            ["Risk Dimension",          "Assessment",   "Level"],
            ["Regulatory Compliance",   f"CBN/SEC {verdict}", risk_level],
            ["Financial Exposure",       "Potential fine exposure" if violations else "Minimal", "HIGH" if violations else "LOW"],
            ["Reputational Risk",        "Elevated — regulatory scrutiny likely" if verdict == "NO-GO" else "Moderate", "HIGH" if verdict == "NO-GO" else "MEDIUM"],
            ["Operational Impact",       "Immediate halt required" if verdict == "NO-GO" else "Monitor and review", "HIGH" if verdict == "NO-GO" else "MEDIUM"],
            ["Timeline Sensitivity",     "Urgent — 24h action window" if verdict == "NO-GO" else "30-day review cycle", "CRITICAL" if verdict == "NO-GO" else "MEDIUM"],
        ]
        risk_colors_map = {"CRITICAL": _C_NO_GO, "HIGH": _C_MONITOR, "MEDIUM": _C_BLUE, "LOW": _C_GO}

        risk_rows_data = [[Paragraph(r[0], S["table_header_text"] if i == 0 else S["table_cell"]),
                            Paragraph(r[1], S["table_header_text"] if i == 0 else S["table_cell"]),
                            Paragraph(r[2], S["table_header_text"] if i == 0 else
                                      ParagraphStyle("RiskLevel", parent=S["table_cell"],
                                          fontName="Helvetica-Bold",
                                          textColor=risk_colors_map.get(r[2], _C_BLUE))),
                           ] for i, r in enumerate(risk_matrix)]

        risk_table = Table(
            risk_rows_data,
            colWidths=[usable_w * 0.38, usable_w * 0.40, usable_w * 0.22],
        )
        risk_table.setStyle(_dark_table_style())
        flow.append(risk_table)
        flow.append(Spacer(1, 14))

        # ── SECTION 6: EVIDENCE SOURCES ────────────────────────────────────────
        if sources:
            flow.append(Paragraph("6.  Evidence Sources", S["section_h1"]))
            flow.append(HRFlowable(width="100%", thickness=2, color=_C_NAVY, spaceAfter=10))
            src_rows = [[Paragraph("Source Title", S["table_header_text"]),
                          Paragraph("Reference", S["table_header_text"])]]
            for src in sources:
                if isinstance(src, dict):
                    title = _esc(src.get("title", ""))
                    url   = _esc(src.get("url", "—"))
                else:
                    title = _esc(str(src))
                    url = "—"
                src_rows.append([
                    Paragraph(title, S["table_cell"]),
                    Paragraph(url, S["table_cell"]),
                ])
            src_table = Table(src_rows, colWidths=[usable_w * 0.55, usable_w * 0.45])
            src_table.setStyle(_dark_table_style())
            flow.append(src_table)
            flow.append(Spacer(1, 14))

        # ── SECTION 7: AUDIT TRAIL ────────────────────────────────────────────
        if include_audit_trail and audit_entries:
            flow.append(Paragraph("7.  Audit Trail  (Hash-Verified Chain)", S["section_h1"]))
            flow.append(HRFlowable(width="100%", thickness=2, color=_C_NAVY, spaceAfter=10))
            flow.append(Paragraph(
                "The following audit trail is cryptographically hash-chained. Each entry's "
                "chain hash incorporates the previous entry's hash, ensuring tamper-evidence "
                "across the full compliance decision record.",
                S["body"],
            ))
            flow.append(Spacer(1, 6))

            audit_rows = [[
                Paragraph("Agent",       S["table_header_text"]),
                Paragraph("Action",      S["table_header_text"]),
                Paragraph("Verdict",     S["table_header_text"]),
                Paragraph("Timestamp",   S["table_header_text"]),
                Paragraph("Chain Hash",  S["table_header_text"]),
            ]]
            for entry in (audit_entries or [])[:25]:
                chain_hash = str(entry.get("chain_hash", "") or "")
                v_str = str(entry.get("verdict", "") or "")
                v_ps = ParagraphStyle("AuditVerdict", parent=S["table_cell"],
                    fontName="Helvetica-Bold",
                    textColor=_verdict_color(v_str) if v_str else _C_MUTED)
                audit_rows.append([
                    Paragraph(_esc(entry.get("agent_name", "")),  S["table_cell"]),
                    Paragraph(_esc(entry.get("action_type", "")), S["table_cell"]),
                    Paragraph(_esc(v_str),                         v_ps),
                    Paragraph(_esc(str(entry.get("created_at", ""))[:19].replace("T", " ")), S["table_cell"]),
                    Paragraph(_esc(f"…{chain_hash[-8:]}"),         S["table_cell"]),
                ])
            audit_table = Table(
                audit_rows,
                colWidths=[
                    usable_w * 0.18,
                    usable_w * 0.20,
                    usable_w * 0.13,
                    usable_w * 0.28,
                    usable_w * 0.21,
                ],
            )
            audit_table.setStyle(_dark_table_style(header_color=colors.HexColor("#1e293b")))
            flow.append(audit_table)
            flow.append(Spacer(1, 14))

        # ── DISCLAIMER & FOOTER ────────────────────────────────────────────────
        flow.append(HRFlowable(width="100%", thickness=1, color=_C_BORDER, spaceBefore=12, spaceAfter=8))
        disclaimer = (
            "This document is generated by the Iroko AI Enterprise Intelligence Platform using "
            "the Atlas Intelligence Engine and live CBN/SEC regulatory data. It is intended solely "
            "for the authorised recipient and contains confidential, commercially sensitive "
            "information. The compliance verdicts expressed herein are AI-assisted assessments "
            "and should be reviewed by qualified legal or regulatory counsel before acting. "
            "Iroko AI does not accept liability for actions taken solely on the basis of this report "
            "without independent legal review. CONFIDENTIAL — NOT FOR EXTERNAL DISTRIBUTION."
        )
        flow.append(Paragraph(disclaimer, S["body_small"]))

        doc.build(flow, onFirstPage=on_page, onLaterPages=on_page)

        logger.info(
            "[BriefGenerator] generate_brief: verdict=%s workspace=%s audit=%s bytes~%d",
            verdict, workspace_name, include_audit_trail, buf.tell(),
        )
        return buf.getvalue()

    # ── 2. Weekly Regulatory Digest ───────────────────────────────────────────

    def generate_regulatory_digest(
        self,
        ncc_updates: list[dict[str, Any]],
        workspace_name: str = "African Fintech Platform",
    ) -> bytes:
        """
        Generate a multi-page Weekly Regulatory Digest PDF from live CBN/SEC update dicts.
        """
        from services.regulatory_service import NCC_REGULATIONS  # variable name retained for compat

        buf = io.BytesIO()
        page_w, page_h = A4
        margin = 1.8 * cm
        usable_w = page_w - 2 * margin

        on_page = _make_page_callback(workspace_name, "MONITOR")

        doc = SimpleDocTemplate(
            buf,
            pagesize=A4,
            leftMargin=margin,
            rightMargin=margin,
            topMargin=margin + 14,
            bottomMargin=margin,
            title="Iroko AI Weekly CBN/SEC Regulatory Digest",
            author="Iroko AI Platform",
            subject=f"Regulatory Digest — {workspace_name}",
        )

        S = _build_styles()
        flow: list[Any] = []
        today = _now_display()

        # Cover header
        cover = Table(
            [[Paragraph("IROKO AI  |  REGULATORY INTELLIGENCE", S["cover_sub"])],
             [Paragraph("Weekly CBN/SEC Regulatory Digest", S["cover_title"])],
             [Spacer(1, 6)],
             [Paragraph(_esc(workspace_name), S["cover_sub"])],
             [Paragraph(f"Compiled: {today}  |  {len(ncc_updates)} updates processed", S["cover_meta"])],
            ],
            colWidths=[usable_w],
        )
        cover.setStyle(TableStyle([
            ("BACKGROUND",    (0, 0), (-1, -1), _C_NAVY),
            ("ALIGN",         (0, 0), (-1, -1), "CENTER"),
            ("VALIGN",        (0, 0), (-1, -1), "MIDDLE"),
            ("TOPPADDING",    (0, 0), (-1, -1), 12),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 12),
        ]))
        flow.append(Spacer(1, 30))
        flow.append(cover)
        flow.append(Spacer(1, 20))

        # Update summary table
        flow.append(Paragraph("Update Summary", S["section_h1"]))
        flow.append(HRFlowable(width="100%", thickness=2, color=_C_NAVY, spaceAfter=8))

        summary_rows = [[
            Paragraph("Update Title",         S["table_header_text"]),
            Paragraph("Source",               S["table_header_text"]),
            Paragraph("Regulation Matched",   S["table_header_text"]),
            Paragraph("Action Required",      S["table_header_text"]),
        ]]
        for item in ncc_updates:
            update     = item.get("update", {}) if isinstance(item.get("update"), dict) else {}
            title      = _esc(update.get("title", "—"))[:70]
            source     = _esc(update.get("source", "ncc_serp"))
            reg_id     = _esc(item.get("matched_regulation_id") or "Unclassified")
            action_req = "YES" if item.get("action_required") else "No"
            ar_style   = ParagraphStyle("AR", parent=S["table_cell"],
                fontName="Helvetica-Bold",
                textColor=_C_NO_GO if item.get("action_required") else _C_GO)
            summary_rows.append([
                Paragraph(title,      S["table_cell"]),
                Paragraph(source,     S["table_cell"]),
                Paragraph(reg_id,     S["table_cell_mono"]),
                Paragraph(action_req, ar_style),
            ])

        if len(summary_rows) == 1:
            summary_rows.append([
                Paragraph("No live updates retrieved.", S["table_cell"]),
                Paragraph("—", S["table_cell"]),
                Paragraph("—", S["table_cell"]),
                Paragraph("—", S["table_cell"]),
            ])

        summary_table = Table(
            summary_rows,
            colWidths=[usable_w * 0.40, usable_w * 0.17, usable_w * 0.22, usable_w * 0.21],
        )
        summary_table.setStyle(_dark_table_style())
        flow.append(summary_table)
        flow.append(Spacer(1, 16))

        # Per-regulation breakdown
        seen_regs: dict[str, list[dict]] = {}
        for item in ncc_updates:
            reg_id = item.get("matched_regulation_id")
            if reg_id:
                seen_regs.setdefault(reg_id, []).append(item)

        if seen_regs:
            flow.append(Paragraph("Regulation Breakdown", S["section_h1"]))
            flow.append(HRFlowable(width="100%", thickness=2, color=_C_NAVY, spaceAfter=10))

            reg_index = {r["id"]: r for r in NCC_REGULATIONS}
            for reg_id, items in sorted(seen_regs.items()):
                reg      = reg_index.get(reg_id, {})
                reg_name = reg.get("name", reg_id)
                meta     = _ncc_detail(reg_id)

                flow.append(Paragraph(f"{_esc(reg_id)}  —  {_esc(reg_name)}", S["section_h2"]))
                flow.append(Paragraph(meta.get("detail", ""), S["body"]))

                obligations = reg.get("obligations", [])
                if obligations:
                    for ob in obligations[:4]:
                        flow.append(Paragraph(f"  •  {_esc(ob)}", S["body_small"]))

                action_count = sum(1 for it in items if it.get("action_required"))
                if action_count:
                    flow.append(Paragraph(
                        f"  {action_count} update(s) require immediate regulatory action under {_esc(reg_id)}.",
                        ParagraphStyle("ActionNote", parent=S["body_small"],
                            textColor=_C_NO_GO, fontName="Helvetica-Bold"),
                    ))
                flow.append(Spacer(1, 8))

        # Footer
        flow.append(HRFlowable(width="100%", thickness=1, color=_C_BORDER, spaceBefore=10, spaceAfter=6))
        flow.append(Paragraph(
            "Generated by Iroko AI Enterprise Intelligence Platform  |  "
            "Source: CBN Nigeria (cbn.gov.ng) / SEC Nigeria (sec.gov.ng) via Bright Data  |  CONFIDENTIAL",
            S["footer"],
        ))

        doc.build(flow, onFirstPage=on_page, onLaterPages=on_page)
        logger.info(
            "[BriefGenerator] generate_regulatory_digest: %d updates workspace=%s bytes~%d",
            len(ncc_updates), workspace_name, buf.tell(),
        )
        return buf.getvalue()


# ── Route helper ──────────────────────────────────────────────────────────────

async def get_brief_response(brief_bytes: bytes, filename: str = "iroko_brief.pdf"):
    """
    Wrap PDF bytes in a FastAPI ``Response`` with correct headers for browser
    download / inline display.
    """
    from fastapi.responses import Response

    safe_filename = re.sub(r"[^\w\-.]", "_", filename)
    return Response(
        content=brief_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="{safe_filename}"',
            "Content-Length": str(len(brief_bytes)),
            "Cache-Control": "no-store",
        },
    )


# ── Module-level singleton ────────────────────────────────────────────────────

brief_generator = ComplianceBriefGenerator()
