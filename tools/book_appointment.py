from services.google_calendar import book_appointment as _book
from services.email_service import send_email_notification as _send_email


async def execute_book_appointment(
    tool_input: dict,
    owner_email: str = "",
    clinic_name: str = "",
) -> dict:
    result = await _book(
        patient_name=tool_input["patient_name"],
        patient_phone=tool_input["patient_phone"],
        appointment_datetime=tool_input["appointment_datetime"],
        appointment_type=tool_input["appointment_type"],
        duration_minutes=tool_input.get("duration_minutes", 60),
        is_new_patient=tool_input.get("is_new_patient", False),
        notes=tool_input.get("notes", ""),
    )

    # Always fire email immediately — never rely on LLM to call the tool
    try:
        await _send_email(
            patient_name=tool_input["patient_name"],
            patient_phone=tool_input["patient_phone"],
            appointment_datetime=tool_input["appointment_datetime"],
            appointment_type=tool_input["appointment_type"],
            is_new_patient=tool_input.get("is_new_patient", False),
            notes=tool_input.get("notes", ""),
            google_calendar_event_id=result.get("event_id", ""),
            to_email=owner_email,
            clinic_name=clinic_name,
        )
    except Exception:
        pass

    return result
