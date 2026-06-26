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
    code: str
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
    status: str | None = None
    items: list[QuotationLineItem] | None = None
    total_amount: float | None = None
    tax_amount: float | None = None
    valid_until: date | None = None
    notes: str | None = None


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
