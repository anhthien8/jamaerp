"""Quotations API — CRUD with line items and approve workflow."""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.auth import get_current_user
from app.models.user import User
from app.models.quotation import Quotation
from app.schemas.quotation import QuotationCreate, QuotationUpdate, QuotationResponse

router = APIRouter(prefix="/quotations", tags=["quotations"])


@router.get("")
async def list_quotations(
    type: str | None = None,
    status: str | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
):
    """List quotations."""
    q = select(Quotation).order_by(Quotation.created_at.desc())
    if type:
        q = q.where(Quotation.type == type)
    if status:
        q = q.where(Quotation.status == status)

    # Count total (before pagination)
    count_q = select(func.count()).select_from(q.subquery())
    total = (await db.execute(count_q)).scalar() or 0

    q = q.offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(q)
    quotations = result.scalars().all()

    return {
        "items": [QuotationResponse.model_validate(qt) for qt in quotations],
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": (total + page_size - 1) // page_size,
    }


@router.get("/{quotation_id}", response_model=QuotationResponse)
async def get_quotation(
    quotation_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get quotation detail."""
    result = await db.execute(select(Quotation).where(Quotation.id == quotation_id))
    qt = result.scalar_one_or_none()
    if not qt:
        raise HTTPException(status_code=404, detail="Báo giá không tồn tại")
    return QuotationResponse.model_validate(qt)


@router.post("", response_model=QuotationResponse)
async def create_quotation(
    data: QuotationCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create new quotation."""
    # Convert line items to dict for JSON storage
    items_data = [item.model_dump() for item in data.items] if data.items else []
    
    # Auto-calculate total if not provided
    total = data.total_amount
    if not total and items_data:
        total = sum(item.get("total", item.get("quantity", 1) * item.get("unit_price", 0)) for item in items_data)

    qt = Quotation(
        code=data.code,
        type=data.type,
        project_id=str(data.project_id) if data.project_id else None,
        lead_id=str(data.lead_id) if data.lead_id else None,
        title=data.title,
        items={"line_items": items_data},
        total_amount=total,
        tax_amount=data.tax_amount,
        valid_until=data.valid_until,
        notes=data.notes,
        created_by=current_user.id,
        status="draft",
    )
    db.add(qt)
    await db.flush()
    return QuotationResponse.model_validate(qt)


@router.put("/{quotation_id}", response_model=QuotationResponse)
async def update_quotation(
    quotation_id: str,
    data: QuotationUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update quotation."""
    result = await db.execute(select(Quotation).where(Quotation.id == quotation_id))
    qt = result.scalar_one_or_none()
    if not qt:
        raise HTTPException(status_code=404, detail="Báo giá không tồn tại")

    update_data = data.model_dump(exclude_unset=True)
    if "items" in update_data and update_data["items"]:
        items_data = [item.model_dump() if hasattr(item, "model_dump") else item for item in update_data["items"]]
        qt.items = {"line_items": items_data}
        del update_data["items"]

    for k, v in update_data.items():
        setattr(qt, k, v)
    qt.updated_at = datetime.now(timezone.utc)
    await db.flush()
    return QuotationResponse.model_validate(qt)


@router.post("/{quotation_id}/approve", response_model=QuotationResponse)
async def approve_quotation(
    quotation_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Approve a quotation."""
    result = await db.execute(select(Quotation).where(Quotation.id == quotation_id))
    qt = result.scalar_one_or_none()
    if not qt:
        raise HTTPException(status_code=404, detail="Báo giá không tồn tại")
    if qt.status != "draft":
        raise HTTPException(status_code=400, detail=f"Không thể duyệt báo giá ở trạng thái {qt.status}")

    qt.status = "approved"
    qt.updated_at = datetime.now(timezone.utc)
    await db.flush()
    return QuotationResponse.model_validate(qt)
