import os
import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from routers.vapi_webhook import router as vapi_router

app = FastAPI(title="Nova Voice Agent")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(vapi_router)


@app.get("/health")
async def health():
    import os
    return {
        "status": "ok",
        "resend_configured": bool(os.getenv("RESEND_API_KEY", "")),
        "from_email": os.getenv("FROM_EMAIL", "not_set"),
    }


if __name__ == "__main__":
    port = int(os.getenv("PORT", 8000))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=False)
