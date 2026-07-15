"""Salary Grade API — CRUD for bậc lương."""

from datetime import date, datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.auth import get_current_user
from app.models.user import User
from app.models.salary_grade import SalaryGrade
from app.services.audit import log_action


class SalaryGradeCreate(BaseModel):
    grade_name: str = Field(min_length=1, max_length=100)
    base_salary: float = Field(ge=0)
    bhxh_rate: float = Field(default=10.5, ge=0, le=100)
    bhxh_company_rate: float = Field(default=21.5, ge=0, le=100)
    bhyt_rate: float = Field(default=1.5, ge=0, le=100)
    bhtn_rate: float = Field(default=1.0, ge=0, le=100)
    effective_date: date | None = None


class SalaryGradeUpdate(BaseModel):
    grade_name: str | None = Field(default=None, min_length=1, max_length=100)
    base_salary: float | None = Field(default=None, ge=0)
    bhxh_rate: float | None = Field(default=None, ge=0, le=100)
    bhxh_company_rate: float | None = Field(default=None, ge=0, le=100)
    bhyt_rate: float | None = Field(default=None, ge=0, le=100)
    bhtn_rate: float | None = Field(default=None, ge=0, le=100)
    effective_date: date | None = None

router = APIRouter(prefix="/salary-grades", tags=["salary-grades"])


def _require_admin(current_user: User = Depends(get_current_user)) -> User:
    if current_user.role not in ("admin", "accountant"):
        raise HTTPException(status_code=403, detail="Chỉ Admin/Kế toán mới có quyền quản lý bậc lương")
    return current_user


@router.get("")
async def list_grades(db: AsyncSession = Depends(get_db), current_user: User = Depends(_require_admin)):
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
async def create_grade(data: SalaryGradeCreate, db: AsyncSession = Depends(get_db), current_user: User = Depends(_require_admin)):
    import uuid
    grade = SalaryGrade(
        id=str(uuid.uuid4()),
        grade_name=data.grade_name,
        base_salary=data.base_salary,
        bhxh_rate=data.bhxh_rate,
        bhxh_company_rate=data.bhxh_company_rate,
        bhyt_rate=data.bhyt_rate,
        bhtn_rate=data.bhtn_rate,
        effective_date=data.effective_date or datetime.now(timezone.utc).date(),
    )
    db.add(grade)
    await db.flush()
    return {"id": grade.id, "grade_name": grade.grade_name, "base_salary": grade.base_salary}


@router.put("/{grade_id}")
async def update_grade(grade_id: str, data: SalaryGradeUpdate, db: AsyncSession = Depends(get_db), current_user: User = Depends(_require_admin)):
    result = await db.execute(select(SalaryGrade).where(SalaryGrade.id == grade_id))
    grade = result.scalar_one_or_none()
    if not grade:
        raise HTTPException(status_code=404, detail="Bậc lương không tồn tại")
    provided = data.model_dump(exclude_unset=True)
    before = {k: getattr(grade, k) for k in provided if hasattr(grade, k)}
    for k, v in provided.items():
        if hasattr(grade, k):
            setattr(grade, k, v)
    await db.flush()
    await log_action(
        db, actor=current_user, action="salary_grade.update", entity_type="salary_grade",
        entity_id=grade.id, before=before, after=provided,
    )
    return {"id": grade.id, "grade_name": grade.grade_name, "base_salary": grade.base_salary}


@router.delete("/{grade_id}")
async def delete_grade(grade_id: str, db: AsyncSession = Depends(get_db), current_user: User = Depends(_require_admin)):
    result = await db.execute(select(SalaryGrade).where(SalaryGrade.id == grade_id))
    grade = result.scalar_one_or_none()
    if not grade:
        raise HTTPException(status_code=404, detail="Bậc lương không tồn tại")
    await log_action(
        db, actor=current_user, action="salary_grade.delete", entity_type="salary_grade",
        entity_id=grade.id, before={"grade_name": grade.grade_name, "base_salary": grade.base_salary},
    )
    await db.delete(grade)
    await db.flush()
    return {"message": "Đã xóa bậc lương"}
