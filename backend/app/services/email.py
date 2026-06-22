"""Email notification service — Resend API.

All public functions are synchronous so they can be called directly from
Celery workers and wrapped in asyncio.to_thread() from async FastAPI routes.
They no-op gracefully when RESEND_API_KEY is not configured.
"""

import logging
from datetime import datetime

import resend

from app.core.config import settings

logger = logging.getLogger(__name__)

_PRIMARY = "#2563eb"
_LIGHT_BG = "#f0f7ff"


def _base(title: str, body_html: str) -> str:
    return f"""<!DOCTYPE html>
<html lang="en">
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{title}</title></head>
<body style="margin:0;padding:0;background:#f5f5f5;font-family:'Helvetica Neue',Arial,sans-serif;">
  <table width="100%" cellpadding="0" cellspacing="0" style="background:#f5f5f5;padding:32px 0;">
    <tr><td align="center">
      <table width="600" cellpadding="0" cellspacing="0"
             style="background:#ffffff;border-radius:12px;overflow:hidden;box-shadow:0 2px 8px rgba(0,0,0,.08);">
        <!-- Header -->
        <tr>
          <td style="background:{_PRIMARY};padding:28px 40px;">
            <span style="color:#ffffff;font-size:22px;font-weight:700;letter-spacing:-0.5px;">
              EazziDoc
            </span>
            <span style="color:rgba(255,255,255,.7);font-size:13px;margin-left:12px;">
              AI Medical Diagnostics
            </span>
          </td>
        </tr>
        <!-- Body -->
        <tr><td style="padding:36px 40px 24px;">{body_html}</td></tr>
        <!-- Footer -->
        <tr>
          <td style="background:#f9f9f9;padding:20px 40px;border-top:1px solid #eeeeee;">
            <p style="margin:0;font-size:12px;color:#9ca3af;line-height:1.6;">
              This email was sent by EazziDoc. Please do not reply to this message.<br>
              If you have questions, log in to your account at
              <a href="{settings.FRONTEND_URL}" style="color:{_PRIMARY};">{settings.FRONTEND_URL}</a>.
            </p>
          </td>
        </tr>
      </table>
    </td></tr>
  </table>
</body></html>"""


def _send(
    to: str,
    subject: str,
    html: str,
    bcc: str | None = None,
    reply_to: str | None = None,
) -> None:
    """Send via Resend API. Silently skips when RESEND_API_KEY is not set."""
    if not settings.RESEND_API_KEY:
        logger.debug("Resend not configured — skipping email '%s' to %s", subject, to)
        return

    resend.api_key = settings.RESEND_API_KEY

    params: resend.Emails.SendParams = {
        "from": settings.SMTP_FROM,
        "to": [to],
        "subject": subject,
        "html": html,
    }
    if bcc:
        params["bcc"] = [bcc]
    if reply_to:
        params["reply_to"] = [reply_to]

    try:
        resend.Emails.send(params)
        logger.info("Email sent — to=%s subject=%r", to, subject)
    except Exception:
        logger.exception("Failed to send email — to=%s subject=%r", to, subject)


# ── public notification functions ─────────────────────────────────────────────


def send_diagnosis_ready(
    patient_email: str,
    patient_name: str,
    diagnosis_id: str,
    modality: str,
    urgency: str | None,
) -> None:
    urgency_label = (urgency or "routine").capitalize()
    urgency_color = {"Emergent": "#dc2626", "Urgent": "#d97706", "Routine": "#16a34a"}.get(
        urgency_label, "#6b7280"
    )
    modality_display = modality.replace("_", " ").title()
    report_url = f"{settings.FRONTEND_URL}/patient/diagnoses/{diagnosis_id}"

    body = f"""
    <h2 style="margin:0 0 8px;font-size:20px;color:#111827;">Your AI report is ready</h2>
    <p style="margin:0 0 24px;font-size:15px;color:#4b5563;line-height:1.6;">
      Hi {patient_name}, your medical imaging analysis has completed.
    </p>
    <table cellpadding="0" cellspacing="0" width="100%"
           style="background:{_LIGHT_BG};border-radius:8px;padding:20px;margin-bottom:28px;">
      <tr>
        <td style="font-size:13px;color:#6b7280;padding-bottom:6px;">Modality</td>
        <td style="font-size:15px;font-weight:600;color:#111827;text-align:right;">
          {modality_display}
        </td>
      </tr>
      <tr>
        <td style="font-size:13px;color:#6b7280;padding-top:8px;">Urgency level</td>
        <td style="text-align:right;padding-top:8px;">
          <span style="background:{urgency_color}1a;color:{urgency_color};
                       font-size:13px;font-weight:600;padding:3px 10px;border-radius:20px;">
            {urgency_label}
          </span>
        </td>
      </tr>
    </table>
    <p style="margin:0 0 24px;font-size:14px;color:#4b5563;line-height:1.6;">
      A doctor will review your results shortly. You can view the full AI report and
      book a consultation directly from your dashboard.
    </p>
    <a href="{report_url}"
       style="display:inline-block;background:{_PRIMARY};color:#ffffff;
              font-size:15px;font-weight:600;padding:13px 28px;
              border-radius:8px;text-decoration:none;">
      View my report →
    </a>
    """
    html = _base("Your EazziDoc AI Report is Ready", body)
    _send(
        to=patient_email,
        subject=f"[EazziDoc] Your {modality_display} report is ready",
        html=html,
        bcc=settings.REPORT_EMAIL_BCC or None,
    )


