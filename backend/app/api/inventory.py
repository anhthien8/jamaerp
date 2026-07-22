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

def _escape_like(term: str) -> str:
    return term.replace("%", "\\%").replace("_", "\\_")


# ── Import báo giá/danh sách vật tư từ file (CSV parse ở FE, gửi rows JSON) ──
from pydantic import BaseModel, Field

VALID_CATEGORIES = {"wood", "stone", "metal", "paint", "electrical", "plumbing", "furniture", "fabric", "glass", "general"}
# Thu mua điền file bằng nhãn Việt → map về key hệ thống
CATEGORY_VN_MAP = {
    "gỗ": "wood", "go": "wood",
    "đá": "stone", "da": "stone",
    "kim loại": "metal", "kim loai": "metal",
    "sơn": "paint", "son": "paint",
    "điện": "electrical", "dien": "electrical",
    "nước": "plumbing", "nuoc": "plumbing",
    "phụ kiện nội thất": "furniture", "nội thất": "furniture", "noi that": "furniture",
    "vải": "fabric", "vai": "fabric",
    "kính": "glass", "kinh": "glass",
    "khác": "general", "khac": "general", "chung": "general",
}


class MaterialImportRow(BaseModel):
    code: str | None = None
    name: str
    category: str | None = None
    unit: str | None = None
    unit_price: float | None = Field(default=None, ge=0)
    supplier: str | None = None
    quantity_in_stock: float | None = Field(default=None, ge=0)
    min_stock: float | None = Field(default=None, ge=0)


class MaterialImportRequest(BaseModel):
    rows: list[MaterialImportRow]


router = APIRouter(prefix="/inventory", tags=["inventory"])


def verify_inventory_access(user: User = Depends(get_current_user)):
    if user.role not in ("admin", "supervisor", "accountant") and user.department != "PURCHASING":
        raise HTTPException(
            status_code=403,
            detail="Không có quyền truy cập kho vật tư"
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
        escaped = _escape_like(search)
        q = q.where(Material.name.ilike(f"%{escaped}%", escape="\\"))

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


@router.post("/import")
async def import_materials(
    data: MaterialImportRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(verify_inventory_access),
):
    """Import hàng loạt vật tư/báo giá NCC từ file (đã parse ở FE).

    Upsert: khớp theo Mã (code) trước, không có mã thì khớp theo Tên;
    dòng mới tự sinh mã VT-xxx. Chỉ ghi đè các cột có giá trị trong file.
    """
    if not data.rows:
        raise HTTPException(status_code=400, detail="File không có dòng dữ liệu nào")
    if len(data.rows) > 500:
        raise HTTPException(status_code=400, detail="Tối đa 500 dòng mỗi lần import")

    existing = (await db.execute(select(Material))).scalars().all()
    by_code = {m.code.strip().upper(): m for m in existing if m.code}
    by_name = {m.name.strip().lower(): m for m in existing}
    # Sinh mã mới tiếp nối dãy VT-xxx hiện có
    max_num = 0
    for c in by_code:
        if c.startswith("VT-") and c[3:].isdigit():
            max_num = max(max_num, int(c[3:]))

    created, updated, errors = 0, 0, []
    now = datetime.now(timezone.utc)
    for i, row in enumerate(data.rows, start=2):  # dòng 1 của file là tiêu đề
        name = (row.name or "").strip()
        if not name:
            errors.append(f"Dòng {i}: thiếu Tên vật tư")
            continue
        category = None
        if row.category:
            raw = row.category.strip().lower()
            category = raw if raw in VALID_CATEGORIES else CATEGORY_VN_MAP.get(raw)
            if category is None:
                errors.append(f"Dòng {i}: danh mục '{row.category}' không hợp lệ (dùng: Gỗ, Đá, Kim loại, Sơn, Điện, Nước, Phụ kiện nội thất, Vải, Kính, Khác)")
                continue

        code_key = (row.code or "").strip().upper()
        target = by_code.get(code_key) if code_key else by_name.get(name.lower())
        if target:
            if category is not None:
                target.category = category
            if row.unit:
                target.unit = row.unit.strip()
            if row.unit_price is not None:
                target.unit_price = row.unit_price
            if row.supplier:
                target.supplier = row.supplier.strip()
            if row.quantity_in_stock is not None:
                target.quantity_in_stock = row.quantity_in_stock
            if row.min_stock is not None:
                target.min_stock = row.min_stock
            target.updated_at = now
            updated += 1
        else:
            if code_key and code_key in by_code:
                code = code_key  # không xảy ra (đã match ở trên) — giữ nhánh cho rõ
            elif code_key:
                code = code_key
            else:
                max_num += 1
                code = f"VT-{max_num:03d}"
                while code.upper() in by_code:
                    max_num += 1
                    code = f"VT-{max_num:03d}"
            m = Material(
                code=code,
                name=name,
                category=category or "general",
                unit=(row.unit or "cái").strip(),
                unit_price=row.unit_price or 0,
                supplier=(row.supplier or "").strip() or None,
                quantity_in_stock=row.quantity_in_stock or 0,
                min_stock=row.min_stock or 0,
            )
            db.add(m)
            by_code[code.upper()] = m
            by_name[name.lower()] = m
            created += 1

    await db.flush()
    return {"created": created, "updated": updated, "errors": errors, "total": len(data.rows)}


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
