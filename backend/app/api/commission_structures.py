"""Commission Structure API — CRUD for cơ cấu hoa hồng."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.auth import get_current_user
from app.models.user import User
from app.models.commission_structure import CommissionStructure

router = APIRouter(prefix="/commission-structures", tags=["commission-structures"])


def _require_admin(current_user: User = Depends(get_current_user)) -> User:
    if current_user.role not in ("admin", "accountant"):
        raise HTTPException(status_code=403, detail="Chỉ Admin/Kế toán mới có quyền quản lý cơ cấu hoa hồng")
    return current_user


@router.get("")
async def list_structures(db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    result = await db.execute(select(CommissionStructure).order_by(CommissionStructure.department))
    structures = result.scalars().all()
    return [
        {
            "id": s.id, "department": s.department, "commission_type": s.commission_type,
            "rate": s.rate, "effective_date": str(s.effective_date), "created_at": str(s.created_at),
        }
        for s in structures
    ]


@router.post("")
async def create_structure(data: dict, db: AsyncSession = Depends(get_db), current_user: User = Depends(_require_admin)):
    import uuid
    from datetime import datetime, timezone
    structure = CommissionStructure(
        id=str(uuid.uuid4()),
        department=data.get("department", ""),
        commission_type=data.get("commission_type", ""),
        rate=data.get("rate", 0),
        effective_date=data.get("effective_date", datetime.now(timezone.utc).date()),
    )
    db.add(structure)
    await db.flush()
    return {"id": structure.id, "department": structure.department, "rate": structure.rate}


@router.put("/{structure_id}")
async def update_structure(structure_id: str, data: dict, db: AsyncSession = Depends(get_db), current_user: User = Depends(_require_admin)):
    result = await db.execute(select(CommissionStructure).where(CommissionStructure.id == structure_id))
    structure = result.scalar_one_or_none()
    if not structure:
        raise HTTPException(status_code=404, detail="Cơ cấu hoa hồng không tồn tại")
    for k, v in data.items():
        if hasattr(structure, k) and k not in ("id", "created_at"):
            setattr(structure, k, v)
    await db.flush()
    return {"id": structure.id, "department": structure.department, "rate": structure.rate}


@router.delete("/{structure_id}")
async def delete_structure(structure_id: str, db: AsyncSession = Depends(get_db), current_user: User = Depends(_require_admin)):
    result = await db.execute(select(CommissionStructure).where(CommissionStructure.id == structure_id))
    structure = result.scalar_one_or_none()
    if not structure:
        raise HTTPException(status_code=404, detail="Cơ cấu hoa hồng không tồn tại")
    await db.delete(structure)
    await db.flush()
    return {"message": "Đã xóa cơ cấu hoa hồng"}
