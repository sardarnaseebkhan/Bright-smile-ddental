"""
Run once to create the VAPI assistant and link your free phone number.

    python scripts/setup_vapi.py

What it does:
  1. Reads VAPI_API_KEY and SERVER_BASE_URL from .env
  2. Creates a VAPI assistant named "Nova" with:
       - Claude claude-sonnet-4-6 as the AI model
       - Deepgram Aura voice (aura-asteria-en)
       - Deepgram nova-2 transcriber
       - System prompt (dental clinic persona)
       - 3 tools: check_available_slots, book_appointment, send_email_notification
  3. Lists your VAPI phone numbers and assigns the first free number to the assistant
  4. Prints the assistant ID and phone number — save these in .env

Run this again any time you update the system prompt or tools.
"""
import json
import os
import sys

import httpx
from dotenv import load_dotenv

load_dotenv()

VAPI_API_KEY = os.getenv("VAPI_API_KEY", "")
SERVER_BASE_URL = os.getenv("SERVER_BASE_URL", "").rstrip("/")
CLINIC_NAME = os.getenv("CLINIC_NAME", "Bright Smiles Dental")
CLINIC_ADDRESS = os.getenv("CLINIC_ADDRESS", "1234 Main St, McLean, VA 22101")
CLINIC_PHONE = os.getenv("CLINIC_PHONE", "")
CLINIC_HOURS_MON_FRI = os.getenv("CLINIC_HOURS_MON_FRI", "8:00 AM - 6:00 PM")
CLINIC_HOURS_SAT = os.getenv("CLINIC_HOURS_SAT", "9:00 AM - 2:00 PM")
CLINIC_HOURS_SUN = os.getenv("CLINIC_HOURS_SUN", "Closed")

if not VAPI_API_KEY or VAPI_API_KEY == "your_vapi_private_api_key":
    print("ERROR: Set VAPI_API_KEY in your .env file first.")
    sys.exit(1)

if not SERVER_BASE_URL or "ngrok.io" not in SERVER_BASE_URL and "ngrok-free.app" not in SERVER_BASE_URL and "localhost" not in SERVER_BASE_URL:
    print(f"WARNING: SERVER_BASE_URL='{SERVER_BASE_URL}' — make sure ngrok is running and this URL is public.")

WEBHOOK_URL = f"{SERVER_BASE_URL}/vapi/webhook"

HEADERS = {
    "Authorization": f"Bearer {VAPI_API_KEY}",
    "Content-Type": "application/json",
}

