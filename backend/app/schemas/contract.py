"""Contract schemas."""

from pydantic import BaseModel
from datetime import datetime, date


class ContractCreate(BaseModel):
    code: str
    project_id: str
    title: str
    total_value: float | None = None
    signed_date: date | None = None
    working_days: int | None = None
    start_date: date | None = None
    notes: str | None = None


class ContractUpdate(BaseModel):
    title: str | None = None
    status: str | None = None
    total_value: float | None = None
    signed_date: date | None = None
    working_days: int | None = None
    start_date: date | None = None
    notes: str | None = None


class ContractResponse(BaseModel):
    id: str
    code: str
    project_id: str
    quotation_id: str | None = None
    title: str
    status: str
    total_value: float | None = None
    payment_terms: dict | None = None
    signed_date: date | None = None
    working_days: int | None = None
    start_date: date | None = None
    notes: str | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class PaymentUpdate(BaseModel):
    """Update a payment installment status."""
    status: str = "paid"  # pending, paid
    paid_date: date | None = None
    amount: float | None = None
    evidence_url: str | None = None
