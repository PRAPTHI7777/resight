import logging
import os
import re
from email.message import EmailMessage
from email.utils import getaddresses

import requests


logger = logging.getLogger(__name__)
RESEND_EMAILS_URL = "https://api.resend.com/emails"
RESEND_TIMEOUT_SECONDS = 10
_ERROR_NAME_PATTERN = re.compile(r"[A-Za-z0-9_-]{1,64}")


def _message_payload(message: EmailMessage, sender: str) -> dict:
    recipients = [
        address
        for _, address in getaddresses(message.get_all("To", []))
        if address
    ]
    if not recipients:
        raise RuntimeError("Email requires at least one valid recipient.")

    payload = {
        "from": sender,
        "to": recipients,
        "subject": str(message.get("Subject", "")),
    }

    for part in message.walk():
        if part.get_content_maintype() != "text":
            continue
        subtype = part.get_content_subtype()
        if subtype in {"plain", "html"}:
            body_field = "text" if subtype == "plain" else "html"
            payload[body_field] = part.get_content()

    if "text" not in payload and "html" not in payload:
        raise RuntimeError("Email requires a plain-text or HTML body.")

    return payload


def send_message(message: EmailMessage) -> None:
    api_key = os.getenv("RESEND_API_KEY", "").strip()
    sender = os.getenv("RESEND_FROM_EMAIL", "").strip()
    if not api_key or not sender:
        logger.error(
            "Resend email configuration is incomplete (missing API key or sender)."
        )
        raise RuntimeError(
            "RESEND_API_KEY and RESEND_FROM_EMAIL must be configured."
        )

    payload = _message_payload(message, sender)
    try:
        response = requests.post(
            RESEND_EMAILS_URL,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=RESEND_TIMEOUT_SECONDS,
        )
    except requests.RequestException as error:
        logger.warning("Resend email request failed (%s).", type(error).__name__)
        raise RuntimeError("The email provider request failed.") from error

    if not 200 <= response.status_code < 300:
        try:
            error_body = response.json()
        except ValueError:
            error_body = {}
        error_name = (
            error_body.get("name")
            if isinstance(error_body, dict)
            else None
        )
        if not isinstance(error_name, str) or not _ERROR_NAME_PATTERN.fullmatch(
            error_name
        ):
            error_name = "unknown"
        logger.warning(
            "Resend rejected an email request (HTTP %s, error=%s).",
            response.status_code,
            error_name,
        )
        raise RuntimeError(
            "The email provider rejected the request "
            f"(HTTP {response.status_code}, error={error_name})."
        )


def send_email(to_email: str, subject: str, body: str) -> None:
    message = EmailMessage()
    message["To"] = to_email
    message["Subject"] = subject
    message.add_alternative(body, subtype="html")
    send_message(message)