SYSTEM_PROMPT = f"""You are Nova, a warm and professional AI receptionist for {CLINIC_NAME}, a dental clinic at {CLINIC_ADDRESS} in Virginia.

## Clinic Information

Phone: {CLINIC_PHONE or "our main line"}
Address: {CLINIC_ADDRESS}
Hours:
  Monday–Friday: {CLINIC_HOURS_MON_FRI}
  Saturday: {CLINIC_HOURS_SAT}
  Sunday: {CLINIC_HOURS_SUN}

Services: General dentistry (cleanings, fillings, extractions, root canals, crowns), cosmetic dentistry (whitening, veneers, bonding), orthodontics (braces, Invisalign), pediatric dentistry, same-day emergency care.

Insurance: Delta Dental, MetLife, Cigna, Aetna, United Concordia, BlueCross BlueShield, CareCredit financing.

New patients: Please arrive 15 minutes early with insurance card and photo ID.

## Voice Guidelines

- Keep responses SHORT and CONVERSATIONAL. You are speaking on the phone.
- One idea per sentence. No bullet points.
- Always confirm details before booking.

## Appointment Booking Flow

1. Ask for the patient's name and whether they are new or returning.
2. Ask what brings them in.
3. Ask for their preferred day/time.
4. Call check_available_slots to find open times.
5. Offer 2-3 options: "I have Monday at 9 AM or Tuesday at 2 PM — which works?"
6. Get their phone number.
7. Call book_appointment once they confirm.
8. Call send_email_notification immediately after — never skip this.
9. Confirm the appointment and mention they'll get a reminder the day before.

## Emergency Handling

Severe pain, swelling, knocked-out tooth, or abscess — say: "That sounds urgent, let me check our emergency slots right now." Call check_available_slots with appointment_type="emergency" and preferred_date="today".

## Human Handoff

Billing disputes or complex insurance questions — say: "Let me connect you to our office manager who can help right away." Then end warmly.

## Sample Phrases

Greeting: "Thank you for calling {CLINIC_NAME}, this is Nova! How can I help you today?"
Scheduling: "I'd love to get that set up — can I start with your name?"
Empathy: "I'm so sorry you're in pain. Let me check our availability right now."
Closing: "Wonderful, we'll see you then! Have a great day!"
"""

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "check_available_slots",
            "description": (
                "Check available appointment slots on the dental clinic's Google Calendar. "
                "Call this when a patient wants to book and you need to find open times."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "preferred_date": {
                        "type": "string",
                        "description": "Preferred date as YYYY-MM-DD or natural language like 'today', 'tomorrow', 'next Monday'.",
                    },
                    "preferred_time_of_day": {
                        "type": "string",
                        "enum": ["morning", "afternoon", "evening", "any"],
                        "description": "Patient's preferred time of day.",
                    },
                    "appointment_type": {
                        "type": "string",
                        "description": "Type of visit: 'cleaning', 'filling', 'consultation', 'emergency', 'whitening', 'extraction', 'other'.",
                    },
                    "duration_minutes": {
                        "type": "integer",
                        "description": "Estimated duration in minutes. Default 60.",
                    },
                },
                "required": ["preferred_date", "appointment_type"],
            },
        },
        "server": {"url": WEBHOOK_URL},
    },
    {
        "type": "function",
        "function": {
            "name": "book_appointment",
            "description": (
                "Book a dental appointment by creating a Google Calendar event. "
                "Only call this after the patient confirms a specific date and time."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "patient_name": {"type": "string", "description": "Full name of the patient."},
                    "patient_phone": {"type": "string", "description": "Patient's phone number."},
                    "appointment_datetime": {
                        "type": "string",
                        "description": "Appointment start in ISO 8601: YYYY-MM-DDTHH:MM:SS",
                    },
                    "duration_minutes": {"type": "integer", "description": "Duration in minutes. Default 60."},
                    "appointment_type": {"type": "string", "description": "Type or reason for the visit."},
                    "is_new_patient": {"type": "boolean", "description": "True if new patient."},
                    "notes": {"type": "string", "description": "Additional notes."},
                },
                "required": ["patient_name", "patient_phone", "appointment_datetime", "appointment_type"],
            },
        },
        "server": {"url": WEBHOOK_URL},
    },
    {
        "type": "function",
        "function": {
            "name": "send_email_notification",
            "description": (
                "Send an email to the clinic owner about a newly booked appointment. "
                "Always call this immediately after book_appointment succeeds."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "patient_name": {"type": "string", "description": "Patient's full name."},
                    "patient_phone": {"type": "string", "description": "Patient's phone number."},
                    "appointment_datetime": {"type": "string", "description": "Datetime in ISO 8601."},
                    "appointment_type": {"type": "string", "description": "Type of appointment."},
                    "is_new_patient": {"type": "boolean", "description": "True if new patient."},
                    "notes": {"type": "string", "description": "Additional notes."},
                    "google_calendar_event_id": {"type": "string", "description": "Event ID from book_appointment."},
                },
                "required": ["patient_name", "patient_phone", "appointment_datetime", "appointment_type"],
            },
        },
        "server": {"url": WEBHOOK_URL},
    },
]

