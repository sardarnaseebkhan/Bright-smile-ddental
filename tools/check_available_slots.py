from services.google_calendar import check_available_slots as _check


async def execute_check_available_slots(tool_input: dict) -> dict:
    return await _check(
        preferred_date=tool_input["preferred_date"],
        appointment_type=tool_input["appointment_type"],
        preferred_time_of_day=tool_input.get("preferred_time_of_day", "any"),
        duration_minutes=tool_input.get("duration_minutes", 60),
    )
