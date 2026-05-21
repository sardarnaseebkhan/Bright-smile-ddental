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


@router.post("/admin/switch-to-gemini")
async def switch_to_gemini():
    """One-time endpoint: patches the VAPI assistant to use Google Gemini 2.0 Flash."""
    async with httpx.AsyncClient(timeout=20) as client:
        resp = await client.get("https://api.vapi.ai/assistant", headers=VAPI_HEADERS)
        resp.raise_for_status()
        asst_list = resp.json() if isinstance(resp.json(), list) else resp.json().get("data", [])
        nova = next((a for a in asst_list if "Nova" in a.get("name", "")), None)
        if not nova:
            return JSONResponse({"error": "No Nova assistant found"}, status_code=404)

        old_model = nova.get("model", {})
        patch = await client.patch(
            f"https://api.vapi.ai/assistant/{nova['id']}",
            headers=VAPI_HEADERS,
            json={
                "model": {
                    "provider": "google",
                    "model": "gemini-2.0-flash",
                    "systemPrompt": old_model.get("systemPrompt", ""),
                    "temperature": 0.7,
                    "tools": old_model.get("tools", []),
                }
            },
        )
        patch.raise_for_status()
        m = patch.json().get("model", {})
        return JSONResponse({"updated": True, "provider": m.get("provider"), "model": m.get("model")})