ASSISTANT_PAYLOAD = {
    "name": f"Nova — {CLINIC_NAME} Receptionist",
    "firstMessage": f"Thank you for calling {CLINIC_NAME}, this is Nova! How can I help you today?",
    "model": {
        "provider": "anthropic",
        "model": "claude-3-5-sonnet-20241022",
        "systemPrompt": SYSTEM_PROMPT,
        "temperature": 0.7,
    },
    "voice": {
        "provider": "deepgram",
        "voiceId": "asteria",
    },
    "transcriber": {
        "provider": "deepgram",
        "model": "nova-2",
        "language": "en",
    },
    "tools": TOOLS,
    "serverUrl": WEBHOOK_URL,
    "endCallMessage": "Thank you for calling. Have a wonderful day!",
    "recordingEnabled": False,
    "silenceTimeoutSeconds": 30,
    "maxDurationSeconds": 600,
}


def create_or_update_assistant() -> str:
    """Create a new assistant or update if one with the same name exists."""
    with httpx.Client() as client:
        # Check for existing assistant with same name
        resp = client.get("https://api.vapi.ai/assistant", headers=HEADERS)
        resp.raise_for_status()
        existing = resp.json()

        for asst in (existing if isinstance(existing, list) else existing.get("data", [])):
            if asst.get("name") == ASSISTANT_PAYLOAD["name"]:
                asst_id = asst["id"]
                print(f"Updating existing assistant: {asst_id}")
                r = client.patch(
                    f"https://api.vapi.ai/assistant/{asst_id}",
                    headers=HEADERS,
                    json=ASSISTANT_PAYLOAD,
                )
                r.raise_for_status()
                return asst_id

        # Create new
        print("Creating new VAPI assistant...")
        r = client.post("https://api.vapi.ai/assistant", headers=HEADERS, json=ASSISTANT_PAYLOAD)
        r.raise_for_status()
        return r.json()["id"]


def list_phone_numbers() -> list:
    with httpx.Client() as client:
        resp = client.get("https://api.vapi.ai/phone-number", headers=HEADERS)
        resp.raise_for_status()
        data = resp.json()
        return data if isinstance(data, list) else data.get("data", [])


def assign_phone_to_assistant(phone_id: str, assistant_id: str):
    with httpx.Client() as client:
        resp = client.patch(
            f"https://api.vapi.ai/phone-number/{phone_id}",
            headers=HEADERS,
            json={"assistantId": assistant_id},
        )
        resp.raise_for_status()


def main():
    print(f"\n{'='*60}")
    print(f"  VAPI Setup — {CLINIC_NAME}")
    print(f"  Webhook URL: {WEBHOOK_URL}")
    print(f"{'='*60}\n")

    # Step 1: Create/update assistant
    asst_id = create_or_update_assistant()
    print(f"✓ Assistant ID: {asst_id}")

    # Step 2: List phone numbers
    numbers = list_phone_numbers()
    if not numbers:
        print("\n⚠  No phone numbers found on your VAPI account.")
        print("   Go to dashboard.vapi.ai → Phone Numbers → get a free number first.")
        print(f"\n   Then run: python scripts/setup_vapi.py")
        print(f"\n   Add to .env:  VAPI_PHONE_NUMBER_ID=<the phone number id>")
        print(f"   Assistant ID: {asst_id}")
        return

    # Use first available number
    phone = numbers[0]
    phone_id = phone["id"]
    phone_number = phone.get("number", phone_id)

    print(f"✓ Found phone number: {phone_number} (id: {phone_id})")

    # Step 3: Assign phone number to assistant
    assign_phone_to_assistant(phone_id, asst_id)
    print(f"✓ Phone number assigned to assistant")

    print(f"\n{'='*60}")
    print(f"  Setup complete! Add these to your .env:")
    print(f"  VAPI_PHONE_NUMBER_ID={phone_id}")
    print(f"\n  Call {phone_number} to test Nova!")
    print(f"  (Make sure your FastAPI server + ngrok are running first)")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    main()
