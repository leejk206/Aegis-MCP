from __future__ import annotations

from typing import Any

from pydantic import BaseModel


class SlackEventPayload(BaseModel):
    type: str
    challenge: str | None = None
    event: dict[str, Any] | None = None


class SlackMentionEvent(BaseModel):
    type: str
    user: str
    channel: str
    ts: str | None = None
    thread_ts: str | None = None
