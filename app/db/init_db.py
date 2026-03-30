from __future__ import annotations

from sqlalchemy import select

from app.core.database import Base, SessionLocal, engine
from app.models.task import Task
from app.models.user import User

MOCK_USERS: list[dict[str, str | int]] = [
    {"slack_id": "U_BOSS", "clearance_level": 4},
    {"slack_id": "U_SECRETARY", "clearance_level": 3},
    {"slack_id": "U_SUPERVISOR", "clearance_level": 2},
    {"slack_id": "U_WORKER", "clearance_level": 1},
]

MOCK_TASKS: list[dict[str, str | None]] = [
    {
        "task_id": "T-001",
        "title": "스마트 컨트랙트 개발 총괄",
        "description": "신규 ERC20 토큰 컨트랙트 개발 및 보안 감사 진행",
        "assigned_role": "SUPERVISOR",
        "status": "IN_PROGRESS",
        "payload": None,
    },
    {
        "task_id": "T-002",
        "title": "ERC20 기본 컨트랙트 구현",
        "description": "OpenZeppelin을 활용한 기본 코드 작성",
        "assigned_role": "WORKER",
        "status": "COMPLETED",
        "payload": "pragma solidity ^0.8.0;\nimport '@openzeppelin/contracts/token/ERC20/ERC20.sol';\ncontract AegisToken is ERC20 { ... }",
    },
    {
        "task_id": "T-003",
        "title": "Reentrancy 취약점 분석",
        "description": "T-002 코드의 재진입 공격 취약점 점검",
        "assigned_role": "WORKER",
        "status": "REVIEW",
        "payload": "분석 결과 특이사항 없음. 검토 요망.",
    },
    {
        "task_id": "T-004",
        "title": "최종 보안 보고서 작성",
        "description": "개발 및 감사 완료 후 Boss에게 보고할 최종 요약본 작성",
        "assigned_role": "SECRETARY",
        "status": "PENDING",
        "payload": None,
    },
]


def init_db() -> None:
    Base.metadata.create_all(bind=engine)

    with SessionLocal() as db:
        users_exist = db.execute(select(User.slack_id).limit(1)).first() is not None
        tasks_exist = db.execute(select(Task.task_id).limit(1)).first() is not None

        if not users_exist:
            users = [
                User(
                    slack_id=str(user["slack_id"]),
                    clearance_level=int(user["clearance_level"]),
                )
                for user in MOCK_USERS
            ]
            db.add_all(users)

        if not tasks_exist:
            tasks = [
                Task(
                    task_id=str(task["task_id"]),
                    title=str(task["title"]),
                    description=str(task["description"]),
                    assigned_role=str(task["assigned_role"]),
                    status=str(task["status"]),
                    payload=task["payload"],
                )
                for task in MOCK_TASKS
            ]
            db.add_all(tasks)

        if not users_exist or not tasks_exist:
            db.commit()
