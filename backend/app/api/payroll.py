"""Payroll API — bảng lương tự động, duyệt 2 cấp, phiếu lương riêng tư, tạm ứng.

Luồng kỳ lương:
    generate (accountant) → draft
    submit   (accountant) → pending_approval + tạo ApprovalRequest cho admin
    admin approve (qua Approval Center) → approved (KHÓA KỲ — cấm sửa công/hoa hồng kỳ đó)
    pay      (accountant) → paid + gửi phiếu lương Telegram chat riêng từng người
"""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.auth import get_current_user
from app.models.approval import ApprovalRequest
from app.models.payroll import Commission, Payroll, SalaryAdvance
from app.models.user import User
from app.services import approval_engine, payroll_engine
from app.services.approval_engine import ApprovalError
from app.services.audit import log_action

router = APIRouter(prefix="/payroll", tags=["payroll"])

PERIOD_PATTERN = r"^\d{4}-\d{2}$"


class RowUpdateBody(BaseModel):
    bonus: float | None = Field(default=None, ge=0)
    allowance: float | None = Field(default=None, ge=0)
    deductions: float | None = Field(default=None, ge=0)
    notes: str | None = Field(default=None, max_length=500)


class AdvanceCreateBody(BaseModel):
    amount: float = Field(..., gt=0)
    reason: str = Field(..., min_length=3, max_length=500)


class SettingsBody(BaseModel):
    pit_personal_deduction: float | None = Field(default=None, ge=0)
    pit_dependent_deduction: float | None = Field(default=None, ge=0)
    bhxh_salary_cap: float | None = Field(default=None, ge=0)
    payroll_standard_days: float | None = Field(default=None, gt=0, le=31)
    ot_multiplier: float | None = Field(default=None, ge=1, le=3)


def _require_accountant(current_user: User) -> None:
    if current_user.role not in ("admin", "accountant"):
        raise HTTPException(status_code=403, detail="Chỉ Kế toán/Admin mới có quyền thao tác bảng lương")


def _serialize(row: Payroll, extra: dict | None = None) -> dict:
    data = {
        "id": row.id,
        "user_id": row.user_id,
        "period": row.period,
        "base_salary": row.base_salary,
        "work_days": row.work_days,
        "standard_days": row.standard_days,
        "ot_hours": row.ot_hours,
        "ot_pay": row.ot_pay,
        "commission_total": row.commission_total,
        "bonus": row.bonus,
        "allowance": row.allowance,
        "gross_salary": row.gross_salary,
        "bhxh_employee": row.bhxh_employee,
        "bhxh_company": row.bhxh_company,
        "taxable_income": row.taxable_income,
        "pit": row.pit,
        "advance_deduction": row.advance_deduction,
        "deductions": row.deductions,
        "net_salary": row.net_salary,
        "status": row.status,
        "notes": row.notes,
        "paid_at": str(row.paid_at) if row.paid_at else None,
        "payslip_sent_at": str(row.payslip_sent_at) if row.payslip_sent_at else None,
    }
    if extra:
        data.update(extra)
    return data


def _recompute_net(row: Payroll) -> None:
    """Tính lại gross/taxable/PIT/net sau khi kế toán sửa bonus/allowance/deductions."""
    # Lưu ý: chỉnh sửa chỉ được phép ở trạng thái draft
    row.gross_salary = round(
        row.base_salary * min(row.work_days / row.standard_days, 1.0)
        + row.ot_pay + row.commission_total + row.bonus + row.allowance
    )


async def _refresh_tax(db: AsyncSession, row: Payroll, user: User) -> None:
    settings = await payroll_engine.get_payroll_settings(db)
    taxable = max(
        0.0,
        row.gross_salary - row.bhxh_employee - settings["pit_personal_deduction"]
        - user.dependents_count * settings["pit_dependent_deduction"],
    )
    row.taxable_income = round(taxable)
    row.pit = payroll_engine.compute_pit(taxable)
    row.net_salary = round(
        row.gross_salary - row.bhxh_employee - row.pit - row.advance_deduction - row.deductions
    )


