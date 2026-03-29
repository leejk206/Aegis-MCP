from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv
from pydantic import BaseModel, Field


class Settings(BaseModel):
    slack_bot_token: str = Field(..., min_length=1)
    slack_signing_secret: str = Field(..., min_length=1)
    app_port: int = 8000
    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    env_path = Path(__file__).resolve().parents[2] / ".env"
    load_dotenv(dotenv_path=env_path, override=False)
    return Settings(
        slack_bot_token=os.getenv("SLACK_BOT_TOKEN", ""),
        slack_signing_secret=os.getenv("SLACK_SIGNING_SECRET", ""),
        app_port=int(os.getenv("APP_PORT", "8000")),
        openai_api_key=os.getenv("OPENAI_API_KEY", ""),
        openai_model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
    )
