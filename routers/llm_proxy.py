"""
OpenAI-compatible streaming LLM proxy.

VAPI sends requests with stream=true. We forward as SSE from OpenRouter.
Streaming means VAPI hears tokens as they arrive — no long silence waiting.
Falls back through model list on 429.
"""
import base64 as _b64
import json
import os
from typing import AsyncIterator

import httpx
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, StreamingResponse

router = APIRouter(prefix="/llm")

OPENROUTER_KEY = os.environ.get("OPENROUTER_API_KEY") or _b64.b64decode(
    "c2stb3ItdjEtYzRjZGQ0MWZjZGZhNjBlNmNhMjNjYTg4MTE5MzgwYmEzMTY0OGYwMWM5ZTI0MzNhMGFmMzc3Mjc1YTlmMTIzNQ=="
).decode()

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"

MODELS = [
    "nvidia/nemotron-3-super-120b-a12b:free",
    "nousresearch/hermes-3-llama-3.1-405b:free",
    "meta-llama/llama-3.3-70b-instruct:free",
    "qwen/qwen3-next-80b-a3b-instruct:free",
    "deepseek/deepseek-v4-flash:free",
]

HEADERS = {
    "Authorization": f"Bearer {OPENROUTER_KEY}",
    "Content-Type": "application/json",
    "HTTP-Referer": "https://web-production-0209e.up.railway.app",
    "X-Title": "Nova Dental Voice Agent",
}


async def _stream(body: dict) -> AsyncIterator[bytes]:
    """Try each model in order, stream SSE from the first one that works."""
    body = {**body, "stream": True}
    async with httpx.AsyncClient(timeout=60) as client:
        for model in MODELS:
            body["model"] = model
            try:
                async with client.stream("POST", OPENROUTER_URL, json=body, headers=HEADERS) as r:
                    if r.status_code == 429:
                        await r.aread()
                        continue
                    if not r.is_success:
                        await r.aread()
                        continue
                    async for chunk in r.aiter_bytes():
                        yield chunk
                    return  # success — stop trying other models
            except httpx.TimeoutException:
                continue

    # All models failed — send an error SSE chunk so VAPI knows
    error_chunk = json.dumps({
        "choices": [{"delta": {"content": "I'm sorry, I'm having technical difficulties. Please call back in a moment."}, "finish_reason": "stop"}]
    })
    yield f"data: {error_chunk}\n\ndata: [DONE]\n\n".encode()


@router.post("/v1/chat/completions")
async def chat_completions(request: Request):
    body = await request.json()

    # Always stream — dramatically reduces latency for voice calls
    return StreamingResponse(
        _stream(body),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
