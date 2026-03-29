from __future__ import annotations

import os
from functools import lru_cache

from dotenv import load_dotenv
from pydantic import BaseModel, Field


class Settings(BaseModel):
    slack_bot_token: str = Field(..., min_length=1)
    slack_signing_secret: str = Field(..., min_length=1)
    app_port: int = 8000


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    load_dotenv()
    return Settings(
        slack_bot_token=os.getenv("SLACK_BOT_TOKEN", ""),
        slack_signing_secret=os.getenv("SLACK_SIGNING_SECRET", ""),
        app_port=int(os.getenv("APP_PORT", "8000")),
    )
