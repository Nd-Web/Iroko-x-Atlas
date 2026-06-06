# -*- coding: utf-8 -*-
"""
services/brief_generator.py — Professional PDF compliance brief generator for Iroko AI.
========================================================================================
Generates two document types as raw bytes (never written to disk):

  1. ``generate_brief()``            — One-page enterprise intelligence brief with
                                       verdict banner, NCC references, recommended actions,
                                       evidence sources, and optional audit trail.
  2. ``generate_regulatory_digest()``— Weekly regulatory digest from live NCC updates.

ReportLab patterns adapted from Polaris ``backend/audit/chain.py`` and
``polaris/agents/auditor.py`` (render_compliance_report).

Design constraints:
  - Font: Helvetica only (always available in ReportLab, no external fonts).
  - Page: A4.
  - Emojis stripped from labels (Helvetica cannot render Unicode emoji).
  - All text passed through ``_esc()`` before entering Paragraph flowables
    to prevent XML parse errors from angle brackets / ampersands.
  - Returns ``bytes`` only — never writes to disk.

Usage::

    from services.brief_generator import brief_generator, get_brief_response

    pdf_bytes = brief_generator.generate_brief(verdict_output)

    # FastAPI:
    return await get_brief_response(pdf_bytes, "iroko_brief.pdf")
"""

from __future__ import annotations

import io
import logging
import re
from datetime import datetime, timezone
from typing import Any, Optional
from xml.sax.saxutils import escape as _xml_escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
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
)

logger = logging.getLogger(__name__)

# ── Brand colours ─────────────────────────────────────────────────────────────

_C_HEADER  = colors.HexColor("#0f172a")   # slate-900 — top bar and section headings
_C_GO      = colors.HexColor("#22c55e")   # green-500
_C_MONITOR = colors.HexColor("#f59e0b")   # amber-400
_C_NO_GO   = colors.HexColor("#ef4444")   # red-500
_C_WHITE   = colors.white
_C_LIGHT   = colors.HexColor("#f8fafc")   # table alternating row
_C_BORDER  = colors.HexColor("#e2e8f0")   # table grid
_C_MUTED   = colors.HexColor("#64748b")   # slate-500 — captions

_VERDICT_COLOR_MAP: dict[str, Any] = {
    "GO":      _C_GO,
    "MONITOR": _C_MONITOR,
    "NO-GO":   _C_NO_GO,
}

_VERDICT_LABEL_MAP: dict[str, str] = {
    "GO":      "GO  --  Proceed with confidence",
    "MONITOR": "MONITOR  --  Watch closely",
    "NO-GO":   "NO-GO  --  Action required",
}

# ── Internal helpers ──────────────────────────────────────────────────────────

def _esc(value: Any) -> str:
    """
    Escape any value for safe embedding in a ReportLab Paragraph XML context.
    Strips emoji / non-BMP characters that Helvetica cannot render, then
    XML-escapes ``<``, ``>``, ``&``.
    """
    text = str(value) if value is not None else ""
    # Strip characters outside the Basic Multilingual Plane (emoji, symbols)
    text = re.sub(r"[^\u0000-\uFFFF]", "", text)
    # Also strip any remaining control/surrogate-range characters
    text = re.sub(r"[\u2000-\u206F\u2700-\u27BF\uFE00-\uFE0F]", "", text)
    return _xml_escape(text)


def _now_display() -> str:
    """Return a human-readable UTC timestamp string."""
    return datetime.now(tz=timezone.utc).strftime("%d %B %Y  %H:%M UTC")


def _verdict_color(verdict: str) -> Any:
    return _VERDICT_COLOR_MAP.get(verdict, _C_MONITOR)


def _verdict_label(verdict: str) -> str:
    return _VERDICT_LABEL_MAP.get(verdict, verdict)


