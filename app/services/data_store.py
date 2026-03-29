from __future__ import annotations

from typing import TypedDict


class MockDocument(TypedDict):
    id: str
    title: str
    content: str
    required_clearance: int


# Slack user_id -> clearance level (1 ~ 4)
MOCK_USERS: dict[str, int] = {
    "U_LJK91": 4,
    "U_ANALYST_1": 1,
    "U_ANALYST_2": 2,
    "U_MANAGER_1": 3,
    "U0APFDRJ4UD": 4,
}


MOCK_DOCUMENTS: list[MockDocument] = [
    {
        "id": "DOC-001",
        "title": "사내 공지",
        "content": "일반 공지 사항 및 근무 일정 안내",
        "required_clearance": 1,
    },
    {
        "id": "DOC-002",
        "title": "내부감사 일정",
        "content": "내부감사 준비 회의는 4월 2일 14:00 진행",
        "required_clearance": 2,
    },
    {
        "id": "DOC-003",
        "title": "Q3매출 분석",
        "content": "Q3매출 잠정 수치와 지역별 원인 분석",
        "required_clearance": 3,
    },
    {
        "id": "DOC-004",
        "title": "ProjectX 마스터 플랜",
        "content": "ProjectX 핵심 로드맵 및 외부 공유 금지 항목",
        "required_clearance": 4,
    },
]
