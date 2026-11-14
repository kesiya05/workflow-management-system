"""Notifications are stored in the database (the in-app inbox). If SMTP_HOST is set they are also emailed."""
import logging
import os
import smtplib
from email.message import EmailMessage

from sqlalchemy.orm import Session

from . import models

log = logging.getLogger("notify")


def send_email(to: str, subject: str, body: str) -> bool:
    host = os.getenv("SMTP_HOST")
    if not host:
        return False
    msg = EmailMessage()
    msg["From"] = os.getenv("SMTP_FROM", "workflow@example.com")
    msg["To"], msg["Subject"] = to, subject
    msg.set_content(body)
    try:
        with smtplib.SMTP(host, int(os.getenv("SMTP_PORT", "25")), timeout=5) as s:
            s.send_message(msg)
        return True
    except OSError as exc:  # never let a mail problem break a business action
        log.warning("email to %s failed: %s", to, exc)
        return False


def notify(db: Session, user: models.User, message: str) -> None:
    db.add(models.Notification(user_id=user.id, message=message))
    send_email(user.email, "Workflow update", message)


def record(db: Session, user: models.User | None, action: str, detail: str = "") -> None:
    db.add(models.Activity(user_id=user.id if user else None, action=action, detail=detail[:300]))
