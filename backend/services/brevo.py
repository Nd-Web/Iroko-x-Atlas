"""Brevo HTTPS API client for Iroko transactional email."""

from __future__ import annotations

import os

import httpx


def send_message(*, sender: str, recipient: str, subject: str, text: str, html: str) -> None:
    token = os.getenv("BREVO_API_KEY", "").strip()
    if not token:
        raise RuntimeError("BREVO_API_KEY is not configured")
    response = httpx.post(
        "https://api.brevo.com/v3/smtp/email",
        headers={
            "accept": "application/json",
            "api-key": token,
            "content-type": "application/json",
        },
        json={
            "sender": {"email": sender, "name": "Iroko AI"},
            "to": [{"email": recipient}],
            "replyTo": {"email": sender},
            "subject": subject,
            "textContent": text,
            "htmlContent": html,
        },
        timeout=20.0,
    )
    response.raise_for_status()
