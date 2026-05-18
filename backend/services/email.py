import os
import logging
from azure.communication.email import EmailClient

logger = logging.getLogger(__name__)

SENDER = "DoNotReply@2e268f16-5cee-4935-9fe2-37a5804a2466.azurecomm.net"
PLATFORM_NAME = "Iroko AI"
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:3000")

# Modern Styling Variables
BRAND_COLOR = "#F5C71A"  # Slightly more sophisticated gold
TEXT_DARK = "#1A1A1A"
TEXT_GRAY = "#666666"
FONT_STACK = "-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif"

def _get_client() -> EmailClient:
    conn_str = os.getenv("ACS_CONNECTION_STRING")
    if not conn_str:
        raise RuntimeError("ACS_CONNECTION_STRING is not set.")
    return EmailClient.from_connection_string(conn_str)

def get_base_template(content_html: str) -> str:
    """Wraps content in a modern, responsive shell."""
    return f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{PLATFORM_NAME}</title>
</head>
<body style="margin:0;padding:0;background-color:#ffffff;font-family:{FONT_STACK};-webkit-font-smoothing:antialiased;">
    <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0">
        <tr>
            <td align="center" style="padding: 40px 20px;">
                <table role="presentation" width="100%" style="max-width:540px;text-align:left;" cellspacing="0" cellpadding="0" border="0">
                    <!-- Logo/Header -->
                    <tr>
                        <td style="padding-bottom: 32px;">
                            <div style="font-size: 20px; font-weight: 800; letter-spacing: -0.5px; color: {TEXT_DARK};">
                                IROKO <span style="color: {BRAND_COLOR};">AI</span>
                            </div>
                        </td>
                    </tr>
                    {content_html}
                    <!-- Footer -->
                    <tr>
                        <td style="padding-top: 48px; border-top: 1px solid #EEEEEE;">
                            <p style="margin: 0; font-size: 12px; color: #999999; line-height: 1.5;">
                                Sent by <strong>{PLATFORM_NAME}</strong> • Enterprise Document Intelligence<br>
                                This is an automated security message. Please do not reply.
                            </p>
                        </td>
                    </tr>
                </table>
            </td>
        </tr>
    </table>
