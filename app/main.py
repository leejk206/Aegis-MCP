from __future__ import annotations

import uvicorn
from fastapi import FastAPI

from app.api.endpoints import router as api_router
from app.core.config import get_settings
from app.db.init_db import init_db

app = FastAPI(title="Aegis-MCP")
app.include_router(api_router)


@app.on_event("startup")
async def log_openai_key_status() -> None:
    init_db()
    settings = get_settings()
    if settings.openai_api_key:
        print(
            f"API Key loaded successfully ({settings.openai_api_key[:4]}****)",
            flush=True,
        )
    else:
        print("OPENAI_API_KEY is empty. LLM features will use fallback.", flush=True)


@app.get("/health")
async def health_check() -> dict[str, str]:
    return {"status": "ok"}


if __name__ == "__main__":
    settings = get_settings()
    uvicorn.run("app.main:app", host="0.0.0.0", port=settings.app_port, reload=True)
