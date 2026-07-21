"""Accounting schemas — Transaction, Payroll, Commission."""

from datetime import datetime, date
from decimal import Decimal
from uuid import UUID
from pydantic import AliasChoices, BaseModel, Field


# ── Transaction ────────────────────────────────────────

class TransactionCreate(BaseModel):
    type: str  # income / expense
    category: str  # salary, commission, material, design_fee, misc
    amount: Decimal
    project_id: UUID | None = None
    contract_id: UUID | None = None
    user_id: UUID | None = None
    description: str | None = None
    reference: str | None = None
    # FE gửi key 'date'; bản cũ bắt buộc 'transaction_date' → mọi lần tạo giao dịch
    # work mode đều 422 (bug tiềm ẩn, lộ ra khi audit 22/07). Nhận cả 2 tên, cho phép trống.
    transaction_date: date | None = Field(default=None, validation_alias=AliasChoices("transaction_date", "date"))


class TransactionUpdate(BaseModel):
    type: str | None = None
    category: str | None = None
    amount: Decimal | None = None
    project_id: UUID | None = None
    contract_id: UUID | None = None
    description: str | None = None
    reference: str | None = None
    transaction_date: date | None = None
    status: str | None = None


class TransactionResponse(BaseModel):
    id: UUID
    code: str
    type: str
    category: str
    amount: Decimal
    project_id: UUID | None = None
    contract_id: UUID | None = None
    user_id: UUID | None = None
    description: str | None = None
    reference: str | None = None
    transaction_date: date
    status: str
    created_at: datetime
    # Joined names
    project_name: str | None = None
    user_name: str | None = None

    class Config:
        from_attributes = True


class AccountingSummary(BaseModel):
    period: str
    total_income: Decimal
    total_expense: Decimal
    net_profit: Decimal
    by_category: dict[str, Decimal]


# ── Payroll ────────────────────────────────────────────

class PayrollCreate(BaseModel):
    user_id: UUID
    period: str  # "2026-06"
    base_salary: Decimal | None = None
    allowances: dict | None = None
    deductions: dict | None = None
    bonus: Decimal = Decimal(0)
    notes: str | None = None


class PayrollResponse(BaseModel):
    id: UUID
    user_id: UUID
    period: str
    base_salary: Decimal
    allowances: dict | None = None
    deductions: dict | None = None
    commission_total: Decimal
    bonus: Decimal
    net_salary: Decimal
    status: str
    approved_by: UUID | None = None
    paid_at: datetime | None = None
    notes: str | None = None
    created_at: datetime
    # Joined
    user_name: str | None = None
    user_role: str | None = None
    user_department: str | None = None
    commission_details: list[dict] | None = None

    class Config:
        from_attributes = True


# ── Commission ─────────────────────────────────────────

class CommissionCreate(BaseModel):
    user_id: UUID
    project_id: UUID | None = None
    lead_id: UUID | None = None
    type: str
    rate: Decimal
    base_amount: Decimal
    milestone: str = "signing"
    milestone_pct: float = 1.0
    status: str = "pending"
    period: str | None = None


class CommissionStatusUpdate(BaseModel):
    status: str | None = None


class CommissionCalculateRequest(BaseModel):
    period: str  # "2026-06"


class CommissionResponse(BaseModel):
    id: UUID
    user_id: UUID
    contract_id: UUID
    project_id: UUID | None = None
    contract_value: Decimal
    commission_rate: Decimal
    commission_amount: Decimal
    milestone: str | None = None
    status: str
    payroll_id: UUID | None = None
    period: str | None = None
    notes: str | None = None
    created_at: datetime
    # Joined
    user_name: str | None = None
    contract_code: str | None = None
    project_name: str | None = None

    class Config:
        from_attributes = True
