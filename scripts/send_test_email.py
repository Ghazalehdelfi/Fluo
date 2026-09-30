"""
Send a test email using the SMTP credentials in smtp.csv (project root).

Usage:
    python scripts/send_test_email.py                          # sends to ghazalehdelfi@gmail.com
    python scripts/send_test_email.py someone@example.com      # custom recipient
    SES_SENDER_EMAIL=no-reply@learnwithfluo.com python scripts/send_test_email.py

The sender address is read from SES_SENDER_EMAIL (must be a verified identity
in SES). Falls back to the recipient address if unset.
"""

import csv
import os
import smtplib
import sys
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SMTP_CSV = ROOT / "smtp.csv"

DEFAULT_RECIPIENT = "ghazalehdelfi@gmail.com"
DEFAULT_SENDER = "no-reply@learnwithfluo.com"


def load_smtp_credentials(path: Path = SMTP_CSV) -> dict:
    """Read endpoint/port/username/password from the AWS-issued smtp.csv."""
    if not path.exists():
        sys.exit(f"error: {path} not found")
    with path.open(newline="") as f:
        rows = list(csv.DictReader(f))
    if not rows:
        sys.exit(f"error: {path} has no credential rows")
    row = rows[0]
    return {
        "host": row["SMTP Endpoint"].strip(),
        "port": int(row["Port"].strip()),
        "username": row["Username"].strip(),
        "password": row["Password"].strip(),
    }


def send_test_email(recipient: str) -> None:
    creds = load_smtp_credentials()
    sender = os.getenv("SES_SENDER_EMAIL", DEFAULT_SENDER)

    msg = MIMEMultipart("alternative")
    msg["Subject"] = "Fluō — SMTP test"
    msg["From"] = sender
    msg["To"] = recipient
    msg.attach(MIMEText("SMTP is working. This is a test from the Fluō project.", "plain"))
    msg.attach(
        MIMEText(
            "<p style='font-family:sans-serif'>SMTP is working. "
            "This is a test from the <strong>Fluō</strong> project.</p>",
            "html",
        )
    )

    print(f"Connecting to {creds['host']}:{creds['port']} ...")
    with smtplib.SMTP(creds["host"], creds["port"], timeout=30) as smtp:
        smtp.set_debuglevel(1)  # log the full SMTP conversation
        smtp.ehlo()
        smtp.starttls()
        smtp.ehlo()
        smtp.login(creds["username"], creds["password"])
        refused = smtp.sendmail(sender, [recipient], msg.as_string())
        if refused:
            print(f"REFUSED by server: {refused}")
        else:
            print("Server accepted the message (250 OK).")
    print(f"Test email sent: {sender} -> {recipient}")


if __name__ == "__main__":
    send_test_email(sys.argv[1] if len(sys.argv) > 1 else DEFAULT_RECIPIENT)
