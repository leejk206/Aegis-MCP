from __future__ import annotations

from sqlalchemy.orm import Session

from app.models.task import Task
from app.models.user import User


class MACService:
    def get_user_clearance(self, user_id: str, db: Session) -> int:
        user = db.get(User, user_id)
        clearance = user.clearance_level if user else 1
        print(f"[AUTH] User: {user_id} | Clearance: {clearance}", flush=True)
        return clearance

    def get_accessible_tasks(self, user_id: str, db: Session) -> list[Task]:
        user_clearance = self.get_user_clearance(user_id, db)
        if user_clearance >= 4:
            return db.query(Task).all()
        if user_clearance == 3:
            allowed_roles = ["WORKER", "SUPERVISOR", "SECRETARY"]
        elif user_clearance == 2:
            allowed_roles = ["WORKER", "SUPERVISOR"]
        else:
            allowed_roles = ["WORKER"]
        return db.query(Task).filter(Task.assigned_role.in_(allowed_roles)).all()