def _build_styles() -> dict[str, ParagraphStyle]:
    """Build and return a reusable style dictionary for brief documents."""
    base = getSampleStyleSheet()

    def ps(name: str, **kw) -> ParagraphStyle:
        return ParagraphStyle(name, parent=base["Normal"], **kw)

    return {
        "doc_title": ps(
            "DocTitle",
            fontName="Helvetica-Bold",
            fontSize=22,
            leading=28,
            textColor=_C_HEADER,
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
            fontSize=11,
            textColor=_C_HEADER,
            alignment=TA_LEFT,
        ),
        "header_right": ps(
            "HeaderRight",
            fontName="Helvetica-Bold",
            fontSize=10,
            textColor=_C_NO_GO,
            alignment=TA_RIGHT,
        ),
        "section_heading": ps(
            "SectionHeading",
            fontName="Helvetica-Bold",
            fontSize=11,
            textColor=_C_HEADER,
            spaceBefore=12,
            spaceAfter=4,
        ),
        "body": ps(
            "Body",
            fontName="Helvetica",
            fontSize=9,
            leading=14,
            textColor=colors.HexColor("#1e293b"),
            spaceAfter=4,
        ),
        "body_small": ps(
            "BodySmall",
            fontName="Helvetica",
            fontSize=8,
            leading=12,
            textColor=_C_MUTED,
        ),
        "verdict_banner": ps(
            "VerdictBanner",
            fontName="Helvetica-Bold",
            fontSize=16,
            textColor=_C_WHITE,
            alignment=TA_CENTER,
        ),
        "table_header": ps(
            "TableHeader",
            fontName="Helvetica-Bold",
            fontSize=8,
            textColor=_C_WHITE,
        ),
        "table_cell": ps(
            "TableCell",
            fontName="Helvetica",
            fontSize=8,
            leading=11,
            textColor=colors.HexColor("#1e293b"),
        ),
        "footer": ps(
            "Footer",
            fontName="Helvetica",
            fontSize=7,
            textColor=_C_MUTED,
            alignment=TA_CENTER,
        ),
        "confidential": ps(
            "Confidential",
            fontName="Helvetica-Bold",
            fontSize=9,
            textColor=_C_NO_GO,
            alignment=TA_RIGHT,
        ),
        "digest_title": ps(
            "DigestTitle",
            fontName="Helvetica-Bold",
            fontSize=18,
            textColor=_C_HEADER,
            spaceAfter=4,
        ),
        "action_item": ps(
            "ActionItem",
            fontName="Helvetica",
            fontSize=9,
            leading=13,
            textColor=colors.HexColor("#1e293b"),
            leftIndent=16,
            spaceAfter=2,
        ),
    }


# ── Shared table style builders ───────────────────────────────────────────────

