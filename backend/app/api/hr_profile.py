"""Hồ sơ nhân viên 360° (dựng 09/09/2026) — profile/HĐLĐ/CCCD, giấy tờ JPG,
toàn bộ vết tiền + công + phép + bàn giao + nhật ký của MỘT nhân viên.

Phân quyền (chốt 09/09/2026):
- Hồ sơ + giấy tờ: admin/kế toán sửa; chính chủ XEM của mình.
- Tab Tiền: CHỈ admin + kế toán (và chính chủ xem của mình) — không mở cho
  trưởng phòng, tránh lặp lại lỗ hở lương đã vá 13/08.
- Chấm công/nghỉ phép: thêm trưởng nhóm/phòng trong phạm vi team mình.
- Bàn giao: admin/kế toán. Nhật ký (audit): chỉ admin.
"""

import base64
import binascii

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.auth import get_current_user
from app.middleware.rbac import is_team_lead
from app.models.attendance import AttendanceRecord  # noqa: F401 — dùng qua service
from app.models.employee_profile import EmployeeDocument, EmployeeProfile
from app.models.handover import HandoverRecord
from app.models.leave import LeaveBalance, LeaveRequest
from app.models.payroll import Commission, Payroll, SalaryAdvance, Transaction
from app.models.user import User
from app.services.attendance_service import month_records, month_summary, period_of, vn_today
from app.services.audit import log_action, query_logs

router = APIRouter(prefix="/hr/employees", tags=["hr-profile"])

# JPG nén phía client ≤ ~500KB; trần server nới nhẹ để không chặn oan file sát mép
MAX_DOC_BYTES = 700_000
ALLOWED_MIMES = {"image/jpeg", "image/png"}
DOC_TYPES = {"cccd_front", "cccd_back", "contract", "other"}
CONTRACT_TYPES = {"probation", "fixed_1y", "fixed_2y", "indefinite"}


# ---------------------------------------------------------------------------
# Phạm vi truy cập
# ---------------------------------------------------------------------------

async def _get_target(db: AsyncSession, user_id: str) -> User:
    target = await db.get(User, user_id)
    if not target:
        raise HTTPException(status_code=404, detail="Nhân viên không tồn tại")
    return target


def _is_hr(user: User) -> bool:
    return user.role in ("admin", "accountant")


def _require_hr_or_self(current: User, target: User) -> None:
    if not (_is_hr(current) or current.id == target.id):
        raise HTTPException(status_code=403, detail="Không có quyền xem hồ sơ nhân viên này")


def _require_hr(current: User) -> None:
    if not _is_hr(current):
        raise HTTPException(status_code=403, detail="Chỉ admin/kế toán-nhân sự mới có quyền này")


def _require_attendance_scope(current: User, target: User) -> None:
    """Công/phép: admin, kế toán, chính chủ, hoặc trưởng nhóm/phòng cùng team."""
    if _is_hr(current) or current.id == target.id:
        return
    if is_team_lead(current) and current.team_id and target.team_id == current.team_id:
        return
    raise HTTPException(status_code=403, detail="Không có quyền xem chấm công của nhân viên này")


# ---------------------------------------------------------------------------
# Hồ sơ + HĐLĐ
# ---------------------------------------------------------------------------

class ProfileBody(BaseModel):
    national_id: str | None = Field(default=None, max_length=20)
    national_id_issued_date: str | None = None   # yyyy-mm-dd
    national_id_issued_place: str | None = Field(default=None, max_length=100)
    date_of_birth: str | None = None
    address: str | None = Field(default=None, max_length=255)
    emergency_contact: str | None = Field(default=None, max_length=200)
    bank_account: str | None = Field(default=None, max_length=30)
    bank_name: str | None = Field(default=None, max_length=100)
    social_insurance_no: str | None = Field(default=None, max_length=20)
    hire_date: str | None = None
    contract_type: str | None = None
    contract_signed_date: str | None = None
    contract_end_date: str | None = None
    note: str | None = Field(default=None, max_length=500)


_DATE_FIELDS = {
    "national_id_issued_date", "date_of_birth", "hire_date",
    "contract_signed_date", "contract_end_date",
}


def _parse_date(value: str | None, field: str):
    from datetime import date as date_cls

    if value in (None, ""):
        return None
    try:
        return date_cls.fromisoformat(value)
    except ValueError:
        raise HTTPException(status_code=422, detail=f"{field} phải là ngày dạng yyyy-mm-dd")


