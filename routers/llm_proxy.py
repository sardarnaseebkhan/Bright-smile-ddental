"""
OpenAI-compatible LLM proxy.

VAPI sends chat/completions requests here as a custom LLM.
We forward to OpenRouter (Railway US → OpenRouter US, no geo-block).
Retries through a fallback list if the primary model is rate-limited.
"""
import base64 as _b64
import os

import httpx
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

router = APIRouter(prefix="/llm")

OPENROUTER_KEY = os.environ.get("OPENROUTER_API_KEY") or _b64.b64decode(
    "c2stb3ItdjEtYzRjZGQ0MWZjZGZhNjBlNmNhMjNjYTg4MTE5MzgwYmEzMTY0OGYwMWM5ZTI0MzNhMGFmMzc3Mjc1YTlmMTIzNQ=="
).decode()

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"

# Ordered fallback list — all support tool calling, all free
MODELS = [
    "nvidia/nemotron-3-super-120b-a12b:free",
    "nousresearch/hermes-3-llama-3.1-405b:free",
    "meta-llama/llama-3.3-70b-instruct:free",
    "qwen/qwen3-next-80b-a3b-instruct:free",
    "deepseek/deepseek-v4-flash:free",
]


@router.post("/v1/chat/completions")
async def chat_completions(request: Request):
    body = await request.json()
    body["stream"] = False  # VAPI custom LLM works with non-streaming

    headers = {
        "Authorization": f"Bearer {OPENROUTER_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://web-production-0209e.up.railway.app",
        "X-Title": "Nova Dental Voice Agent",
    }

    # Try each model in order until one works
    last_error = "all models failed"
    async with httpx.AsyncClient(timeout=45) as client:
        for model in MODELS:
            body["model"] = model
            try:
                r = await client.post(OPENROUTER_URL, json=body, headers=headers)
                if r.is_success:
                    return JSONResponse(r.json())
                err_body = r.json() if r.headers.get("content-type", "").startswith("application/json") else {}
                err_msg = err_body.get("error", {}).get("message", r.text[:100])
                # 429 = rate limited, try next model
                if r.status_code == 429:
                    last_error = f"{model} rate-limited: {err_msg[:80]}"
                    continue
                # Other errors — still try next model
                last_error = f"{model} error {r.status_code}: {err_msg[:80]}"
                continue
            except httpx.TimeoutException:
                last_error = f"{model} timed out"
                continue

    return JSONResponse(
        {"error": {"message": last_error, "type": "proxy_error"}},
        status_code=503,
    )