def send_appointment_booked_to_doctor(
    doctor_email: str,
    doctor_name: str,
    patient_name: str,
    scheduled_at: datetime,
    duration_mins: int,
    appointment_id: str,
) -> None:
    date_str = scheduled_at.strftime("%A, %d %B %Y at %H:%M UTC")
    appt_url = f"{settings.FRONTEND_URL}/doctor/appointments"

    body = f"""
    <h2 style="margin:0 0 8px;font-size:20px;color:#111827;">New appointment request</h2>
    <p style="margin:0 0 24px;font-size:15px;color:#4b5563;line-height:1.6;">
      Hi Dr. {doctor_name}, a patient has requested a consultation with you.
    </p>
    <table cellpadding="0" cellspacing="0" width="100%"
           style="background:{_LIGHT_BG};border-radius:8px;padding:20px;margin-bottom:28px;">
      <tr>
        <td style="font-size:13px;color:#6b7280;padding-bottom:6px;">Patient</td>
        <td style="font-size:15px;font-weight:600;color:#111827;text-align:right;">
          {patient_name}
        </td>
      </tr>
      <tr>
        <td style="font-size:13px;color:#6b7280;padding-top:8px;">Date &amp; time</td>
        <td style="font-size:14px;color:#111827;text-align:right;padding-top:8px;">{date_str}</td>
      </tr>
      <tr>
        <td style="font-size:13px;color:#6b7280;padding-top:8px;">Duration</td>
        <td style="font-size:14px;color:#111827;text-align:right;padding-top:8px;">
          {duration_mins} minutes
        </td>
      </tr>
    </table>
    <p style="margin:0 0 24px;font-size:14px;color:#4b5563;">
      Please confirm or decline this appointment from your dashboard.
    </p>
    <a href="{appt_url}"
       style="display:inline-block;background:{_PRIMARY};color:#ffffff;
              font-size:15px;font-weight:600;padding:13px 28px;
              border-radius:8px;text-decoration:none;">
      View appointments →
    </a>
    """
    _send(
        to=doctor_email,
        subject=f"[EazziDoc] New appointment request from {patient_name}",
        html=_base("New Appointment Request — EazziDoc", body),
    )


def send_appointment_confirmed_to_patient(
    patient_email: str,
    patient_name: str,
    doctor_name: str,
    scheduled_at: datetime,
    duration_mins: int,
) -> None:
    date_str = scheduled_at.strftime("%A, %d %B %Y at %H:%M UTC")
    appt_url = f"{settings.FRONTEND_URL}/patient/appointments"

    body = f"""
    <h2 style="margin:0 0 8px;font-size:20px;color:#111827;">Appointment confirmed</h2>
    <p style="margin:0 0 24px;font-size:15px;color:#4b5563;line-height:1.6;">
      Hi {patient_name}, Dr. {doctor_name} has confirmed your appointment.
    </p>
    <table cellpadding="0" cellspacing="0" width="100%"
           style="background:{_LIGHT_BG};border-radius:8px;padding:20px;margin-bottom:28px;">
      <tr>
        <td style="font-size:13px;color:#6b7280;padding-bottom:6px;">Doctor</td>
        <td style="font-size:15px;font-weight:600;color:#111827;text-align:right;">
          Dr. {doctor_name}
        </td>
      </tr>
      <tr>
        <td style="font-size:13px;color:#6b7280;padding-top:8px;">Date &amp; time</td>
        <td style="font-size:14px;color:#111827;text-align:right;padding-top:8px;">{date_str}</td>
      </tr>
      <tr>
        <td style="font-size:13px;color:#6b7280;padding-top:8px;">Duration</td>
        <td style="font-size:14px;color:#111827;text-align:right;padding-top:8px;">
          {duration_mins} minutes
        </td>
      </tr>
    </table>
    <p style="margin:0 0 24px;font-size:14px;color:#4b5563;">
      Please join the consultation on time. You can view details or cancel from your dashboard.
    </p>
    <a href="{appt_url}"
       style="display:inline-block;background:{_PRIMARY};color:#ffffff;
              font-size:15px;font-weight:600;padding:13px 28px;
              border-radius:8px;text-decoration:none;">
      View appointment →
    </a>
    """
    _send(
        to=patient_email,
        subject=f"[EazziDoc] Appointment confirmed with Dr. {doctor_name}",
        html=_base("Appointment Confirmed — EazziDoc", body),
    )


