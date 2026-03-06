import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from app.core.config import settings
import logging

logger = logging.getLogger(__name__)

# ── NA Tours brand colours ──────────────────────────────────────────────────
BRAND_BLACK  = "#0a0a0a"
BRAND_YELLOW = "#f5c518"
BRAND_WHITE  = "#ffffff"
BRAND_GRAY   = "#1a1a1a"
BRAND_LIGHT  = "#f9f6f0"


def _base_template(content: str) -> str:
    """Shared wrapper: black background, yellow accent, white text."""
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>NA Tours</title>
</head>
<body style="margin:0;padding:0;background:{BRAND_BLACK};font-family:'Segoe UI',Arial,sans-serif;">
  <table width="100%" cellpadding="0" cellspacing="0" style="background:{BRAND_BLACK};padding:40px 16px;">
    <tr>
      <td align="center">
        <table width="100%" style="max-width:600px;background:{BRAND_GRAY};border-radius:16px;
               overflow:hidden;border:1px solid #2a2a2a;">

          <!-- HEADER -->
          <tr>
            <td style="background:{BRAND_BLACK};padding:28px 36px;border-bottom:3px solid {BRAND_YELLOW};">
              <table width="100%" cellpadding="0" cellspacing="0">
                <tr>
                  <td>
                    <span style="font-size:26px;font-weight:900;color:{BRAND_YELLOW};
                                 letter-spacing:2px;text-transform:uppercase;">NA</span>
                    <span style="font-size:26px;font-weight:900;color:{BRAND_WHITE};
                                 letter-spacing:2px;text-transform:uppercase;"> Travels</span>
                    <div style="font-size:11px;color:#888;letter-spacing:3px;
                                text-transform:uppercase;margin-top:2px;">
                      Explore the World
                    </div>
                  </td>
                  <td align="right">
                    <span style="font-size:28px;">✈️</span>
                  </td>
                </tr>
              </table>
            </td>
          </tr>

          <!-- BODY -->
          <tr>
            <td style="padding:36px 36px 28px;">
              {content}
            </td>
          </tr>

          <!-- FOOTER -->
          <tr>
            <td style="background:{BRAND_BLACK};padding:20px 36px;
                       border-top:1px solid #2a2a2a;text-align:center;">
              <p style="margin:0;color:#555;font-size:12px;">
                © 2025 NA Tours · All rights reserved
              </p>
              <p style="margin:6px 0 0;color:#444;font-size:11px;">
                If you have questions, contact us at
                <a href="mailto:{settings.EMAIL_FROM}"
                   style="color:{BRAND_YELLOW};text-decoration:none;">{settings.EMAIL_FROM}</a>
              </p>
            </td>
          </tr>

        </table>
      </td>
    </tr>
  </table>
