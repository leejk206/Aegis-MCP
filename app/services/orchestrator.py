from __future__ import annotations

import re

from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.document import Document
from app.services.dp_filter import DPFilter
from app.services.intent_classifier import ContextDocument, IntentClassifier, IntentType
from app.services.mac_service import MACService


class AegisOrchestrator:
    CONFIDENTIAL_KEYWORDS: list[str] = ["ProjectX", "내부감사", "Q3매출"]

    def __init__(self) -> None:
        self.dp_filter = DPFilter()
        self.mac_service = MACService()
        self.intent_classifier = IntentClassifier()

    def process_slack_message(self, user_id: str, raw_text: str) -> str:
        db_gen = get_db()
        db = next(db_gen)
        print(f"[INCOMING] User: {user_id} | Raw: '{raw_text}'", flush=True)
        try:
            classification = self.intent_classifier.classify(raw_text)
            intent = classification.intent
            print(f"[INTENT] User: {user_id} | Intent: {intent.value}", flush=True)

            if intent == IntentType.DATA_RETRIEVAL:
                response_text = self._handle_data_retrieval(
                    user_id=user_id,
                    question=raw_text,
                    query=classification.query,
                    db=db,
                )
            elif intent == IntentType.SECURITY_QUERY:
                response_text = self._handle_security_query(user_id=user_id, db=db)
            else:
                response_text = self._handle_general_conversation(raw_text)

            print("[OUTPUT] Applying final masking guardrail.", flush=True)
            return self._format_output(response_text)
        finally:
            try:
                next(db_gen)
            except StopIteration:
                pass

    def _handle_data_retrieval(
        self,
        user_id: str,
        question: str,
        query: str,
        db: Session,
    ) -> str:
        print(f"[SEARCH] Query: '{query}' by User: {user_id}", flush=True)

        user_clearance = self.mac_service.get_user_clearance(user_id, db)
        accessible_documents = self.mac_service.get_accessible_documents(user_id, db)

        if not query:
            return (
                f"사용자 등급: {user_clearance}\n"
                "검색 키워드를 입력해 주세요. 예) 검색: 감사"
            )

        lowered_query = query.lower()
        results = self._search_documents(accessible_documents, lowered_query)

        if not results:
            return (
                f"사용자 등급: {user_clearance}\n"
                f"접근 가능한 문서({len(accessible_documents)}건)에서 "
                f"'{query}' 검색 결과가 없습니다."
            )

        print(f"[RAG] Building context from {len(results)} documents.", flush=True)
        rag_answer = self.intent_classifier.answer_with_context(
            question=question,
            documents=[self._document_to_mock(document) for document in results],
        )
        print(f"[RESULT] Found {len(results)} docs | Masking applied.", flush=True)
        return f"사용자 등급: {user_clearance}\nRAG 답변:\n{rag_answer}"

    def _handle_security_query(self, user_id: str, db: Session) -> str:
        clearance = self.mac_service.get_user_clearance(user_id, db)
        return (
            f"현재 사용자 보안 등급은 {clearance}입니다.\n"
            "MAC 정책상 본인 등급 이하 문서만 조회할 수 있습니다."
        )

    def _handle_general_conversation(self, raw_text: str) -> str:
        return (
            "일반 대화로 분류되었습니다. "
            "데이터 조회가 필요하면 '검색: [키워드]' 형식으로 요청해 주세요.\n"
            f"입력 메시지: {raw_text}"
        )

    def _search_documents(
        self,
        accessible_documents: list[Document],
        lowered_query: str,
    ) -> list[Document]:
        query_tokens = self._query_tokens(lowered_query)
        if not query_tokens:
            query_tokens = [lowered_query]

        return [
            document
            for document in accessible_documents
            if self._matches_document(document, lowered_query, query_tokens)
        ]

    def _matches_document(
        self,
        document: Document,
        lowered_query: str,
        query_tokens: list[str],
    ) -> bool:
        searchable_text = f"{document.title} {document.content}".lower()
        if lowered_query in searchable_text:
            return True
        return any(token in searchable_text for token in query_tokens)

    def _query_tokens(self, lowered_query: str) -> list[str]:
        tokens = re.findall(r"[a-zA-Z0-9가-힣]+", lowered_query)
        stopwords = {"검색", "요약", "해줘", "해주세요", "문서", "자료", "알려줘"}
        return [token for token in tokens if len(token) >= 2 and token not in stopwords]

    def _format_output(self, response_text: str) -> str:
        masked_text = self.dp_filter.mask_confidential(
            response_text,
            self.CONFIDENTIAL_KEYWORDS,
        )
        masked_text = self.dp_filter.mask_pii(masked_text)
        return masked_text

    def _document_to_mock(self, document: Document) -> ContextDocument:
        return {
            "id": document.document_id,
            "title": document.title,
            "content": document.content,
            "required_clearance": document.required_clearance,
        }
