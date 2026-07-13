"""User & Team models — employees, roles, Telegram mapping."""

import uuid
from datetime import datetime, timezone

from sqlalchemy import String, Boolean, BigInteger, ForeignKey, DateTime, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Team(Base):
    __tablename__ = "teams"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    code: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    department: Mapped[str] = mapped_column(String(20), nullable=False)  # EXEC, SALES, DESIGN, PM, ACCT
    leader_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc)
    )

    # Relationships
    members = relationship("User", back_populates="team", foreign_keys="User.team_id")
    leader = relationship("User", foreign_keys=[leader_id], post_update=True)

    def __repr__(self) -> str:
        return f"<Team {self.code}: {self.name}>"


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    full_name: Mapped[str] = mapped_column(String(150), nullable=False)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    phone: Mapped[str | None] = mapped_column(String(20), nullable=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)

    role: Mapped[str] = mapped_column(String(20), nullable=False, default="data_entry")
    # Roles: admin, leader, data_entry, designer, pm, accountant
    department: Mapped[str] = mapped_column(String(20), nullable=False, default="SALES")
    # Departments: EXEC, SALES, DESIGN, PM, ACCT
    team_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("teams.id"), nullable=True)

    # Telegram mapping
    telegram_user_id: Mapped[int | None] = mapped_column(BigInteger, unique=True, nullable=True)
    telegram_username: Mapped[str | None] = mapped_column(String(100), nullable=True)

    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    # Resignation tracking
    resign_date: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    resigned_by: Mapped[str | None] = mapped_column(String(36), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc)
    )

    # Relationships
    team = relationship("Team", back_populates="members", foreign_keys=[team_id])
    assigned_leads = relationship("Lead", back_populates="assigned_user", foreign_keys="Lead.assigned_to")
    activities = relationship("Activity", back_populates="user")

    __table_args__ = (
        Index("ix_users_role_dept", "role", "department"),
    )

    def __repr__(self) -> str:
        return f"<User {self.full_name} ({self.role})>"
