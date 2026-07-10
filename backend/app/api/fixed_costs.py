"""Fixed Cost API — CRUD for chi phí định phí."""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.auth import get_current_user
from app.models.user import User
from app.models.fixed_cost import FixedCost


class FixedCostCreate(BaseModel):
    category: str = Field(min_length=1, max_length=200)
    amount: float = Field(ge=0)
    month: str = Field(min_length=1, max_length=10)
    notes: str | None = None


class FixedCostUpdate(BaseModel):
    category: str | None = Field(default=None, min_length=1, max_length=200)
    amount: float | None = Field(default=None, ge=0)
    month: str | None = Field(default=None, min_length=1, max_length=10)
    notes: str | None = None

router = APIRouter(prefix="/fixed-costs", tags=["fixed-costs"])


def _require_finance(current_user: User = Depends(get_current_user)) -> User:
    if current_user.role not in ("admin", "accountant"):
        raise HTTPException(status_code=403, detail="Chỉ Admin/Kế toán mới có quyền quản lý chi phí")
    return current_user


@router.get("")
async def list_fixed_costs(
    month: str = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    q = select(FixedCost).order_by(FixedCost.category)
    if month:
        q = q.where(FixedCost.month == month)
    result = await db.execute(q)
    costs = result.scalars().all()
    return [
        {
            "id": c.id, "category": c.category, "amount": c.amount,
            "month": c.month, "notes": c.notes, "created_at": str(c.created_at),
        }
        for c in costs
    ]


@router.post("")
async def create_fixed_cost(data: FixedCostCreate, db: AsyncSession = Depends(get_db), current_user: User = Depends(_require_finance)):
    import uuid
    cost = FixedCost(
        id=str(uuid.uuid4()),
        category=data.category,
        amount=data.amount,
        month=data.month,
        notes=data.notes,
        created_by=current_user.id,
    )
    db.add(cost)
    await db.flush()
    return {"id": cost.id, "category": cost.category, "amount": cost.amount}


@router.put("/{cost_id}")
async def update_fixed_cost(cost_id: str, data: FixedCostUpdate, db: AsyncSession = Depends(get_db), current_user: User = Depends(_require_finance)):
    result = await db.execute(select(FixedCost).where(FixedCost.id == cost_id))
    cost = result.scalar_one_or_none()
    if not cost:
        raise HTTPException(status_code=404, detail="Chi phí không tồn tại")
    for k, v in data.model_dump(exclude_unset=True).items():
        if hasattr(cost, k):
            setattr(cost, k, v)
    await db.flush()
    return {"id": cost.id, "category": cost.category, "amount": cost.amount}


@router.delete("/{cost_id}")
async def delete_fixed_cost(cost_id: str, db: AsyncSession = Depends(get_db), current_user: User = Depends(_require_finance)):
    result = await db.execute(select(FixedCost).where(FixedCost.id == cost_id))
    cost = result.scalar_one_or_none()
    if not cost:
        raise HTTPException(status_code=404, detail="Chi phí không tồn tại")
    await db.delete(cost)
    await db.flush()
    return {"message": "Đã xóa chi phí"}