def _dark_table_style(header_color: Any = _C_HEADER) -> TableStyle:
    return TableStyle([
        ("BACKGROUND",  (0, 0), (-1, 0), header_color),
        ("TEXTCOLOR",   (0, 0), (-1, 0), _C_WHITE),
        ("FONTNAME",    (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE",    (0, 0), (-1, 0), 8),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [_C_WHITE, _C_LIGHT]),
        ("FONTNAME",    (0, 1), (-1, -1), "Helvetica"),
        ("FONTSIZE",    (0, 1), (-1, -1), 8),
        ("GRID",        (0, 0), (-1, -1), 0.3, _C_BORDER),
        ("VALIGN",      (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING",  (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
    ])


# ── NCC Regulation lookup ─────────────────────────────────────────────────────

def _ncc_implication(reg_id: str) -> str:
    """Return a short implication string for a given NCC regulation ID."""
    _IMPLICATIONS: dict[str, str] = {
        "NCC-001": "Licence, false-submission offences (s.73) — fine + prosecution risk.",
        "NCC-002": "Consumer Code: billing, outage notification, complaint SLAs.",
        "NCC-003": "QoS reporting deadlines — quarterly, 15th of month. Fine up to N12.4bn.",
        "NCC-004": "SIM-NIN linkage; RGE within 48h/96h. N200k per non-compliant SIM.",
        "NCC-005": "Spectrum licensing; signal booster authorisation required.",
        "NCC-006": "Board tenure limits; ICT/cybersecurity director required by Mar 2025.",
    }
    return _IMPLICATIONS.get(reg_id, "Review NCC enforcement register for details.")


# ── Service class ─────────────────────────────────────────────────────────────


class ComplianceBriefGenerator:
    """
    Generates professional PDF compliance briefs and regulatory digests for
    Iroko AI as raw bytes suitable for FastAPI streaming responses.

    All methods return ``bytes``. Nothing is written to disk.
    """

    # ── 1. Enterprise Intelligence Brief ─────────────────────────────────────

    def generate_brief(
        self,
        verdict_output: dict[str, Any],
        workspace_name: str = "MTN Nigeria",
        include_audit_trail: bool = False,
        audit_entries: Optional[list[dict]] = None,
    ) -> bytes:
        """
        Generate a professional one-page PDF compliance brief.

        Page structure
        --------------
        1. Header row: ``IROKO AI INTELLIGENCE`` (left) | ``CONFIDENTIAL`` (right) | date
        2. Horizontal rule
        3. Title: "Enterprise Intelligence Brief"
        4. Subtitle: workspace_name + timestamp
        5. Verdict Banner: full-width coloured box
        6. Summary paragraph
        7. NCC References table (skipped if empty)
        8. Recommended Actions numbered list
        9. Sources bullet list (skipped if empty)
        10. Audit trail table (optional)
        11. Footer

        Parameters
        ----------
        verdict_output : dict
            ``VerdictOutput``-shaped dict from ``VerdictEngine.format_verdict_output()``.
        workspace_name : str
            Tenant / workspace display name.
        include_audit_trail : bool
            If ``True``, append an audit trail table from ``audit_entries``.
        audit_entries : list[dict], optional
            List of audit trail dicts (from ``AuditService.get_audit_trail()``).
            Each must have: ``agent_name``, ``action_type``, ``created_at``, ``chain_hash``.

        Returns
        -------
        bytes
            PDF document as raw bytes.
        """
        buf = io.BytesIO()
        page_w, page_h = A4
        margin = 1.8 * cm

        doc = SimpleDocTemplate(
            buf,
            pagesize=A4,
            leftMargin=margin,
            rightMargin=margin,
            topMargin=margin,
            bottomMargin=margin,
            title="Iroko AI Enterprise Intelligence Brief",
            author="Iroko AI Platform",
            subject=f"Compliance Brief — {workspace_name}",
        )

        S = _build_styles()
        flow: list[Any] = []
        usable_w = page_w - 2 * margin

        # ── 1. Header ─────────────────────────────────────────────────────────
        header_table = Table(
            [[
                Paragraph("IROKO AI  |  ENTERPRISE INTELLIGENCE", S["header_left"]),
                Paragraph(f"CONFIDENTIAL  |  {_now_display()}", S["confidential"]),
            ]],
            colWidths=[usable_w * 0.6, usable_w * 0.4],
        )
        header_table.setStyle(TableStyle([
            ("VALIGN",       (0, 0), (-1, -1), "MIDDLE"),
            ("LEFTPADDING",  (0, 0), (-1, -1), 0),
            ("RIGHTPADDING", (0, 0), (-1, -1), 0),
            ("TOPPADDING",   (0, 0), (-1, -1), 0),
            ("BOTTOMPADDING",(0, 0), (-1, -1), 0),
        ]))
        flow.append(header_table)
        flow.append(HRFlowable(width="100%", thickness=2, color=_C_HEADER, spaceAfter=10))

        # ── 2. Title + subtitle ───────────────────────────────────────────────
        flow.append(Paragraph("Enterprise Intelligence Brief", S["doc_title"]))
        generated_at = _esc(verdict_output.get("generated_at", _now_display()))
        flow.append(Paragraph(
            f"{_esc(workspace_name)}  |  Generated: {generated_at}",
            S["subtitle"],
        ))
        flow.append(Spacer(1, 6))

        # ── 3. Verdict Banner ─────────────────────────────────────────────────
        verdict    = verdict_output.get("verdict", "MONITOR")
        v_color    = _verdict_color(verdict)
        v_label    = _verdict_label(verdict)
        confidence = float(verdict_output.get("confidence_score", 0.0))

        banner_table = Table(
            [[Paragraph(
                f"{_esc(v_label)}    |    Confidence: {confidence:.0%}",
                S["verdict_banner"],
            )]],
            colWidths=[usable_w],
            rowHeights=[36],
        )
        banner_table.setStyle(TableStyle([
            ("BACKGROUND",    (0, 0), (-1, -1), v_color),
            ("ALIGN",         (0, 0), (-1, -1), "CENTER"),
            ("VALIGN",        (0, 0), (-1, -1), "MIDDLE"),
            ("ROUNDEDCORNERS",[4, 4, 4, 4]),
            ("LEFTPADDING",   (0, 0), (-1, -1), 12),
            ("RIGHTPADDING",  (0, 0), (-1, -1), 12),
        ]))
        flow.append(banner_table)
        flow.append(Spacer(1, 12))

        # ── 4. Summary ────────────────────────────────────────────────────────
        summary = verdict_output.get("summary", "")
        if summary:
            flow.append(Paragraph("Summary", S["section_heading"]))
            flow.append(HRFlowable(width="100%", thickness=0.5, color=_C_BORDER, spaceAfter=4))
            flow.append(Paragraph(_esc(summary), S["body"]))
            flow.append(Spacer(1, 8))

        # ── 5. NCC References Table ───────────────────────────────────────────
        ncc_refs: list[str] = verdict_output.get("ncc_references", []) or []
        if ncc_refs:
            flow.append(Paragraph("NCC Regulatory References", S["section_heading"]))
            flow.append(HRFlowable(width="100%", thickness=0.5, color=_C_BORDER, spaceAfter=4))

            ncc_rows = [["Regulation ID", "Category / Section", "Implication"]]
            for ref in ncc_refs:
                ncc_rows.append([
                    Paragraph(_esc(ref), S["table_cell"]),
                    Paragraph(_esc("NCC Enforcement Register"), S["table_cell"]),
                    Paragraph(_esc(_ncc_implication(ref)), S["table_cell"]),
                ])

            ncc_table = Table(
                ncc_rows,
                colWidths=[usable_w * 0.18, usable_w * 0.22, usable_w * 0.60],
            )
            ncc_table.setStyle(_dark_table_style())
            flow.append(ncc_table)
            flow.append(Spacer(1, 10))

        # ── 6. Recommended Actions ────────────────────────────────────────────
        actions: list[str] = verdict_output.get("recommended_actions", []) or []
        if actions:
            flow.append(Paragraph("Recommended Actions", S["section_heading"]))
            flow.append(HRFlowable(width="100%", thickness=0.5, color=_C_BORDER, spaceAfter=4))
            for i, action in enumerate(actions, start=1):
                flow.append(Paragraph(f"{i}.  {_esc(action)}", S["action_item"]))
            flow.append(Spacer(1, 8))

        # ── 7. Sources ────────────────────────────────────────────────────────
        sources: list[Any] = verdict_output.get("sources", []) or []
        if sources:
            flow.append(Paragraph("Evidence Sources", S["section_heading"]))
            flow.append(HRFlowable(width="100%", thickness=0.5, color=_C_BORDER, spaceAfter=4))
            for src in sources:
                if isinstance(src, dict):
                    title = _esc(src.get("title", ""))
                    url   = _esc(src.get("url", ""))
                    line  = f"• {title}" + (f"  —  {url}" if url else "")
                else:
                    line = f"• {_esc(str(src))}"
                flow.append(Paragraph(line, S["body_small"]))
            flow.append(Spacer(1, 8))

        # ── 8. Audit Trail Table (optional) ───────────────────────────────────
        if include_audit_trail and audit_entries:
            flow.append(Paragraph("Audit Trail (Hash-Verified)", S["section_heading"]))
            flow.append(HRFlowable(width="100%", thickness=0.5, color=_C_BORDER, spaceAfter=4))

            audit_rows = [["Agent", "Action Type", "Timestamp", "Chain Hash"]]
            for entry in audit_entries[:20]:  # cap at 20 rows for one-page fit
                chain_hash = str(entry.get("chain_hash", "") or "")
                audit_rows.append([
                    Paragraph(_esc(entry.get("agent_name", "")),   S["table_cell"]),
                    Paragraph(_esc(entry.get("action_type", "")),  S["table_cell"]),
                    Paragraph(_esc(str(entry.get("created_at", ""))), S["table_cell"]),
                    Paragraph(_esc(f"…{chain_hash[-8:]}"),          S["table_cell"]),
                ])

            audit_table = Table(
                audit_rows,
                colWidths=[usable_w * 0.22, usable_w * 0.24, usable_w * 0.32, usable_w * 0.22],
            )
            audit_table.setStyle(_dark_table_style(header_color=colors.HexColor("#1e293b")))
            flow.append(audit_table)
            flow.append(Spacer(1, 8))

        # ── 9. Footer ─────────────────────────────────────────────────────────
        flow.append(HRFlowable(width="100%", thickness=0.5, color=_C_BORDER, spaceBefore=8))
        flow.append(Paragraph(
            "Generated by Iroko AI Enterprise Intelligence Platform  |  "
            "Hash-verified audit trail  |  CONFIDENTIAL — NOT FOR DISTRIBUTION",
            S["footer"],
        ))

        doc.build(flow)
        logger.info(
            "[BriefGenerator] generate_brief: verdict=%s workspace=%s audit=%s bytes~%d",
            verdict, workspace_name, include_audit_trail, buf.tell(),
        )
        return buf.getvalue()

    # ── 2. Weekly Regulatory Digest ───────────────────────────────────────────

    def generate_regulatory_digest(
        self,
        ncc_updates: list[dict[str, Any]],
        workspace_name: str = "MTN Nigeria",
    ) -> bytes:
        """
        Generate a "Weekly Regulatory Digest" PDF from live NCC update dicts.

        Each update is expected to have the shape returned by
        ``NCCLiveRulesService.compile_live_enforcement_rules()``
        ``live_updates`` items::

            {
                "update": {"title": str, "url": str, "summary": str, "date_str": str, "source": str},
                "matched_regulation_id": str | None,
                "matched_section":       str | None,
                "confidence":            float,
                "action_required":       bool,
            }

        Page structure
        --------------
        1. Header + date range
        2. Title: "Weekly NCC Regulatory Digest"
        3. Summary table: Update Title | Source | Regulation Matched | Action Required
        4. Per-regulation breakdown sections (obligations summary)
        5. Footer

        Parameters
        ----------
        ncc_updates : list[dict]
            Live update dicts from ``compile_live_enforcement_rules()["live_updates"]``.
        workspace_name : str
            Tenant name for the document header.

        Returns
        -------
        bytes
            PDF as raw bytes.
        """
        from services.regulatory_service import NCC_REGULATIONS  # local import avoids circulars

        buf = io.BytesIO()
        page_w, page_h = A4
        margin = 1.8 * cm
        usable_w = page_w - 2 * margin

        doc = SimpleDocTemplate(
            buf,
            pagesize=A4,
            leftMargin=margin,
            rightMargin=margin,
            topMargin=margin,
            bottomMargin=margin,
            title="Iroko AI Weekly NCC Regulatory Digest",
            author="Iroko AI Platform",
            subject=f"Regulatory Digest — {workspace_name}",
        )

        S = _build_styles()
        flow: list[Any] = []
        today = _now_display()

        # ── Header ────────────────────────────────────────────────────────────
        hdr = Table(
            [[
                Paragraph("IROKO AI  |  REGULATORY INTELLIGENCE", S["header_left"]),
                Paragraph(f"CONFIDENTIAL  |  {today}", S["confidential"]),
            ]],
            colWidths=[usable_w * 0.6, usable_w * 0.4],
        )
        hdr.setStyle(TableStyle([
            ("VALIGN",       (0, 0), (-1, -1), "MIDDLE"),
            ("LEFTPADDING",  (0, 0), (-1, -1), 0),
            ("RIGHTPADDING", (0, 0), (-1, -1), 0),
            ("TOPPADDING",   (0, 0), (-1, -1), 0),
            ("BOTTOMPADDING",(0, 0), (-1, -1), 0),
        ]))
        flow.append(hdr)
        flow.append(HRFlowable(width="100%", thickness=2, color=_C_HEADER, spaceAfter=10))

        # ── Title ─────────────────────────────────────────────────────────────
        flow.append(Paragraph("Weekly NCC Regulatory Digest", S["digest_title"]))
        flow.append(Paragraph(
            f"{_esc(workspace_name)}  |  Compiled: {today}  |  {len(ncc_updates)} updates processed",
            S["subtitle"],
        ))
        flow.append(Spacer(1, 8))

        # ── Summary table ─────────────────────────────────────────────────────
        flow.append(Paragraph("Update Summary", S["section_heading"]))
        flow.append(HRFlowable(width="100%", thickness=0.5, color=_C_BORDER, spaceAfter=4))

        summary_rows = [["Update Title", "Source", "Regulation Matched", "Action Required"]]
        for item in ncc_updates:
            update      = item.get("update", {}) if isinstance(item.get("update"), dict) else {}
            title       = _esc(update.get("title", "—"))[:60]
            source      = _esc(update.get("source", "ncc_serp"))
            reg_id      = _esc(item.get("matched_regulation_id") or "Unclassified")
            action_req  = "YES" if item.get("action_required") else "No"
            summary_rows.append([
                Paragraph(title, S["table_cell"]),
                Paragraph(source, S["table_cell"]),
                Paragraph(reg_id, S["table_cell"]),
                Paragraph(action_req, S["table_cell"]),
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
            colWidths=[usable_w * 0.38, usable_w * 0.15, usable_w * 0.23, usable_w * 0.24],
        )
        summary_table.setStyle(_dark_table_style())
        flow.append(summary_table)
        flow.append(Spacer(1, 14))

        # ── Per-regulation breakdown ───────────────────────────────────────────
        # Collect which regulations appeared in the updates
        seen_regs: dict[str, list[dict]] = {}
        for item in ncc_updates:
            reg_id = item.get("matched_regulation_id")
            if reg_id:
                seen_regs.setdefault(reg_id, []).append(item)

        if seen_regs:
            flow.append(Paragraph("Regulation Breakdown", S["section_heading"]))
            flow.append(HRFlowable(width="100%", thickness=0.5, color=_C_BORDER, spaceAfter=6))

            # Build a regulation ID → full reg dict lookup
            reg_index = {r["id"]: r for r in NCC_REGULATIONS}

            for reg_id, items in sorted(seen_regs.items()):
                reg = reg_index.get(reg_id, {})
                reg_name = reg.get("name", reg_id)

                flow.append(Paragraph(
                    f"{_esc(reg_id)}  —  {_esc(reg_name)}",
                    ParagraphStyle(
                        "RegSubhead",
                        parent=S["section_heading"],
                        fontSize=10,
                        textColor=colors.HexColor("#334155"),
                        spaceBefore=8,
                        spaceAfter=2,
                    ),
                ))

                # Obligations summary
                obligations = reg.get("obligations", [])
                if obligations:
                    for ob in obligations[:3]:
                        flow.append(Paragraph(f"  •  {_esc(ob)}", S["body_small"]))

                # Updates matched to this regulation
                action_count = sum(1 for it in items if it.get("action_required"))
                if action_count:
                    flow.append(Paragraph(
                        f"  {action_count} update(s) require immediate action under this regulation.",
                        ParagraphStyle(
                            "ActionNote",
                            parent=S["body_small"],
                            textColor=_C_NO_GO,
                            fontName="Helvetica-Bold",
                        ),
                    ))
                flow.append(Spacer(1, 4))

        # ── Footer ────────────────────────────────────────────────────────────
        flow.append(HRFlowable(width="100%", thickness=0.5, color=_C_BORDER, spaceBefore=8))
        flow.append(Paragraph(
            "Generated by Iroko AI Enterprise Intelligence Platform  |  "
            "Source: NCC Nigeria (ncc.gov.ng) via Bright Data  |  CONFIDENTIAL",
            S["footer"],
        ))

        doc.build(flow)
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

    Parameters
    ----------
    brief_bytes : bytes
        Raw PDF bytes from ``generate_brief()`` or ``generate_regulatory_digest()``.
    filename : str
        Suggested download filename.

    Returns
    -------
    fastapi.Response
        Streaming-compatible response with ``application/pdf`` MIME type.

    Example usage in a FastAPI route::

        from services.brief_generator import brief_generator, get_brief_response

        @router.get("/brief/{workspace_id}")
        async def download_brief(...):
            pdf = brief_generator.generate_brief(verdict_output, workspace_name="MTN Nigeria")
            return await get_brief_response(pdf, "mtn_compliance_brief.pdf")
    """
    # Import inside function to avoid hard dependency when module is imported
    # in non-FastAPI contexts (e.g. unit tests, CLI scripts).
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
"""
Shared ``ComplianceBriefGenerator`` singleton.

Import and use directly::

    from services.brief_generator import brief_generator, get_brief_response

    pdf = brief_generator.generate_brief(verdict_output)
    pdf = brief_generator.generate_regulatory_digest(live_updates)
    return await get_brief_response(pdf, "brief.pdf")
"""
