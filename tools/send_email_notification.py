from services.email_service import send_email_notification as _send


async def execute_send_email_notification(tool_input: dict) -> dict:
    return await _send(
        patient_name=tool_input["patient_name"],
        patient_phone=tool_input["patient_phone"],
        appointment_datetime=tool_input["appointment_datetime"],
        appointment_type=tool_input["appointment_type"],
        is_new_patient=tool_input.get("is_new_patient", False),
        notes=tool_input.get("notes", ""),
        google_calendar_event_id=tool_input.get("google_calendar_event_id", ""),
    )
