"""
All-in-one startup script.
Run:  python start.py

What it does:
  1. Opens a Cloudflare Quick Tunnel on port 8000 (free, no account needed)
  2. Updates SERVER_BASE_URL in .env with the live tunnel URL
  3. Creates/updates the VAPI assistant with the correct webhook URL
  4. Starts the FastAPI server (blocks until Ctrl+C)
"""
import os
import re
import sys
import subprocess
import threading
import time

import httpx
import uvicorn
from dotenv import load_dotenv, set_key

load_dotenv()

VAPI_API_KEY = os.getenv("VAPI_API_KEY", "")
ENV_FILE = os.path.join(os.path.dirname(__file__), ".env")
CLOUDFLARED = os.path.join(os.path.dirname(__file__), "cloudflared.exe")

HEADERS = {
    "Authorization": f"Bearer {VAPI_API_KEY}",
    "Content-Type": "application/json",
}

CLINIC_NAME = os.getenv("CLINIC_NAME", "Bright Smiles Dental")
CLINIC_ADDRESS = os.getenv("CLINIC_ADDRESS", "1234 Main St, McLean, VA 22101")
CLINIC_PHONE = os.getenv("CLINIC_PHONE", "")
CLINIC_HOURS_MON_FRI = os.getenv("CLINIC_HOURS_MON_FRI", "8:00 AM - 6:00 PM")
CLINIC_HOURS_SAT = os.getenv("CLINIC_HOURS_SAT", "9:00 AM - 2:00 PM")
CLINIC_HOURS_SUN = os.getenv("CLINIC_HOURS_SUN", "Closed")

SYSTEM_PROMPT = f"""You are Nova, a warm and professional AI receptionist for {CLINIC_NAME}, a dental clinic at {CLINIC_ADDRESS} in Virginia.

## Clinic Information

Phone: {CLINIC_PHONE or "our main line"}
Address: {CLINIC_ADDRESS}
Hours:
  Monday-Friday: {CLINIC_HOURS_MON_FRI}
  Saturday: {CLINIC_HOURS_SAT}
  Sunday: {CLINIC_HOURS_SUN}

Services: General dentistry (cleanings, fillings, extractions, root canals, crowns), cosmetic dentistry (whitening, veneers, bonding), orthodontics (braces, Invisalign), pediatric dentistry, same-day emergency care.

Insurance: Delta Dental, MetLife, Cigna, Aetna, United Concordia, BlueCross BlueShield, CareCredit financing.

New patients: Please arrive 15 minutes early with insurance card and photo ID.

## Voice Guidelines

- Keep responses SHORT and CONVERSATIONAL. You are speaking on the phone.
- One idea per sentence. No bullet points or lists.
- Always confirm details before booking.

## Appointment Booking Flow

1. Ask for patient name and whether they are new or returning.
2. Ask what brings them in today.
3. Ask for preferred day and time.
4. Call check_available_slots to find open times.
5. Offer 2-3 options: "I have Monday at 9 AM or Tuesday at 2 PM, which works better for you?"
6. Get their phone number for records.
7. Call book_appointment once they confirm.
8. Call send_email_notification immediately after booking, without exception.
9. Confirm the appointment and tell them they will receive a reminder the day before.

## Emergency Handling

Severe pain, swelling, knocked-out tooth, or abscess: say "That sounds urgent, let me check our emergency slots right now." Then call check_available_slots with appointment_type="emergency" and preferred_date="today".

## Human Handoff

Billing disputes or complex insurance questions: say "Let me connect you to our office manager who can help you right away." Then end the call warmly.

## Sample Phrases

Greeting: "Thank you for calling {CLINIC_NAME}, this is Nova! How can I help you today?"
Scheduling: "I would love to get that set up for you, can I start with your name?"
Empathy: "I am so sorry you are in pain. Let me check our availability right now."
Closing: "Wonderful, we will see you then! Have a great day!"
"""


def update_env(key: str, value: str):
    set_key(ENV_FILE, key, value)
    os.environ[key] = value