</body>
</html>"""


def _btn(url: str, label: str) -> str:
    return f"""
    <a href="{url}"
       style="display:inline-block;padding:14px 36px;background:{BRAND_YELLOW};
              color:{BRAND_BLACK};text-decoration:none;border-radius:8px;
              font-weight:800;font-size:15px;letter-spacing:0.5px;margin:20px 0;">
      {label}
    </a>"""


def _send_email(to_email: str, subject: str, html_body: str):
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = f"NA Tours <{settings.EMAIL_FROM}>"
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


# ── 1. Email Verification ─────────────────────────────────────────────────────

def send_verification_email(to_email: str, username: str, token: str):
    api_base = "https://elaborate-flori-zerocreationhh-63a658e0.koyeb.app"
    verify_url = f"{api_base}/api/v1/auth/verify-email?token={token}"
    content = f"""
      <h1 style="margin:0 0 8px;font-size:28px;font-weight:900;color:{BRAND_WHITE};">
        Welcome to NA Tours! 🌍
      </h1>
      <p style="margin:0 0 20px;font-size:15px;color:#aaa;">
        Your adventure starts here.
      </p>

      <p style="color:{BRAND_WHITE};font-size:15px;margin:0 0 6px;">
        Hi <strong style="color:{BRAND_YELLOW};">{username}</strong>,
      </p>
      <p style="color:#ccc;font-size:15px;line-height:1.6;margin:0 0 4px;">
        Thanks for signing up! Please verify your email address to activate
        your account and start exploring amazing destinations.
      </p>

      {_btn(verify_url, "✅ Verify My Email")}

      <div style="background:{BRAND_BLACK};border-left:3px solid {BRAND_YELLOW};
                  border-radius:6px;padding:14px 18px;margin-top:8px;">
        <p style="margin:0;color:#888;font-size:13px;line-height:1.6;">
          ⏰ This link expires in <strong style="color:{BRAND_WHITE};">24 hours</strong>.<br>
          🔒 If you didn't create an account, you can safely ignore this email.
        </p>
      </div>
    """
    _send_email(to_email, "Verify your NA Tours account ✈️", _base_template(content))


# ── 2. Welcome (after verification) ──────────────────────────────────────────

def send_welcome_email(to_email: str, username: str):
    content = f"""
      <h1 style="margin:0 0 8px;font-size:28px;font-weight:900;color:{BRAND_WHITE};">
        Email Verified! 🎉
      </h1>
      <p style="margin:0 0 20px;font-size:15px;color:#aaa;">
        You're all set to explore.
      </p>

      <p style="color:{BRAND_WHITE};font-size:15px;margin:0 0 6px;">
        Hi <strong style="color:{BRAND_YELLOW};">{username}</strong>,
      </p>
      <p style="color:#ccc;font-size:15px;line-height:1.6;">
        Your email has been verified successfully. Welcome to the NA Tours family!<br>
        Discover breathtaking destinations, write reviews, and share your travel experiences.
      </p>

      {_btn(settings.FRONTEND_URL, "🌍 Start Exploring")}

      <div style="background:{BRAND_BLACK};border-radius:8px;padding:18px;margin-top:8px;">
        <p style="margin:0 0 10px;color:{BRAND_YELLOW};font-weight:700;font-size:13px;
                  text-transform:uppercase;letter-spacing:1px;">
          What you can do now:
        </p>
        <p style="margin:4px 0;color:#aaa;font-size:14px;">✈️ Browse tourist destinations worldwide</p>
        <p style="margin:4px 0;color:#aaa;font-size:14px;">⭐ Write reviews & upload travel photos</p>
        <p style="margin:4px 0;color:#aaa;font-size:14px;">🗺️ Save your favourite places</p>
      </div>
    """
    _send_email(to_email, "Welcome to NA Tours — You're verified! 🎉", _base_template(content))


# ── 3. Password Reset ─────────────────────────────────────────────────────────

def send_password_reset_email(to_email: str, username: str, token: str):
    api_base = "https://elaborate-flori-zerocreationhh-63a658e0.koyeb.app"
    reset_url = f"{api_base}/api/v1/auth/reset-password?token={token}"
    content = f"""
      <h1 style="margin:0 0 8px;font-size:28px;font-weight:900;color:{BRAND_WHITE};">
        Password Reset 🔑
      </h1>
      <p style="margin:0 0 20px;font-size:15px;color:#aaa;">
        We received a reset request for your account.
      </p>

      <p style="color:{BRAND_WHITE};font-size:15px;margin:0 0 6px;">
        Hi <strong style="color:{BRAND_YELLOW};">{username}</strong>,
      </p>
      <p style="color:#ccc;font-size:15px;line-height:1.6;">
        Someone requested a password reset for your NA Tours account.
        Click the button below to set a new password.
      </p>

      {_btn(reset_url, "🔐 Reset My Password")}

      <div style="background:{BRAND_BLACK};border-left:3px solid #ff4444;
                  border-radius:6px;padding:14px 18px;margin-top:8px;">
        <p style="margin:0;color:#888;font-size:13px;line-height:1.6;">
          ⏰ This link expires in <strong style="color:{BRAND_WHITE};">1 hour</strong>.<br>
          🛡️ If you didn't request this, ignore this email — your password will remain unchanged.
        </p>
      </div>
    """
    _send_email(to_email, "Reset your NA Tours password 🔑", _base_template(content))
