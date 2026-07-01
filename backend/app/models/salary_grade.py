"""Salary Grade model (Bac luong)."""

import uuid
from datetime import datetime, timezone

from sqlalchemy import String, Float, Date, DateTime
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class SalaryGrade(Base):
    __tablename__ = "salary_grades"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    grade_name: Mapped[str] = mapped_column(String(100), nullable=False)
    base_salary: Mapped[float] = mapped_column(Float, nullable=False)
    bhxh_rate: Mapped[float] = mapped_column(Float, nullable=False, default=10.5)  # BHXH NLD %
    bhxh_company_rate: Mapped[float] = mapped_column(Float, nullable=False, default=21.5)  # BHXH NSDLĐ
    bhyt_rate: Mapped[float] = mapped_column(Float, nullable=False, default=1.5)  # BHYT %
    bhtn_rate: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)  # BHTN %
    effective_date: Mapped[datetime] = mapped_column(Date, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))

    def __repr__(self):
        return f"<SalaryGrade {self.grade_name} ({self.base_salary})>"
