import smtplib
from email.message import EmailMessage

from src.config import settings


def send_email(subject: str, recipient: str, body: str) -> None:
    if settings.TESTING:
        return

    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = settings.smtp_from_email
    message["To"] = recipient
    message.set_content(body)

    with smtplib.SMTP(settings.smtp_host, settings.smtp_port) as server:
        server.starttls()
        server.login(settings.smtp_username, settings.smtp_password)
        server.send_message(message)