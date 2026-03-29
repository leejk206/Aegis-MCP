from __future__ import annotations

from fastapi import Header, HTTPException, Request, status
from slack_sdk.signature import SignatureVerifier

from app.core.config import get_settings


def _build_signature_verifier() -> SignatureVerifier:
    settings = get_settings()
    return SignatureVerifier(signing_secret=settings.slack_signing_secret)


async def verify_slack_request(
    request: Request,
    x_slack_request_timestamp: str = Header(default="", alias="X-Slack-Request-Timestamp"),
    x_slack_signature: str = Header(default="", alias="X-Slack-Signature"),
) -> bytes:
    body = await request.body()
    verifier = _build_signature_verifier()

    is_valid = verifier.is_valid(
        body=body,
        timestamp=x_slack_request_timestamp,
        signature=x_slack_signature,
    )
    if not is_valid:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid Slack signature",
        )

    return body
