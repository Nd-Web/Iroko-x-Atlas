"""Zoho SMTP delivery for pilot booking notifications."""

from __future__ import annotations

import logging
import os
import smtplib
from email.message import EmailMessage
from html import escape

from models.pilot_request import PilotRequest

logger = logging.getLogger(__name__)

WAT_LABEL = "West Africa Time (WAT)"


def _smtp_send(message: EmailMessage) -> None:
    host = os.getenv("ZOHO_SMTP_HOST", "smtp.zoho.com")
    port = int(os.getenv("ZOHO_SMTP_PORT", "465"))
    username = os.getenv("ZOHO_SMTP_USERNAME", "")
    password = os.getenv("ZOHO_SMTP_PASSWORD", "")
    if not username or not password:
        raise RuntimeError("ZOHO_SMTP_USERNAME and ZOHO_SMTP_PASSWORD must be set")

    if port == 465:
        with smtplib.SMTP_SSL(host, port, timeout=20) as smtp:
            smtp.login(username, password)
            smtp.send_message(message)
    else:
        with smtplib.SMTP(host, port, timeout=20) as smtp:
            smtp.ehlo()
            smtp.starttls()
            smtp.ehlo()
            smtp.login(username, password)
            smtp.send_message(message)


def _safe_smtp_send(message: EmailMessage) -> None:
    try:
        _smtp_send(message)
    except Exception:
        logger.exception('Failed to send pilot email to %s', message.get('To'))


def _message(to_email: str, subject: str, text: str, html: str) -> EmailMessage:
    sender = os.getenv("PILOT_FROM_EMAIL") or os.getenv("ZOHO_SMTP_USERNAME", "")
    if not sender:
        raise RuntimeError("PILOT_FROM_EMAIL or ZOHO_SMTP_USERNAME must be set")
    message = EmailMessage()
    message["From"] = sender
    message["To"] = to_email
    message["Subject"] = subject
    message.set_content(text)
    message.add_alternative(html, subtype="html")
    return message


def send_pilot_booking_emails(booking: PilotRequest) -> None:
    """Send both emails after the booking transaction has committed."""
    try:
        slot = booking.slot_start.strftime("%A, %d %B %Y at %H:%M")
        goal = booking.pilot_goal or "Not provided"
        notification_email = os.getenv(
            "PILOT_NOTIFICATION_EMAIL", "ndubuisiekeh169@gmail.com"
        )

        rows = [
            ("Full name", booking.full_name),
            ("Work email", booking.work_email),
            ("Phone", booking.phone),
            ("Company", booking.company_name),
            ("Job title", booking.job_title),
            ("Company type", booking.company_type),
            ("Country", booking.country),
            ("Pilot goal", goal),
            ("Consent to contact", "Yes"),
            ("Onboarding call", f"{slot} {WAT_LABEL}"),
        ]
        admin_text = "New Iroko AI pilot request\n\n" + "\n".join(
            f"{label}: {value}" for label, value in rows
        )
        admin_rows = "".join(
            f"<tr><th align='left' style='padding:8px;border-bottom:1px solid #eee'>{escape(label)}</th>"
            f"<td style='padding:8px;border-bottom:1px solid #eee'>{escape(str(value))}</td></tr>"
            for label, value in rows
        )
        _safe_smtp_send(
            _message(
                notification_email,
                f"New pilot request from {booking.company_name}",
                admin_text,
                f"<h2>New Iroko AI pilot request</h2><table>{admin_rows}</table>",
            )
        )

        first_name = booking.full_name.split()[0]
        visitor_text = (
            f"Hi {first_name},\n\nWe've received your request for a free 30-day Iroko AI pilot. "
            f"Your onboarding call is booked for {slot} {WAT_LABEL}.\n\n"
            "Your 30-day pilot kicks off from this call. We'll contact you using the details you provided."
        )
        visitor_html = (
            f"<h2>You're booked, {escape(first_name)}.</h2>"
            "<p>We've received your request for a free 30-day Iroko AI pilot.</p>"
            f"<p><strong>Onboarding call:</strong><br>{escape(slot)} {WAT_LABEL}</p>"
            "<p>Your 30-day pilot kicks off from this call. We'll contact you using the details you provided.</p>"
        )
        _safe_smtp_send(
            _message(
                booking.work_email,
                "We've received your pilot request",
                visitor_text,
                visitor_html,
            )
        )
    except Exception:
        # The booking remains valid if SMTP is temporarily unavailable.
        logger.exception("Failed to send pilot booking emails for %s", booking.id)
