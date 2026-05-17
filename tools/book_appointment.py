from services.google_calendar import book_appointment as _book


async def execute_book_appointment(tool_input: dict) -> dict:
    return await _book(
        patient_name=tool_input["patient_name"],
        patient_phone=tool_input["patient_phone"],
        appointment_datetime=tool_input["appointment_datetime"],
        appointment_type=tool_input["appointment_type"],
        duration_minutes=tool_input.get("duration_minutes", 60),
        is_new_patient=tool_input.get("is_new_patient", False),
        notes=tool_input.get("notes", ""),
    )
