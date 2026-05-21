"""
POST /vapi/webhook

VAPI calls this endpoint whenever the AI assistant wants to execute a tool
(check_available_slots, book_appointment, send_email_notification).

Payload shape from VAPI:
{
  "message": {
    "type": "tool-calls",
    "toolCallList": [
      {
        "id": "toolu_xxx",
        "type": "function",
        "function": { "name": "book_appointment", "arguments": "{...}" }
      }
    ]
  }
}

Response shape VAPI expects:
{
  "results": [
    { "toolCallId": "toolu_xxx", "result": "plain text result" }
  ]
}
"""
import asyncio
import json
import os

import httpx
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from tools.book_appointment import execute_book_appointment
from tools.check_available_slots import execute_check_available_slots
from tools.send_email_notification import execute_send_email_notification
from utils.logging import get_logger

router = APIRouter(prefix="/vapi")
logger = get_logger(__name__)

VAPI_KEY = os.environ.get("VAPI_API_KEY", "3a2e87a1-6100-42d2-b805-376dfae6cf99")
VAPI_HEADERS = {"Authorization": f"Bearer {VAPI_KEY}", "Content-Type": "application/json"}

TOOL_EXECUTORS = {
    "book_appointment": execute_book_appointment,
    "check_available_slots": execute_check_available_slots,
    "send_email_notification": execute_send_email_notification,
}


async def _run_tool(tool_id: str, name: str, arguments: str) -> dict:
    try:
        args = json.loads(arguments)
        executor = TOOL_EXECUTORS.get(name)
        if not executor:
            return {"toolCallId": tool_id, "result": f"Unknown tool: {name}"}
        result = await executor(args)
        return {"toolCallId": tool_id, "result": json.dumps(result)}
    except Exception as exc:
        logger.error(f"Tool {name} failed: {exc}")
        return {"toolCallId": tool_id, "result": f"Error: {exc}"}


@router.post("/webhook")
async def vapi_webhook(request: Request):
    body = await request.json()
    message = body.get("message", {})
    msg_type = message.get("type")

    logger.info(f"VAPI webhook received: type={msg_type}")

    if msg_type == "tool-calls":
        tool_call_list = message.get("toolCallList", [])

        # Execute all tool calls concurrently
        tasks = [
            _run_tool(
                tc["id"],
                tc["function"]["name"],
                tc["function"].get("arguments", "{}"),
            )
            for tc in tool_call_list
            if tc.get("type") == "function"
        ]
        results = await asyncio.gather(*tasks)
        logger.info(f"Tool results: {results}")
        return JSONResponse({"results": list(results)})

    return JSONResponse({})


