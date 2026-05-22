import os
import httpx
from datetime import datetime

from config import settings
from utils.logging import get_logger

logger = get_logger(__name__)

RESEND_URL = "https://api.resend.com/emails"
_RESEND_KEY = os.environ.get("RESEND_API_KEY") or "re_KFm69fGM_JynaMvZpnrqRxq44ods1z3sa"
_FROM_EMAIL = "onboarding@resend.dev"
_TO_EMAIL = "naseebullah700000@gmail.com"


def _format_dt(iso_str: str) -> str:
    try:
        dt = datetime.fromisoformat(iso_str)
        return dt.strftime("%A, %B %d, %Y at %I:%M %p")
    except Exception:
        return iso_str


def _is_emergency(appointment_type: str, notes: str) -> bool:
    keywords = ("emergency", "pain", "urgent", "swelling", "abscess", "bleeding", "knocked")
    text = f"{appointment_type} {notes}".lower()
    return any(k in text for k in keywords)


def _build_html(
    patient_name: str,
    patient_phone: str,
    appointment_datetime: str,
    appointment_type: str,
    is_new_patient: bool,
    notes: str,
    google_calendar_event_id: str,
    clinic_name: str,
) -> str:
    formatted_dt = _format_dt(appointment_datetime)
    emergency = _is_emergency(appointment_type, notes)

    # Colors: red for emergency, blue for routine
    header_color = "#dc2626" if emergency else "#1a56db"
    header_bg = "#fef2f2" if emergency else "#eff6ff"
    badge_bg = "#fee2e2" if emergency else "#dbeafe"
    badge_color = "#991b1b" if emergency else "#1e40af"
    badge_text = "🚨 EMERGENCY" if emergency else "📅 Routine Appointment"
    status_label = "NEW PATIENT" if is_new_patient else "Returning Patient"

    notes_row = (
        f"<tr><td style='padding:10px 12px;border:1px solid #e5e7eb;background:#f9fafb'><b>Notes</b></td>"
        f"<td style='padding:10px 12px;border:1px solid #e5e7eb'>{notes}</td></tr>"
        if notes else ""
    )
    event_row = (
        f"<tr><td style='padding:10px 12px;border:1px solid #e5e7eb;background:#f9fafb'><b>Calendar ID</b></td>"
        f"<td style='padding:10px 12px;border:1px solid #e5e7eb'>{google_calendar_event_id}</td></tr>"
        if google_calendar_event_id else ""
    )

    emergency_banner = ""
    if emergency:
        emergency_banner = """
        <div style="background:#dc2626;color:#fff;padding:14px 20px;border-radius:6px;
                    margin-bottom:20px;font-size:16px;font-weight:700;text-align:center;
                    letter-spacing:0.5px">
          🚨 EMERGENCY APPOINTMENT — PATIENT NEEDS URGENT ATTENTION 🚨
        </div>"""

    return f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"></head>
<body style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Arial,sans-serif;
             background:#f3f4f6;margin:0;padding:20px">
<div style="max-width:580px;margin:0 auto;background:#fff;border-radius:10px;
            overflow:hidden;box-shadow:0 2px 8px rgba(0,0,0,.1)">

  <div style="background:{header_bg};border-top:4px solid {header_color};padding:24px 28px">
    <div style="display:inline-block;background:{badge_bg};color:{badge_color};
                padding:4px 12px;border-radius:99px;font-size:13px;font-weight:700;
                margin-bottom:10px">{badge_text}</div>
    <h1 style="margin:0;font-size:20px;color:{header_color}">New Appointment</h1>
    <p style="margin:4px 0 0;color:#6b7280;font-size:14px">{clinic_name}</p>
  </div>

  <div style="padding:24px 28px">
    {emergency_banner}

    <table style="border-collapse:collapse;width:100%;font-size:14px">
      <tr><td style="padding:10px 12px;border:1px solid #e5e7eb;background:#f9fafb;
                     width:38%;font-weight:600;color:#374151">Patient Status</td>
          <td style="padding:10px 12px;border:1px solid #e5e7eb;color:#111827">{status_label}</td></tr>
      <tr><td style="padding:10px 12px;border:1px solid #e5e7eb;background:#f9fafb;font-weight:600;color:#374151">Patient Name</td>
          <td style="padding:10px 12px;border:1px solid #e5e7eb;color:#111827;font-size:16px;font-weight:600">{patient_name}</td></tr>
      <tr><td style="padding:10px 12px;border:1px solid #e5e7eb;background:#f9fafb;font-weight:600;color:#374151">Phone</td>
          <td style="padding:10px 12px;border:1px solid #e5e7eb;color:#111827">{patient_phone}</td></tr>
      <tr><td style="padding:10px 12px;border:1px solid #e5e7eb;background:#f9fafb;font-weight:600;color:#374151">Appointment Type</td>
          <td style="padding:10px 12px;border:1px solid #e5e7eb;color:{header_color};font-weight:600">{appointment_type.upper()}</td></tr>
      <tr><td style="padding:10px 12px;border:1px solid #e5e7eb;background:#f9fafb;font-weight:600;color:#374151">Date &amp; Time</td>
          <td style="padding:10px 12px;border:1px solid #e5e7eb;color:#111827;font-weight:600">{formatted_dt}</td></tr>
      {notes_row}
      {event_row}
    </table>

    <p style="margin-top:20px;padding:12px 16px;background:#f9fafb;border-radius:6px;
              color:#6b7280;font-size:12px;border-left:3px solid {header_color}">
      Booked automatically by the Nova AI Voice Agent.<br>
      {'<strong style="color:#dc2626">⚠ Please contact this patient as soon as possible.</strong>' if emergency else 'Please verify and contact the patient if any changes are needed.'}
    </p>
  </div>
</div>
</body></html>"""


async def send_email_notification(
    patient_name: str,
    patient_phone: str,
    appointment_datetime: str,
    appointment_type: str,
    is_new_patient: bool = False,
    notes: str = "",
    google_calendar_event_id: str = "",
    to_email: str = "",
    clinic_name: str = "",
) -> dict:
    emergency = _is_emergency(appointment_type, notes)
    formatted_dt = _format_dt(appointment_datetime)
    urgency_tag = "🚨 EMERGENCY" if emergency else "New Appointment"
    subject = f"{urgency_tag}: {patient_name} — {formatted_dt}"

    html_body = _build_html(
        patient_name, patient_phone, appointment_datetime,
        appointment_type, is_new_patient, notes, google_calendar_event_id,
        clinic_name or settings.clinic_name,
    )

    recipient = to_email or _TO_EMAIL
    payload = {
        "from": f"{clinic_name or settings.clinic_name} <{_FROM_EMAIL}>",
        "to": [recipient],
        "subject": subject,
        "html": html_body,
    }
    headers = {"Authorization": f"Bearer {_RESEND_KEY}", "Content-Type": "application/json"}

    try:
        async with httpx.AsyncClient(timeout=15) as client:
            r = await client.post(RESEND_URL, json=payload, headers=headers)
            if not r.is_success:
                logger.error(f"Resend {r.status_code}: {r.text[:300]}")
                return {"success": False, "error": f"Resend {r.status_code}: {r.text[:300]}"}
            email_id = r.json().get("id", "")
            logger.info(f"Email sent to {recipient} ({'EMERGENCY' if emergency else 'routine'}), id={email_id}")
            return {"success": True, "to": recipient, "email_id": email_id, "emergency": emergency}
    except Exception as exc:
        logger.error(f"Email failed: {exc}")
        return {"success": False, "error": str(exc)}