def send_appointment_cancelled(
    to_email: str,
    to_name: str,
    other_party_name: str,
    scheduled_at: datetime,
    cancelled_by: str,
) -> None:
    date_str = scheduled_at.strftime("%A, %d %B %Y at %H:%M UTC")
    dashboard_url = f"{settings.FRONTEND_URL}/patient/appointments"
    by_label = f"Dr. {other_party_name}" if cancelled_by == "doctor" else other_party_name

    body = f"""
    <h2 style="margin:0 0 8px;font-size:20px;color:#111827;">Appointment cancelled</h2>
    <p style="margin:0 0 24px;font-size:15px;color:#4b5563;line-height:1.6;">
      Hi {to_name}, your appointment scheduled for <strong>{date_str}</strong>
      has been cancelled by {by_label}.
    </p>
    <p style="margin:0 0 24px;font-size:14px;color:#4b5563;">
      You can book a new appointment from your dashboard at any time.
    </p>
    <a href="{dashboard_url}"
       style="display:inline-block;background:{_PRIMARY};color:#ffffff;
              font-size:15px;font-weight:600;padding:13px 28px;
              border-radius:8px;text-decoration:none;">
      Go to dashboard →
    </a>
    """
    _send(
        to=to_email,
        subject="[EazziDoc] Appointment cancelled",
        html=_base("Appointment Cancelled — EazziDoc", body),
    )


def send_welcome(email: str, name: str, role: str) -> None:
    role_label = "patient" if role == "patient" else "doctor"
    dashboard_url = f"{settings.FRONTEND_URL}/{role_label}"
    portal_section = (
        "upload medical images and receive AI-powered diagnostic reports"
        if role == "patient"
        else "review AI diagnostic reports and manage patient appointments"
    )

    body = f"""
    <h2 style="margin:0 0 8px;font-size:20px;color:#111827;">Welcome to EazziDoc, {name}!</h2>
    <p style="margin:0 0 20px;font-size:15px;color:#4b5563;line-height:1.6;">
      Your account is ready. As a {role_label}, you can {portal_section}
      directly from your dashboard.
    </p>
    <table cellpadding="0" cellspacing="0" width="100%"
           style="background:{_LIGHT_BG};border-radius:8px;padding:20px;margin-bottom:28px;">
      <tr>
        <td style="font-size:13px;color:#6b7280;padding-bottom:6px;">Account email</td>
        <td style="font-size:14px;font-weight:600;color:#111827;text-align:right;">{email}</td>
      </tr>
      <tr>
        <td style="font-size:13px;color:#6b7280;padding-top:8px;">Role</td>
        <td style="font-size:14px;color:#111827;text-align:right;padding-top:8px;
                   text-transform:capitalize;">{role_label}</td>
      </tr>
    </table>
    <a href="{dashboard_url}"
       style="display:inline-block;background:{_PRIMARY};color:#ffffff;
              font-size:15px;font-weight:600;padding:13px 28px;
              border-radius:8px;text-decoration:none;">
      Go to my dashboard →
    </a>
    """
    _send(
        to=email,
        subject="[EazziDoc] Welcome — your account is ready",
        html=_base("Welcome to EazziDoc", body),
    )