@router.post("/admin/setup-gemini")
async def setup_gemini(request: Request):
    """One-time: adds LLM credential to VAPI and switches assistant model."""
    results = {}
    try:
        body = await request.json()
    except Exception:
        body = {}

    PROVIDER_KEY = body.get("apiKey") or os.environ.get("NEW_LLM_KEY", "")
    PROVIDER = body.get("provider") or os.environ.get("NEW_LLM_PROVIDER", "together-ai")
    MODEL = body.get("model") or os.environ.get("NEW_LLM_MODEL", "meta-llama/Llama-3.3-70B-Instruct-Turbo")

    if not PROVIDER_KEY:
        return JSONResponse({"error": "Pass apiKey in request body"}, status_code=400)

    try:
        async with httpx.AsyncClient(timeout=20) as client:
            # Step 1: Add credential to VAPI
            cred_resp = await client.post(
                "https://api.vapi.ai/credential",
                headers=VAPI_HEADERS,
                json={"provider": PROVIDER, "apiKey": PROVIDER_KEY},
            )
            if cred_resp.status_code in (200, 201):
                results["credential"] = "added"
            elif cred_resp.status_code == 409:
                creds = await client.get("https://api.vapi.ai/credential", headers=VAPI_HEADERS)
                cred_list = creds.json() if isinstance(creds.json(), list) else creds.json().get("data", [])
                cred = next((c for c in cred_list if c.get("provider") == PROVIDER), None)
                if cred:
                    await client.patch(
                        f"https://api.vapi.ai/credential/{cred['id']}",
                        headers=VAPI_HEADERS,
                        json={"apiKey": PROVIDER_KEY},
                    )
                results["credential"] = "updated"
            else:
                results["credential"] = f"error {cred_resp.status_code}: {cred_resp.text[:300]}"

            # Step 2: Switch Nova assistant model
            resp = await client.get("https://api.vapi.ai/assistant", headers=VAPI_HEADERS)
            resp.raise_for_status()
            asst_list = resp.json() if isinstance(resp.json(), list) else resp.json().get("data", [])
            nova = next((a for a in asst_list if "Nova" in a.get("name", "")), None)
            if not nova:
                results["assistant"] = "error: Nova not found"
                return JSONResponse(results, status_code=404)

            old_model = nova.get("model", {})
            patch = await client.patch(
                f"https://api.vapi.ai/assistant/{nova['id']}",
                headers=VAPI_HEADERS,
                json={
                    "model": {
                        "provider": PROVIDER,
                        "model": MODEL,
                        "systemPrompt": old_model.get("systemPrompt", ""),
                        "temperature": 0.7,
                        "tools": old_model.get("tools", []),
                    }
                },
            )
            if not patch.is_success:
                results["assistant"] = f"error {patch.status_code}: {patch.text[:300]}"
            else:
                m = patch.json().get("model", {})
                results["assistant"] = f"{m.get('provider')}/{m.get('model')}"

    except Exception as e:
        results["exception"] = str(e)

    return JSONResponse(results)


