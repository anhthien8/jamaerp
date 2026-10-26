"""Commission Structure API — CRUD for cơ cấu hoa hồng."""

from datetime import date, datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.auth import get_current_user
from app.middleware.permissions import yeu_cau
from app.models.user import User
from app.models.commission_structure import TRANG_THAI_CHO_DUYET, CommissionStructure
from app.services import approval_engine, hoa_hong


class CommissionStructureCreate(BaseModel):
    department: str = Field(min_length=1, max_length=100)
    commission_type: str = Field(min_length=1, max_length=50)
    rate: float = Field(ge=0, le=1)  # tỷ lệ: 0.03 = 3%
    effective_date: date | None = None


class CommissionStructureUpdate(BaseModel):
    department: str | None = Field(default=None, min_length=1, max_length=100)
    commission_type: str | None = Field(default=None, min_length=1, max_length=50)
    rate: float | None = Field(default=None, ge=0, le=1)
    effective_date: date | None = None

router = APIRouter(prefix="/commission-structures", tags=["commission-structures"])


def _require_admin(current_user: User = Depends(get_current_user)) -> User:
    if current_user.role not in ("admin", "accountant"):
        raise HTTPException(status_code=403, detail="Chỉ Admin/Kế toán mới có quyền quản lý cơ cấu hoa hồng")
    return current_user


@router.get("")
# Tỷ lệ hoa hồng theo phòng ban là dữ liệu tài chính nhạy cảm — trước 13/08/2026
# chỉ cần đăng nhập là đọc được. Cùng cửa P&L với chi phí.
async def list_structures(db: AsyncSession = Depends(get_db), current_user: User = Depends(yeu_cau("canViewPnL"))):
    result = await db.execute(select(CommissionStructure).order_by(CommissionStructure.department))
    structures = result.scalars().all()
    return [
        {
            "id": s.id, "department": s.department, "commission_type": s.commission_type,
            "rate": s.rate, "effective_date": str(s.effective_date), "created_at": str(s.created_at),
            "status": s.status, "approval_id": s.approval_id,
            "approved_at": str(s.approved_at) if s.approved_at else None,
        }
        for s in structures
    ]


@router.post("")
async def create_structure(data: CommissionStructureCreate, db: AsyncSession = Depends(get_db), current_user: User = Depends(_require_admin)):
    import uuid
    structure = CommissionStructure(
        id=str(uuid.uuid4()),
        department=data.department,
        commission_type=data.commission_type,
        rate=data.rate,
        effective_date=data.effective_date or datetime.now(timezone.utc).date(),
    )
    db.add(structure)
    await db.flush()
    # Mức mới chỉ có hiệu lực khi BGĐ duyệt — gửi duyệt luôn khi tạo
    await _gui_duyet(db, structure, current_user)
    return {"id": structure.id, "department": structure.department, "rate": structure.rate, "status": structure.status}


async def _gui_duyet(db: AsyncSession, structure: CommissionStructure, actor: User) -> None:
    try:
        await hoa_hong.gui_duyet(db, structure, actor)
    except approval_engine.ApprovalError as err:
        raise HTTPException(status_code=err.status_code, detail=err.detail)


def _chi_sua_khi_cho_duyet(structure: CommissionStructure) -> None:
    """Mức đã duyệt/từ chối là lịch sử — đổi mức thì tạo dòng mới với ngày hiệu lực mới."""
    if structure.status != TRANG_THAI_CHO_DUYET:
        raise HTTPException(
            status_code=400,
            detail="Mức này đã được BGĐ xử lý, không sửa/xóa được. Muốn đổi mức hãy thêm mức mới kèm ngày hiệu lực.",
        )
    # Đang chờ duyệt mà sửa thì BGĐ duyệt nhầm con số khác với con số trên đơn
    if structure.approval_id:
        raise HTTPException(status_code=400, detail="Mức này đang chờ BGĐ duyệt — nhờ BGĐ từ chối rồi tạo mức mới")


@router.post("/{structure_id}/gui-duyet")
async def gui_lai_duyet(structure_id: str, db: AsyncSession = Depends(get_db), current_user: User = Depends(_require_admin)):
    """Gửi BGĐ duyệt cho dòng chưa có đơn (dữ liệu cũ trước 26/10/2026)."""
    structure = await db.get(CommissionStructure, structure_id)
    if not structure:
        raise HTTPException(status_code=404, detail="Cơ cấu hoa hồng không tồn tại")
    _chi_sua_khi_cho_duyet(structure)
    await _gui_duyet(db, structure, current_user)
    return {"id": structure.id, "status": structure.status, "approval_id": structure.approval_id}


@router.put("/{structure_id}")
async def update_structure(structure_id: str, data: CommissionStructureUpdate, db: AsyncSession = Depends(get_db), current_user: User = Depends(_require_admin)):
    result = await db.execute(select(CommissionStructure).where(CommissionStructure.id == structure_id))
    structure = result.scalar_one_or_none()
    if not structure:
        raise HTTPException(status_code=404, detail="Cơ cấu hoa hồng không tồn tại")
    _chi_sua_khi_cho_duyet(structure)
    for k, v in data.model_dump(exclude_unset=True).items():
        if hasattr(structure, k):
            setattr(structure, k, v)
    await db.flush()
    return {"id": structure.id, "department": structure.department, "rate": structure.rate}


@router.delete("/{structure_id}")
async def delete_structure(structure_id: str, db: AsyncSession = Depends(get_db), current_user: User = Depends(_require_admin)):
    result = await db.execute(select(CommissionStructure).where(CommissionStructure.id == structure_id))
    structure = result.scalar_one_or_none()
    if not structure:
        raise HTTPException(status_code=404, detail="Cơ cấu hoa hồng không tồn tại")
    _chi_sua_khi_cho_duyet(structure)
    await db.delete(structure)
    await db.flush()
    return {"message": "Đã xóa cơ cấu hoa hồng"}
