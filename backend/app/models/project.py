"""Project & Task models."""

import uuid
from datetime import datetime, timezone

from sqlalchemy import String, Text, Float, ForeignKey, DateTime, Integer, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Project(Base):
    __tablename__ = "projects"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    code: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    lead_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("leads.id"), nullable=True)
    client_name: Mapped[str] = mapped_column(String(255), nullable=False)
    client_phone: Mapped[str | None] = mapped_column(String(20), nullable=True)
    address: Mapped[str | None] = mapped_column(String(500), nullable=True)

    # Classification
    project_type: Mapped[str] = mapped_column(String(30), nullable=False, default="design_build")
    # Types: design_only, design_build, construction_only
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active")
    # Statuses: active, paused, completed, cancelled
    stage: Mapped[str] = mapped_column(String(30), nullable=False, default="design")
    # Stages: design, quotation, procurement, construction, acceptance, completed

    # Financial
    design_value: Mapped[float | None] = mapped_column(Float, nullable=True)
    construction_value: Mapped[float | None] = mapped_column(Float, nullable=True)
    total_value: Mapped[float | None] = mapped_column(Float, nullable=True)
    spent: Mapped[float] = mapped_column(Float, nullable=False, default=0)

    # Progress
    progress: Mapped[int] = mapped_column(Integer, nullable=False, default=0)  # 0-100

    # Team
    pm_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("users.id"), nullable=True)
    designer_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("users.id"), nullable=True)
    sales_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("users.id"), nullable=True)

    # Timestamps
    start_date: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    target_end_date: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc)
    )

    # Relationships
    lead = relationship("Lead", back_populates="project")
    pm = relationship("User", foreign_keys=[pm_id])
    designer = relationship("User", foreign_keys=[designer_id])
    sales = relationship("User", foreign_keys=[sales_id])
    tasks = relationship("Task", back_populates="project", order_by="Task.order")
    quotations = relationship("Quotation", back_populates="project")
    contracts = relationship("Contract", back_populates="project")

    __table_args__ = (
        Index("ix_projects_status", "status"),
        Index("ix_projects_stage_status", "stage", "status"),
        Index("ix_projects_pm", "pm_id", "status"),
        Index("ix_projects_created", "created_at"),
    )

    def __repr__(self) -> str:
        return f"<Project {self.code}>"


class Task(Base):
    __tablename__ = "tasks"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id: Mapped[str] = mapped_column(String(36), ForeignKey("projects.id"), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="not_started")
    # Statuses: not_started, in_progress, done
    stage: Mapped[str] = mapped_column(String(30), nullable=False, default="design")
    # Stages: design, quotation, procurement, construction, acceptance
    department: Mapped[str | None] = mapped_column(String(30), nullable=True)
    # Departments: design, quotation, procurement, construction, accounting, sales
    final_file_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    assigned_to: Mapped[str | None] = mapped_column(String(36), ForeignKey("users.id"), nullable=True)
    order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    due_date: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc)
    )

    # Relationships
    project = relationship("Project", back_populates="tasks")
    assignee = relationship("User", foreign_keys=[assigned_to])
    activities = relationship("TaskActivity", back_populates="task", order_by="TaskActivity.created_at.desc()")

    __table_args__ = (
        Index("ix_tasks_project_stage", "project_id", "stage"),
        Index("ix_tasks_status", "status"),
        Index("ix_tasks_department", "department"),
    )

    def __repr__(self) -> str:
        return f"<Task {self.title} ({self.status})>"


class TaskActivity(Base):
    __tablename__ = "task_activities"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    task_id: Mapped[str] = mapped_column(String(36), ForeignKey("tasks.id"), nullable=False)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    media_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc)
    )

    # Relationships
    task = relationship("Task", back_populates="activities")
    user = relationship("User")

    __table_args__ = (
        Index("ix_task_activities_task", "task_id", "created_at"),
    )

    def __repr__(self) -> str:
        return f"<TaskActivity on task {self.task_id}>"
