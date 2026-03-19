from datetime import datetime
from sqlalchemy import String, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    email: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    sessions: Mapped[list["ChatSession"]] = relationship(back_populates="user")  # noqa: F821
    trips: Mapped[list["Trip"]] = relationship(back_populates="user")  # noqa: F821
    preferences: Mapped["UserPreference"] = relationship(back_populates="user", uselist=False)  # noqa: F821
