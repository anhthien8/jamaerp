"""Customer model — converted leads or standalone clients."""

import uuid
from datetime import datetime, timezone

from sqlalchemy import String, Text, ForeignKey, DateTime, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Customer(Base):
    __tablename__ = "customers"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    phone: Mapped[str] = mapped_column(String(20), nullable=False)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    address: Mapped[str | None] = mapped_column(String(500), nullable=True)

    # Type
    type: Mapped[str] = mapped_column(String(20), nullable=False, default="individual")
    # Types: individual, company
    tax_code: Mapped[str | None] = mapped_column(String(30), nullable=True)
    company_name: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # Link to lead
    lead_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("leads.id"), nullable=True)

    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc)
    )

    # Relationships
    lead = relationship("Lead", foreign_keys=[lead_id])
    projects = relationship("Project", back_populates="customer", foreign_keys="Project.customer_id")

    __table_args__ = (
        Index("ix_customers_type", "type"),
        Index("ix_customers_name", "name"),
    )

    def __repr__(self) -> str:
        return f"<Customer {self.name}>"
