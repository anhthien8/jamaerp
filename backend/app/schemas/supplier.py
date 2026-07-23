"""Supplier schemas."""

from pydantic import BaseModel
from datetime import datetime


class SupplierCreate(BaseModel):
    name: str
    contact_name: str | None = None
    phone: str | None = None
    zalo: str | None = None
    email: str | None = None
    address: str | None = None
    region: str | None = None
    category: str = "general"
    rating: float = 5.0
    notes: str | None = None


class SupplierUpdate(BaseModel):
    name: str | None = None
    contact_name: str | None = None
    phone: str | None = None
    zalo: str | None = None
    email: str | None = None
    address: str | None = None
    region: str | None = None
    category: str | None = None
    rating: float | None = None
    notes: str | None = None
    is_active: bool | None = None


class SupplierResponse(BaseModel):
    id: str
    name: str
    contact_name: str | None = None
    phone: str | None = None
    zalo: str | None = None
    email: str | None = None
    address: str | None = None
    region: str | None = None
    category: str
    rating: float
    notes: str | None = None
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class SupplierQuoteCreate(BaseModel):
    material_name: str
    material_category: str | None = None
    unit: str = "m2"
    unit_price: float
    min_quantity: float = 1
    lead_time_days: int | None = None
    notes: str | None = None


class SupplierQuoteResponse(BaseModel):
    id: str
    supplier_id: str
    material_name: str
    material_category: str | None = None
    unit: str
    unit_price: float
    min_quantity: float
    lead_time_days: int | None = None
    notes: str | None = None
    quote_date: datetime

    model_config = {"from_attributes": True}


class CompareRequest(BaseModel):
    materials: list[str]
