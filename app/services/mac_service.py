from __future__ import annotations

from app.services.data_store import MOCK_DOCUMENTS, MOCK_USERS, MockDocument


class MACService:
    def get_user_clearance(self, user_id: str) -> int:
        # Unknown users are treated as lowest clearance.
        clearance = MOCK_USERS.get(user_id, 1)
        print(f"[AUTH] User: {user_id} | Clearance: {clearance}", flush=True)
        return clearance

    def get_accessible_documents(self, user_id: str) -> list[MockDocument]:
        user_clearance = self.get_user_clearance(user_id)
        return [
            document
            for document in MOCK_DOCUMENTS
            if document["required_clearance"] <= user_clearance
        ]