@router.post("/admin/full-reset")
async def full_reset(request: Request):
    """Full reset: rebuilds Nova assistant with complete system prompt, tools, and Together AI model."""
    WEBHOOK = "https://web-production-0209e.up.railway.app/vapi/webhook"
    TOGETHER_KEY = "tgp_v1_oqn_c9xhsbwlyePOPY2bqVzyjn01960E0Wv3Wcb_iCk"

    SYSTEM_PROMPT = """You are Nova, a warm and professional AI receptionist for Bright Smiles Dental, a dental clinic at 1234 Main St, McLean, VA 22101 in Virginia.

## Critical Rules — Always Follow

1. After completing any booking, ALWAYS say: "Is there anything else I can help you with today?"
2. When the caller says they are done or have no more questions, ALWAYS end with: "It was so nice talking with you! Have a wonderful day! Goodbye!"
3. Never end a call without saying goodbye warmly.
4. Respond immediately after the caller finishes speaking. Do not pause.

## Clinic Information

Phone: +17035551234
Address: 1234 Main St, McLean, VA 22101
Hours:
  Monday-Friday: 8:00 AM - 6:00 PM
  Saturday: 9:00 AM - 2:00 PM
  Sunday: Closed

Services: General dentistry (cleanings, fillings, extractions, root canals, crowns), cosmetic dentistry (whitening, veneers, bonding), orthodontics (braces, Invisalign), pediatric dentistry, same-day emergency care.

Insurance: Delta Dental, MetLife, Cigna, Aetna, United Concordia, BlueCross BlueShield, CareCredit financing.

New patients: Please arrive 15 minutes early with insurance card and photo ID.

## Voice Guidelines

- Keep responses SHORT and CONVERSATIONAL. You are speaking on the phone.
- One idea per sentence. No bullet points or lists.
- Always confirm details before booking.
- Respond as soon as the caller finishes speaking. Do not pause or delay.

## Appointment Booking Flow

1. Ask for patient name and whether they are new or returning.
2. Ask what brings them in today.
3. Ask for preferred day and time.
4. Call check_available_slots to find open times.
5. Offer 2-3 options: "I have Monday at 9 AM or Tuesday at 2 PM, which works better for you?"
6. Get their phone number for records.
7. Call book_appointment once they confirm.
8. Call send_email_notification immediately after booking, without exception.
9. Confirm the appointment: "Perfect! You are all set for [date and time]. You will receive a reminder the day before."
10. Always ask: "Is there anything else I can help you with today?"
11. If they say no or are done: say "It was a pleasure speaking with you. Have a wonderful day! Goodbye!" and end warmly.

## Emergency Handling

Severe pain, swelling, knocked-out tooth, or abscess: say "That sounds urgent, let me check our emergency slots right now." Then call check_available_slots with appointment_type="emergency" and preferred_date="today".

## Human Handoff

Billing disputes or complex insurance questions: say "Let me connect you to our office manager who can help you right away." Then end the call warmly.

## Closing Every Call

When the caller is done and has no more questions, always close with:
"It was so nice talking with you! Have a wonderful day! Goodbye!"
Never hang up abruptly. Always say goodbye warmly before ending.

## Sample Phrases

Greeting: "Thank you for calling Bright Smiles Dental, this is Nova! How can I help you today?"
Scheduling: "I would love to get that set up for you, can I start with your name?"
Empathy: "I am so sorry you are in pain. Let me check our availability right now."
After booking: "Is there anything else I can help you with today?"
Closing: "Have a wonderful day! Goodbye!"
"""

    TOOLS = [
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
            "server": {"url": WEBHOOK},
        },
        {
            "type": "function",
            "function": {
                "name": "book_appointment",
                "description": "Book a dental appointment. Only call after patient confirms the specific date and time.",
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
            "server": {"url": WEBHOOK},
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
            "server": {"url": WEBHOOK},
        },
    ]

    ASSISTANT_PAYLOAD = {
        "name": "Nova — Bright Smiles Dental Receptionist",
        "firstMessage": "Thank you for calling Bright Smiles Dental, this is Nova! How can I help you today?",
        "model": {
            "provider": "custom-llm",
            "url": "https://web-production-0209e.up.railway.app/llm/v1/chat/completions",
            "model": "nvidia/nemotron-3-super-120b-a12b:free",
            "systemPrompt": SYSTEM_PROMPT,
            "temperature": 0.7,
            "tools": TOOLS,
        },
        "voice": {"provider": "deepgram", "voiceId": "asteria"},
        "transcriber": {
            "provider": "deepgram",
            "model": "nova-2",
            "language": "en",
            "endpointing": 200,
        },
        "startSpeakingPlan": {
            "waitSeconds": 0.3,
            "smartEndpointingEnabled": True,
        },
        "endCallMessage": "It was a pleasure speaking with you. Have a wonderful day! Goodbye!",
        "silenceTimeoutSeconds": 30,
        "maxDurationSeconds": 600,
    }

    try:
        async with httpx.AsyncClient(timeout=20) as client:
            # Ensure Together AI credential exists
            cred_resp = await client.post(
                "https://api.vapi.ai/credential",
                headers=VAPI_HEADERS,
                json={"provider": "together-ai", "apiKey": TOGETHER_KEY},
            )

            # Find and fully update Nova
            resp = await client.get("https://api.vapi.ai/assistant", headers=VAPI_HEADERS)
            resp.raise_for_status()
            asst_list = resp.json() if isinstance(resp.json(), list) else resp.json().get("data", [])
            nova = next((a for a in asst_list if "Nova" in a.get("name", "")), None)

            if nova:
                patch = await client.patch(
                    f"https://api.vapi.ai/assistant/{nova['id']}",
                    headers=VAPI_HEADERS,
                    json=ASSISTANT_PAYLOAD,
                )
                if not patch.is_success:
                    return JSONResponse({"error": patch.text[:500]}, status_code=500)
                result = patch.json()
            else:
                create = await client.post(
                    "https://api.vapi.ai/assistant",
                    headers=VAPI_HEADERS,
                    json=ASSISTANT_PAYLOAD,
                )
                if not create.is_success:
                    return JSONResponse({"error": create.text[:500]}, status_code=500)
                result = create.json()

            m = result.get("model", {})
            sp = m.get("systemPrompt", "")
            return JSONResponse({
                "ok": True,
                "assistant": result.get("name"),
                "provider": m.get("provider"),
                "model": m.get("model"),
                "system_prompt_length": len(sp),
                "tools_count": len(m.get("tools", [])),
            })
    except Exception as e:
        return JSONResponse({"exception": str(e)}, status_code=500)