def _profile_dict(p: EmployeeProfile | None) -> dict:
    if not p:
        return {}
    return {
        "national_id": p.national_id,
        "national_id_issued_date": str(p.national_id_issued_date) if p.national_id_issued_date else None,
        "national_id_issued_place": p.national_id_issued_place,
        "date_of_birth": str(p.date_of_birth) if p.date_of_birth else None,
        "address": p.address,
        "emergency_contact": p.emergency_contact,
        "bank_account": p.bank_account,
        "bank_name": p.bank_name,
        "social_insurance_no": p.social_insurance_no,
        "hire_date": str(p.hire_date) if p.hire_date else None,
        "contract_type": p.contract_type,
        "contract_signed_date": str(p.contract_signed_date) if p.contract_signed_date else None,
        "contract_end_date": str(p.contract_end_date) if p.contract_end_date else None,
        "note": p.note,
    }


async def _get_profile(db: AsyncSession, user_id: str) -> EmployeeProfile | None:
    result = await db.execute(select(EmployeeProfile).where(EmployeeProfile.user_id == user_id))
    return result.scalar_one_or_none()


@router.get("/{user_id}/profile")
async def get_employee_profile(
    user_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    target = await _get_target(db, user_id)
    # Trưởng nhóm/phòng cùng team được mở TRANG hồ sơ của lính (xem công/phép)
    # nhưng chỉ nhận header — KHÔNG CCCD/ngân hàng/giấy tờ (finding vòng phản biện:
    # trước đây họ bấm vào nhân viên ở trang Nhân sự là ăn nguyên banner 403).
    if not (_is_hr(current_user) or current_user.id == target.id):
        _require_attendance_scope(current_user, target)
        return {
            "user": {
                "id": target.id, "full_name": target.full_name, "email": target.email,
                "phone": target.phone, "role": target.role, "department": target.department,
                "team_id": target.team_id, "is_active": target.is_active,
                "resign_date": str(target.resign_date) if target.resign_date else None,
            },
            "profile": {},
            "documents": [],
            "can_edit": False,
            "limited": True,
        }
    profile = await _get_profile(db, user_id)
    docs = (
        await db.execute(
            select(EmployeeDocument).where(EmployeeDocument.user_id == user_id).order_by(EmployeeDocument.created_at)
        )
    ).scalars().all()
    return {
        "user": {
            "id": target.id,
            "full_name": target.full_name,
            "email": target.email,
            "phone": target.phone,
            "role": target.role,
            "department": target.department,
            "team_id": target.team_id,
            "is_active": target.is_active,
            "resign_date": str(target.resign_date) if target.resign_date else None,
        },
        "profile": _profile_dict(profile),
        "documents": [
            {
                "id": d.id, "doc_type": d.doc_type, "filename": d.filename,
                "mime": d.mime, "size_bytes": d.size_bytes,
                "uploaded_by_name": d.uploaded_by_name, "created_at": str(d.created_at),
            }
            for d in docs
        ],
        "can_edit": _is_hr(current_user),
    }


@router.put("/{user_id}/profile")
async def update_employee_profile(
    user_id: str,
    body: ProfileBody,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_hr(current_user)
    target = await _get_target(db, user_id)
    if body.contract_type not in (None, "") and body.contract_type not in CONTRACT_TYPES:
        raise HTTPException(status_code=422, detail="contract_type không hợp lệ")

    profile = await _get_profile(db, user_id)
    if not profile:
        profile = EmployeeProfile(user_id=user_id)
        db.add(profile)

    before = _profile_dict(profile)
    data = body.model_dump()
    for field, value in data.items():
        if field in _DATE_FIELDS:
            setattr(profile, field, _parse_date(value, field))
        else:
            setattr(profile, field, value or None)
    await db.flush()

    await log_action(
        db, actor=current_user, action="employee_profile.update", entity_type="user",
        entity_id=target.id, before=before, after=_profile_dict(profile),
    )
    return {"profile": _profile_dict(profile)}


# ---------------------------------------------------------------------------
# Giấy tờ (JPG nén phía client — CCCD, HĐLĐ scan)
# ---------------------------------------------------------------------------

class DocumentBody(BaseModel):
    doc_type: str
    filename: str = Field(..., max_length=200)
    mime: str = Field(default="image/jpeg", max_length=50)
    data_base64: str  # JPG đã resize/nén ở FE (canvas, cạnh dài ≤1600px)


@router.post("/{user_id}/documents")
async def upload_document(
    user_id: str,
    body: DocumentBody,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_hr(current_user)
    target = await _get_target(db, user_id)
    if body.doc_type not in DOC_TYPES:
        raise HTTPException(status_code=422, detail="doc_type không hợp lệ")
    if body.mime not in ALLOWED_MIMES:
        raise HTTPException(status_code=422, detail="Chỉ nhận ảnh JPG/PNG")
    try:
        raw = base64.b64decode(body.data_base64, validate=True)
    except (binascii.Error, ValueError):
        raise HTTPException(status_code=422, detail="data_base64 không hợp lệ")
    if not raw:
        raise HTTPException(status_code=422, detail="File rỗng")
    if len(raw) > MAX_DOC_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"File quá lớn ({len(raw)//1024}KB > {MAX_DOC_BYTES//1000}KB) — app tự nén khi chọn ảnh, thử chọn lại",
        )

    doc = EmployeeDocument(
        user_id=user_id, doc_type=body.doc_type, filename=body.filename,
        mime=body.mime, size_bytes=len(raw), data=raw,
        uploaded_by=current_user.id, uploaded_by_name=current_user.full_name,
    )
    db.add(doc)
    await db.flush()
    await log_action(
        db, actor=current_user, action="employee_document.upload", entity_type="user",
        entity_id=target.id, after={"doc_type": body.doc_type, "filename": body.filename, "size": len(raw)},
    )
    return {"id": doc.id, "doc_type": doc.doc_type, "filename": doc.filename, "size_bytes": doc.size_bytes}


@router.get("/{user_id}/documents/{doc_id}")
async def get_document(
    user_id: str,
    doc_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    target = await _get_target(db, user_id)
    _require_hr_or_self(current_user, target)
    doc = await db.get(EmployeeDocument, doc_id)
    if not doc or doc.user_id != user_id:
        raise HTTPException(status_code=404, detail="Giấy tờ không tồn tại")
    return {
        "id": doc.id, "doc_type": doc.doc_type, "filename": doc.filename, "mime": doc.mime,
        "data_base64": base64.b64encode(doc.data).decode(),
    }


@router.delete("/{user_id}/documents/{doc_id}")
async def delete_document(
    user_id: str,
    doc_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_hr(current_user)
    target = await _get_target(db, user_id)
    doc = await db.get(EmployeeDocument, doc_id)
    if not doc or doc.user_id != user_id:
        raise HTTPException(status_code=404, detail="Giấy tờ không tồn tại")
    await db.delete(doc)
    await db.flush()
    await log_action(
        db, actor=current_user, action="employee_document.delete", entity_type="user",
        entity_id=target.id, after={"doc_type": doc.doc_type, "filename": doc.filename},
    )
    return {"deleted": True}


# ---------------------------------------------------------------------------
# Tab Tiền — CHỈ admin + kế toán (chính chủ xem của mình)
# ---------------------------------------------------------------------------

@router.get("/{user_id}/finance")
async def employee_finance(
    user_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    target = await _get_target(db, user_id)
    _require_hr_or_self(current_user, target)

    payrolls = (
        await db.execute(
            select(Payroll).where(Payroll.user_id == user_id).order_by(Payroll.period.desc())
        )
    ).scalars().all()
    commissions = (
        await db.execute(
            select(Commission).where(Commission.user_id == user_id).order_by(Commission.created_at.desc()).limit(200)
        )
    ).scalars().all()
    advances = (
        await db.execute(
            select(SalaryAdvance).where(SalaryAdvance.user_id == user_id).order_by(SalaryAdvance.created_at.desc())
        )
    ).scalars().all()
    transactions = (
        await db.execute(
            select(Transaction)
            .where(Transaction.related_user_id == user_id, Transaction.status != "cancelled")
            .order_by(Transaction.date.desc())
            .limit(200)
        )
    ).scalars().all()

    return {
        "payrolls": [
            {
                "id": p.id, "period": p.period, "status": p.status,
                "base_salary": p.base_salary, "commission_total": p.commission_total,
                "bonus": p.bonus, "allowance": p.allowance, "ot_pay": p.ot_pay,
                "work_days": p.work_days, "gross": p.gross, "net": p.net,
                "advance_deduction": p.advance_deduction,
                "paid_at": str(p.paid_at) if p.paid_at else None,
            }
            for p in payrolls
        ],
        "commissions": [
            {
                "id": c.id, "type": c.type, "amount": c.commission_amount, "status": c.status,
                "milestone": c.milestone, "period": c.period, "project_id": c.project_id,
                "created_at": str(c.created_at),
            }
            for c in commissions
        ],
        "advances": [
            {
                "id": a.id, "amount": a.amount, "reason": a.reason, "status": a.status,
                "period_deducted": a.period_deducted, "created_at": str(a.created_at),
            }
            for a in advances
        ],
        "transactions": [
            {
                "id": t.id, "type": t.type, "category": t.category, "amount": t.amount,
                "description": t.description, "transaction_date": str(t.date),
                "status": t.status,
            }
            for t in transactions
        ],
        "totals": {
            "net_paid": sum(p.net or 0 for p in payrolls if p.status == "paid"),
            "commission_paid": sum(c.commission_amount or 0 for c in commissions if c.status == "paid"),
            "commission_pending": sum(c.commission_amount or 0 for c in commissions if c.status in ("pending", "approved")),
            "advance_open": sum(a.amount or 0 for a in advances if a.status == "approved"),
        },
    }


# ---------------------------------------------------------------------------
# Chấm công + nghỉ phép của MỘT nhân viên (thêm phạm vi trưởng nhóm)
# ---------------------------------------------------------------------------

@router.get("/{user_id}/attendance")
async def employee_attendance(
    user_id: str,
    period: str = Query(default=None, pattern=r"^\d{4}-\d{2}$"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    target = await _get_target(db, user_id)
    _require_attendance_scope(current_user, target)
    period = period or period_of(vn_today())
    records = await month_records(db, user_id, period)
    summary = await month_summary(db, user_id, period)
    from app.api.attendance import _serialize  # tái dùng serializer chuẩn

    return {"summary": summary, "records": [_serialize(r) for r in records]}


@router.get("/{user_id}/leaves")
async def employee_leaves(
    user_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    target = await _get_target(db, user_id)
    _require_attendance_scope(current_user, target)
    year = vn_today().year
    balance = (
        await db.execute(
            select(LeaveBalance).where(LeaveBalance.user_id == user_id, LeaveBalance.year == year)
        )
    ).scalar_one_or_none()
    requests = (
        await db.execute(
            select(LeaveRequest).where(LeaveRequest.user_id == user_id).order_by(LeaveRequest.created_at.desc()).limit(100)
        )
    ).scalars().all()
    return {
        "balance": {
            "year": year,
            "annual_total": balance.annual_total if balance else 12,
            "annual_used": balance.annual_used if balance else 0,
            "sick_used": balance.sick_used if balance else 0,
            "unpaid_used": balance.unpaid_used if balance else 0,
        },
        "requests": [
            {
                "id": r.id, "leave_type": r.leave_type, "start_date": str(r.start_date),
                "end_date": str(r.end_date), "days": r.days, "reason": r.reason,
                "status": r.status, "created_at": str(r.created_at),
            }
            for r in requests
        ],
    }


# ---------------------------------------------------------------------------
# Bàn giao + nhật ký
# ---------------------------------------------------------------------------

@router.get("/{user_id}/handovers")
async def employee_handovers(
    user_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_hr(current_user)
    await _get_target(db, user_id)

    def _row(h: HandoverRecord) -> dict:
        return {
            "id": h.id, "entity_type": h.entity_type, "entity_id": h.entity_id,
            "entity_name": h.entity_name, "reason": h.reason,
            "from_user_name": h.from_user_name, "to_user_name": h.to_user_name,
            "actor_name": h.actor_name, "created_at": str(h.created_at),
        }

    given = (
        await db.execute(
            select(HandoverRecord).where(HandoverRecord.from_user_id == user_id).order_by(HandoverRecord.created_at.desc())
        )
    ).scalars().all()
    received = (
        await db.execute(
            select(HandoverRecord).where(HandoverRecord.to_user_id == user_id).order_by(HandoverRecord.created_at.desc())
        )
    ).scalars().all()
    return {"given": [_row(h) for h in given], "received": [_row(h) for h in received]}


@router.get("/{user_id}/audit")
async def employee_audit(
    user_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Chỉ quản trị viên xem được nhật ký")
    await _get_target(db, user_id)
    logs = await query_logs(db, entity_type="user", entity_id=user_id, page_size=100)
    return {
        "items": [
            {
                "id": l.id, "action": l.action, "actor_name": l.actor_name,
                "note": l.note, "created_at": str(l.created_at),
            }
            for l in logs
        ]
    }
