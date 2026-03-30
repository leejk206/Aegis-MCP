from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core import database
from app.core.database import Base
from app.models.document import Document
from app.models.user import User
from app.services.orchestrator import AegisOrchestrator


@pytest.fixture()
def setup_in_memory_db(monkeypatch: pytest.MonkeyPatch) -> None:
    test_engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    testing_session_local = sessionmaker(
        autocommit=False,
        autoflush=False,
        bind=test_engine,
    )
    Base.metadata.create_all(bind=test_engine)
    monkeypatch.setattr(database, "SessionLocal", testing_session_local)

    with testing_session_local() as db:
        db.add_all(
            [
                User(slack_id="U_LEVEL4", clearance_level=4),
                User(slack_id="U_LEVEL1", clearance_level=1),
            ]
        )
        db.add_all(
            [
                Document(
                    document_id="DOC-004",
                    title="ProjectX 마스터 플랜",
                    content="ProjectX 핵심 로드맵 및 외부 공유 금지 항목",
                    required_clearance=4,
                ),
                Document(
                    document_id="DOC-001",
                    title="사내 공지",
                    content="일반 공지 사항",
                    required_clearance=1,
                ),
            ]
        )
        db.commit()

    yield

    Base.metadata.drop_all(bind=test_engine)


def test_mac_clearance_allow(setup_in_memory_db: None) -> None:
    orchestrator = AegisOrchestrator()
    orchestrator.intent_classifier.settings.openai_api_key = ""

    result = orchestrator.process_slack_message("U_LEVEL4", "검색: ProjectX")

    assert "RAG 답변" in result
    assert "[MASKED_CONFIDENTIAL]" in result


def test_mac_clearance_deny(setup_in_memory_db: None) -> None:
    orchestrator = AegisOrchestrator()
    orchestrator.intent_classifier.settings.openai_api_key = ""

    result = orchestrator.process_slack_message("U_LEVEL1", "검색: ProjectX")

    assert "검색 결과가 없습니다." in result
    assert "RAG 답변" not in result
