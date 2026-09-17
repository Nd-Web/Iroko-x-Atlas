from fastapi import APIRouter, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel
import html as html_escape
import markdown
import datetime
from playwright.sync_api import sync_playwright
from fastapi.concurrency import run_in_threadpool
from services.azure_openai import get_chat_completion

router = APIRouter()


class PdfCitation(BaseModel):
    document_id: str | None = None
    document_title: str | None = None
    source: str | None = None
    excerpt: str | None = None


class PdfGenerateRequest(BaseModel):
    query: str | None = None
    original_response: str
    trace_id: str | None = None
    citations: list[PdfCitation] | None = None


@router.post("/generate")
async def generate_detailed_pdf(request: PdfGenerateRequest):
    try:
        citation_lines = ""
        if request.citations:
            titles = [
                c.document_title or c.source or c.document_id or "Source document"
                for c in request.citations
            ]
            citation_lines = "\n".join(f"- {t}" for t in titles)

        # 1. Summarise the response using Azure OpenAI — short, plain, clear.
        prompt = f"""
        You are an analyst at Iroko AI. Write a SHORT, plain, clear summary of the analysis below
        for a microfinance bank / fintech compliance team — NOT a long report. Keep it to about one page and skip all filler.

        User Question:
        {request.query or "N/A"}

        Analysis to summarise:
        {request.original_response}

        {"Source documents cited by the analysis:" + chr(10) + citation_lines if citation_lines else ""}

        Write it in Markdown with these short sections (use these as ## headings):
        1. Summary — 2 to 4 plain sentences with the key takeaway and any headline figure.
        2. Key Points — a short bulleted list (5 bullets max), each one line, each with its metric or evidence.
        3. Recommended Actions — a short bulleted list (4 bullets max), each one line, with an owner where clear.

        Only if the analysis concerns regulatory compliance, add ONE final line formatted exactly as
        **VERDICT: GO** or **VERDICT: MONITOR** or **VERDICT: NO-GO** with a one-line reason; otherwise omit it.

        Rules: plain, clear English; be brief and do not pad to fill space; ground every claim in the
        provided analysis; never invent numbers; no pleasantries or filler; start directly with the first heading.
        """

        expanded_content = await get_chat_completion(
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2,
            max_tokens=1200,
        )

        # 2. Convert expanded Markdown to HTML — tables/fenced-code extensions are
        #    essential, otherwise Markdown tables render as literal pipe characters.
        html_content = markdown.markdown(
            expanded_content,
            extensions=["tables", "fenced_code", "sane_lists"],
        )
        # Highlight the verdict line as a badge
        for verdict, color, bg in (
            ("GO", "#047857", "#D1FAE5"),
            ("MONITOR", "#B45309", "#FEF3C7"),
            ("NO-GO", "#B91C1C", "#FEE2E2"),
        ):
            html_content = html_content.replace(
                f"<strong>VERDICT: {verdict}</strong>",
                f'<span class="verdict" style="color:{color};background:{bg};">VERDICT: {verdict}</span>',
            )

        now = datetime.datetime.now()
        timestamp = now.strftime("%d %B %Y · %H:%M")
        file_date = now.strftime("%Y-%m-%d")
        trace_id = request.trace_id or "AI-EXPANDED-REPORT"
        subject = html_escape.escape((request.query or "AI Automated Analysis").strip())
        if len(subject) > 160:
            subject = subject[:157] + "…"

        sources_html = ""
        if request.citations:
            items = "".join(
                f'<div class="source-item"><span class="source-dot"></span>'
                f"{html_escape.escape(c.document_title or c.source or c.document_id or 'Source document')}</div>"
                for c in request.citations
            )
            sources_html = f"""
              <div class="sources">
                <div class="sources-title">Cited Sources ({len(request.citations)})</div>
                {items}
                <p class="sources-note">Every claim in this report is grounded in the organisation's indexed document corpus. Full passage-level citations are available in the Iroko audit trail under trace {html_escape.escape(trace_id)}.</p>
              </div>
            """

        # 3. Full HTML template — system fonts only (no network fetch), print-safe
        full_html = f"""
        <!DOCTYPE html>
        <html>
          <head>
            <meta charset="utf-8">
            <title>Iroko AI — Intelligence Summary</title>
            <style>
              * {{ box-sizing: border-box; }}
              body {{
                font-family: 'Segoe UI', -apple-system, 'Helvetica Neue', Arial, sans-serif;
                color: #111827; padding: 0; margin: 0; line-height: 1.65;
                -webkit-print-color-adjust: exact;
              }}
              .brandbar {{
                height: 6px;
                background: linear-gradient(90deg, #3B7BF6 0%, #8B5CF6 60%, #4A55D4 100%);
              }}
              .container {{ padding: 26px 44px; }}
              .header {{
                display: flex; justify-content: space-between; align-items: flex-start;
                border-bottom: 2px solid #E5E7EB; padding-bottom: 18px; margin-bottom: 20px;
              }}
              .logo-row {{ display: flex; align-items: center; gap: 12px; }}
              .logo-mark {{
                width: 40px; height: 40px; border-radius: 10px; background: #4A55D4;
                display: flex; align-items: center; justify-content: center; flex-shrink: 0;
              }}
              .brand {{ color: #4A55D4; font-weight: 700; font-size: 10px; text-transform: uppercase; letter-spacing: 2px; }}
              .header h1 {{ font-size: 21px; font-weight: 700; color: #111827; margin: 2px 0 0; letter-spacing: -0.02em; }}
              .meta-right {{ text-align: right; font-size: 10.5px; color: #6B7280; line-height: 1.7; }}
              .meta-right .cls {{
                display: inline-block; font-weight: 700; color: #B91C1C; background: #FEE2E2;
                border-radius: 99px; padding: 1px 10px; font-size: 9.5px; letter-spacing: 1px;
              }}
              .subject-box {{
                background: #F5F7FF; border: 1px solid #DDE3F8; border-left: 4px solid #4A55D4;
                border-radius: 6px; padding: 12px 16px; margin-bottom: 24px;
              }}
              .subject-box .label {{ font-size: 9.5px; font-weight: 700; color: #4A55D4; text-transform: uppercase; letter-spacing: 1.5px; margin-bottom: 3px; }}
              .subject-box .q {{ font-size: 13.5px; font-weight: 600; color: #1F2937; }}
              .subject-box .trace {{ font-size: 10px; color: #9CA3AF; margin-top: 5px; font-family: Consolas, monospace; }}
              .content {{ font-size: 12.5px; color: #1F2937; }}
              .content h2 {{
                font-size: 15px; color: #111827; margin: 1.6em 0 0.5em;
                padding-bottom: 6px; border-bottom: 1px solid #E5E7EB;
                page-break-after: avoid;
              }}
              .content h2:first-child {{ margin-top: 0; }}
              .content h3 {{ font-size: 13px; color: #374151; margin: 1.2em 0 0.4em; page-break-after: avoid; }}
              .content p {{ margin: 0 0 0.9em; }}
              .content ul, .content ol {{ margin: 0 0 1em; padding-left: 20px; }}
              .content li {{ margin-bottom: 0.4em; }}
              .content strong {{ color: #111827; }}
              .content table {{
                width: 100%; border-collapse: collapse; margin: 0.6em 0 1.2em;
                font-size: 11.5px; page-break-inside: avoid;
              }}
              .content th {{
                background: #111827; color: #F9FAFB; font-weight: 600; text-align: left;
                padding: 8px 12px; font-size: 10.5px; text-transform: uppercase; letter-spacing: 0.5px;
              }}
              .content td {{ border: 1px solid #E5E7EB; padding: 8px 12px; vertical-align: top; }}
              .content tr:nth-child(even) td {{ background: #F9FAFB; }}
              .content blockquote {{ border-left: 3px solid #4A55D4; margin: 0 0 1em; padding: 4px 0 4px 14px; color: #4B5563; font-style: italic; }}
              .content code {{ font-family: Consolas, monospace; background: #F3F4F6; padding: 1px 5px; border-radius: 4px; font-size: 11px; }}
              .content pre {{ background: #F3F4F6; padding: 14px; border-radius: 6px; overflow-x: auto; font-size: 11px; }}
              .verdict {{
                display: inline-block; font-weight: 800; border-radius: 99px;
                padding: 3px 14px; font-size: 12px; letter-spacing: 0.5px;
              }}
              .sources {{
                margin-top: 28px; background: #F9FAFB; border: 1px solid #E5E7EB;
                border-radius: 8px; padding: 16px 18px; page-break-inside: avoid;
              }}
              .sources-title {{ font-size: 10.5px; font-weight: 700; color: #374151; text-transform: uppercase; letter-spacing: 1.5px; margin-bottom: 10px; }}
              .source-item {{ font-size: 11.5px; color: #4B5563; margin-bottom: 5px; display: flex; align-items: center; gap: 8px; }}
              .source-dot {{ width: 6px; height: 6px; border-radius: 50%; background: #4A55D4; flex-shrink: 0; }}
              .sources-note {{ font-size: 9.5px; color: #9CA3AF; margin: 10px 0 0; line-height: 1.5; }}
            </style>
          </head>
          <body>
            <div class="brandbar"></div>
            <div class="container">
              <div class="header">
                <div class="logo-row">
                  <div class="logo-mark">
                    <svg width="22" height="22" viewBox="0 0 22 22" fill="none">
                      <path d="M11 2.5L17.5 6.5V14.5L11 18.5L4.5 14.5V6.5L11 2.5Z" stroke="white" stroke-width="1.5" stroke-linejoin="round" fill="none"/>
                      <circle cx="11" cy="10.5" r="2.25" fill="white"/>
                    </svg>
                  </div>
                  <div>
                    <div class="brand">Iroko AI · Document Intelligence</div>
                    <h1>Intelligence Summary</h1>
                  </div>
                </div>
                <div class="meta-right">
                  <div><span class="cls">CONFIDENTIAL</span></div>
                  <div style="margin-top:6px;"><strong>Generated:</strong> {timestamp}</div>
                </div>
              </div>
              <div class="subject-box">
                <div class="label">Subject of analysis</div>
                <div class="q">{subject}</div>
                <div class="trace">Trace: {html_escape.escape(trace_id)}</div>
              </div>
              <div class="content">
                {html_content}
              </div>
              {sources_html}
            </div>
          </body>
        </html>
        """

        # 4. Generate PDF using Playwright with numbered page footers
        def generate_pdf_sync(html_doc: str) -> bytes:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                page = browser.new_page()
                page.set_content(html_doc, wait_until="load")
                pdf_data = page.pdf(
                    format="A4",
                    margin={"top": "14mm", "bottom": "18mm", "left": "13mm", "right": "13mm"},
                    print_background=True,
                    display_header_footer=True,
                    header_template="<span></span>",
                    footer_template=(
                        '<div style="width:100%;font-size:8px;color:#9CA3AF;'
                        'padding:0 13mm;display:flex;justify-content:space-between;'
                        "font-family:'Segoe UI',Arial,sans-serif;\">"
                        "<span>CONFIDENTIAL — Generated by Iroko AI · Multi-Agent Intelligence Engine</span>"
                        '<span>Page <span class="pageNumber"></span> of <span class="totalPages"></span></span>'
                        "</div>"
                    ),
                )
                browser.close()
                return pdf_data

        pdf_bytes = await run_in_threadpool(generate_pdf_sync, full_html)

        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={
                "Content-Disposition": f'attachment; filename="iroko-intelligence-report-{file_date}.pdf"'
            },
        )
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))
