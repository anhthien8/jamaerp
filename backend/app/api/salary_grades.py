"""Salary Grade API — CRUD for bậc lương."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.auth import get_current_user
from app.models.user import User
from app.models.salary_grade import SalaryGrade

router = APIRouter(prefix="/salary-grades", tags=["salary-grades"])


def _require_admin(current_user: User = Depends(get_current_user)) -> User:
    if current_user.role not in ("admin", "accountant"):
        raise HTTPException(status_code=403, detail="Chỉ Admin/Kế toán mới có quyền quản lý bậc lương")
    return current_user


@router.get("")
async def list_grades(db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    result = await db.execute(select(SalaryGrade).order_by(SalaryGrade.base_salary))
    grades = result.scalars().all()
    return [
        {
            "id": g.id, "grade_name": g.grade_name, "base_salary": g.base_salary,
            "bhxh_rate": g.bhxh_rate, "bhxh_company_rate": g.bhxh_company_rate,
            "bhyt_rate": g.bhyt_rate, "bhtn_rate": g.bhtn_rate,
            "effective_date": str(g.effective_date), "created_at": str(g.created_at),
        }
        for g in grades
    ]


@router.post("")
async def create_grade(data: dict, db: AsyncSession = Depends(get_db), current_user: User = Depends(_require_admin)):
    import uuid
    from datetime import datetime, timezone
    grade = SalaryGrade(
        id=str(uuid.uuid4()),
        grade_name=data.get("grade_name", ""),
        base_salary=data.get("base_salary", 0),
        bhxh_rate=data.get("bhxh_rate", 10.5),
        bhxh_company_rate=data.get("bhxh_company_rate", 21.5),
        bhyt_rate=data.get("bhyt_rate", 1.5),
        bhtn_rate=data.get("bhtn_rate", 1.0),
        effective_date=data.get("effective_date", datetime.now(timezone.utc).date()),
    )
    db.add(grade)
    await db.flush()
    return {"id": grade.id, "grade_name": grade.grade_name, "base_salary": grade.base_salary}


@router.put("/{grade_id}")
async def update_grade(grade_id: str, data: dict, db: AsyncSession = Depends(get_db), current_user: User = Depends(_require_admin)):
    result = await db.execute(select(SalaryGrade).where(SalaryGrade.id == grade_id))
    grade = result.scalar_one_or_none()
    if not grade:
        raise HTTPException(status_code=404, detail="Bậc lương không tồn tại")
    for k, v in data.items():
        if hasattr(grade, k) and k not in ("id", "created_at"):
            setattr(grade, k, v)
    await db.flush()
    return {"id": grade.id, "grade_name": grade.grade_name, "base_salary": grade.base_salary}


@router.delete("/{grade_id}")
async def delete_grade(grade_id: str, db: AsyncSession = Depends(get_db), current_user: User = Depends(_require_admin)):
    result = await db.execute(select(SalaryGrade).where(SalaryGrade.id == grade_id))
    grade = result.scalar_one_or_none()
    if not grade:
        raise HTTPException(status_code=404, detail="Bậc lương không tồn tại")
    await db.delete(grade)
    await db.flush()
    return {"message": "Đã xóa bậc lương"}
