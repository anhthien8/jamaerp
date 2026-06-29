"""Lead & Activity models — 7-stage pipeline, activity log."""

import uuid
from datetime import datetime, timezone

from sqlalchemy import String, Text, Float, ForeignKey, DateTime, Index, BigInteger
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


# Stage values
LEAD_STAGES = ["new", "interested", "survey_scheduled", "potential", "signed_design", "lost", "dormant"]
LEAD_SOURCES = ["facebook", "zalo", "website", "referral", "tiktok", "other"]
PROPERTY_TYPES = ["townhouse", "apartment", "villa", "office", "shophouse", "other"]
LEAD_PRIORITIES = ["low", "medium", "high", "urgent"]
ACTIVITY_TYPES = ["call", "email", "meeting", "survey", "note", "stage_change", "assignment"]


class Lead(Base):
    __tablename__ = "leads"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    # Client info
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    phone: Mapped[str] = mapped_column(String(20), nullable=False)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    contact_person: Mapped[str | None] = mapped_column(String(150), nullable=True)
    address: Mapped[str | None] = mapped_column(String(500), nullable=True)
    needs: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Classification
    source: Mapped[str | None] = mapped_column(String(20), nullable=True)
    property_type: Mapped[str | None] = mapped_column(String(20), nullable=True)
    area_sqm: Mapped[float | None] = mapped_column(Float, nullable=True)
    estimated_budget: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Extended classification (from Lark CRM)
    property_class: Mapped[str | None] = mapped_column(String(20), nullable=True)  # luxury/mid_range/budget
    price_per_sqm: Mapped[float | None] = mapped_column(Float, nullable=True)  # VND/m²
    region: Mapped[str | None] = mapped_column(String(100), nullable=True)  # Khu vực
    segment: Mapped[str | None] = mapped_column(String(50), nullable=True)  # Phân khúc
    plan_type: Mapped[str | None] = mapped_column(String(20), nullable=True)  # online/offline/survey/none
    tags: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON array of tags
    deal_value: Mapped[float | None] = mapped_column(Float, nullable=True)  # price_per_sqm × area_sqm

    # Pipeline
    stage: Mapped[str] = mapped_column(String(30), nullable=False, default="new")
    priority: Mapped[str] = mapped_column(String(20), nullable=False, default="medium")

    # Assignment
    assigned_to: Mapped[str | None] = mapped_column(String(36), ForeignKey("users.id"), nullable=True)
    team_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("teams.id"), nullable=True)

    # AI
    ai_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    ai_notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Notes
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Design contract value
    design_contract_value: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc)
    )
    last_contacted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    # Relationships
    assigned_user = relationship("User", back_populates="assigned_leads", foreign_keys=[assigned_to])
    team = relationship("Team", foreign_keys=[team_id])
    activities = relationship("Activity", back_populates="lead", order_by="Activity.created_at.desc()")
    project = relationship("Project", back_populates="lead", uselist=False)
    quotations = relationship("Quotation", back_populates="lead")

    __table_args__ = (
        Index("ix_leads_assigned_stage", "assigned_to", "stage"),
        Index("ix_leads_team_stage", "team_id", "stage"),
        Index("ix_leads_created", "created_at"),
        Index("ix_leads_stage_created", "stage", "created_at"),
        Index("ix_leads_source_stage", "source", "stage"),
        Index("ix_leads_priority_stage", "priority", "stage"),
    )

    def __repr__(self) -> str:
        return f"<Lead {self.name} ({self.stage})>"


# Valid stage transitions
VALID_STAGE_TRANSITIONS: dict[str, list[str]] = {
    "new": ["interested", "lost", "dormant"],
    "interested": ["survey_scheduled", "lost", "dormant"],
    "survey_scheduled": ["potential", "lost", "dormant"],
    "potential": ["signed_design", "lost", "dormant"],
    "signed_design": [],
    "lost": [],
    "dormant": ["interested", "lost"],
}


class Activity(Base):
    __tablename__ = "activities"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    lead_id: Mapped[str] = mapped_column(String(36), ForeignKey("leads.id"), nullable=False)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False)
    type: Mapped[str] = mapped_column(String(20), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)

    # Telegram audit
    telegram_message_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    telegram_chat_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc)
    )

    # Relationships
    lead = relationship("Lead", back_populates="activities")
    user = relationship("User", back_populates="activities")

    __table_args__ = (
        Index("ix_activities_lead", "lead_id", "created_at"),
        Index("ix_activities_user", "user_id", "created_at"),
    )

    def __repr__(self) -> str:
        return f"<Activity {self.type} on lead {self.lead_id}>"
