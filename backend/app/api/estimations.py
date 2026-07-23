"""Estimations API — Dự toán cải tạo.

- POST /estimations: tạo dự toán mới (auto-populate từ renovation template)
- GET /estimations: danh sách (filter theo project)
- GET /estimations/{id}: chi tiết dự toán + items
- PUT /estimations/{id}/items: cập nhật số lượng hàng loạt
- POST /estimations/{id}/submit: chuyển trạng thái → submitted
- POST /estimations/{id}/from-text: tạo từ mô tả text
- POST /estimations/{id}/from-photo: placeholder cho upload ảnh
"""

import json
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.auth import get_current_user
from app.models.user import User
from app.models.estimation import Estimation, EstimationItem
from app.services.instant_quote import RENO_TEMPLATE, _parse_qty_formula, RENO_CATEGORIES

router = APIRouter(prefix="/estimations", tags=["estimations"])


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class EstimationCreate(BaseModel):
    project_id: str | None = None
    floor_count: int = Field(default=3, ge=1, le=4)
    area_sqm: float = Field(default=80, gt=0, le=500)
    description: str | None = None


class ItemQuantityUpdate(BaseModel):
    item_id: str
    quantity: float = Field(ge=0)


class BulkItemUpdate(BaseModel):
    items: list[ItemQuantityUpdate]


class TextEstimationRequest(BaseModel):
    text: str = Field(min_length=5, max_length=2000)
    floor_count: int = Field(default=3, ge=1, le=4)
    area_sqm: float = Field(default=80, gt=0, le=500)


class PhotoEstimationRequest(BaseModel):
    photo_url: str = Field(min_length=1, max_length=500)
    floor_count: int = Field(default=3, ge=1, le=4)
    area_sqm: float = Field(default=80, gt=0, le=500)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _filter_reno_items_by_floor(items: list[tuple], floors: int) -> list[tuple]:
    """Lọc renovation template items theo số tầng."""
    result = []
    for item in items:
        code = item[0]
        if "-2-" in code and floors < 2:
            continue
        if "-3-" in code and floors < 3:
            continue
        if code.startswith("CF-R-") and floors < 3:
            continue
        result.append(item)
    return result


def _populate_items(estimation_id: str, area_sqm: float, floors: int) -> list[EstimationItem]:
    """Tạo estimation items từ renovation template."""
    items = _filter_reno_items_by_floor(RENO_TEMPLATE, floors)
    result = []
    for code, name, category, unit, unit_price, formula, note in items:
        qty = _parse_qty_formula(formula, area_sqm, floors)
        if qty <= 0:
            continue
        line_total = round(qty * unit_price)
        result.append(EstimationItem(
            estimation_id=estimation_id,
            template_code=code,
            name=name,
            category=category,
            unit=unit,
            quantity=qty,
            unit_price=unit_price,
            total=line_total,
            notes=note,
        ))
    return result


