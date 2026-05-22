"""
Provision (create or update) a VAPI assistant for a business.
"""
import os
import httpx
from utils.system_prompt import build as build_prompt

VAPI_KEY = os.environ.get("VAPI_API_KEY", "3a2e87a1-6100-42d2-b805-376dfae6cf99")
VAPI_HEADERS = {"Authorization": f"Bearer {VAPI_KEY}", "Content-Type": "application/json"}
SERVER_BASE_URL = os.environ.get("SERVER_BASE_URL", "https://web-production-0209e.up.railway.app")

_TOOL_PARAMS = {
    "check_available_slots": {
        "description": "Check available appointment slots. Call when patient wants to book.",
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
    "book_appointment": {
        "description": "Book an appointment after patient confirms date and time.",
        "parameters": {
            "type": "object",
            "properties": {
                "patient_name": {"type": "string"},
                "patient_phone": {"type": "string"},
                "appointment_datetime": {"type": "string", "description": "ISO 8601: YYYY-MM-DDTHH:MM:SS"},
                "duration_minutes": {"type": "integer"},
                "appointment_type": {"type": "string"},
                "is_new_patient": {"type": "boolean"},
                "notes": {"type": "string"},
            },
            "required": ["patient_name", "patient_phone", "appointment_datetime", "appointment_type"],
        },
    },
    "send_email_notification": {
        "description": "Email the clinic owner. Always call immediately after book_appointment.",
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
}


def _build_payload(biz: dict) -> dict:
    biz_id = biz["id"]
    webhook_url = f"{SERVER_BASE_URL}/vapi/{biz_id}/webhook"
    llm_url = f"{SERVER_BASE_URL}/llm/{biz_id}/v1/chat/completions"

    tools = [
        {
            "type": "function",
            "function": {"name": name, **params},
            "server": {"url": webhook_url},
        }
        for name, params in _TOOL_PARAMS.items()
    ]

    assistant_name = biz.get("assistant_name") or f"Nova — {biz['name']}"
    first_message = biz.get("first_message") or f"Thank you for calling {biz['name']}, this is Nova! How can I help you today?"

    return {
        "name": assistant_name,
        "firstMessage": first_message,
        "model": {
            "provider": "custom-llm",
            "url": llm_url,
            "model": "openai/gpt-oss-120b:free",
            "systemPrompt": build_prompt(biz),
            "temperature": 0.7,
            "tools": tools,
        },
        "voice": {"provider": "deepgram", "voiceId": "asteria"},
        "transcriber": {
            "provider": "deepgram",
            "model": "nova-2",
            "language": "en",
            "endpointing": 200,
        },
        "startSpeakingPlan": {"waitSeconds": 0.3, "smartEndpointingEnabled": True},
        "endCallMessage": "It was a pleasure speaking with you. Have a wonderful day! Goodbye!",
        "endCallPhrases": [
            "Goodbye!",
            "Have a wonderful day! Goodbye",
            "Have a great day! Goodbye",
            "Take care! Goodbye",
        ],
        "silenceTimeoutSeconds": 30,
        "maxDurationSeconds": 600,
    }


async def provision(biz: dict) -> str:
    """Create or update VAPI assistant. Returns assistant ID."""
    payload = _build_payload(biz)
    existing_id = biz.get("vapi_assistant_id", "")

    async with httpx.AsyncClient(timeout=20) as client:
        if existing_id:
            r = await client.patch(
                f"https://api.vapi.ai/assistant/{existing_id}",
                headers=VAPI_HEADERS,
                json=payload,
            )
            if r.is_success:
                return existing_id

        r = await client.post("https://api.vapi.ai/assistant", headers=VAPI_HEADERS, json=payload)
        r.raise_for_status()
        return r.json()["id"]
