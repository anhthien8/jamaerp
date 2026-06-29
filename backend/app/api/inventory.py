"""Inventory API — materials CRUD, stock tracking, usage."""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.auth import get_current_user
from app.models.user import User
from app.models.inventory import Material, MaterialUsage
from app.schemas.inventory import (
    MaterialCreate, MaterialUpdate, MaterialResponse,
    MaterialUsageCreate, MaterialUsageResponse, StockAdjust,
)

router = APIRouter(prefix="/inventory", tags=["inventory"])


def verify_inventory_access(user: User = Depends(get_current_user)):
    if user.role not in ("admin", "purchasing") and user.department != "PURCHASING":
        raise HTTPException(
            status_code=403,
            detail="Không có quyền truy cập kho vật tư. Chỉ Admin và bộ phận Thu mua được phép xem."
        )
    return user


@router.get("")
async def list_materials(
    category: str | None = None,
    search: str | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(verify_inventory_access),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
):
    """List all materials."""
    q = select(Material).order_by(Material.name)
    if category:
        q = q.where(Material.category == category)
    if search:
        q = q.where(Material.name.ilike(f"%{search}%"))

    # Count total (before pagination)
    count_q = select(func.count()).select_from(q.subquery())
    total = (await db.execute(count_q)).scalar() or 0

    q = q.offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(q)
    materials = result.scalars().all()

    return {
        "items": [MaterialResponse.model_validate(m) for m in materials],
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": (total + page_size - 1) // page_size,
    }


@router.get("/low-stock")
async def low_stock_alerts(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(verify_inventory_access),
):
    """Materials with stock at or below minimum."""
    q = select(Material).where(Material.quantity_in_stock <= Material.min_stock)
    result = await db.execute(q)
    materials = result.scalars().all()
    return [
        {
            "id": m.id, "code": m.code, "name": m.name,
            "quantity_in_stock": m.quantity_in_stock, "min_stock": m.min_stock,
            "unit": m.unit, "category": m.category,
            "deficit": m.min_stock - m.quantity_in_stock,
        }
        for m in materials
    ]


@router.get("/{material_id}", response_model=MaterialResponse)
async def get_material(
    material_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(verify_inventory_access),
):
    """Get material detail."""
    result = await db.execute(select(Material).where(Material.id == material_id))
    m = result.scalar_one_or_none()
    if not m:
        raise HTTPException(status_code=404, detail="Vật tư không tồn tại")
    return MaterialResponse.model_validate(m)


@router.post("", response_model=MaterialResponse)
async def create_material(
    data: MaterialCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(verify_inventory_access),
):
    """Add new material."""
    m = Material(**data.model_dump())
    db.add(m)
    await db.flush()
    return MaterialResponse.model_validate(m)


@router.put("/{material_id}", response_model=MaterialResponse)
async def update_material(
    material_id: str,
    data: MaterialUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(verify_inventory_access),
):
    """Update material."""
    result = await db.execute(select(Material).where(Material.id == material_id))
    m = result.scalar_one_or_none()
    if not m:
        raise HTTPException(status_code=404, detail="Vật tư không tồn tại")

    for k, v in data.model_dump(exclude_unset=True).items():
        setattr(m, k, v)
    m.updated_at = datetime.now(timezone.utc)
    await db.flush()
    return MaterialResponse.model_validate(m)


@router.post("/{material_id}/adjust-stock", response_model=MaterialResponse)
async def adjust_stock(
    material_id: str,
    data: StockAdjust,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(verify_inventory_access),
):
    """Add or remove stock (positive = nhập, negative = xuất)."""
    result = await db.execute(select(Material).where(Material.id == material_id))
    m = result.scalar_one_or_none()
    if not m:
        raise HTTPException(status_code=404, detail="Vật tư không tồn tại")

    new_stock = m.quantity_in_stock + data.quantity
    if new_stock < 0:
        raise HTTPException(status_code=400, detail="Không đủ tồn kho")
    m.quantity_in_stock = new_stock
    m.updated_at = datetime.now(timezone.utc)
    await db.flush()
    return MaterialResponse.model_validate(m)


# --- Material Usage (xuất kho cho dự án) ---

@router.get("/{material_id}/usages")
async def list_usages(
    material_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(verify_inventory_access),
):
    """Usage history for a material."""
    q = select(MaterialUsage).where(
        MaterialUsage.material_id == material_id
    ).order_by(MaterialUsage.date.desc())
    result = await db.execute(q)
    usages = result.scalars().all()
    return [MaterialUsageResponse.model_validate(u) for u in usages]


@router.post("/use", response_model=MaterialUsageResponse)
async def record_usage(
    data: MaterialUsageCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(verify_inventory_access),
):
    """Record material usage for a project (auto-deducts stock)."""
    # Get material
    result = await db.execute(select(Material).where(Material.id == data.material_id))
    m = result.scalar_one_or_none()
    if not m:
        raise HTTPException(status_code=404, detail="Vật tư không tồn tại")

    if m.quantity_in_stock < data.quantity:
        raise HTTPException(status_code=400, detail=f"Tồn kho không đủ (còn {m.quantity_in_stock} {m.unit})")

    price = data.unit_price_at_use if data.unit_price_at_use else m.unit_price
    total = data.quantity * price

    usage = MaterialUsage(
        material_id=data.material_id,
        project_id=data.project_id,
        quantity=data.quantity,
        unit_price_at_use=price,
        total_cost=total,
        date=datetime.now(timezone.utc),
        notes=data.notes,
        created_by=current_user.id,
    )
    db.add(usage)

    # Deduct stock
    m.quantity_in_stock -= data.quantity
    m.updated_at = datetime.now(timezone.utc)

    await db.flush()
    return MaterialUsageResponse.model_validate(usage)
