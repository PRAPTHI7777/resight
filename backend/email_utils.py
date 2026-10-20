from email.message import EmailMessage

from email_service import send_message


def send_otp_email(receiver_email: str, otp: str) -> None:
    message = EmailMessage()
    message["Subject"] = "Your Resight verification code"
    message["To"] = receiver_email
    message.set_content(
        f"""Hello!

Your Resight verification code is:

{otp}

This code expires shortly.

If you did not request this code, you can ignore this email.

Resight
"""
    )
    send_message(message)
