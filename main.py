import os
import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

import db
from routers.vapi_webhook import router as vapi_router
from routers.llm_proxy import router as llm_router
from routers.admin import router as admin_router

app = FastAPI(title="Nova Voice Agent")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(vapi_router)
app.include_router(llm_router)
app.include_router(admin_router)


@app.on_event("startup")
async def startup():
    db.init_db()


@app.get("/health")
async def health():
    key = os.environ.get("RESEND_API_KEY") or "re_KFm69fGM_JynaMvZpnrqRxq44ods1z3sa"
    businesses = db.get_all()
    return {
        "status": "ok",
        "version": "multi-tenant-v7",
        "businesses": len(businesses),
        "resend_configured": key.startswith("re_"),
        "from_email": os.environ.get("FROM_EMAIL") or "onboarding@resend.dev",
    }


if __name__ == "__main__":
    port = int(os.getenv("PORT", 8000))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=False)