# ---------------------------------------------------------------------------
# Side-effects: duyệt kỳ lương qua Approval Center
# ---------------------------------------------------------------------------

async def _on_payroll_approved(db: AsyncSession, request: ApprovalRequest) -> None:
    period = request.ref_id
    result = await db.execute(
        select(Payroll).where(Payroll.period == period, Payroll.status == "pending_approval")
    )
    for row in result.scalars().all():
        row.status = "approved"
        row.approved_by = request.current_approver_id
    await db.flush()


async def _on_payroll_rejected(db: AsyncSession, request: ApprovalRequest) -> None:
    period = request.ref_id
    result = await db.execute(
        select(Payroll).where(Payroll.period == period, Payroll.status == "pending_approval")
    )
    for row in result.scalars().all():
        row.status = "draft"
    await db.flush()


approval_engine.register_side_effect("payroll_period", _on_payroll_approved)
approval_engine.register_reject_effect("payroll_period", _on_payroll_rejected)


# ---------------------------------------------------------------------------
# Kỳ lương
# ---------------------------------------------------------------------------

@router.post("/generate")
async def generate(
    period: str = Query(..., pattern=PERIOD_PATTERN),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_accountant(current_user)
    try:
        result = await payroll_engine.generate_period(db, period)
    except ValueError as err:
        raise HTTPException(status_code=409, detail=str(err))
    await log_action(
        db, actor=current_user, action="payroll.generate", entity_type="payroll",
        entity_id=period, after=result,
    )
    return result


@router.get("")
async def list_period(
    period: str = Query(..., pattern=PERIOD_PATTERN),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_accountant(current_user)
    result = await db.execute(
        select(Payroll, User.full_name, User.role)
        .join(User, User.id == Payroll.user_id)
        .where(Payroll.period == period)
        .order_by(User.full_name)
    )
    rows = result.all()
    items = [_serialize(r, {"full_name": name, "role": role}) for r, name, role in rows]
    return {
        "period": period,
        "items": items,
        "total_net": round(sum(r.net_salary for r, _, _ in rows)),
        "total_company_cost": round(sum(r.gross_salary + r.bhxh_company for r, _, _ in rows)),
        "status": items[0]["status"] if items else None,
    }


@router.patch("/rows/{row_id}")
async def update_row(
    row_id: str,
    body: RowUpdateBody,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Kế toán bổ sung thưởng/phụ cấp/khấu trừ — chỉ khi kỳ còn draft."""
    _require_accountant(current_user)
    row = await db.get(Payroll, row_id)
    if not row:
        raise HTTPException(status_code=404, detail="Dòng lương không tồn tại")
    if row.status != "draft":
        raise HTTPException(status_code=409, detail=f"Kỳ đã {row.status} — không thể sửa")

    user = await db.get(User, row.user_id)
    before = {"bonus": row.bonus, "allowance": row.allowance, "deductions": row.deductions}
    provided = body.model_dump(exclude_unset=True)
    for k in ("bonus", "allowance", "deductions"):
        if k in provided and provided[k] is not None:
            setattr(row, k, provided[k])
    if "notes" in provided:
        row.notes = provided["notes"]

    _recompute_net(row)
    await _refresh_tax(db, row, user)
    await db.flush()

    await log_action(
        db, actor=current_user, action="payroll.edit_row", entity_type="payroll",
        entity_id=row.id, before=before,
        after={k: getattr(row, k) for k in ("bonus", "allowance", "deductions", "net_salary")},
    )
    return {"row": _serialize(row)}


@router.post("/{period}/submit")
async def submit(
    period: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_accountant(current_user)
    result = await db.execute(
        select(Payroll).where(Payroll.period == period, Payroll.status == "draft")
    )
    rows = list(result.scalars().all())
    if not rows:
        raise HTTPException(status_code=400, detail=f"Kỳ {period} không có dòng draft nào để submit")

    total_net = round(sum(r.net_salary for r in rows))
    for row in rows:
        row.status = "pending_approval"
    await db.flush()

    # Admin duyệt kỳ lương (1 cấp — kế toán đã là người lập)
    admin_result = await db.execute(
        select(User).where(User.role == "admin", User.is_active == True).limit(1)  # noqa: E712
    )
    admin = admin_result.scalar_one_or_none()
    if not admin:
        raise HTTPException(status_code=400, detail="Hệ thống chưa có admin để duyệt lương")

    try:
        approval = await approval_engine.create_request(
            db,
            type_="payroll_period",
            ref_id=period,
            title=f"Bảng lương kỳ {period}: {len(rows)} nhân viên, tổng thực lĩnh {total_net:,.0f}đ",
            requester=current_user,
            approver_ids=[admin.id],
            amount=total_net,
            sla_hours=72,
        )
    except ApprovalError as err:
        raise HTTPException(status_code=err.status_code, detail=err.detail)

    await log_action(
        db, actor=current_user, action="payroll.submit", entity_type="payroll",
        entity_id=period, after={"rows": len(rows), "total_net": total_net},
    )
    return {"period": period, "rows": len(rows), "total_net": total_net, "approval_id": approval.id}


@router.post("/{period}/pay")
async def pay(
    period: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Đánh dấu đã chi + gửi phiếu lương chat riêng từng người."""
    _require_accountant(current_user)
    result = await db.execute(
        select(Payroll).where(Payroll.period == period, Payroll.status == "approved")
    )
    rows = list(result.scalars().all())
    if not rows:
        raise HTTPException(status_code=409, detail=f"Kỳ {period} chưa được admin duyệt (hoặc đã chi)")

    now = datetime.now(timezone.utc)
    for row in rows:
        row.status = "paid"
        row.paid_at = now

    # Tạm ứng đã trừ trong kỳ → chốt deducted
    adv_result = await db.execute(
        select(SalaryAdvance).where(
            SalaryAdvance.status == "approved",
            SalaryAdvance.period_deducted == period,
        )
    )
    for advance in adv_result.scalars().all():
        advance.status = "deducted"
        advance.resolved_at = now

    # Hoa hồng của kỳ → paid
    comm_result = await db.execute(
        select(Commission).where(Commission.period == period, Commission.status == "approved")
    )
    for commission in comm_result.scalars().all():
        commission.status = "paid"

    await db.flush()

    payslips = await payroll_engine.send_payslips(db, period)

    await log_action(
        db, actor=current_user, action="payroll.pay", entity_type="payroll",
        entity_id=period, after={"rows": len(rows), **payslips},
    )
    return {"period": period, "paid_rows": len(rows), **payslips}


@router.post("/{period}/resend-payslips")
async def resend_payslips(
    period: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Gửi lại phiếu lương cho người chưa nhận (mới link Telegram sau kỳ chi)."""
    _require_accountant(current_user)
    payslips = await payroll_engine.send_payslips(db, period)
    return {"period": period, **payslips}


@router.get("/me")
async def my_payslips(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Phiếu lương của CHÍNH TÔI — chỉ các kỳ đã chi (paid)."""
    result = await db.execute(
        select(Payroll).where(
            Payroll.user_id == current_user.id,
            Payroll.status == "paid",
        ).order_by(Payroll.period.desc()).limit(24)
    )
    return {"items": [_serialize(r) for r in result.scalars().all()]}


# ---------------------------------------------------------------------------
# Tạm ứng lương
# ---------------------------------------------------------------------------

async def _on_advance_approved(db: AsyncSession, request: ApprovalRequest) -> None:
    advance = await db.get(SalaryAdvance, request.ref_id)
    if advance and advance.status == "pending":
        advance.status = "approved"
        await db.flush()


async def _on_advance_rejected(db: AsyncSession, request: ApprovalRequest) -> None:
    advance = await db.get(SalaryAdvance, request.ref_id)
    if advance and advance.status == "pending":
        advance.status = "rejected" if request.status == "rejected" else "cancelled"
        advance.resolved_at = datetime.now(timezone.utc)
        await db.flush()


approval_engine.register_side_effect("advance", _on_advance_approved)
approval_engine.register_reject_effect("advance", _on_advance_rejected)

ADVANCE_ADMIN_THRESHOLD = 5_000_000  # >5tr cần thêm admin duyệt


@router.post("/advance")
async def create_advance(
    body: AdvanceCreateBody,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # Giới hạn 30% lương bậc (nếu có bậc)
    if current_user.salary_grade_id:
        from app.models.salary_grade import SalaryGrade
        grade = await db.get(SalaryGrade, current_user.salary_grade_id)
        if grade and body.amount > grade.base_salary * 0.3:
            raise HTTPException(
                status_code=400,
                detail=f"Tạm ứng tối đa 30% lương cơ bản ({grade.base_salary * 0.3:,.0f}đ)",
            )

    # Không cho tạo khi còn tạm ứng chưa trừ
    existing = await db.execute(
        select(SalaryAdvance).where(
            SalaryAdvance.user_id == current_user.id,
            SalaryAdvance.status.in_(("pending", "approved")),
        ).limit(1)
    )
    if existing.first():
        raise HTTPException(status_code=409, detail="Bạn còn khoản tạm ứng chưa xử lý xong")

    advance = SalaryAdvance(user_id=current_user.id, amount=body.amount, reason=body.reason)
    db.add(advance)
    await db.flush()

    # Chuỗi duyệt: kế toán (+ admin nếu >5tr). Kế toán tự xin → admin duyệt.
    acct_result = await db.execute(
        select(User).where(User.role == "accountant", User.is_active == True).limit(1)  # noqa: E712
    )
    accountant = acct_result.scalar_one_or_none()
    admin_result = await db.execute(
        select(User).where(User.role == "admin", User.is_active == True).limit(1)  # noqa: E712
    )
    admin = admin_result.scalar_one_or_none()

    chain: list[str] = []
    if accountant and accountant.id != current_user.id:
        chain.append(accountant.id)
    if body.amount > ADVANCE_ADMIN_THRESHOLD or not chain:
        if admin and admin.id not in chain:
            chain.append(admin.id)

    try:
        approval = await approval_engine.create_request(
            db,
            type_="advance",
            ref_id=advance.id,
            title=f"Tạm ứng {body.amount:,.0f}đ — {current_user.full_name}",
            requester=current_user,
            approver_ids=chain,
            amount=body.amount,
            sla_hours=48,
        )
    except ApprovalError as err:
        raise HTTPException(status_code=err.status_code, detail=err.detail)

    advance.approval_id = approval.id
    await db.flush()
    return {
        "advance": {
            "id": advance.id, "amount": advance.amount, "reason": advance.reason,
            "status": advance.status,
        },
        "approval_id": approval.id,
    }


@router.get("/advances/me")
async def my_advances(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(SalaryAdvance).where(SalaryAdvance.user_id == current_user.id)
        .order_by(SalaryAdvance.created_at.desc()).limit(20)
    )
    return {"items": [
        {
            "id": a.id, "amount": a.amount, "reason": a.reason, "status": a.status,
            "period_deducted": a.period_deducted, "created_at": str(a.created_at),
        }
        for a in result.scalars().all()
    ]}


# ---------------------------------------------------------------------------
# Cấu hình PIT/BHXH (SystemSetting)
# ---------------------------------------------------------------------------

@router.get("/settings")
async def get_settings_endpoint(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_accountant(current_user)
    return await payroll_engine.get_payroll_settings(db)


@router.put("/settings")
async def update_settings(
    body: SettingsBody,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_accountant(current_user)
    from app.services.automation import set_automation_setting
    provided = body.model_dump(exclude_unset=True)
    before = await payroll_engine.get_payroll_settings(db)
    for key, value in provided.items():
        if value is not None:
            await set_automation_setting(db, key, str(value))
    await log_action(
        db, actor=current_user, action="payroll.settings_update", entity_type="payroll",
        entity_id="settings", before={k: before.get(k) for k in provided}, after=provided,
    )
    return await payroll_engine.get_payroll_settings(db)
