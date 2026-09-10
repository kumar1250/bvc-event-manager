"""
Transactional email sending via the Brevo (formerly Sendinblue) HTTP API.

Docs: https://developers.brevo.com/reference/sendtransacemail

Configure via environment variables (see .env.example):
    BREVO_API_KEY        - your Brevo API v3 key
    BREVO_SENDER_EMAIL    - verified sender email in your Brevo account
    BREVO_SENDER_NAME     - display name for the sender
    FRONTEND_URL          - base URL of the frontend, used to build links in emails

Every send is logged to notifications.EmailLog for auditing, and failures
never raise — a broken email provider should not break registration/signup.
"""
import logging

import requests
from django.conf import settings

logger = logging.getLogger(__name__)

BREVO_ENDPOINT = "https://api.brevo.com/v3/smtp/email"


def _send_via_brevo(to_email, to_name, subject, html_content, template_name):
    from .models import EmailLog

    api_key = getattr(settings, "BREVO_API_KEY", "")
    sender_email = getattr(settings, "BREVO_SENDER_EMAIL", "")
    sender_name = getattr(settings, "BREVO_SENDER_NAME", "Event Platform")

    if not api_key or not sender_email:
        logger.warning(
            "BREVO_API_KEY / BREVO_SENDER_EMAIL not configured - skipping email to %s (%s)",
            to_email, template_name,
        )
        EmailLog.objects.create(
            to_email=to_email, subject=subject, template=template_name,
            success=False, error_message="Brevo not configured",
        )
        return False

    payload = {
        "sender": {"name": sender_name, "email": sender_email},
        "to": [{"email": to_email, "name": to_name or to_email}],
        "subject": subject,
        "htmlContent": html_content,
    }
    headers = {
        "accept": "application/json",
        "api-key": api_key,
        "content-type": "application/json",
    }

    try:
        response = requests.post(BREVO_ENDPOINT, json=payload, headers=headers, timeout=10)
        ok = response.status_code in (200, 201)
        EmailLog.objects.create(
            to_email=to_email, subject=subject, template=template_name,
            success=ok, error_message="" if ok else response.text[:2000],
        )
        if not ok:
            logger.error("Brevo send failed (%s): %s", response.status_code, response.text)
        return ok
    except requests.RequestException as exc:
        logger.exception("Brevo request error")
        EmailLog.objects.create(
            to_email=to_email, subject=subject, template=template_name,
            success=False, error_message=str(exc)[:2000],
        )
        return False


def _wrap_html(title, body_html):
    return f"""
    <div style="font-family: Arial, Helvetica, sans-serif; max-width: 600px; margin: 0 auto;
                background:#f7f7fb; padding: 24px;">
      <div style="background:#ffffff; border-radius: 12px; overflow:hidden; box-shadow:0 1px 4px rgba(0,0,0,0.08);">
        <div style="background:linear-gradient(135deg,#6d28d9,#4f46e5); padding: 24px 28px;">
          <h1 style="color:#fff; margin:0; font-size:20px;">{title}</h1>
        </div>
        <div style="padding: 28px; color:#1f2937; font-size: 14px; line-height: 1.6;">
          {body_html}
        </div>
        <div style="padding: 16px 28px; color:#9ca3af; font-size:12px; border-top:1px solid #eee;">
          This is an automated email. Please do not reply directly to this message.
        </div>
      </div>
    </div>
    """


def send_welcome_email(user):
    html = _wrap_html(
        "Welcome!",
        f"<p>Hi {user.full_name or user.email},</p>"
        "<p>Your account has been created successfully. You can now browse events and register.</p>",
    )
    return _send_via_brevo(user.email, user.full_name, "Welcome to the Event Platform", html, "welcome")


def send_password_reset_email(user, token):
    frontend_url = getattr(settings, "FRONTEND_URL", "http://localhost:5173")
    reset_link = f"{frontend_url}/reset-password?token={token}"
    html = _wrap_html(
        "Reset your password",
        f"<p>Hi {user.full_name or user.email},</p>"
        "<p>We received a request to reset your password. This link expires in 1 hour.</p>"
        f'<p><a href="{reset_link}" style="background:#4f46e5;color:#fff;padding:10px 20px;'
        f'border-radius:8px;text-decoration:none;display:inline-block;">Reset Password</a></p>'
        f"<p>Or copy this link: {reset_link}</p>"
        "<p>If you did not request this, you can safely ignore this email.</p>",
    )
    return _send_via_brevo(user.email, user.full_name, "Reset your password", html, "password_reset")


def send_registration_confirmation_email(submission):
    user = submission.user
    event = submission.event
    to_email = user.email if user else submission.get_answer_value_for_label("Email") or ""
    to_name = user.full_name if user else submission.get_answer_value_for_label("Full Name") or ""
    if not to_email:
        return False

    html = _wrap_html(
        "Registration Successful!",
        f"<p>Hi {to_name or 'there'},</p>"
        f"<p>Your registration for <strong>{event.name}</strong> was successful.</p>"
        "<table style='width:100%;border-collapse:collapse;margin:16px 0;'>"
        f"<tr><td style='padding:6px 0;color:#6b7280;'>Registration ID</td>"
        f"<td style='padding:6px 0;font-weight:bold;'>{submission.registration_id}</td></tr>"
        f"<tr><td style='padding:6px 0;color:#6b7280;'>Event</td><td style='padding:6px 0;'>{event.name}</td></tr>"
        f"<tr><td style='padding:6px 0;color:#6b7280;'>Date</td><td style='padding:6px 0;'>{event.date}</td></tr>"
        f"<tr><td style='padding:6px 0;color:#6b7280;'>Time</td><td style='padding:6px 0;'>{event.start_time}</td></tr>"
        f"<tr><td style='padding:6px 0;color:#6b7280;'>Venue</td><td style='padding:6px 0;'>{event.venue}</td></tr>"
        "</table>"
        f"<p>{event.instructions or 'Please arrive at least 15 minutes before the scheduled time.'}</p>",
    )
    return _send_via_brevo(
        to_email, to_name, f"Registration Confirmed - {event.name}", html, "registration_confirmation"
    )


def send_event_update_email(event, recipients, message):
    html = _wrap_html(
        f"Update: {event.name}",
        f"<p>{message}</p>",
    )
    sent_any = False
    for user in recipients:
        if _send_via_brevo(user.email, user.full_name, f"Update: {event.name}", html, "event_update"):
            sent_any = True
    return sent_any


def send_event_cancellation_email(event, recipients):
    html = _wrap_html(
        f"Event Cancelled: {event.name}",
        f"<p>We're sorry to inform you that <strong>{event.name}</strong> "
        f"scheduled on {event.date} has been cancelled.</p>",
    )
    sent_any = False
    for user in recipients:
        if _send_via_brevo(user.email, user.full_name, f"Cancelled: {event.name}", html, "event_cancellation"):
            sent_any = True
    return sent_any
