"""
OpenAI-compatible LLM proxy for VAPI custom LLM.

Handles both streaming and non-streaming. Falls back through model list on 429.
On total failure, returns a graceful text response so VAPI doesn't drop the call.
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

FALLBACK_RESPONSE = {
    "id": "fallback",
    "object": "chat.completion",
    "choices": [{
        "index": 0,
        "message": {
            "role": "assistant",
            "content": "I apologize, I'm having a brief technical issue. Could you please repeat that?"
        },
        "finish_reason": "stop"
    }],
    "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
}


async def _call_non_streaming(body: dict) -> dict:
    """Try each model until one responds. Returns OpenAI-format dict."""
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
                continue
            except httpx.TimeoutException:
                continue
    return FALLBACK_RESPONSE


async def _stream_sse(body: dict):
    """Stream SSE from OpenRouter. Converts non-streaming responses to SSE format."""
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

                    # Buffer the response to check if it's SSE or plain JSON
                    raw = b""
                    async for chunk in r.aiter_bytes():
                        raw += chunk

                    text = raw.decode("utf-8", errors="ignore").strip()

                    # If it's already SSE (starts with "data:"), forward as-is
                    if text.startswith("data:"):
                        yield raw
                        return

                    # It's a plain JSON response — convert to SSE format
                    try:
                        data = json.loads(text)
                        # Extract content from non-streaming response
                        content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
                        tool_calls = data.get("choices", [{}])[0].get("message", {}).get("tool_calls")
                        finish_reason = data.get("choices", [{}])[0].get("finish_reason", "stop")

                        chunk_data = {
                            "id": data.get("id", "gen"),
                            "object": "chat.completion.chunk",
                            "choices": [{
                                "index": 0,
                                "delta": {"role": "assistant", "content": content},
                                "finish_reason": None
                            }]
                        }
                        if tool_calls:
                            chunk_data["choices"][0]["delta"]["tool_calls"] = tool_calls

                        yield f"data: {json.dumps(chunk_data)}\n\n".encode()

                        # Final chunk with finish_reason
                        final = {**chunk_data, "choices": [{**chunk_data["choices"][0], "delta": {}, "finish_reason": finish_reason}]}
                        yield f"data: {json.dumps(final)}\n\n".encode()
                        yield b"data: [DONE]\n\n"
                    except Exception:
                        yield f"data: {text}\n\ndata: [DONE]\n\n".encode()
                    return

            except httpx.TimeoutException:
                continue

    # All models failed — send graceful fallback
    fallback_content = "I apologize, I'm having a brief technical issue. Could you please repeat that?"
    chunk = {"id": "fallback", "object": "chat.completion.chunk", "choices": [{"index": 0, "delta": {"role": "assistant", "content": fallback_content}, "finish_reason": "stop"}]}
    yield f"data: {json.dumps(chunk)}\n\ndata: [DONE]\n\n".encode()


@router.post("/v1/chat/completions")
async def chat_completions(request: Request):
    body = await request.json()
    wants_stream = body.get("stream", False)

    if wants_stream:
        return StreamingResponse(
            _stream_sse(body),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )
    else:
        result = await _call_non_streaming(body)
        return JSONResponse(result)
