"""Project & Task models."""

import uuid
from datetime import datetime, timezone

from sqlalchemy import String, Text, Float, ForeignKey, DateTime, Integer, Index, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Project(Base):
    __tablename__ = "projects"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    code: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    lead_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("leads.id"), nullable=True)
    customer_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("customers.id"), nullable=True)
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
    # Ngân sách kế hoạch — so với chi thực tế (spent) để cảnh báo vượt ngân sách sớm
    budget_total: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Lý do tạm dừng
    pause_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    paused_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    # Bàn giao & bảo hành: warranty_end = handover_date + warranty_months
    handover_date: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    warranty_months: Mapped[int] = mapped_column(Integer, nullable=False, default=12)
    warranty_end_date: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    # Nghiệm thu giai đoạn qua Customer Portal: {stage: {"at": iso, "note": str}}
    stage_acceptances: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    # Progress
    progress: Mapped[int] = mapped_column(Integer, nullable=False, default=0)  # 0-100

    # Team
    pm_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("users.id"), nullable=True)
    designer_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("users.id"), nullable=True)
    sales_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("users.id"), nullable=True)
    # PIC Báo giá – Thu mua (phòng PURCHASING). Thêm 05/09/2026: 3 trường trên đã có
    # từ đầu nhưng thiếu hẳn bộ phận này, nên dự toán/thu mua không ai gắn được vào
    # dự án và cũng không lọc được dự án của mình.
    purchasing_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("users.id"), nullable=True)

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
    customer = relationship("Customer", foreign_keys=[customer_id], back_populates="projects")
    pm = relationship("User", foreign_keys=[pm_id])
    designer = relationship("User", foreign_keys=[designer_id])
    sales = relationship("User", foreign_keys=[sales_id])
    purchasing = relationship("User", foreign_keys=[purchasing_id])
    tasks = relationship("Task", back_populates="project", order_by="Task.order")
    quotations = relationship("Quotation", back_populates="project")
    contracts = relationship("Contract", back_populates="project")

    __table_args__ = (
        Index("ix_projects_status", "status"),
        Index("ix_projects_stage_status", "stage", "status"),
        Index("ix_projects_pm", "pm_id", "status"),
        Index("ix_projects_created", "created_at"),
        # Sort ưu tiên nguồn lực (spec 07B): quá hạn → cận hạn → giá trị HĐ
        Index("ix_projects_end_value", "status", "target_end_date", "total_value"),
    )

    def __repr__(self) -> str:
        return f"<Project {self.code}>"


# Giai đoạn task → phòng ban đảm nhận. Key giai đoạn trùng key phòng ban, trừ
# «acceptance» (nghiệm thu) do đội thi công làm. Dùng ở cả tạo task tự động lẫn
# tạo tay khi form bỏ trống phòng ban, và migration backfill u01.
STAGE_TO_DEPARTMENT: dict[str, str] = {
    "design": "design",
    "quotation": "quotation",
    "procurement": "procurement",
    "construction": "construction",
    "acceptance": "construction",
}


def task_department_for_stage(stage: str | None) -> str | None:
    if not stage:
        return None
    return STAGE_TO_DEPARTMENT.get(stage, stage)


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
    final_file_versions: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    # JSON array: [{"url": str, "version": int, "label": str|None, "uploaded_at": iso}]
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
        # Phạm vi dự án (05/09) lọc «dự án tôi có đầu việc» bằng subquery
        # SELECT project_id FROM tasks WHERE assigned_to = ? — chạy mỗi lần
        # mở danh sách dự án của mọi tài khoản không phải admin.
        Index("ix_tasks_assigned", "assigned_to"),
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
