"""
Tool definitions in VAPI/OpenAI function-calling format.
These are embedded in the VAPI assistant config and also used by the webhook router.
"""

VAPI_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "check_available_slots",
            "description": (
                "Check available appointment slots on the dental clinic's Google Calendar. "
                "Call this when a patient wants to book and you need to find open times. "
                "Returns a list of available datetime options."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "preferred_date": {
                        "type": "string",
                        "description": (
                            "Preferred date as YYYY-MM-DD or natural language "
                            "like 'today', 'tomorrow', 'next Monday', 'this week'."
                        ),
                    },
                    "preferred_time_of_day": {
                        "type": "string",
                        "enum": ["morning", "afternoon", "evening", "any"],
                        "description": "Patient's preferred time of day.",
                    },
                    "appointment_type": {
                        "type": "string",
                        "description": (
                            "Type of visit: 'cleaning', 'filling', 'consultation', "
                            "'emergency', 'whitening', 'invisalign', 'extraction', 'other'."
                        ),
                    },
                    "duration_minutes": {
                        "type": "integer",
                        "description": (
                            "Estimated duration in minutes. Default 60. "
                            "Use 30 for quick consultations, 90 for complex procedures."
                        ),
                    },
                },
                "required": ["preferred_date", "appointment_type"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "book_appointment",
            "description": (
                "Book a dental appointment by creating a Google Calendar event. "
                "Only call this after the patient has confirmed the specific date and time. "
                "Returns a confirmation with the event ID."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "patient_name": {
                        "type": "string",
                        "description": "Full name of the patient.",
                    },
                    "patient_phone": {
                        "type": "string",
                        "description": "Patient's phone number for confirmation.",
                    },
                    "appointment_datetime": {
                        "type": "string",
                        "description": "Appointment start in ISO 8601 format: YYYY-MM-DDTHH:MM:SS",
                    },
                    "duration_minutes": {
                        "type": "integer",
                        "description": "Appointment duration in minutes. Default 60.",
                    },
                    "appointment_type": {
                        "type": "string",
                        "description": "Type or reason for the visit.",
                    },
                    "is_new_patient": {
                        "type": "boolean",
                        "description": "True if this is a new patient.",
                    },
                    "notes": {
                        "type": "string",
                        "description": "Any additional notes about the patient or visit.",
                    },
                },
                "required": [
                    "patient_name",
                    "patient_phone",
                    "appointment_datetime",
                    "appointment_type",
                ],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "send_email_notification",
            "description": (
                "Send an email notification to the clinic owner about a newly booked appointment. "
                "Always call this immediately after book_appointment succeeds."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "patient_name": {
                        "type": "string",
                        "description": "Patient's full name.",
                    },
                    "patient_phone": {
                        "type": "string",
                        "description": "Patient's phone number.",
                    },
                    "appointment_datetime": {
                        "type": "string",
                        "description": "Appointment datetime in ISO 8601 format.",
                    },
                    "appointment_type": {
                        "type": "string",
                        "description": "Type of appointment.",
                    },
                    "is_new_patient": {
                        "type": "boolean",
                        "description": "True if this is a new patient.",
                    },
                    "notes": {
                        "type": "string",
                        "description": "Additional notes about the appointment.",
                    },
                    "google_calendar_event_id": {
                        "type": "string",
                        "description": "The event ID returned by book_appointment.",
                    },
                },
                "required": [
                    "patient_name",
                    "patient_phone",
                    "appointment_datetime",
                    "appointment_type",
                ],
            },
        },
    },
]
