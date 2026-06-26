"""Inventory models — materials & usage tracking."""

import uuid
from datetime import datetime, timezone

from sqlalchemy import String, Text, Float, Integer, ForeignKey, DateTime, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Material(Base):
    __tablename__ = "materials"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    code: Mapped[str] = mapped_column(String(30), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    category: Mapped[str] = mapped_column(String(50), nullable=False, default="general")
    # Categories: wood, stone, metal, paint, electrical, plumbing, furniture, fabric, glass, general
    unit: Mapped[str] = mapped_column(String(20), nullable=False, default="cái")
    # Units: cái, m2, m, kg, tấm, bộ, cuộn, hộp, lít
    unit_price: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    quantity_in_stock: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    min_stock: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    supplier: Mapped[str | None] = mapped_column(String(255), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc)
    )

    # Relationships
    usages = relationship("MaterialUsage", back_populates="material")

    __table_args__ = (
        Index("ix_materials_category", "category"),
        Index("ix_materials_name", "name"),
    )

    @property
    def is_low_stock(self) -> bool:
        return self.quantity_in_stock <= self.min_stock

    def __repr__(self) -> str:
        return f"<Material {self.code}: {self.name}>"


class MaterialUsage(Base):
    __tablename__ = "material_usages"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    material_id: Mapped[str] = mapped_column(String(36), ForeignKey("materials.id"), nullable=False)
    project_id: Mapped[str] = mapped_column(String(36), ForeignKey("projects.id"), nullable=False)
    quantity: Mapped[float] = mapped_column(Float, nullable=False)
    unit_price_at_use: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    total_cost: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    date: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[str | None] = mapped_column(String(36), ForeignKey("users.id"), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc)
    )

    # Relationships
    material = relationship("Material", back_populates="usages")
    project = relationship("Project", foreign_keys=[project_id])
    creator = relationship("User", foreign_keys=[created_by])

    __table_args__ = (
        Index("ix_material_usages_project", "project_id"),
        Index("ix_material_usages_material", "material_id"),
    )

    def __repr__(self) -> str:
        return f"<MaterialUsage {self.material_id} -> {self.project_id}>"
