"""Inventory schemas."""

from pydantic import BaseModel
from datetime import datetime


class MaterialCreate(BaseModel):
    code: str
    name: str
    category: str = "general"
    unit: str = "cái"
    unit_price: float = 0
    quantity_in_stock: float = 0
    min_stock: float = 0
    supplier: str | None = None
    notes: str | None = None


class MaterialUpdate(BaseModel):
    name: str | None = None
    category: str | None = None
    unit: str | None = None
    unit_price: float | None = None
    quantity_in_stock: float | None = None
    min_stock: float | None = None
    supplier: str | None = None
    notes: str | None = None


class MaterialResponse(BaseModel):
    id: str
    code: str
    name: str
    category: str
    unit: str
    unit_price: float
    quantity_in_stock: float
    min_stock: float
    supplier: str | None = None
    notes: str | None = None
    is_low_stock: bool = False
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class MaterialUsageCreate(BaseModel):
    material_id: str
    project_id: str
    quantity: float
    unit_price_at_use: float | None = None
    notes: str | None = None


class MaterialUsageResponse(BaseModel):
    id: str
    material_id: str
    project_id: str
    quantity: float
    unit_price_at_use: float
    total_cost: float
    date: datetime
    notes: str | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class StockAdjust(BaseModel):
    """Add or remove stock."""
    quantity: float
    reason: str = ""