</body>
</html>
"""

def send_invite_email(to_email: str, invited_by_name: str, invite_token: str, role: str, department: str | None, personal_message: str | None) -> bool:
    invite_url = f"{FRONTEND_URL}/invite?token={invite_token}"
    
    dept_section = f"<p style='margin: 0 0 16px 0;'><strong>Team:</strong> {department}</p>" if department else ""
    personal_section = (
        f"<div style='margin: 24px 0; padding: 16px; border-left: 2px solid {BRAND_COLOR}; background-color: #FAFAFA; color: {TEXT_GRAY}; font-style: italic;'>"
        f"\"{personal_message}\"</div>"
        if personal_message else ""
    )

    body_content = f"""
    <tr>
        <td>
            <h2 style="margin: 0 0 16px 0; font-size: 24px; font-weight: 700; color: {TEXT_DARK}; letter-spacing: -0.5px;">
                Join the workspace
            </h2>
            <p style="margin: 0 0 24px 0; font-size: 16px; line-height: 1.6; color: {TEXT_GRAY};">
                <strong>{invited_by_name}</strong> has invited you to collaborate on <strong>{PLATFORM_NAME}</strong> as a 
                <span style="display: inline-block; background: #EEE; padding: 2px 8px; border-radius: 12px; font-size: 12px; font-weight: 600; color: #444;">{role.upper()}</span>.
            </p>
            {dept_section}
            {personal_section}
            <table role="presentation" cellspacing="0" cellpadding="0" border="0" style="margin: 32px 0;">
                <tr>
                    <td align="center" bgcolor="{TEXT_DARK}" style="border-radius: 6px;">
                        <a href="{invite_url}" target="_blank" style="padding: 14px 28px; font-size: 15px; font-weight: 600; color: #FFFFFF; text-decoration: none; display: inline-block;">
                            Get Started
                        </a>
                    </td>
                </tr>
            </table>
            <p style="font-size: 13px; color: #999999; margin-bottom: 40px;">
                Link expires in 48 hours. <br>
                <a href="{invite_url}" style="color: {TEXT_GRAY}; text-decoration: underline;">Or click here to accept</a>
            </p>
        </td>
    </tr>
    """
    
    return _execute_send(to_email, f"Invitation to join {PLATFORM_NAME}", body_content)

def send_password_reset_email(to_email: str, full_name: str, reset_token: str) -> bool:
    reset_url = f"{FRONTEND_URL}/auth/reset-password?token={reset_token}"
    display_name = full_name.split()[0] if full_name else "there" # More personal first-name greeting

    body_content = f"""
    <tr>
        <td>
            <h2 style="margin: 0 0 16px 0; font-size: 24px; font-weight: 700; color: {TEXT_DARK}; letter-spacing: -0.5px;">
                Reset your password
            </h2>
            <p style="margin: 0 0 24px 0; font-size: 16px; line-height: 1.6; color: {TEXT_GRAY};">
                Hi {display_name}, we received a request to reset your password for your {PLATFORM_NAME} account. 
                If you didn't make this request, you can safely ignore this email.
            </p>
            <table role="presentation" cellspacing="0" cellpadding="0" border="0" style="margin: 32px 0;">
                <tr>
                    <td align="center" bgcolor="{BRAND_COLOR}" style="border-radius: 6px;">
                        <a href="{reset_url}" target="_blank" style="padding: 14px 28px; font-size: 15px; font-weight: 700; color: {TEXT_DARK}; text-decoration: none; display: inline-block;">
                            Reset Password
                        </a>
                    </td>
                </tr>
            </table>
            <p style="font-size: 13px; color: #999999; margin-bottom: 40px;">
                This link expires in 60 minutes for security reasons.
            </p>
        </td>
    </tr>
    """
    return _execute_send(to_email, "Password Reset Request", body_content)

async def send_morning_briefing_email(
    recipient_email: str,
    recipient_name: str,
    briefing: dict,
) -> bool:
    """Send a daily intelligence briefing to an admin/analyst user."""
    date_str = briefing.get("date", "Today")
    critical = briefing.get("critical_count", 0)
    warnings = briefing.get("warning_count", 0)
    queries = briefing.get("queries_24h", 0)

    alert_rows = "".join(
        f"<tr>"
        f"<td style='padding:8px 0;border-bottom:1px solid #EEE;'>"
        f"<span style='display:inline-block;padding:2px 8px;border-radius:10px;"
        f"background:{'#FDECEA' if a['severity']=='critical' else '#FFF8E1'};"
        f"color:{'#C0392B' if a['severity']=='critical' else '#F39C12'};"
        f"font-size:11px;font-weight:700;margin-right:8px;'>{a['severity'].upper()}</span>"
        f"{a['title']}</td></tr>"
        for a in briefing.get("top_alerts", [])
    ) or "<tr><td style='padding:8px 0;color:#999;'>No active alerts</td></tr>"

    gap_items = "".join(
        f"<li style='margin-bottom:6px;color:{TEXT_GRAY};'>{q}</li>"
        for q in briefing.get("top_gaps", [])
    ) or f"<li style='color:#999;'>No knowledge gaps logged in last 24h</li>"

    body_content = f"""
    <tr>
        <td>
            <h2 style="margin:0 0 4px 0;font-size:22px;font-weight:700;color:{TEXT_DARK};">
                Daily Intelligence Briefing
            </h2>
            <p style="margin:0 0 24px 0;font-size:14px;color:{TEXT_GRAY};">{date_str} &nbsp;•&nbsp; {recipient_name}</p>

            <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0"
                   style="margin-bottom:24px;background:#FAFAFA;border-radius:8px;padding:16px;">
                <tr>
                    <td style="width:33%;text-align:center;padding:8px;">
                        <div style="font-size:28px;font-weight:800;color:#C0392B;">{critical}</div>
                        <div style="font-size:12px;color:{TEXT_GRAY};">Critical Alerts</div>
                    </td>
                    <td style="width:33%;text-align:center;padding:8px;border-left:1px solid #EEE;border-right:1px solid #EEE;">
                        <div style="font-size:28px;font-weight:800;color:#F39C12;">{warnings}</div>
                        <div style="font-size:12px;color:{TEXT_GRAY};">Warnings</div>
                    </td>
                    <td style="width:33%;text-align:center;padding:8px;">
                        <div style="font-size:28px;font-weight:800;color:{TEXT_DARK};">{queries}</div>
                        <div style="font-size:12px;color:{TEXT_GRAY};">Queries (24h)</div>
                    </td>
                </tr>
            </table>

            <h3 style="margin:0 0 12px 0;font-size:15px;font-weight:700;color:{TEXT_DARK};">Active Alerts</h3>
            <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0"
                   style="margin-bottom:24px;">
                {alert_rows}
            </table>

            <h3 style="margin:0 0 8px 0;font-size:15px;font-weight:700;color:{TEXT_DARK};">Knowledge Gaps</h3>
            <p style="margin:0 0 8px 0;font-size:13px;color:{TEXT_GRAY};">
                Questions asked in the last 24h that Atlas could not answer:
            </p>
            <ul style="margin:0 0 24px 0;padding-left:20px;font-size:14px;">{gap_items}</ul>

            <table role="presentation" cellspacing="0" cellpadding="0" border="0" style="margin-top:8px;">
                <tr>
                    <td align="center" bgcolor="{TEXT_DARK}" style="border-radius:6px;">
                        <a href="{FRONTEND_URL}/dashboard" target="_blank"
                           style="padding:12px 24px;font-size:14px;font-weight:600;color:#FFFFFF;text-decoration:none;display:inline-block;">
                            Open Dashboard
                        </a>
                    </td>
                </tr>
            </table>
        </td>
    </tr>
    """
    return _execute_send(
        recipient_email,
        f"Iroko AI Briefing — {date_str}: {critical} critical, {warnings} warnings",
        body_content,
    )


def _execute_send(to_email: str, subject: str, body_content: str) -> bool:
    """Helper to wrap and send the email."""
    html_body = get_base_template(body_content)
    try:
        client = _get_client()
        poller = client.begin_send({
            "senderAddress": SENDER,
            "recipients": {"to": [{"address": to_email}]},
            "content": {
                "subject": subject,
                "plainText": "Please use an HTML-capable email client to view this message.",
                "html": html_body,
            },
        })
        poller.result()
        return True
    except Exception as exc:
        logger.error(f"Failed to send email to {to_email}: {exc}")
        return False