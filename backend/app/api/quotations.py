"""Quotations API — CRUD with line items and approve workflow."""

import random
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.auth import get_current_user
from app.middleware.permissions import quyen_hieu_luc
from app.middleware.rbac import can_approve_quotation
from app.models.user import User
from app.models.quotation import Quotation
from app.schemas.quotation import QuotationCreate, QuotationUpdate, QuotationResponse

router = APIRouter(prefix="/quotations", tags=["quotations"])


async def _yeu_cau_quyen_bao_gia(current_user: User, db: AsyncSession) -> None:
    """Chặn ai không có «Tạo Báo giá» (canCreateQuotations) khỏi mọi thao tác GHI."""
    perms = await quyen_hieu_luc(current_user, db)
    if not perms.get("canCreateQuotations"):
        raise HTTPException(status_code=403, detail="Không có quyền tạo/sửa báo giá")


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
    # Backend PHẢI tự gác, không dựa nút bị ẩn trên FE: kế toán là «Đọc» báo giá
    # theo ma trận quyền lẫn tài liệu công ty, nhưng endpoint trước đây cho mọi
    # tài khoản đăng nhập tạo/sửa báo giá (QC 29/08 gọi thử bằng token kế toán → 200).
    await _yeu_cau_quyen_bao_gia(current_user, db)
    # Convert line items to dict for JSON storage
    items_data = [item.model_dump() for item in data.items] if data.items else []

    # Auto-calculate total if not provided
    total = data.total_amount
    if not total and items_data:
        total = sum(item.get("total", item.get("quantity", 1) * item.get("unit_price", 0)) for item in items_data)

    year = datetime.now(timezone.utc).year
    code = data.code
    if not code:
        for _attempt in range(100):
            candidate = f"BG-{year}-{random.randint(1000, 9999)}"
            exists = (await db.execute(select(Quotation).where(Quotation.code == candidate))).scalar_one_or_none()
            if not exists:
                code = candidate
                break
        if not code:
            code = f"BG-{year}-{uuid.uuid4().hex[:8]}"

    qt = Quotation(
        code=code,
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

    # Check-then-insert ở trên không nguyên tử: 2 request cùng lúc có thể bốc trùng mã
    # (unique của cột code sẽ chặn ở tầng DB). Bắt lại và bốc mã khác trong savepoint
    # thay vì nổ 500; mã do người dùng tự nhập mà trùng thì báo 409 tử tế.
    for _retry in range(3):
        try:
            async with db.begin_nested():
                db.add(qt)
                await db.flush()
            break
        except IntegrityError:
            if data.code:
                raise HTTPException(status_code=409, detail=f"Mã báo giá {data.code} đã tồn tại — chọn mã khác")
            qt.code = f"BG-{year}-{uuid.uuid4().hex[:8]}"
    else:
        raise HTTPException(status_code=500, detail="Không sinh được mã báo giá, thử lưu lại lần nữa")

    return QuotationResponse.model_validate(qt)


@router.put("/{quotation_id}", response_model=QuotationResponse)
async def update_quotation(
    quotation_id: str,
    data: QuotationUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update quotation."""
    await _yeu_cau_quyen_bao_gia(current_user, db)
    result = await db.execute(select(Quotation).where(Quotation.id == quotation_id))
    qt = result.scalar_one_or_none()
    if not qt:
        raise HTTPException(status_code=404, detail="Báo giá không tồn tại")

    update_data = data.model_dump(exclude_unset=True)
    if "items" in update_data:
        # Nhận cả mảng RỖNG: người dùng xóa hết hạng mục rồi lưu là hợp lệ.
        # Trước 15/08/2026 điều kiện `and update_data["items"]` làm [] lọt thẳng
        # vào setattr → qt.items thành list → QuotationResponse (items: dict) nổ 500.
        items_value = update_data.pop("items")
        if items_value is not None:
            items_data = [item.model_dump() if hasattr(item, "model_dump") else item for item in items_value]
            qt.items = {"line_items": items_data}

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
    # Duyệt là quyền của cấp trên, KHÁC quyền soạn — sale không tự duyệt bản mình.
    if not can_approve_quotation(current_user):
        raise HTTPException(status_code=403, detail="Chỉ Giám đốc / Trưởng nhóm / Giám sát được duyệt báo giá")
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
