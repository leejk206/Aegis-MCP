from __future__ import annotations

import uvicorn
from fastapi import FastAPI

from app.api.endpoints import router as api_router
from app.core.config import get_settings

app = FastAPI(title="Aegis-MCP")
app.include_router(api_router)


@app.get("/health")
async def health_check() -> dict[str, str]:
    return {"status": "ok"}


if __name__ == "__main__":
    settings = get_settings()
    uvicorn.run("app.main:app", host="0.0.0.0", port=settings.app_port, reload=True)
