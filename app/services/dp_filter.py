from __future__ import annotations

import re


class DPFilter:
    EMAIL_PATTERN = re.compile(r"\b[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}\b")
    KR_MOBILE_PATTERN = re.compile(r"01[0-9][-\s]?\d{3,4}[-\s]?\d{4}")
    RRN_PATTERN = re.compile(r"\b\d{6}-?[1-4]\d{6}\b")

    def mask_pii(self, text: str) -> str:
        masked_text = self.EMAIL_PATTERN.sub("[MASKED_PII]", text)
        masked_text = self.KR_MOBILE_PATTERN.sub("[MASKED_PII]", masked_text)
        masked_text = self.RRN_PATTERN.sub("[MASKED_PII]", masked_text)
        return masked_text

    def mask_confidential(self, text: str, keywords: list[str]) -> str:
        masked_text = text
        for keyword in keywords:
            if keyword:
                masked_text = masked_text.replace(keyword, "[MASKED_CONFIDENTIAL]")
        return masked_text

