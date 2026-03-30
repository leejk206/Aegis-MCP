from __future__ import annotations

import pytest
from unittest.mock import patch
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core import database
from app.core.database import Base
from app.models.task import Task
from app.models.user import User
from app.services.intent_classifier import IntentClassification, IntentClassifier, IntentType
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
                User(slack_id="U_BOSS", clearance_level=4),
                User(slack_id="U_SECRETARY", clearance_level=3),
                User(slack_id="U_SUPERVISOR", clearance_level=2),
                User(slack_id="U_WORKER", clearance_level=1),
            ]
        )
        db.add_all(
            [
                Task(
                    task_id="T-001",
                    title="스마트 컨트랙트 개발 총괄",
                    description="신규 ERC20 토큰 컨트랙트 개발 및 보안 감사 진행",
                    assigned_role="SUPERVISOR",
                    status="IN_PROGRESS",
                    payload=None,
                ),
                Task(
                    task_id="T-002",
                    title="ERC20 기본 컨트랙트 구현",
                    description="OpenZeppelin을 활용한 기본 코드 작성",
                    assigned_role="WORKER",
                    status="COMPLETED",
                    payload="pragma solidity ^0.8.0;\nimport '@openzeppelin/contracts/token/ERC20/ERC20.sol';\ncontract AegisToken is ERC20 { ... }",
                ),
                Task(
                    task_id="T-003",
                    title="Reentrancy 취약점 분석",
                    description="T-002 코드의 재진입 공격 취약점 점검",
                    assigned_role="WORKER",
                    status="REVIEW",
                    payload="분석 결과 특이사항 없음. 검토 요망.",
                ),
                Task(
                    task_id="T-004",
                    title="최종 보안 보고서 작성",
                    description="개발 및 감사 완료 후 Boss에게 보고할 최종 요약본 작성",
                    assigned_role="SECRETARY",
                    status="PENDING",
                    payload=None,
                ),
            ]
        )
        db.commit()

    yield

    Base.metadata.drop_all(bind=test_engine)


def test_agent_boss_access(setup_in_memory_db: None) -> None:
    orchestrator = AegisOrchestrator()

    def fake_answer_with_context(question: str, documents: list[dict[str, str | None]]) -> str:
        lines = [f"질문: {question}", "조회 작업:"]
        for task in documents:
            lines.append(
                f"- [{task['task_id']}] {task['title']} / {task['assigned_role']} / "
                f"{task['status']} / payload={task['payload']}"
            )
        return "\n".join(lines)

    with patch.object(
        IntentClassifier,
        "classify",
        return_value=IntentClassification(
            intent=IntentType.DATA_RETRIEVAL,
            query="스마트 컨트랙트",
        ),
    ), patch.object(
        IntentClassifier,
        "answer_with_context",
        side_effect=fake_answer_with_context,
    ) as mocked_answer:
        result = orchestrator.process_slack_message("U_BOSS", "검색: 스마트 컨트랙트")

    assert "RAG 답변" in result
    assert "pragma solidity ^0.8.0;" in result
    assert "[T-002]" in result
    mocked_answer.assert_called_once()


def test_agent_worker_access(setup_in_memory_db: None) -> None:
    orchestrator = AegisOrchestrator()
    with patch.object(
        IntentClassifier,
        "classify",
        return_value=IntentClassification(
            intent=IntentType.DATA_RETRIEVAL,
            query="최종 보안 보고서",
        ),
    ), patch.object(
        IntentClassifier,
        "answer_with_context",
        return_value="이 값은 호출되면 안 됩니다.",
    ) as mocked_answer:
        result = orchestrator.process_slack_message("U_WORKER", "검색: 최종 보안 보고서")

    assert "검색 결과가 없습니다." in result
    assert "RAG 답변" not in result
    mocked_answer.assert_not_called()
