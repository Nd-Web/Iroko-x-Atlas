from fastapi import APIRouter, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel
import markdown
import datetime
from playwright.sync_api import sync_playwright
from fastapi.concurrency import run_in_threadpool
from services.azure_openai import get_chat_completion

router = APIRouter()

class PdfGenerateRequest(BaseModel):
    query: str | None = None
    original_response: str
    trace_id: str | None = None

@router.post("/generate")
async def generate_detailed_pdf(request: PdfGenerateRequest):
    try:
        # 1. Expand the response using Azure OpenAI
        prompt = f"""
        You are an expert intelligence analyst at Iroko AI. Your task is to expand the following summary response into a highly detailed, comprehensive, and professional Executive Intelligence Report (around 2 pages long).
        
        User Query / Context:
        {request.query or "N/A"}
        
        Original Summary Response:
        {request.original_response}
        
        Your expanded report MUST be written in Markdown format. Use professional headings, bullet points, and an analytical, authoritative tone. Include deep-dive sections, strategic implications, and actionable recommendations based on the provided context.
        Do not include any pleasantries or conversational filler. Start directly with the report content.
        """
        
        expanded_content = await get_chat_completion(
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2,
            max_tokens=4000
        )
        
        # 2. Convert expanded Markdown to HTML
        html_content = markdown.markdown(expanded_content)
        
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        trace_id = request.trace_id or "AI-EXPANDED-REPORT"
        
        # 3. Create full HTML template
        full_html = f"""
        <!DOCTYPE html>
        <html>
          <head>
            <meta charset="utf-8">
            <title>Iroko AI - Executive Intelligence Report</title>
            <style>
              @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&display=swap');
              body {{
                font-family: 'Inter', sans-serif;
                color: #111827;
                padding: 0;
                margin: 0;
                line-height: 1.6;
              }}
              .container {{
                padding: 20px 40px;
              }}
              .header {{
                border-bottom: 3px solid #3B7BF6;
                padding-bottom: 18px;
                margin-bottom: 28px;
                display: flex;
                justify-content: space-between;
                align-items: flex-end;
              }}
              .header .brand {{
                color: #3B7BF6;
                font-weight: 700;
                font-size: 11px;
                text-transform: uppercase;
                letter-spacing: 2px;
                margin-bottom: 4px;
              }}
              .header h1 {{
                font-size: 22px;
                font-weight: 700;
                color: #111827;
                margin: 0;
              }}
              .header .meta-right {{
                text-align: right;
                font-size: 11px;
                color: #6B7280;
              }}
              .meta-box {{
                background: #F9FAFB;
                border: 1px solid #E5E7EB;
                border-radius: 6px;
                padding: 12px 16px;
                margin-bottom: 28px;
                font-size: 11px;
                color: #6B7280;
              }}
              .content {{
                font-size: 13px;
                color: #1F2937;
              }}
              .content h1, .content h2, .content h3 {{ color: #111827; margin-top: 1.5em; margin-bottom: 0.5em; }}
              .content h1 {{ font-size: 20px; border-bottom: 1px solid #E5E7EB; padding-bottom: 8px; }}
              .content p {{ margin-bottom: 1em; }}
              .content ul, .content ol {{ margin-bottom: 1em; padding-left: 20px; }}
              .content li {{ margin-bottom: 0.5em; }}
              .content pre {{ background: #F3F4F6; padding: 15px; border-radius: 6px; overflow-x: auto; font-family: monospace; font-size: 12px; }}
              .content code {{ font-family: monospace; background: #F3F4F6; padding: 2px 4px; border-radius: 4px; font-size: 12px; }}
              .content blockquote {{ border-left: 4px solid #3B7BF6; margin: 0; padding-left: 15px; color: #4B5563; font-style: italic; }}
              .content table {{ width: 100%; border-collapse: collapse; margin-bottom: 1em; font-size: 13px; }}
              .content th, .content td {{ border: 1px solid #E5E7EB; padding: 10px; text-align: left; }}
              .content th {{ background: #F9FAFB; font-weight: 600; }}
              .footer {{
                margin-top: 50px;
                padding-top: 16px;
                border-top: 1px solid #E5E7EB;
                font-size: 9px;
                color: #9CA3AF;
                text-align: center;
              }}
            </style>
          </head>
          <body>
            <div class="container">
              <div class="header">
                <div>
                  <div class="brand">Iroko AI Platform</div>
                  <h1>Detailed Executive Intelligence Report</h1>
                </div>
                <div class="meta-right">
                  <div><strong>Generated:</strong> {timestamp}</div>
                  <div><strong>Classification:</strong> Confidential</div>
                </div>
              </div>
              <div class="meta-box">
                <div><strong style="color: #374151;">Subject:</strong> &nbsp;AI Automated Analysis (Expanded)</div>
                <div style="margin-top: 4px;"><strong style="color: #374151;">Trace ID:</strong> &nbsp;{trace_id}</div>
              </div>
              <div class="content">
                {html_content}
              </div>
              <div class="footer">
                CONFIDENTIAL — Generated by Iroko AI · Powered by Atlas Intelligence Engine · {timestamp}
              </div>
            </div>
          </body>
        </html>
        """
        
        # 4. Generate PDF using Playwright synchronously in a background thread
        def generate_pdf_sync(html_content: str) -> bytes:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                page = browser.new_page()
                page.set_content(html_content)
                page.wait_for_timeout(800)
                pdf_data = page.pdf(
                    format="A4",
                    margin={"top": "15mm", "bottom": "15mm", "left": "15mm", "right": "15mm"},
                    print_background=True
                )
                browser.close()
                return pdf_data

        pdf_bytes = await run_in_threadpool(generate_pdf_sync, full_html)
            
        return Response(
            content=pdf_bytes, 
            media_type="application/pdf", 
            headers={"Content-Disposition": 'attachment; filename="iroko-ai-detailed-report.pdf"'}
        )
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))