async def _recalc_totals(db: AsyncSession, estimation_id: str) -> tuple[float, int]:
    """Recalculate total_estimate và item_count cho estimation."""
    result = await db.execute(
        select(EstimationItem).where(EstimationItem.estimation_id == estimation_id)
    )
    items = result.scalars().all()
    total = sum(i.total for i in items)
    count = len(items)
    return round(total), count


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post("", status_code=201)
async def create_estimation(
    payload: EstimationCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Tạo dự toán mới — tự động populate items từ renovation template."""
    estimation = Estimation(
        project_id=payload.project_id,
        estimation_type="manual",
        description=payload.description,
        floor_count=payload.floor_count,
        area_sqm=payload.area_sqm,
        created_by=current_user.id,
    )
    db.add(estimation)
    await db.flush()

    # Auto-populate items from renovation template
    items = _populate_items(estimation.id, payload.area_sqm, payload.floor_count)
    for item in items:
        db.add(item)
    await db.flush()

    # Recalculate totals
    total, count = await _recalc_totals(db, estimation.id)
    estimation.total_estimate = total
    estimation.item_count = count
    await db.flush()

    return {
        "id": estimation.id,
        "floor_count": estimation.floor_count,
        "area_sqm": estimation.area_sqm,
        "total_estimate": estimation.total_estimate,
        "item_count": estimation.item_count,
        "status": estimation.status,
        "created_at": estimation.created_at.isoformat(),
    }


@router.get("")
async def list_estimations(
    project_id: str | None = None,
    status: str | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
):
    """Danh sách dự toán — filter theo project_id hoặc status."""
    q = select(Estimation).order_by(Estimation.created_at.desc())
    if project_id:
        q = q.where(Estimation.project_id == project_id)
    if status:
        q = q.where(Estimation.status == status)

    count_q = select(func.count()).select_from(q.subquery())
    total = (await db.execute(count_q)).scalar() or 0

    q = q.offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(q)
    estimations = result.scalars().all()

    return {
        "items": [
            {
                "id": e.id,
                "project_id": e.project_id,
                "estimation_type": e.estimation_type,
                "floor_count": e.floor_count,
                "area_sqm": e.area_sqm,
                "total_estimate": e.total_estimate,
                "item_count": e.item_count,
                "status": e.status,
                "created_by": e.created_by,
                "created_at": e.created_at.isoformat() if e.created_at else None,
            }
            for e in estimations
        ],
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": (total + page_size - 1) // page_size,
    }


@router.get("/{estimation_id}")
async def get_estimation(
    estimation_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Chi tiết dự toán kèm items."""
    result = await db.execute(select(Estimation).where(Estimation.id == estimation_id))
    estimation = result.scalar_one_or_none()
    if not estimation:
        raise HTTPException(status_code=404, detail="Dự toán không tồn tại")

    items_result = await db.execute(
        select(EstimationItem)
        .where(EstimationItem.estimation_id == estimation_id)
        .order_by(EstimationItem.template_code)
    )
    items = items_result.scalars().all()

    # Group items by category
    categories: dict[str, list[dict]] = {}
    for item in items:
        cat_label = RENO_CATEGORIES.get(item.category, item.category)
        if cat_label not in categories:
            categories[cat_label] = []
        categories[cat_label].append({
            "id": item.id,
            "template_code": item.template_code,
            "name": item.name,
            "category": item.category,
            "unit": item.unit,
            "quantity": item.quantity,
            "unit_price": item.unit_price,
            "total": item.total,
            "notes": item.notes,
        })

    return {
        "id": estimation.id,
        "project_id": estimation.project_id,
        "estimation_type": estimation.estimation_type,
        "description": estimation.description,
        "photo_urls": json.loads(estimation.photo_urls) if estimation.photo_urls else None,
        "floor_count": estimation.floor_count,
        "area_sqm": estimation.area_sqm,
        "total_estimate": estimation.total_estimate,
        "item_count": estimation.item_count,
        "status": estimation.status,
        "created_by": estimation.created_by,
        "created_at": estimation.created_at.isoformat() if estimation.created_at else None,
        "updated_at": estimation.updated_at.isoformat() if estimation.updated_at else None,
        "categories": categories,
    }


@router.put("/{estimation_id}/items")
async def update_estimation_items(
    estimation_id: str,
    payload: BulkItemUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Cập nhật số lượng hàng loạt cho items trong dự toán."""
    result = await db.execute(select(Estimation).where(Estimation.id == estimation_id))
    estimation = result.scalar_one_or_none()
    if not estimation:
        raise HTTPException(status_code=404, detail="Dự toán không tồn tại")
    if estimation.status != "draft":
        raise HTTPException(status_code=400, detail="Chỉ cập nhật được dự toán ở trạng thái draft")

    updated_count = 0
    for item_update in payload.items:
        item_result = await db.execute(
            select(EstimationItem).where(
                EstimationItem.id == item_update.item_id,
                EstimationItem.estimation_id == estimation_id,
            )
        )
        item = item_result.scalar_one_or_none()
        if item:
            item.quantity = item_update.quantity
            item.total = round(item.quantity * item.unit_price)
            updated_count += 1

    await db.flush()

    # Recalculate totals
    total, count = await _recalc_totals(db, estimation_id)
    estimation.total_estimate = total
    estimation.item_count = count
    await db.flush()

    return {
        "status": "ok",
        "updated_items": updated_count,
        "total_estimate": estimation.total_estimate,
        "item_count": estimation.item_count,
    }


@router.post("/{estimation_id}/submit")
async def submit_estimation(
    estimation_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Chuyển dự toán sang trạng thái submitted."""
    result = await db.execute(select(Estimation).where(Estimation.id == estimation_id))
    estimation = result.scalar_one_or_none()
    if not estimation:
        raise HTTPException(status_code=404, detail="Dự toán không tồn tại")
    if estimation.status != "draft":
        raise HTTPException(status_code=400, detail=f"Không thể gửi dự toán ở trạng thái {estimation.status}")

    estimation.status = "submitted"
    estimation.updated_at = datetime.now(timezone.utc)
    await db.flush()

    return {
        "status": "ok",
        "id": estimation.id,
        "new_status": estimation.status,
    }


@router.post("/{estimation_id}/from-text")
async def create_from_text(
    estimation_id: str,
    payload: TextEstimationRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Tạo dự toán từ mô tả text — parse text, gợi ý items phù hợp."""
    result = await db.execute(select(Estimation).where(Estimation.id == estimation_id))
    estimation = result.scalar_one_or_none()
    if not estimation:
        raise HTTPException(status_code=404, detail="Dự toán không tồn tại")
    if estimation.status != "draft":
        raise HTTPException(status_code=400, detail="Chỉ cập nhật được dự toán ở trạng thái draft")

    # Update estimation with text data
    estimation.estimation_type = "text"
    estimation.description = payload.text
    estimation.floor_count = payload.floor_count
    estimation.area_sqm = payload.area_sqm

    # Clear old items and repopulate
    old_items = await db.execute(
        select(EstimationItem).where(EstimationItem.estimation_id == estimation_id)
    )
    for item in old_items.scalars().all():
        await db.delete(item)
    await db.flush()

    # Auto-populate items from renovation template
    items = _populate_items(estimation_id, payload.area_sqm, payload.floor_count)
    for item in items:
        db.add(item)
    await db.flush()

    # Recalculate totals
    total, count = await _recalc_totals(db, estimation_id)
    estimation.total_estimate = total
    estimation.item_count = count
    await db.flush()

    return {
        "status": "ok",
        "id": estimation.id,
        "estimation_type": "text",
        "total_estimate": estimation.total_estimate,
        "item_count": estimation.item_count,
        "note": "Items được tự động gợi ý từ mô tả. Vui lòng cập nhật số lượng theo thực tế.",
    }


@router.post("/{estimation_id}/from-photo")
async def create_from_photo(
    estimation_id: str,
    payload: PhotoEstimationRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Tạo dự toán từ ảnh — placeholder, lưu URL ảnh và gợi ý items."""
    result = await db.execute(select(Estimation).where(Estimation.id == estimation_id))
    estimation = result.scalar_one_or_none()
    if not estimation:
        raise HTTPException(status_code=404, detail="Dự toán không tồn tại")
    if estimation.status != "draft":
        raise HTTPException(status_code=400, detail="Chỉ cập nhật được dự toán ở trạng thái draft")

    # Update estimation with photo data
    estimation.estimation_type = "photo"
    existing_urls = json.loads(estimation.photo_urls) if estimation.photo_urls else []
    existing_urls.append(payload.photo_url)
    estimation.photo_urls = json.dumps(existing_urls)
    estimation.floor_count = payload.floor_count
    estimation.area_sqm = payload.area_sqm

    # Clear old items and repopulate
    old_items = await db.execute(
        select(EstimationItem).where(EstimationItem.estimation_id == estimation_id)
    )
    for item in old_items.scalars().all():
        await db.delete(item)
    await db.flush()

    # Auto-populate items from renovation template
    items = _populate_items(estimation_id, payload.area_sqm, payload.floor_count)
    for item in items:
        db.add(item)
    await db.flush()

    # Recalculate totals
    total, count = await _recalc_totals(db, estimation_id)
    estimation.total_estimate = total
    estimation.item_count = count
    await db.flush()

    return {
        "status": "ok",
        "id": estimation.id,
        "estimation_type": "photo",
        "photo_urls": existing_urls,
        "total_estimate": estimation.total_estimate,
        "item_count": estimation.item_count,
        "note": "Ảnh đã lưu. Items được tự động gợi ý. Vui lòng cập nhật số lượng theo thực tế.",
    }
