"""Lead & Activity models — 7-stage pipeline, activity log."""

import uuid
from datetime import datetime, timezone

from sqlalchemy import String, Text, Float, ForeignKey, DateTime, Index, BigInteger
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


# Stage values — 6 active stages + 2 end states
LEAD_STAGES = ["new", "interested", "survey_scheduled", "potential", "signed_design", "lost", "dormant"]
LEAD_SOURCES = ["facebook", "zalo", "website", "referral", "tiktok", "other"]
# Kênh phân bổ: phân biệt với Source (platform). Source = từ đâu, Channel = kênh nào bán/giới thiệu
LEAD_CHANNELS = ["kenh_a", "kenh_b", "kenh_chinh", "kenh_sale", "kenh_affiliate", "khac"]
PROPERTY_TYPES = ["townhouse", "apartment", "villa", "office", "shophouse", "other"]
LEAD_PRIORITIES = ["low", "medium", "high", "urgent"]
# Tình trạng liên hệ
CONTACT_STATUSES = ["reachable", "unreachable", "wrong_number", "no_need", "pending"]
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
    source: Mapped[str | None] = mapped_column(String(20), nullable=True)  # Platform: facebook, zalo, etc.
    channel: Mapped[str | None] = mapped_column(String(30), nullable=True)  # Kênh phân bổ: kenh_a, kenh_b, etc.
    property_type: Mapped[str | None] = mapped_column(String(20), nullable=True)
    area_sqm: Mapped[float | None] = mapped_column(Float, nullable=True)
    estimated_budget: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Contact & survey status
    contact_status: Mapped[str | None] = mapped_column(String(20), nullable=True)  # reachable/unreachable/wrong_number/no_need
    survey_date: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    survey_photos: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON array of photo URLs

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
# Nới theo thực tế sales (feedback beta 22/07): khách có thể chốt tắt/quay lùi bước,
# máy trạng thái 1-bước-tiến cũ khiến kéo thả/đổi trạng thái bị chặn 400 khó hiểu.
# Chỉ giữ 1 khóa: signed_design là TERMINAL (đã tự sinh Khách hàng + Dự án, không lùi).
_OPEN_STAGES = ["new", "interested", "survey_scheduled", "potential", "signed_design", "lost", "dormant"]
VALID_STAGE_TRANSITIONS: dict[str, list[str]] = {
    "new": [s for s in _OPEN_STAGES if s != "new"],
    "interested": [s for s in _OPEN_STAGES if s != "interested"],
    "survey_scheduled": [s for s in _OPEN_STAGES if s != "survey_scheduled"],
    "potential": [s for s in _OPEN_STAGES if s != "potential"],
    "signed_design": [],
    "lost": ["new", "interested", "dormant"],
    "dormant": [s for s in _OPEN_STAGES if s != "dormant"],
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
