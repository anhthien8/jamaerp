"""Pydantic schemas for projects, tasks, and task activities."""

from pydantic import BaseModel, Field, computed_field, model_validator
from datetime import datetime


class ProjectCreate(BaseModel):
    # Bỏ trống thì server tự sinh (sinh_ma_du_an). Bắt buộc như trước làm nút
    # «Tạo dự án mới» trên màn Dự án trả 422 cho mọi tài khoản — form không có ô mã.
    code: str | None = None
    name: str
    lead_id: str | None = None
    client_name: str
    client_phone: str | None = None
    address: str | None = None
    project_type: str = "design_build"
    design_value: float | None = None
    construction_value: float | None = None
    total_value: float | None = None
    pm_id: str | None = None
    designer_id: str | None = None
    sales_id: str | None = None
    purchasing_id: str | None = None
    start_date: datetime | None = None
    target_end_date: datetime | None = None
    stage: str = "design"


class ProjectUpdate(BaseModel):
    name: str | None = None
    # Nhóm trường form «Sửa dự án» FE vẫn gửi từ lâu nhưng schema quên khai báo —
    # Pydantic nuốt im lặng nên đổi tên khách/SĐT/địa chỉ/loại/giá trị/ngày đều
    # toast xanh mà không đổi gì (QC 27/08, cùng lớp bug «Mất lead»).
    client_name: str | None = None
    client_phone: str | None = None
    address: str | None = None
    project_type: str | None = None
    total_value: float | None = None
    start_date: datetime | None = None
    target_end_date: datetime | None = None
    status: str | None = None
    stage: str | None = None
    progress: int | None = None
    spent: float | None = None
    pm_id: str | None = None
    designer_id: str | None = None
    # Bổ sung 05/09: form «Chỉnh sửa» phải gán được ĐỦ 4 PIC
    sales_id: str | None = None
    purchasing_id: str | None = None
    budget_total: float | None = None
    handover_date: datetime | None = None
    warranty_months: int | None = None
    # Khách riêng của sale → hoa hồng 2% (chỉ TP KD + BGĐ đổi được, kiểm ở API)
    khach_rieng: bool | None = None

    # Field lạ → 422 thay vì bị nuốt im lặng (cùng chốt chặn như LeadUpdate).
    model_config = {"extra": "forbid"}


class ProjectResponse(BaseModel):
    id: str
    code: str
    name: str
    lead_id: str | None = None
    client_name: str
    client_phone: str | None = None
    address: str | None = None
    project_type: str
    status: str
    stage: str
    design_value: float | None = None
    construction_value: float | None = None
    total_value: float | None = None
    spent: float
    progress: int
    pm_id: str | None = None
    designer_id: str | None = None
    sales_id: str | None = None
    purchasing_id: str | None = None
    khach_rieng: bool = False
    start_date: datetime | None = None
    target_end_date: datetime | None = None
    budget_total: float | None = None
    handover_date: datetime | None = None
    warranty_months: int = 12
    pause_reason: str | None = None
    paused_at: datetime | None = None
    stage_acceptances: dict | None = None
    created_at: datetime
    updated_at: datetime
    # Tiến độ đầu việc theo giai đoạn: {"design": {"done": 3, "total": 5}, ...}
    # Chỉ được đổ ở endpoint kanban (aggregate 1 query) — nơi khác để None
    stage_progress: dict[str, dict] | None = None
    # Trạng thái hiển thị gộp (status + stage) — frontend dùng thay cho 2 field riêng
    display_status: str | None = None

    _STAGE_LABELS = {
        "design": "Thiet ke",
        "quotation": "Bao gia",
        "procurement": "Thu mau",
        "construction": "Thi cong",
        "acceptance": "Nghiem thu",
        "completed": "Hoan thanh",
        "paused": "Tam dung",
    }

    @model_validator(mode="after")
    def _compute_display_status(self):
        stage = getattr(self, "stage", None)
        status = getattr(self, "status", None)
        if stage == "paused" or status == "paused":
            self.display_status = "Tam dung"
        elif stage == "completed" or status == "completed":
            self.display_status = "Hoan thanh"
        else:
            self.display_status = self._STAGE_LABELS.get(stage, stage)
        return self

    model_config = {"from_attributes": True}


class TaskAssigneeOut(BaseModel):
    """Một người trong nhóm đảm nhận đầu việc."""

    user_id: str

    model_config = {"from_attributes": True}


class TaskResponse(BaseModel):
    id: str
    project_id: str
    title: str
    description: str | None = None
    status: str
    stage: str
    department: str | None = None
    final_file_url: str | None = None
    final_file_versions: list[dict] | None = None
    # BẢN SAO của một người trong nhóm — giữ cho FE/truy vấn cũ. Nhóm thật nằm ở
    # `assignee_ids` (13/10/2026, một việc nhiều người ngang vai).
    assigned_to: str | None = None
    assignees: list[TaskAssigneeOut] = []
    order: int
    due_date: datetime | None = None       # hạn thoả thuận
    started_at: datetime | None = None     # mốc bắt đầu — đồng hồ SLA chạy từ đây
    sla_due_at: datetime | None = None     # hạn theo chuẩn nội bộ
    completed_at: datetime | None = None
    created_at: datetime

    @computed_field
    @property
    def assignee_ids(self) -> list[str]:
        return [a.user_id for a in self.assignees]

    model_config = {"from_attributes": True}


class TaskActivityCreate(BaseModel):
    content: str
    # Link ảnh qua Kho ảnh (/media/...). Trước 23/10 web nhét base64 vào đây
    # → Postgres từ chối vì cột chỉ 500 ký tự; chặn sớm bằng 422 rõ ràng.
    media_url: str | None = Field(default=None, max_length=500)
    kind: str | None = Field(default=None, pattern=r"^(tien_do|su_co|vat_tu|cham_cong|khac)$")


class TaskActivityResponse(BaseModel):
    id: str
    task_id: str
    user_id: str
    user_name: str | None = None
    content: str
    media_url: str | None = None
    kind: str | None = None
    created_at: datetime

    model_config = {"from_attributes": True}
