"""
Email sending utilities — AWS SES with a console fallback for local dev.

Configuration (environment variables):
    SES_SENDER_EMAIL  — verified "From" address, e.g. no-reply@learnwithfluo.com
    AWS_REGION        — AWS region for SES (default: ca-central-1)

If SES_SENDER_EMAIL is not set (local development), emails are logged to the
console instead of being sent, so the verification flow still works end-to-end.
"""

import logging
import os

logger = logging.getLogger(__name__)

VERIFICATION_CODE_TTL_MINUTES = 10


def send_email(to: str, subject: str, body_text: str, body_html: str | None = None) -> bool:
    """
    Send an email via AWS SES. Returns True on success.

    In local dev (no SES_SENDER_EMAIL configured), logs the email and returns
    True so flows can be tested without a mail server.
    """
    sender = os.getenv("SES_SENDER_EMAIL") or os.getenv("DEFAULT_SENDER")

    # Prefer SMTP if explicit SMTP env vars are provided or an smtp.csv file
    # exists at the project root (AWS SES SMTP credentials). This lets users
    # supply SMTP credentials instead of AWS API credentials.
    smtp_host = os.getenv("SMTP_HOST")
    smtp_port = os.getenv("SMTP_PORT")
    smtp_username = os.getenv("SMTP_USERNAME")
    smtp_password = os.getenv("SMTP_PASSWORD")

    smtp_csv_path = os.path.join(os.path.dirname(__file__), "smtp.csv")
    use_smtp = False
    smtp_creds = {}
    if smtp_host and smtp_username and smtp_password:
        use_smtp = True
        smtp_creds = {
            "host": smtp_host,
            "port": int(smtp_port) if smtp_port else 587,
            "username": smtp_username,
            "password": smtp_password,
        }
    else:
        # try loading the project-level smtp.csv (same format as scripts/send_test_email.py)
        try:
            import csv

            if os.path.exists(smtp_csv_path):
                with open(smtp_csv_path, newline="") as f:
                    rows = list(csv.DictReader(f))
                if rows:
                    row = rows[0]
                    smtp_creds = {
                        "host": row.get("SMTP Endpoint", "").strip(),
                        "port": int(row.get("Port", "587").strip() or 587),
                        "username": row.get("Username", "").strip(),
                        "password": row.get("Password", "").strip(),
                    }
                    if smtp_creds["host"] and smtp_creds["username"] and smtp_creds["password"]:
                        use_smtp = True
        except Exception:
            # ignore CSV parsing errors and fall back to boto3 or local logging
            logger.debug("Could not load smtp.csv for SMTP fallback", exc_info=True)

    # If no explicit sender configured, fall back to a safe default so flows
    # that expect emails to be generated still behave deterministically.
    if not sender:
        sender = os.getenv("DEFAULT_SENDER", "no-reply@learnwithfluo.com")

    # If SMTP creds are available, send via smtplib (SES SMTP-compatible)
    if use_smtp:
        try:
            import smtplib
            from email.mime.multipart import MIMEMultipart
            from email.mime.text import MIMEText

            msg = MIMEMultipart("alternative")
            msg["Subject"] = subject
            msg["From"] = sender
            msg["To"] = to
            msg.attach(MIMEText(body_text or "", "plain"))
            if body_html:
                msg.attach(MIMEText(body_html, "html"))

            with smtplib.SMTP(smtp_creds["host"], smtp_creds.get("port", 587), timeout=30) as smtp:
                smtp.ehlo()
                try:
                    smtp.starttls()
                    smtp.ehlo()
                except Exception:
                    # If STARTTLS isn't supported, continue — some endpoints already
                    # use implicit TLS or do not require STARTTLS.
                    logger.debug("STARTTLS not available or failed", exc_info=True)
                smtp.login(smtp_creds["username"], smtp_creds["password"])
                refused = smtp.sendmail(sender, [to], msg.as_string())
                if refused:
                    logger.error("SMTP server refused recipients: %s", refused)
                    return False
            logger.info("Sent email via SMTP to %s: %s", to, subject)
            return True
        except Exception:
            logger.exception("Failed to send email via SMTP to %s", to)
            return False

    # Otherwise, attempt to send via AWS SES API (boto3). If SES_SENDER_EMAIL is
    # not configured, fall back to logging for local development.
    try:
        import boto3

        ses = boto3.client(
            "ses", region_name=os.getenv("AWS_REGION", "ca-central-1")
        )
        message = {
            "Subject": {"Data": subject, "Charset": "UTF-8"},
            "Body": {"Text": {"Data": body_text, "Charset": "UTF-8"}},
        }
        if body_html:
            message["Body"]["Html"] = {"Data": body_html, "Charset": "UTF-8"}
        if not os.getenv("SES_SENDER_EMAIL"):
            logger.info(
                "SES_SENDER_EMAIL not set — logging email to %s instead of sending via SES.\n"
                "Subject: %s\n%s",
                to,
                subject,
                body_text,
            )
            return True

        ses.send_email(Source=sender, Destination={"ToAddresses": [to]}, Message=message)
        logger.info("Sent email via SES API to %s: %s", to, subject)
        return True
    except Exception:
        logger.exception("Failed to send email to %s", to)
        return False


def send_verification_code_email(email: str, code: str, purpose: str) -> bool:
    """Send a 6-digit verification code. purpose: 'register' | 'password_reset'."""
    if purpose == "password_reset":
        subject = "Fluō — your password reset code"
        heading = "Reset your password"
        intro = (
            "We received a request to reset the password for your Fluō account. "
            "Enter the code below to choose a new password."
        )
        ignore_note = "If you didn't request a password reset, you can safely ignore this email — your password will stay the same."
    else:
        subject = "Fluō — confirm your email"
        heading = "Confirm your email"
        intro = (
            "Thanks for signing up for Fluō! Enter the code below to verify "
            "your email address and finish creating your account."
        )
        ignore_note = "If you didn't create a Fluō account, you can safely ignore this email."

    body_text = (
        f"{heading}\n\n"
        f"{intro}\n\n"
        f"Your verification code is: {code}\n\n"
        f"This code expires in {VERIFICATION_CODE_TTL_MINUTES} minutes.\n\n"
        f"{ignore_note}\n"
    )

    body_html = f"""
    <div style="font-family: -apple-system, Segoe UI, Roboto, sans-serif; max-width: 480px; margin: 0 auto; padding: 32px 24px; color: #1a2e28;">
      <h1 style="font-size: 22px; margin: 0 0 8px;">Fluō</h1>
      <h2 style="font-size: 17px; font-weight: 600; margin: 0 0 12px;">{heading}</h2>
      <p style="font-size: 14px; line-height: 1.6; margin: 0 0 20px;">{intro}</p>
      <div style="background: #f2f5f4; border-radius: 12px; padding: 20px; text-align: center; margin: 0 0 20px;">
        <span style="font-size: 32px; font-weight: 700; letter-spacing: 8px;">{code}</span>
      </div>
      <p style="font-size: 13px; color: #5a6b66; margin: 0 0 8px;">This code expires in {VERIFICATION_CODE_TTL_MINUTES} minutes.</p>
      <p style="font-size: 13px; color: #5a6b66; margin: 0;">{ignore_note}</p>
    </div>
    """

    return send_email(email, subject, body_text, body_html)
