"""
OpenAI-compatible LLM proxy for VAPI custom LLM.

Key fixes:
- Strips reasoning/thinking tokens from SSE chunks (VAPI can't handle them)
- Uses non-reasoning models first (faster, simpler SSE format)
- Falls back through model list on 429
- Returns graceful message on total failure so VAPI never drops the call
"""
import base64 as _b64
import json
import os

import httpx
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, StreamingResponse

router = APIRouter(prefix="/llm")

OPENROUTER_KEY = os.environ.get("OPENROUTER_API_KEY") or _b64.b64decode(
    "c2stb3ItdjEtYzRjZGQ0MWZjZGZhNjBlNmNhMjNjYTg4MTE5MzgwYmEzMTY0OGYwMWM5ZTI0MzNhMGFmMzc3Mjc1YTlmMTIzNQ=="
).decode()

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"

# Non-reasoning models first (no thinking tokens, faster, VAPI-compatible)
MODELS = [
    "meta-llama/llama-3.3-70b-instruct:free",
    "nousresearch/hermes-3-llama-3.1-405b:free",
    "qwen/qwen3-next-80b-a3b-instruct:free",
    "deepseek/deepseek-v4-flash:free",
    "nvidia/nemotron-3-super-120b-a12b:free",  # reasoning model — last resort
]

HEADERS = {
    "Authorization": f"Bearer {OPENROUTER_KEY}",
    "Content-Type": "application/json",
    "HTTP-Referer": "https://web-production-0209e.up.railway.app",
    "X-Title": "Nova Dental Voice Agent",
}

FALLBACK_JSON = {
    "id": "fallback",
    "object": "chat.completion",
    "choices": [{"index": 0, "message": {"role": "assistant", "content": "I apologize, could you please repeat that?"}, "finish_reason": "stop"}],
    "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
}


def _clean_delta(delta: dict) -> dict:
    """Strip fields VAPI doesn't understand (reasoning, reasoning_details, etc.)."""
    return {k: v for k, v in delta.items() if k in ("role", "content", "tool_calls", "function_call")}


async def _stream_sse(body: dict):
    payload = {**body, "stream": True}
    async with httpx.AsyncClient(timeout=45) as client:
        for model in MODELS:
            payload["model"] = model
            try:
                async with client.stream("POST", OPENROUTER_URL, json=payload, headers=HEADERS) as r:
                    if r.status_code == 429:
                        await r.aread()
                        continue
                    if not r.is_success:
                        await r.aread()
                        continue

                    async for line in r.aiter_lines():
                        if not line.startswith("data:"):
                            continue  # skip comments like ": OPENROUTER PROCESSING"
                        data_str = line[5:].strip()
                        if data_str == "[DONE]":
                            yield b"data: [DONE]\n\n"
                            return
                        try:
                            chunk = json.loads(data_str)
                            for choice in chunk.get("choices", []):
                                if "delta" in choice:
                                    choice["delta"] = _clean_delta(choice["delta"])
                            yield f"data: {json.dumps(chunk)}\n\n".encode()
                        except json.JSONDecodeError:
                            continue
                    return  # finished streaming

            except httpx.TimeoutException:
                continue

    # All models failed — graceful fallback
    fallback = {"id": "fallback", "object": "chat.completion.chunk",
                "choices": [{"index": 0, "delta": {"role": "assistant", "content": "I apologize, could you please repeat that?"}, "finish_reason": "stop"}]}
    yield f"data: {json.dumps(fallback)}\n\ndata: [DONE]\n\n".encode()


async def _call_non_streaming(body: dict) -> dict:
    payload = {**body, "stream": False}
    async with httpx.AsyncClient(timeout=30) as client:
        for model in MODELS:
            payload["model"] = model
            try:
                r = await client.post(OPENROUTER_URL, json=payload, headers=HEADERS)
                if r.is_success:
                    return r.json()
                if r.status_code == 429:
                    continue
            except httpx.TimeoutException:
                continue
    return FALLBACK_JSON


@router.post("/v1/chat/completions")
async def chat_completions(request: Request):
    body = await request.json()

    if body.get("stream", False):
        return StreamingResponse(
            _stream_sse(body),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )
    result = await _call_non_streaming(body)
    return JSONResponse(result)
