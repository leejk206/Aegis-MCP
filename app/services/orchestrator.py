from __future__ import annotations

from app.services.dp_filter import DPFilter
from app.services.mac_service import MACService


class AegisOrchestrator:
    def process_slack_message(self, user_id: str, raw_text: str) -> str:
        dp_filter = DPFilter()
        mac_service = MACService()
        confidential_keywords: list[str] = ["ProjectX", "내부감사", "Q3매출"]
        print(f"[INCOMING] User: {user_id} | Raw: '{raw_text}'", flush=True)

        masked_input = dp_filter.mask_pii(raw_text)
        stripped_input = masked_input.strip()

        if stripped_input.startswith("검색:"):
            query = stripped_input.split("검색:", maxsplit=1)[1].strip()
            print(f"[SEARCH] Query: '{query}' by User: {user_id}", flush=True)
            user_clearance = mac_service.get_user_clearance(user_id)
            accessible_documents = mac_service.get_accessible_documents(user_id)

            if not query:
                return (
                    f"사용자 등급: {user_clearance}\n"
                    "검색 키워드를 입력해 주세요. 예) 검색: 감사"
                )

            lowered_keyword = query.lower()
            results = [
                document
                for document in accessible_documents
                if lowered_keyword in document["title"].lower()
                or lowered_keyword in document["content"].lower()
            ]

            if not results:
                return (
                    f"사용자 등급: {user_clearance}\n"
                    f"접근 가능한 문서({len(accessible_documents)}건)에서 "
                    f"'{query}' 검색 결과가 없습니다."
                )

            lines = [f"사용자 등급: {user_clearance}", "검색 결과:"]
            for document in results:
                lines.append(
                    f"- [{document['id']}] {document['title']} "
                    f"(등급 {document['required_clearance']}): {document['content']}"
                )
            response_text = "\n".join(lines)
            response_text = dp_filter.mask_confidential(response_text, confidential_keywords)
            response_text = dp_filter.mask_pii(response_text)
            print(f"[RESULT] Found {len(results)} docs | Masking applied.", flush=True)
            return response_text

        masked_text = dp_filter.mask_confidential(masked_input, confidential_keywords)
        return masked_text