def send_admin_welcome(email: str, name: str) -> None:
    admin_url = f"{settings.FRONTEND_URL}/admin"

    body = f"""
    <h2 style="margin:0 0 8px;font-size:20px;color:#111827;">Admin account created</h2>
    <p style="margin:0 0 20px;font-size:15px;color:#4b5563;line-height:1.6;">
      Hi {name}, a new EazziDoc administrator account has been registered using this email address.
    </p>
    <table cellpadding="0" cellspacing="0" width="100%"
           style="background:{_LIGHT_BG};border-radius:8px;padding:20px;margin-bottom:28px;">
      <tr>
        <td style="font-size:13px;color:#6b7280;padding-bottom:6px;">Account email</td>
        <td style="font-size:14px;font-weight:600;color:#111827;text-align:right;">{email}</td>
      </tr>
      <tr>
        <td style="font-size:13px;color:#6b7280;padding-top:8px;">Role</td>
        <td style="font-size:14px;color:#111827;text-align:right;padding-top:8px;">Administrator</td>
      </tr>
    </table>
    <p style="margin:0 0 24px;font-size:14px;color:#4b5563;line-height:1.6;">
      If you did not create this account, your invite code may be compromised.
      Contact your team immediately to rotate it.
    </p>
    <a href="{admin_url}"
       style="display:inline-block;background:{_PRIMARY};color:#ffffff;
              font-size:15px;font-weight:600;padding:13px 28px;
              border-radius:8px;text-decoration:none;">
      Go to admin portal →
    </a>
    """
    _send(
        to=email,
        subject="[EazziDoc] Admin account created",
        html=_base("Admin Account Created — EazziDoc", body),
    )


def send_settings_updated(email: str, name: str, changed_fields: list[str]) -> None:
    fields_html = "".join(
        f'<li style="font-size:14px;color:#374151;padding:3px 0;">{f.replace("_", " ").capitalize()}</li>'
        for f in changed_fields
    )
    dashboard_url = f"{settings.FRONTEND_URL}"

    body = f"""
    <h2 style="margin:0 0 8px;font-size:20px;color:#111827;">Profile updated</h2>
    <p style="margin:0 0 20px;font-size:15px;color:#4b5563;line-height:1.6;">
      Hi {name}, your EazziDoc profile was just updated. The following fields were changed:
    </p>
    <ul style="margin:0 0 24px;padding-left:20px;background:{_LIGHT_BG};
               border-radius:8px;padding:16px 16px 16px 36px;">
      {fields_html}
    </ul>
    <p style="margin:0 0 24px;font-size:14px;color:#4b5563;">
      If you did not make this change, please contact support immediately by replying to this email.
    </p>
    <a href="{dashboard_url}"
       style="display:inline-block;background:{_PRIMARY};color:#ffffff;
              font-size:15px;font-weight:600;padding:13px 28px;
              border-radius:8px;text-decoration:none;">
      Go to dashboard →
    </a>
    """
    _send(
        to=email,
        subject="[EazziDoc] Your profile has been updated",
        html=_base("Profile Updated — EazziDoc", body),
    )


def send_contact_message(
    to_email: str,
    to_name: str,
    from_name: str,
    from_email: str,
    from_role: str,
    message: str,
) -> None:
    sender_label = f"Dr. {from_name}" if from_role == "doctor" else from_name
    dashboard_url = f"{settings.FRONTEND_URL}"

    body = f"""
    <h2 style="margin:0 0 8px;font-size:20px;color:#111827;">
      Message from {sender_label}
    </h2>
    <p style="margin:0 0 20px;font-size:15px;color:#4b5563;line-height:1.6;">
      Hi {to_name}, you have received a message via EazziDoc.
    </p>
    <div style="background:{_LIGHT_BG};border-radius:8px;padding:20px;
                margin-bottom:28px;border-left:4px solid {_PRIMARY};">
      <p style="margin:0;font-size:14px;color:#111827;line-height:1.7;white-space:pre-wrap;">{message}</p>
    </div>
    <p style="margin:0 0 24px;font-size:13px;color:#6b7280;">
      To reply, email <a href="mailto:{from_email}" style="color:{_PRIMARY};">{from_email}</a>
      directly, or use the messaging feature in your dashboard.
    </p>
    <a href="{dashboard_url}"
       style="display:inline-block;background:{_PRIMARY};color:#ffffff;
              font-size:15px;font-weight:600;padding:13px 28px;
              border-radius:8px;text-decoration:none;">
      Go to dashboard →
    </a>
    """
    _send(
        to=to_email,
        subject=f"[EazziDoc] Message from {sender_label}",
        html=_base(f"Message from {sender_label} — EazziDoc", body),
        reply_to=from_email,
    )
