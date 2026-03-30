from __future__ import annotations

import json
from dataclasses import dataclass
from enum import Enum
from typing import TypedDict
from urllib import error, request

from app.core.config import get_settings


class IntentType(str, Enum):
    GENERAL_CONVERSATION = "GENERAL_CONVERSATION"
    DATA_RETRIEVAL = "DATA_RETRIEVAL"
    SECURITY_QUERY = "SECURITY_QUERY"


@dataclass
class IntentClassification:
    intent: IntentType
    query: str


class ContextDocument(TypedDict):
    task_id: str
    title: str
    description: str
    assigned_role: str
    status: str
    payload: str | None


class IntentClassifier:
    def __init__(self) -> None:
        self.settings = get_settings()

    def classify(self, raw_text: str) -> IntentClassification:
        if not self.settings.openai_api_key:
            return self._fallback_classify(raw_text)

        try:
            return self._classify_with_llm(raw_text)
        except (error.URLError, TimeoutError, ValueError, KeyError, json.JSONDecodeError):
            return self._fallback_classify(raw_text)

    def answer_with_context(self, question: str, documents: list[ContextDocument]) -> str:
        if not documents:
            return "참고할 문서가 없어 답변할 수 없습니다."

        if not self.settings.openai_api_key:
            return self._fallback_grounded_answer(question, documents)

        try:
            return self._answer_with_llm_context(question, documents)
        except (error.URLError, TimeoutError, ValueError, KeyError, json.JSONDecodeError):
            return self._fallback_grounded_answer(question, documents)

    def _classify_with_llm(self, raw_text: str) -> IntentClassification:
        system_prompt = (
            "사용자 질문을 DATA_RETRIEVAL, SECURITY_QUERY, GENERAL_CONVERSATION 중 하나로 분류하고 "
            "검색어가 있으면 query에 넣어라. JSON만 출력: "
            '{"intent":"...","query":"..."}'
        )
        payload = {
            "model": self.settings.openai_model,
            "temperature": 0,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": raw_text},
            ],
            "response_format": {"type": "json_object"},
        }
        data = json.dumps(payload).encode("utf-8")
        req = request.Request(
            "https://api.openai.com/v1/chat/completions",
            data=data,
            method="POST",
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.settings.openai_api_key}",
            },
        )
        with request.urlopen(req, timeout=8) as resp:
            resp_body = json.loads(resp.read().decode("utf-8"))

        llm_text = resp_body["choices"][0]["message"]["content"]
        parsed = json.loads(llm_text)
        intent_value = parsed.get("intent", IntentType.GENERAL_CONVERSATION.value)
        query = str(parsed.get("query", "")).strip()
        intent = self._normalize_intent(intent_value)
        return IntentClassification(intent=intent, query=query)

    def _answer_with_llm_context(self, question: str, documents: list[ContextDocument]) -> str:
        system_prompt = (
            "다음 문서 내용만 근거로 한국어로 답하라. "
            "문서에 없는 내용은 절대 추측하지 말고 모르면 '모르겠습니다'라고 답하라."
        )
        context_lines: list[str] = []
        for document in documents:
            context_lines.append(
                f"[{document['task_id']}] {document['title']} | "
                f"역할 {document['assigned_role']} | 상태 {document['status']} | "
                f"설명 {document['description']} | payload {document['payload']}"
            )
        context = "\n".join(context_lines)

        payload = {
            "model": self.settings.openai_model,
            "temperature": 0,
            "messages": [
                {"role": "system", "content": system_prompt},
                {
                    "role": "user",
                    "content": (
                        f"질문: {question}\n"
                        f"문서 컨텍스트:\n{context}\n"
                        "요청: 다음 문서 내용을 바탕으로 사용자의 질문에 답해줘."
                    ),
                },
            ],
        }
        data = json.dumps(payload).encode("utf-8")
        req = request.Request(
            "https://api.openai.com/v1/chat/completions",
            data=data,
            method="POST",
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.settings.openai_api_key}",
            },
        )
        with request.urlopen(req, timeout=12) as resp:
            resp_body = json.loads(resp.read().decode("utf-8"))
        return str(resp_body["choices"][0]["message"]["content"]).strip()

    def _fallback_classify(self, raw_text: str) -> IntentClassification:
        text = raw_text.strip()
        lowered = text.lower()
        if any(signal in lowered for signal in ["검색:", "search:", "조회", "찾아", "문서", "자료"]):
            query = self._extract_query(text)
            return IntentClassification(intent=IntentType.DATA_RETRIEVAL, query=query)
        if any(signal in lowered for signal in ["보안", "권한", "접근", "등급", "mac", "정책"]):
            return IntentClassification(intent=IntentType.SECURITY_QUERY, query="")
        return IntentClassification(intent=IntentType.GENERAL_CONVERSATION, query="")

    def _fallback_grounded_answer(self, question: str, documents: list[ContextDocument]) -> str:
        lines = [
            "LLM 연결이 없어 문서 기반 요약으로 답변합니다.",
            f"질문: {question}",
            "근거 문서:",
        ]
        for document in documents:
            lines.append(
                f"- [{document['task_id']}] {document['title']} "
                f"(role={document['assigned_role']}, status={document['status']}): "
                f"{document['description']} | payload={document['payload']}"
            )
        return "\n".join(lines)

    def _extract_query(self, text: str) -> str:
        if "검색:" in text:
            return text.split("검색:", maxsplit=1)[1].strip()
        lowered = text.lower()
        if "search:" in lowered:
            idx = lowered.index("search:")
            return text[idx + len("search:") :].strip()
        return text

    def _normalize_intent(self, intent_value: str) -> IntentType:
        normalized = intent_value.strip().upper()
        if normalized == IntentType.DATA_RETRIEVAL.value:
            return IntentType.DATA_RETRIEVAL
        if normalized == IntentType.SECURITY_QUERY.value:
            return IntentType.SECURITY_QUERY
        return IntentType.GENERAL_CONVERSATION
