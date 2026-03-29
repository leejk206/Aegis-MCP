from __future__ import annotations

import re

from slack_sdk import WebClient

from app.core.config import get_settings
from app.schemas.slack import SlackMentionEvent
from app.services.orchestrator import AegisOrchestrator


def _get_slack_client() -> WebClient:
    settings = get_settings()
    return WebClient(token=settings.slack_bot_token)


def reply_app_mention(event: SlackMentionEvent) -> None:
    client = _get_slack_client()
    thread_ts = event.thread_ts or event.ts
    raw_text = event.text
    text_without_mentions = re.sub(r"<@[A-Z0-9]+>", "", raw_text).strip()
    print(f"[SLACK] Mention received | User: {event.user} | Text: '{text_without_mentions}'", flush=True)

    orchestrator = AegisOrchestrator()
    filtered_text = orchestrator.process_slack_message(
        user_id=event.user,
        raw_text=text_without_mentions,
    )
    message_text = (
        "Aegis-MCP 1차 필터 통과 완료.\n"
        f"보안 처리된 텍스트: {filtered_text}"
    )

    client.chat_postMessage(
        channel=event.channel,
        text=message_text,
        thread_ts=thread_ts,
    )
