from __future__ import annotations

from sqlalchemy import select

from app.core.database import Base, SessionLocal, engine
from app.models.document import Document
from app.models.user import User

MOCK_USERS: dict[str, int] = {
    "U_LJK91": 4,
    "U_ANALYST_1": 1,
    "U_ANALYST_2": 2,
    "U_MANAGER_1": 3,
    "U0APFDRJ4UD": 4,
}

MOCK_DOCUMENTS: list[dict[str, str | int]] = [
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


def init_db() -> None:
    Base.metadata.create_all(bind=engine)

    with SessionLocal() as db:
        users_exist = db.execute(select(User.slack_id).limit(1)).first() is not None
        documents_exist = db.execute(select(Document.document_id).limit(1)).first() is not None

        if not users_exist:
            users = [
                User(slack_id=slack_id, clearance_level=clearance_level)
                for slack_id, clearance_level in MOCK_USERS.items()
            ]
            db.add_all(users)

        if not documents_exist:
            documents = [
                Document(
                    document_id=document["id"],
                    title=document["title"],
                    content=document["content"],
                    required_clearance=document["required_clearance"],
                )
                for document in MOCK_DOCUMENTS
            ]
            db.add_all(documents)

        if not users_exist or not documents_exist:
            db.commit()
