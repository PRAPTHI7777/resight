import os
import smtplib
from email.message import EmailMessage

from config import SMTP_HOST, SMTP_PORT, SMTP_TIMEOUT_SECONDS


def send_message(message: EmailMessage) -> None:
    sender = os.getenv("SMTP_EMAIL", "").strip()
    password = os.getenv("SMTP_PASSWORD", "").strip()
    if not sender or not password:
        raise RuntimeError("SMTP_EMAIL and SMTP_PASSWORD must be configured.")

    message["From"] = sender
    with smtplib.SMTP(
        SMTP_HOST,
        SMTP_PORT,
        timeout=SMTP_TIMEOUT_SECONDS,
    ) as server:
        server.starttls()
        server.login(sender, password)
        server.send_message(message)


def send_email(to_email: str, subject: str, body: str) -> None:
    message = EmailMessage()
    message["To"] = to_email
    message["Subject"] = subject
    message.add_alternative(body, subtype="html")
    send_message(message)
