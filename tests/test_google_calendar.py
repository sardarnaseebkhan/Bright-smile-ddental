"""
Run: python -m tests.test_google_calendar
Tests Google Calendar slot checking and event creation.
Requires valid credentials in ./credentials/google-service-account.json and GOOGLE_CALENDAR_ID in .env
"""
import asyncio
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from services.google_calendar import check_available_slots, book_appointment


async def main():
    print("Checking available slots for tomorrow morning...")
    slots = await check_available_slots(
        preferred_date="tomorrow",
        appointment_type="cleaning",
        preferred_time_of_day="morning",
        duration_minutes=60,
    )
    print(f"Available slots: {slots['available_slots']}")

    if slots["available_slots"]:
        slot = slots["available_slots"][0]
        print(f"\nBooking test appointment at {slot}...")
        result = await book_appointment(
            patient_name="Test Patient DO NOT CONFIRM",
            patient_phone="703-555-0000",
            appointment_datetime=slot,
            appointment_type="cleaning",
            duration_minutes=60,
            is_new_patient=True,
            notes="TEST — please delete this event",
        )
        print(f"Booking result: {result}")
    else:
        print("No slots available — check your calendar and .env settings")


if __name__ == "__main__":
    asyncio.run(main())
