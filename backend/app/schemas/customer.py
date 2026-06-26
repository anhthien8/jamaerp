"""Customer schemas."""

from pydantic import BaseModel
from datetime import datetime


class CustomerCreate(BaseModel):
    name: str
    phone: str
    email: str | None = None
    address: str | None = None
    type: str = "individual"
    tax_code: str | None = None
    company_name: str | None = None
    lead_id: str | None = None
    notes: str | None = None


class CustomerUpdate(BaseModel):
    name: str | None = None
    phone: str | None = None
    email: str | None = None
    address: str | None = None
    type: str | None = None
    tax_code: str | None = None
    company_name: str | None = None
    notes: str | None = None


class CustomerResponse(BaseModel):
    id: str
    name: str
    phone: str
    email: str | None = None
    address: str | None = None
    type: str
    tax_code: str | None = None
    company_name: str | None = None
    lead_id: str | None = None
    notes: str | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
