"""
Run this ONCE after deploying to Railway to point VAPI at your permanent URL.

    python scripts/update_vapi_url.py https://your-app.railway.app

What it does:
  - Updates all 3 tool server URLs on the VAPI assistant
  - Verifies the health endpoint is reachable
  - Saves the URL to .env
"""
import sys
import os
import httpx
from dotenv import load_dotenv, set_key

load_dotenv()

VAPI_API_KEY = os.getenv("VAPI_API_KEY", "")
ENV_FILE = os.path.join(os.path.dirname(__file__), "..", ".env")
HEADERS = {"Authorization": f"Bearer {VAPI_API_KEY}", "Content-Type": "application/json"}

CLINIC_NAME = os.getenv("CLINIC_NAME", "Bright Smiles Dental")

SYSTEM_PROMPT = f"""You are Nova, a warm and professional AI receptionist for {CLINIC_NAME}.

Answer questions about the clinic, check appointment availability, and book appointments.
After every booking, always send an email notification to the clinic owner.
Keep all responses short and conversational — you are speaking on the phone.
"""


def get_assistant_id() -> str:
    with httpx.Client(timeout=10) as c:
        r = c.get("https://api.vapi.ai/assistant", headers=HEADERS)
        r.raise_for_status()
        for a in r.json():
            if "Nova" in a.get("name", ""):
                return a["id"]
    raise RuntimeError("No Nova assistant found. Run start.py first.")


def update_assistant(asst_id: str, webhook_url: str):
    tools = [
        {
            "type": "function",
            "function": {
                "name": "check_available_slots",
                "description": "Check available appointment slots on the dental clinic calendar.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "preferred_date": {"type": "string"},
                        "preferred_time_of_day": {"type": "string", "enum": ["morning", "afternoon", "evening", "any"]},
                        "appointment_type": {"type": "string"},
                        "duration_minutes": {"type": "integer"},
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
                "description": "Book a dental appointment after patient confirms date and time.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "patient_name": {"type": "string"},
                        "patient_phone": {"type": "string"},
                        "appointment_datetime": {"type": "string"},
                        "duration_minutes": {"type": "integer"},
                        "appointment_type": {"type": "string"},
                        "is_new_patient": {"type": "boolean"},
                        "notes": {"type": "string"},
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
                "description": "Email the clinic owner after a booking. Always call immediately after book_appointment.",
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

    with httpx.Client(timeout=15) as c:
        r = c.patch(
            f"https://api.vapi.ai/assistant/{asst_id}",
            headers=HEADERS,
            json={"model": {"provider": "groq", "model": "llama-3.3-70b-versatile",
                            "systemPrompt": SYSTEM_PROMPT, "tools": tools}},
        )
        r.raise_for_status()
        print(f"Assistant updated — using Groq llama-3.3-70b-versatile (free)")


def main():
    if len(sys.argv) < 2:
        print("Usage: python scripts/update_vapi_url.py https://your-app.railway.app")
        sys.exit(1)

    base_url = sys.argv[1].rstrip("/")
    webhook_url = f"{base_url}/vapi/webhook"

    print(f"\nVerifying server at {base_url}...")
    try:
        r = httpx.get(f"{base_url}/health", timeout=10)
        if r.status_code == 200:
            print(f"Server is live: {r.json()}")
        else:
            print(f"Warning: health check returned {r.status_code}")
    except Exception as e:
        print(f"Could not reach server: {e}")
        print("Deploy to Railway first, then run this script.")
        sys.exit(1)

    print(f"\nUpdating VAPI assistant...")
    asst_id = get_assistant_id()
    print(f"Found assistant: {asst_id}")
    update_assistant(asst_id, webhook_url)

    set_key(ENV_FILE, "SERVER_BASE_URL", base_url)
    print(f"Updated SERVER_BASE_URL in .env")

    print(f"\n{'='*55}")
    print(f"  Done! Nova is permanently live at:")
    print(f"  {base_url}")
    print(f"  Webhook: {webhook_url}")
    print(f"  Call your VAPI number to test!")
    print(f"{'='*55}\n")


if __name__ == "__main__":
    main()
