"""Project & Task models."""

import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    Boolean, String, Text, Float, ForeignKey, DateTime, Integer, Index, JSON, UniqueConstraint, false, select,
)
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
    # Khách riêng của sale (24/10/2026, JD NVKD): hoa hồng sale 2% thay 1%.
    # Chỉ Trưởng phòng KD + BGĐ được đánh dấu.
    khach_rieng: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default=false())

    # Kho ảnh (Đợt 2, 23/10/2026): topic của dự án trong nhóm Telegram «JAMA
    # Công trình» (bot tự tạo lần đầu có ảnh) + thư mục con trên Drive công ty.
    telegram_topic_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    drive_folder_id: Mapped[str | None] = mapped_column(String(100), nullable=True)

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
    # BẢN SAO của một người bất kỳ trong nhóm đảm nhận — nguồn sự thật là bảng
    # `task_assignees` (13/10/2026, một việc nhiều người ngang vai). Giữ cột này
    # để dữ liệu cũ và các truy vấn cũ không gãy; mọi chỗ ĐẾM người phải đi qua
    # bảng kia, nếu không một việc 3 người sẽ chỉ tính cho 1.
    assigned_to: Mapped[str | None] = mapped_column(String(36), ForeignKey("users.id"), nullable=True)
    order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    due_date: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    # Mốc bắt đầu thật (lần đầu chuyển sang «Đang làm», hoặc lần đầu có người
    # nhận việc). SLA đếm từ đây chứ không từ created_at: 19 đầu việc mẫu sinh
    # cùng một lúc lúc «Deal thắng» nên đếm từ created_at thì việc nghiệm thu vi
    # phạm SLA ngay ngày đầu tiên của dự án.
    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    # Hạn theo CHUẨN NỘI BỘ = started_at + số ngày SLA của đầu việc. Khác
    # `due_date` (hạn thoả thuận, có thể dài hơn) — xem app/services/task_sla.py.
    sla_due_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc)
    )

    # Relationships
    project = relationship("Project", back_populates="tasks")
    assignee = relationship("User", foreign_keys=[assigned_to])
    assignees = relationship(
        "TaskAssignee", back_populates="task", lazy="selectin", cascade="all, delete-orphan"
    )
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


class TaskAssignee(Base):
    """Người đảm nhận một đầu việc — nhiều người/việc, TẤT CẢ NGANG VAI.

    Chốt với chủ dự án 13/10/2026: không phân biệt người chính/người phụ. Hệ quả
    phải nhớ khi đọc số: một đầu việc quá hạn sẽ tính là việc trễ của TỪNG người
    trong nhóm, nên tổng «việc trễ» cộng theo người sẽ lớn hơn số đầu việc trễ.
    """

    __tablename__ = "task_assignees"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    task_id: Mapped[str] = mapped_column(String(36), ForeignKey("tasks.id"), nullable=False)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc), nullable=False
    )

    task = relationship("Task", back_populates="assignees")
    user = relationship("User", foreign_keys=[user_id])

    __table_args__ = (
        UniqueConstraint("task_id", "user_id", name="uq_task_assignee"),
        Index("ix_task_assignees_task", "task_id"),
        Index("ix_task_assignees_user", "user_id"),
    )

    def __repr__(self) -> str:
        return f"<TaskAssignee {self.user_id} → {self.task_id}>"


def dieu_kien_task_cua_nguoi(user_id: str):
    """Điều kiện SQL «đầu việc này của người đó» — dùng cho MỌI chỗ lọc/đếm việc
    theo người (13/10/2026, một việc nhiều người ngang vai).

    Phải xét CẢ HAI nguồn:
    - `task_assignees` — nguồn sự thật của nhóm đảm nhận;
    - `tasks.assigned_to` — bản sao; vẫn có dòng chỉ có cột này do seed, agent AI
      và dữ liệu cũ ghi thẳng vào cột mà không qua `dat_nguoi_lam`.
    Chỉ đọc một trong hai thì người thứ 2–3 của một đầu việc sẽ không thấy việc
    của mình (và dự án tương ứng biến mất khỏi danh sách của họ).
    """
    from sqlalchemy import or_

    return or_(
        Task.assigned_to == user_id,
        Task.id.in_(select(TaskAssignee.task_id).where(TaskAssignee.user_id == user_id)),
    )


class TaskActivity(Base):
    __tablename__ = "task_activities"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    task_id: Mapped[str] = mapped_column(String(36), ForeignKey("tasks.id"), nullable=False)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    media_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    # tien_do | su_co | vat_tu | cham_cong | khac — portal khách chỉ hiện `tien_do`
    # (trước 23/10 khách thấy cả sự cố, yêu cầu vật tư, check-in của thợ).
    kind: Mapped[str] = mapped_column(String(20), nullable=False, default="khac", server_default="khac")
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


async def sinh_ma_du_an(db) -> str:
    """Sinh mã dự án PRJ-<năm>-<4 số> chưa trùng.

    Trước 22/09 logic này chỉ nằm trong luồng «Deal thắng» của lead, còn
    `ProjectCreate.code` thì bắt buộc — nên nút «Tạo dự án mới» trên màn Dự án
    gửi payload không có `code` và trả 422 cho MỌI tài khoản (đo prod 22/09:
    153 dự án đều sinh tự động từ lead, chưa ai tạo tay được lần nào). Nay dùng
    chung một hàm để hai đường đi không lệch định dạng mã.
    """
    import random
    import uuid as _uuid

    nam = datetime.now(timezone.utc).year
    for _ in range(100):
        ma = f"PRJ-{nam}-{random.randint(1000, 9999)}"
        trung = await db.execute(select(Project).where(Project.code == ma))
        if trung.scalar_one_or_none() is None:
            return ma
    # 100 lần vẫn trùng (kho 9000 mã gần cạn) → rơi về mã dài, chắc chắn duy nhất
    return f"PRJ-{nam}-{_uuid.uuid4().hex[:8]}"