def open_cloudflare_tunnel(port: int = 8000) -> str:
    """Start cloudflared quick tunnel and return the public HTTPS URL."""
    print("Opening Cloudflare Quick Tunnel...")
    proc = subprocess.Popen(
        [CLOUDFLARED, "tunnel", "--url", f"http://localhost:{port}", "--no-autoupdate"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )

    url = None
    deadline = time.time() + 30
    while time.time() < deadline:
        line = proc.stderr.readline()
        if not line:
            time.sleep(0.2)
            continue
        match = re.search(r"https://[a-z0-9\-]+\.trycloudflare\.com", line)
        if match:
            url = match.group(0)
            break

    if not url:
        proc.terminate()
        raise RuntimeError("Could not get cloudflare tunnel URL within 30s. Check your network.")

    # Keep the tunnel process running in background
    threading.Thread(target=proc.communicate, daemon=True).start()
    print(f"Tunnel URL: {url}")
    return url


def build_tools(webhook_url: str) -> list:
    return [
        {
            "type": "function",
            "function": {
                "name": "check_available_slots",
                "description": "Check available appointment slots on the dental clinic calendar. Call this when a patient wants to book.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "preferred_date": {"type": "string", "description": "Preferred date (YYYY-MM-DD or 'today', 'tomorrow', 'next Monday')."},
                        "preferred_time_of_day": {"type": "string", "enum": ["morning", "afternoon", "evening", "any"], "description": "Preferred time of day."},
                        "appointment_type": {"type": "string", "description": "Type: cleaning, filling, consultation, emergency, whitening, extraction, other."},
                        "duration_minutes": {"type": "integer", "description": "Duration in minutes. Default 60."},
                    },
                    "required": ["preferred_date", "appointment_type"],
                },
            },
            "server": {"url": webhook_url},
        },
        {
            "type": "function",
            "function": {
                "name": "book_appointment",
                "description": "Book a dental appointment. Only call after patient confirms the specific date and time.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "patient_name": {"type": "string", "description": "Full name."},
                        "patient_phone": {"type": "string", "description": "Phone number."},
                        "appointment_datetime": {"type": "string", "description": "ISO 8601: YYYY-MM-DDTHH:MM:SS"},
                        "duration_minutes": {"type": "integer", "description": "Duration in minutes."},
                        "appointment_type": {"type": "string", "description": "Reason for visit."},
                        "is_new_patient": {"type": "boolean", "description": "True if new patient."},
                        "notes": {"type": "string", "description": "Any extra notes."},
                    },
                    "required": ["patient_name", "patient_phone", "appointment_datetime", "appointment_type"],
                },
            },
            "server": {"url": webhook_url},
        },
        {
            "type": "function",
            "function": {
                "name": "send_email_notification",
                "description": "Email the clinic owner about the booking. Always call immediately after book_appointment succeeds.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "patient_name": {"type": "string"},
                        "patient_phone": {"type": "string"},
                        "appointment_datetime": {"type": "string"},
                        "appointment_type": {"type": "string"},
                        "is_new_patient": {"type": "boolean"},
                        "notes": {"type": "string"},
                        "google_calendar_event_id": {"type": "string"},
                    },
                    "required": ["patient_name", "patient_phone", "appointment_datetime", "appointment_type"],
                },
            },
            "server": {"url": webhook_url},
        },
    ]


def setup_vapi(webhook_url: str) -> str:
    payload = {
        "name": f"Nova — {CLINIC_NAME} Receptionist",
        "firstMessage": f"Thank you for calling {CLINIC_NAME}, this is Nova! How can I help you today?",
        "model": {
            "provider": "anthropic",
            "model": "claude-3-5-sonnet-20241022",
            "systemPrompt": SYSTEM_PROMPT,
            "temperature": 0.7,
            "tools": build_tools(webhook_url),
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
        "endCallMessage": "Thank you for calling. Have a wonderful day!",
        "silenceTimeoutSeconds": 30,
        "maxDurationSeconds": 600,
    }

    with httpx.Client(timeout=20) as client:
        resp = client.get("https://api.vapi.ai/assistant", headers=HEADERS)
        resp.raise_for_status()
        existing = resp.json()
        existing_list = existing if isinstance(existing, list) else existing.get("data", [])

        for asst in existing_list:
            if asst.get("name") == payload["name"]:
                asst_id = asst["id"]
                print(f"Updating existing assistant: {asst_id}")
                r = client.patch(f"https://api.vapi.ai/assistant/{asst_id}", headers=HEADERS, json=payload)
                if not r.is_success:
                    print(f"Update error: {r.text}")
                    r.raise_for_status()
                return asst_id

        print("Creating new VAPI assistant...")
        r = client.post("https://api.vapi.ai/assistant", headers=HEADERS, json=payload)
        if not r.is_success:
            print(f"Create error: {r.text}")
            r.raise_for_status()
        return r.json()["id"]


def assign_phone(assistant_id: str):
    phone_id = os.getenv("VAPI_PHONE_NUMBER_ID", "").strip()
    if not phone_id:
        print("No VAPI_PHONE_NUMBER_ID — skipping phone assignment.")
        return
    with httpx.Client(timeout=10) as client:
        r = client.patch(
            f"https://api.vapi.ai/phone-number/{phone_id}",
            headers=HEADERS,
            json={"assistantId": assistant_id},
        )
        if r.is_success:
            print("Phone number linked to assistant.")
        else:
            print(f"Phone link note: {r.text}")


def main():
    print("\n" + "=" * 60)
    print("  Nova — Bright Smiles Dental Voice Agent")
    print("=" * 60)

    # Step 1: Open tunnel
    public_url = open_cloudflare_tunnel(8000)
    webhook_url = f"{public_url}/vapi/webhook"

    # Step 2: Update .env
    update_env("SERVER_BASE_URL", public_url)
    print(f"SERVER_BASE_URL updated in .env")

    # Step 3: Create/update VAPI assistant
    print("\nConfiguring VAPI assistant...")
    asst_id = setup_vapi(webhook_url)
    print(f"Assistant ready: {asst_id}")

    # Step 4: Link phone number
    assign_phone(asst_id)

    print("\n" + "=" * 60)
    print(f"  Nova is LIVE!")
    print(f"  Tunnel:  {public_url}")
    print(f"  Webhook: {webhook_url}")
    print(f"  Emails -> khannn762@gmail.com")
    print(f"  Call your VAPI number now to test!")
    print(f"  Press Ctrl+C to stop")
    print("=" * 60 + "\n")

    # Step 5: Start server
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=False)


if __name__ == "__main__":
    main()
