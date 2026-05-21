"""
OpenAI-compatible LLM proxy for VAPI custom LLM.

Handles the full tool-calling loop internally:
  1. VAPI sends conversation to us
  2. We call OpenRouter (with tools defined)
  3. If model returns tool_calls → we execute them directly → loop back
  4. When model returns text → stream it back to VAPI

This way VAPI never needs to route tool calls; we handle everything.
"""
import base64 as _b64
import json
import os

import httpx
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, StreamingResponse

from tools.check_available_slots import execute_check_available_slots
from tools.book_appointment import execute_book_appointment
from tools.send_email_notification import execute_send_email_notification

router = APIRouter(prefix="/llm")

OPENROUTER_KEY = os.environ.get("OPENROUTER_API_KEY") or _b64.b64decode(
    "c2stb3ItdjEtYzRjZGQ0MWZjZGZhNjBlNmNhMjNjYTg4MTE5MzgwYmEzMTY0OGYwMWM5ZTI0MzNhMGFmMzc3Mjc1YTlmMTIzNQ=="
).decode()

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"

MODELS = [
    "openai/gpt-oss-120b:free",
    "openai/gpt-oss-20b:free",
    "deepseek/deepseek-v4-flash:free",
    "meta-llama/llama-3.3-70b-instruct:free",
    "nousresearch/hermes-3-llama-3.1-405b:free",
    "qwen/qwen3-next-80b-a3b-instruct:free",
    "nvidia/nemotron-3-super-120b-a12b:free",
    "minimax/minimax-m2.5:free",
]

OR_HEADERS = {
    "Authorization": f"Bearer {OPENROUTER_KEY}",
    "Content-Type": "application/json",
    "HTTP-Referer": "https://web-production-0209e.up.railway.app",
    "X-Title": "Nova Dental Voice Agent",
}

TOOL_EXECUTORS = {
    "check_available_slots": execute_check_available_slots,
    "book_appointment": execute_book_appointment,
    "send_email_notification": execute_send_email_notification,
}

TOOL_DEFINITIONS = [
    {
        "type": "function",
        "function": {
            "name": "check_available_slots",
            "description": "Check available appointment slots on the dental clinic calendar. Call this when a patient wants to book.",
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
                    "appointment_datetime": {"type": "string"},
                    "duration_minutes": {"type": "integer"},
                    "appointment_type": {"type": "string"},
                    "is_new_patient": {"type": "boolean"},
                    "notes": {"type": "string"},
                },
                "required": ["patient_name", "patient_phone", "appointment_datetime", "appointment_type"],
            },
        },
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
    },
]


def _sse_text(content: str) -> bytes:
    """Wrap a text string as SSE chunks without another LLM call."""
    chunk = {"id": "chatcmpl-0", "object": "chat.completion.chunk",
             "choices": [{"index": 0, "delta": {"role": "assistant", "content": content}, "finish_reason": None}]}
    stop = {"id": "chatcmpl-0", "object": "chat.completion.chunk",
            "choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}]}
    return (
        f"data: {json.dumps(chunk)}\n\n"
        f"data: {json.dumps(stop)}\n\n"
        "data: [DONE]\n\n"
    ).encode()


async def _call_openrouter(messages: list) -> dict | None:
    """Call OpenRouter non-streaming with tool support. Returns response dict or None."""
    payload = {
        "messages": messages,
        "tools": TOOL_DEFINITIONS,
        "tool_choice": "auto",
        "stream": False,
    }
    async with httpx.AsyncClient(timeout=30) as client:
        for model in MODELS:
            payload["model"] = model
            try:
                r = await client.post(OPENROUTER_URL, json=payload, headers=OR_HEADERS)
                if r.is_success:
                    return r.json()
                continue
            except (httpx.TimeoutException, httpx.RequestError):
                continue
    return None


async def _run_tool_loop(messages: list):
    """Execute the tool-calling loop, then stream the final response."""
    for _ in range(5):
        response = await _call_openrouter(messages)
        if response is None:
            break

        choice = response.get("choices", [{}])[0]
        message = choice.get("message", {})
        finish_reason = choice.get("finish_reason", "stop")
        tool_calls = message.get("tool_calls") or []

        if not tool_calls or finish_reason != "tool_calls":
            content = (message.get("content") or "").strip()
            if not content:
                content = "I'm sorry, I didn't catch that. Could you please repeat?"
            yield _sse_text(content)
            return

        # Execute tool calls
        messages.append({"role": "assistant", "content": message.get("content") or "", "tool_calls": tool_calls})

        for tc in tool_calls:
            fn_name = tc.get("function", {}).get("name", "")
            fn_args_str = tc.get("function", {}).get("arguments", "{}")
            tc_id = tc.get("id", "tc_0")
            executor = TOOL_EXECUTORS.get(fn_name)
            if executor:
                try:
                    args = json.loads(fn_args_str)
                    result = await executor(args)
                    tool_content = json.dumps(result)
                except Exception as e:
                    tool_content = json.dumps({"error": str(e)})
            else:
                tool_content = json.dumps({"error": f"Unknown tool: {fn_name}"})
            messages.append({"role": "tool", "tool_call_id": tc_id, "content": tool_content})

    # Loop exhausted after tool calls — ask LLM one final time for the text response
    final = await _call_openrouter(messages)
    if final:
        content = (final.get("choices", [{}])[0].get("message", {}).get("content") or "").strip()
        if content:
            yield _sse_text(content)
            return

    yield _sse_text("I'm sorry, I'm having trouble connecting right now. Please try again in a moment.")


@router.post("/v1/chat/completions")
async def chat_completions(request: Request):
    body = await request.json()
    messages = body.get("messages", [])

    return StreamingResponse(
        _run_tool_loop(messages),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
