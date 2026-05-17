import asyncio
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from datetime import datetime

from config import settings
from utils.logging import get_logger

logger = get_logger(__name__)


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
  Please verify in Google Calendar and contact the patient if any changes are needed.
</p>
</body></html>"""


def _send_smtp(subject: str, html_body: str, to_email: str):
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = f"{settings.clinic_name} <{settings.from_email}>"
    msg["To"] = to_email
    msg.attach(MIMEText(html_body, "html"))

    with smtplib.SMTP_SSL(settings.smtp_host, settings.smtp_port) as server:
        server.login(settings.smtp_user, settings.smtp_password)
        server.sendmail(settings.from_email, to_email, msg.as_string())


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
    try:
        await asyncio.to_thread(_send_smtp, subject, html_body, settings.clinic_owner_email)
        logger.info(f"Email sent to {settings.clinic_owner_email} for {patient_name}")
        return {"success": True, "to": settings.clinic_owner_email}
    except Exception as exc:
        logger.error(f"Email failed: {exc}")
        return {"success": False, "error": str(exc)}
