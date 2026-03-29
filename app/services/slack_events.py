from __future__ import annotations

from slack_sdk import WebClient

from app.core.config import get_settings
from app.schemas.slack import SlackMentionEvent


def _get_slack_client() -> WebClient:
    settings = get_settings()
    return WebClient(token=settings.slack_bot_token)


def reply_app_mention(event: SlackMentionEvent) -> None:
    client = _get_slack_client()
    thread_ts = event.thread_ts or event.ts
    message_text = f"Aegis-MCP 게이트웨이에 연결되었습니다. (User ID: {event.user})"

    client.chat_postMessage(
        channel=event.channel,
        text=message_text,
        thread_ts=thread_ts,
    )
