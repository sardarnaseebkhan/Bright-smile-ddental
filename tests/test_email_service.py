"""
Run: python -m tests.test_email_service
Sends a real test email to CLINIC_OWNER_EMAIL. Ensure SMTP settings are set in .env
"""
import asyncio
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from services.email_service import send_email_notification


async def main():
    print("Sending test email to clinic owner...")
    result = await send_email_notification(
        patient_name="Jane Doe (TEST)",
        patient_phone="703-555-0101",
        appointment_datetime="2025-01-06T10:00:00",
        appointment_type="Teeth Cleaning",
        is_new_patient=True,
        notes="This is a test email from the AI Voice Agent. Please ignore.",
        google_calendar_event_id="test-event-id-123",
    )
    print(f"Result: {result}")


if __name__ == "__main__":
    asyncio.run(main())
