import os
import smtplib
from email.message import EmailMessage
from dotenv import load_dotenv

load_dotenv()

SMTP_EMAIL = os.getenv("SMTP_EMAIL")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD")


def send_otp_email(receiver_email: str, otp: str):

    message = EmailMessage()

    message["Subject"] = "Your Resight verification code"
    message["From"] = SMTP_EMAIL
    message["To"] = receiver_email

    message.set_content(
        f"""Hello!

Your Resight verification code is:

{otp}

This code expires shortly.

If you did not request this code, you can ignore this email.

— Resight
"""
    )

    with smtplib.SMTP("smtp.gmail.com", 587) as server:
        server.starttls()
        server.login(SMTP_EMAIL, SMTP_PASSWORD)
        server.send_message(message)