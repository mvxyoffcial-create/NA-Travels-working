import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from app.core.config import settings
import logging

logger = logging.getLogger(__name__)


def _send_email(to_email: str, subject: str, html_body: str):
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = f"{settings.EMAIL_FROM_NAME} <{settings.EMAIL_FROM}>"
    msg["To"] = to_email
    msg.attach(MIMEText(html_body, "html"))

    try:
        with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT) as server:
            server.ehlo()
            server.starttls()
            server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
            server.sendmail(settings.EMAIL_FROM, to_email, msg.as_string())
        logger.info(f"Email sent to {to_email}: {subject}")
    except Exception as e:
        logger.error(f"Failed to send email to {to_email}: {e}")
        raise


def send_verification_email(to_email: str, username: str, token: str):
    verify_url = f"{settings.FRONTEND_URL}/verify-email?token={token}"
    html = f"""
    <!DOCTYPE html>
    <html>
    <head><meta charset="utf-8"></head>
    <body style="font-family: Arial, sans-serif; background:#f4f4f4; padding:20px;">
      <div style="max-width:600px;margin:auto;background:#fff;border-radius:10px;padding:30px;">
        <h2 style="color:#2c7be5;">Welcome to {settings.APP_NAME}! 🌍</h2>
        <p>Hi <strong>{username}</strong>,</p>
        <p>Thanks for signing up! Please verify your email address to get started.</p>
        <a href="{verify_url}"
           style="display:inline-block;padding:12px 28px;background:#2c7be5;color:#fff;
                  text-decoration:none;border-radius:6px;margin:16px 0;font-weight:bold;">
          Verify Email
        </a>
        <p style="color:#888;font-size:13px;">This link expires in 24 hours.<br>
           If you didn't create an account, ignore this email.</p>
        <hr style="border:none;border-top:1px solid #eee;margin:24px 0;">
        <p style="color:#aaa;font-size:12px;">© {settings.APP_NAME}</p>
      </div>
    </body>
    </html>
    """
    _send_email(to_email, f"Verify your {settings.APP_NAME} account", html)


def send_password_reset_email(to_email: str, username: str, token: str):
    reset_url = f"{settings.FRONTEND_URL}/reset-password?token={token}"
    html = f"""
    <!DOCTYPE html>
    <html>
    <head><meta charset="utf-8"></head>
    <body style="font-family: Arial, sans-serif; background:#f4f4f4; padding:20px;">
      <div style="max-width:600px;margin:auto;background:#fff;border-radius:10px;padding:30px;">
        <h2 style="color:#e74c3c;">Password Reset Request 🔑</h2>
        <p>Hi <strong>{username}</strong>,</p>
        <p>We received a request to reset your password. Click the button below:</p>
        <a href="{reset_url}"
           style="display:inline-block;padding:12px 28px;background:#e74c3c;color:#fff;
                  text-decoration:none;border-radius:6px;margin:16px 0;font-weight:bold;">
          Reset Password
        </a>
        <p style="color:#888;font-size:13px;">This link expires in 1 hour.<br>
           If you didn't request this, ignore this email — your password won't change.</p>
        <hr style="border:none;border-top:1px solid #eee;margin:24px 0;">
        <p style="color:#aaa;font-size:12px;">© {settings.APP_NAME}</p>
      </div>
    </body>
    </html>
    """
    _send_email(to_email, f"Reset your {settings.APP_NAME} password", html)


def send_welcome_email(to_email: str, username: str):
    html = f"""
    <!DOCTYPE html>
    <html>
    <head><meta charset="utf-8"></head>
    <body style="font-family: Arial, sans-serif; background:#f4f4f4; padding:20px;">
      <div style="max-width:600px;margin:auto;background:#fff;border-radius:10px;padding:30px;">
        <h2 style="color:#27ae60;">Email Verified! 🎉</h2>
        <p>Hi <strong>{username}</strong>,</p>
        <p>Your email has been verified successfully. Welcome to {settings.APP_NAME}!</p>
        <p>Start exploring amazing tourist destinations and share your experiences.</p>
        <a href="{settings.FRONTEND_URL}"
           style="display:inline-block;padding:12px 28px;background:#27ae60;color:#fff;
                  text-decoration:none;border-radius:6px;margin:16px 0;font-weight:bold;">
          Explore Now
        </a>
        <hr style="border:none;border-top:1px solid #eee;margin:24px 0;">
        <p style="color:#aaa;font-size:12px;">© {settings.APP_NAME}</p>
      </div>
    </body>
    </html>
    """
    _send_email(to_email, f"Welcome to {settings.APP_NAME}!", html)
