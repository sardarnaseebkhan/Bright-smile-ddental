import os
import httpx
from datetime import datetime

from config import settings
from utils.logging import get_logger

logger = get_logger(__name__)

RESEND_URL = "https://api.resend.com/emails"
# Use `or` so an empty-string env var still falls back to the hardcoded default
_RESEND_KEY = os.environ.get("RESEND_API_KEY") or "re_KFm69fGM_JynaMvZpnrqRxq44ods1z3sa"
_FROM_EMAIL = "onboarding@resend.dev"  # Resend free-tier verified sender
# Resend free tier: can only deliver to the account owner's email until a domain is verified
_TO_EMAIL = "naseebullah700000@gmail.com"


def _format_dt(iso_str: str) -> str:
    try:
        dt = datetime.fromisoformat(iso_str)
        return dt.strftime("%A, %B %d, %Y at %I:%M %p")
    except Exception:
        return iso_str


def _build_html(
    patient_name: str,
    patient_phone: str,
    appointment_datetime: str,
    appointment_type: str,
    is_new_patient: bool,
    notes: str,
    google_calendar_event_id: str,
) -> str:
    formatted_dt = _format_dt(appointment_datetime)
    status_label = "NEW PATIENT" if is_new_patient else "Returning Patient"
    notes_row = (
        f"<tr><td style='padding:8px;border:1px solid #ddd'><b>Notes</b></td>"
        f"<td style='padding:8px;border:1px solid #ddd'>{notes}</td></tr>"
        if notes else ""
    )
    event_row = (
        f"<tr><td style='padding:8px;border:1px solid #ddd'><b>Calendar Event ID</b></td>"
        f"<td style='padding:8px;border:1px solid #ddd'>{google_calendar_event_id}</td></tr>"
        if google_calendar_event_id else ""
    )
    return f"""<html><body style="font-family:Arial,sans-serif;max-width:600px;margin:0 auto">
<h2 style="color:#2c7be5">New Appointment — {settings.clinic_name}</h2>
<table style="border-collapse:collapse;width:100%">
  <tr><td style="padding:8px;border:1px solid #ddd"><b>Patient Status</b></td>
      <td style="padding:8px;border:1px solid #ddd">{status_label}</td></tr>
  <tr><td style="padding:8px;border:1px solid #ddd"><b>Patient Name</b></td>
      <td style="padding:8px;border:1px solid #ddd">{patient_name}</td></tr>
  <tr><td style="padding:8px;border:1px solid #ddd"><b>Phone</b></td>
      <td style="padding:8px;border:1px solid #ddd">{patient_phone}</td></tr>
  <tr><td style="padding:8px;border:1px solid #ddd"><b>Appointment Type</b></td>
      <td style="padding:8px;border:1px solid #ddd">{appointment_type}</td></tr>
  <tr><td style="padding:8px;border:1px solid #ddd"><b>Date &amp; Time</b></td>
      <td style="padding:8px;border:1px solid #ddd">{formatted_dt} ET</td></tr>
  {notes_row}
  {event_row}
</table>
<p style="color:#666;font-size:12px;margin-top:20px">
  Booked automatically by the AI Voice Agent.<br>
  Please verify and contact the patient if any changes are needed.
</p>
</body></html>"""


async def send_email_notification(
    patient_name: str,
    patient_phone: str,
    appointment_datetime: str,
    appointment_type: str,
    is_new_patient: bool = False,
    notes: str = "",
    google_calendar_event_id: str = "",
) -> dict:
    formatted_dt = _format_dt(appointment_datetime)
    subject = f"New Appointment: {patient_name} — {formatted_dt}"
    html_body = _build_html(
        patient_name, patient_phone, appointment_datetime,
        appointment_type, is_new_patient, notes, google_calendar_event_id,
    )

    payload = {
        "from": f"{settings.clinic_name} <{_FROM_EMAIL}>",
        "to": [_TO_EMAIL],
        "subject": subject,
        "html": html_body,
    }
    headers = {
        "Authorization": f"Bearer {_RESEND_KEY}",
        "Content-Type": "application/json",
    }

    try:
        async with httpx.AsyncClient(timeout=15) as client:
            r = await client.post(RESEND_URL, json=payload, headers=headers)
            if not r.is_success:
                body = r.text[:300]
                logger.error(f"Resend {r.status_code}: {body}")
                return {"success": False, "error": f"Resend {r.status_code}: {body}"}
            email_id = r.json().get("id", "")
            logger.info(f"Email sent via Resend to {_TO_EMAIL}, id={email_id}")
            return {"success": True, "to": _TO_EMAIL, "email_id": email_id}
    except Exception as exc:
        logger.error(f"Email failed: {exc}")
        return {"success": False, "error": str(exc)}
