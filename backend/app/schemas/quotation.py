"""Quotation schemas."""

from pydantic import BaseModel
from datetime import datetime, date


class QuotationLineItem(BaseModel):
    name: str
    description: str | None = None
    category: str = "general"  # phong_khach, phong_ngu, bep, phong_tam, general, custom
    unit: str = "bộ"
    quantity: float = 1
    unit_price: float = 0
    total: float = 0


class QuotationCreate(BaseModel):
    code: str | None = None  # bỏ trống → backend tự sinh BG-{năm}-{số}
    type: str  # design, construction
    project_id: str | None = None
    lead_id: str | None = None
    title: str
    items: list[QuotationLineItem] = []
    total_amount: float | None = None
    tax_amount: float | None = None
    valid_until: date | None = None
    notes: str | None = None


class QuotationUpdate(BaseModel):
    title: str | None = None
    # Form «Sửa báo giá» có ô đổi loại + dự án nhưng schema quên khai báo — đổi
    # bị nuốt im lặng dù toast báo thành công (QC 27/08).
    type: str | None = None
    project_id: str | None = None
    status: str | None = None
    items: list[QuotationLineItem] | None = None
    total_amount: float | None = None
    tax_amount: float | None = None
    valid_until: date | None = None
    notes: str | None = None

    # Field lạ → 422 thay vì bị nuốt im lặng (cùng chốt chặn như LeadUpdate).
    model_config = {"extra": "forbid"}


class QuotationResponse(BaseModel):
    id: str
    code: str
    type: str
    project_id: str | None = None
    lead_id: str | None = None
    title: str
    status: str
    total_amount: float | None = None
    tax_amount: float | None = None
    valid_until: date | None = None
    items: dict | None = None
    revision: int = 1
    notes: str | None = None
    created_by: str | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
