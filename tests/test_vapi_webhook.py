"""
Run: python -m tests.test_vapi_webhook
Simulates a VAPI tool-call webhook locally without needing an actual phone call.
"""
import asyncio
import json
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import httpx

BASE_URL = "http://localhost:8000"


async def simulate_tool_call(tool_name: str, arguments: dict):
    """Send a fake VAPI tool-call webhook and print the result."""
    payload = {
        "message": {
            "type": "tool-calls",
            "toolCallList": [
                {
                    "id": "test_call_001",
                    "type": "function",
                    "function": {
                        "name": tool_name,
                        "arguments": json.dumps(arguments),
                    },
                }
            ],
        }
    }
    async with httpx.AsyncClient() as client:
        resp = await client.post(f"{BASE_URL}/vapi/webhook", json=payload, timeout=30.0)
        print(f"\nTool: {tool_name}")
        print(f"Status: {resp.status_code}")
        print(f"Response: {json.dumps(resp.json(), indent=2)}")


async def main():
    print("=" * 60)
    print("VAPI Webhook Simulator")
    print("Make sure 'uvicorn main:app --reload' is running first!")
    print("=" * 60)

    # Test 1: Check available slots
    await simulate_tool_call("check_available_slots", {
        "preferred_date": "tomorrow",
        "appointment_type": "cleaning",
        "preferred_time_of_day": "morning",
        "duration_minutes": 60,
    })

    # Test 2: Book appointment (use a slot from Test 1 result)
    from datetime import datetime, timedelta
    tomorrow_9am = (datetime.now() + timedelta(days=1)).replace(
        hour=9, minute=0, second=0, microsecond=0
    ).strftime("%Y-%m-%dT%H:%M:%S")

    await simulate_tool_call("book_appointment", {
        "patient_name": "Test Patient DELETE ME",
        "patient_phone": "703-555-0000",
        "appointment_datetime": tomorrow_9am,
        "appointment_type": "cleaning",
        "duration_minutes": 60,
        "is_new_patient": True,
        "notes": "TEST BOOKING — please delete from Google Calendar",
    })

    # Test 3: Send email notification
    await simulate_tool_call("send_email_notification", {
        "patient_name": "Test Patient DELETE ME",
        "patient_phone": "703-555-0000",
        "appointment_datetime": tomorrow_9am,
        "appointment_type": "Teeth Cleaning",
        "is_new_patient": True,
        "notes": "TEST — please ignore",
        "google_calendar_event_id": "test-event-id",
    })


if __name__ == "__main__":
    asyncio.run(main())
