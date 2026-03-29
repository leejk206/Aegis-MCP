from __future__ import annotations

import json

from fastapi import APIRouter, Depends

from app.schemas.slack import SlackEventPayload, SlackMentionEvent
from app.services.slack_events import reply_app_mention
from app.services.slack_security import verify_slack_request

router = APIRouter()


@router.post("/slack/events")
async def handle_slack_events(body: bytes = Depends(verify_slack_request)) -> dict[str, str | bool]:
    payload_dict = json.loads(body.decode("utf-8"))
    payload = SlackEventPayload.model_validate(payload_dict)

    if payload.type == "url_verification" and payload.challenge:
        return {"challenge": payload.challenge}

    if payload.type == "event_callback" and payload.event:
        if payload.event.get("type") == "app_mention":
            mention_event = SlackMentionEvent.model_validate(payload.event)
            reply_app_mention(mention_event)
        return {"ok": True}

    return {"ok": True}
