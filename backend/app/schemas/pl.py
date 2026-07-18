"""P&L (Profit & Loss) schemas."""

from __future__ import annotations

from pydantic import BaseModel


class PLCostCategory(BaseModel):
    """Cost breakdown by category within a project."""
    category: str
    total: float = 0.0
    count: int = 0


class PLProjectItem(BaseModel):
    """Per-project P&L line item."""
    project_id: str
    project_code: str
    project_name: str
    revenue: float = 0.0
    cost_material: float = 0.0
    cost_transaction: float = 0.0
    total_cost: float = 0.0
    profit: float = 0.0
    margin: float = 0.0


class PLProjectDetail(PLProjectItem):
    """Detailed P&L for one project with cost breakdown by category."""
    cost_by_category: list[PLCostCategory] = []
    # Ngân sách kế hoạch (nếu đã nhập) — so với total_cost để cảnh báo vượt
    budget_total: float | None = None


class PLSummary(BaseModel):
    """Company-wide P&L summary."""
    total_revenue: float = 0.0
    total_cost_material: float = 0.0
    total_cost_transaction: float = 0.0
    total_cost: float = 0.0
    net_profit: float = 0.0
    margin: float = 0.0
    project_count: int = 0
