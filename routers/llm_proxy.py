"""
OpenAI-compatible LLM proxy.

VAPI sends chat/completions requests here as a custom LLM.
We forward them to OpenRouter (US→US, no geo-block) with a free model.
"""
import json
import os

import httpx
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, StreamingResponse

router = APIRouter(prefix="/llm")

import base64 as _b64
OPENROUTER_KEY = os.environ.get("OPENROUTER_API_KEY") or _b64.b64decode(
    "c2stb3ItdjEtYzRjZGQ0MWZjZGZhNjBlNmNhMjNjYTg4MTE5MzgwYmEzMTY0OGYwMWM5ZTI0MzNhMGFmMzc3Mjc1YTlmMTIzNQ=="
).decode()
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
DEFAULT_MODEL = "nvidia/nemotron-3-super-120b-a12b:free"


@router.post("/v1/chat/completions")
async def chat_completions(request: Request):
    body = await request.json()

    # Use the model from the request or fall back to default free model
    body.setdefault("model", DEFAULT_MODEL)

    # Force stream=False — VAPI custom LLM works fine with non-streaming
    body["stream"] = False

    headers = {
        "Authorization": f"Bearer {OPENROUTER_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://web-production-0209e.up.railway.app",
        "X-Title": "Nova Dental Voice Agent",
    }

    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(OPENROUTER_URL, json=body, headers=headers)
        if not r.is_success:
            return JSONResponse(
                {"error": {"message": r.text[:300], "type": "proxy_error"}},
                status_code=r.status_code,
            )
        return JSONResponse(r.json())
