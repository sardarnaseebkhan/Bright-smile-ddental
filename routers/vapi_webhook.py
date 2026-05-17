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

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from tools.book_appointment import execute_book_appointment
from tools.check_available_slots import execute_check_available_slots
from tools.send_email_notification import execute_send_email_notification
from utils.logging import get_logger

router = APIRouter(prefix="/vapi")
logger = get_logger(__name__)

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

    # VAPI sends other event types (status-update, end-of-call-report, etc.)
    # Return 200 with empty body to acknowledge
    return JSONResponse({})
