import logging
import os
import re
from email.message import EmailMessage
from email.utils import getaddresses
from urllib.parse import urlsplit

import requests


logger = logging.getLogger(__name__)
GAS_EMAIL_RELAY_TIMEOUT_SECONDS = 30
MAX_EMAIL_RECIPIENTS = 50
MAX_EMAIL_SUBJECT_LENGTH = 250
MAX_EMAIL_BODY_BYTES = 100_000
_EMAIL_ADDRESS_PATTERN = re.compile(
    r"^[A-Z0-9.!#$%&'*+/=?^_`{|}~-]+@"
    r"[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?"
    r"(?:\.[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?)+$",
    re.IGNORECASE,
)
_SUBJECT_CONTROL_PATTERN = re.compile(r"[\x00-\x1f\x7f]")
_RELAY_ERROR_CODES = {
    "unauthorized",
    "invalid_request",
    "quota_exceeded",
    "delivery_failed",
    "internal_error",
}


def _message_payload(message: EmailMessage) -> dict:
    recipients = [
        address.strip()
        for _, address in getaddresses(message.get_all("To", []))
        if address.strip()
    ]
    if not recipients or len(recipients) > MAX_EMAIL_RECIPIENTS:
        raise RuntimeError("Email requires between 1 and 50 valid recipients.")
    if any(not _EMAIL_ADDRESS_PATTERN.fullmatch(address) for address in recipients):
        raise RuntimeError("Email contains an invalid recipient address.")

    subject = str(message.get("Subject", "")).strip()
    if (
        not subject
        or len(subject) > MAX_EMAIL_SUBJECT_LENGTH
        or _SUBJECT_CONTROL_PATTERN.search(subject)
    ):
        raise RuntimeError("Email subject is missing or invalid.")

    payload = {
        "to": recipients,
        "subject": subject,
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
    if not payload.get("text", "").strip() and not payload.get("html", "").strip():
        raise RuntimeError("Email body cannot be empty.")
    body_size = sum(
        len(payload.get(field, "").encode("utf-8"))
        for field in ("text", "html")
    )
    if body_size > MAX_EMAIL_BODY_BYTES:
        raise RuntimeError("Email body exceeds the supported size limit.")

    return payload


def send_message(message: EmailMessage) -> None:
    relay_url = os.getenv("GAS_EMAIL_RELAY_URL", "").strip()
    shared_secret = os.getenv("GAS_EMAIL_RELAY_SECRET", "").strip()
    if not relay_url or not shared_secret:
        logger.error("Google Apps Script email relay configuration is incomplete.")
        raise RuntimeError(
            "GAS_EMAIL_RELAY_URL and GAS_EMAIL_RELAY_SECRET must be configured."
        )
    try:
        parsed_url = urlsplit(relay_url)
    except ValueError as error:
        logger.error("Google Apps Script email relay URL is invalid.")
        raise RuntimeError(
            "GAS_EMAIL_RELAY_URL must be a deployed HTTPS web-app URL."
        ) from error
    if (
        parsed_url.scheme != "https"
        or parsed_url.hostname != "script.google.com"
        or not parsed_url.path.startswith("/macros/s/")
        or not parsed_url.path.endswith("/exec")
        or parsed_url.username
        or parsed_url.password
    ):
        logger.error("Google Apps Script email relay URL is invalid.")
        raise RuntimeError("GAS_EMAIL_RELAY_URL must be a deployed HTTPS web-app URL.")
    if not 32 <= len(shared_secret) <= 256:
        logger.error("Google Apps Script email relay secret has an invalid length.")
        raise RuntimeError("GAS_EMAIL_RELAY_SECRET must be 32 to 256 characters.")

    try:
        payload = _message_payload(message)
    except (TypeError, ValueError) as error:
        logger.warning("Email message headers or content are invalid.")
        raise RuntimeError("Email message is invalid.") from error
    payload["secret"] = shared_secret

    try:
        response = requests.post(
            relay_url,
            json=payload,
            timeout=GAS_EMAIL_RELAY_TIMEOUT_SECONDS,
            allow_redirects=True,
        )
    except requests.Timeout as error:
        logger.warning("Google Apps Script email relay timed out.")
        raise RuntimeError("Email relay timed out.") from error
    except requests.RequestException as error:
        logger.warning(
            "Google Apps Script email relay request failed (%s).",
            type(error).__name__,
        )
        raise RuntimeError("Email relay request failed.") from error

    if not 200 <= response.status_code < 300:
        logger.warning(
            "Google Apps Script email relay returned HTTP %s.",
            response.status_code,
        )
        raise RuntimeError("Email relay returned an HTTP error.")

    try:
        result = response.json()
    except ValueError as error:
        logger.warning("Google Apps Script email relay returned invalid JSON.")
        raise RuntimeError("Email relay returned an invalid response.") from error

    if not isinstance(result, dict) or result.get("ok") is not True:
        error_code = result.get("error") if isinstance(result, dict) else None
        if not isinstance(error_code, str) or error_code not in _RELAY_ERROR_CODES:
            error_code = "unknown"
        logger.warning(
            "Google Apps Script email relay reported failure (error=%s).",
            error_code,
        )
        raise RuntimeError("Email relay could not deliver the message.")


def send_email(to_email: str, subject: str, body: str) -> None:
    message = EmailMessage()
    message["To"] = to_email
    message["Subject"] = subject
    message.add_alternative(body, subtype="html")
    send_message(message)
