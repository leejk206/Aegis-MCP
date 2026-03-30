from __future__ import annotations

from sqlalchemy import Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class User(Base):
    __tablename__ = "users"

    slack_id: Mapped[str] = mapped_column(String(50), primary_key=True, index=True)
    clearance_level: Mapped[int] = mapped_column(Integer, nullable=False)
