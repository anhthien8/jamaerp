"""Payroll engine — tính lương tự động: công thực tế + hoa hồng + OT − BHXH − thuế TNCN.

Công thức:
    gross = base_salary × (công thực tế / công chuẩn) + ot_pay + hoa hồng + thưởng + phụ cấp
    BHXH NLĐ = (8% + 1.5% + 1%) × min(base_salary, trần đóng BHXH)
    Thu nhập tính thuế = gross − BHXH NLĐ − giảm trừ bản thân − (số người phụ thuộc × giảm trừ/người)
    PIT = biểu lũy tiến 7 bậc (5/10/15/20/25/30/35%)
    net = gross − BHXH NLĐ − PIT − tạm ứng − khấu trừ khác

Mức giảm trừ + trần BHXH đọc từ SystemSetting (kế toán chỉnh khi luật đổi, không hardcode).
"""

import logging
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.attendance import AttendanceRecord  # noqa: F401 — dùng qua attendance_service
from app.models.payroll import Commission, Payroll, SalaryAdvance
from app.models.salary_grade import SalaryGrade
from app.models.user import User
from app.services.attendance_service import (
    STANDARD_DAYS_PER_MONTH,
    STANDARD_HOURS_PER_DAY,
    month_summary,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Cấu hình PIT/BHXH — lưu SystemSetting, default theo luật hiện hành
# ---------------------------------------------------------------------------

PAYROLL_SETTING_DEFAULTS = {
    # Giảm trừ gia cảnh (đồng/tháng) — Nghị quyết UBTVQH, kế toán cập nhật khi thay đổi
    "pit_personal_deduction": "11000000",
    "pit_dependent_deduction": "4400000",
    # Trần lương đóng BHXH = 20 × mức lương cơ sở — cập nhật khi lương cơ sở đổi
    "bhxh_salary_cap": "46800000",
    # Công chuẩn/tháng
    "payroll_standard_days": str(int(STANDARD_DAYS_PER_MONTH)),
    # Hệ số OT (ngày thường theo luật tối thiểu 150%)
    "ot_multiplier": "1.5",
}

# Biểu thuế lũy tiến từng phần (thu nhập tính thuế/tháng, đồng)
PIT_BRACKETS = [
    (5_000_000, 0.05),
    (10_000_000, 0.10),
    (18_000_000, 0.15),
    (32_000_000, 0.20),
    (52_000_000, 0.25),
    (80_000_000, 0.30),
    (float("inf"), 0.35),
]


async def get_payroll_settings(db: AsyncSession) -> dict[str, float]:
    from app.models.notification import SystemSetting
    result = await db.execute(select(SystemSetting))
    stored = {s.key: s.value for s in result.scalars().all()}
    merged = {**PAYROLL_SETTING_DEFAULTS, **{k: v for k, v in stored.items() if k in PAYROLL_SETTING_DEFAULTS}}
    return {k: float(v) for k, v in merged.items()}


def compute_pit(taxable_income: float) -> float:
    """Thuế TNCN lũy tiến từng phần. taxable_income đã trừ BHXH + giảm trừ gia cảnh."""
    if taxable_income <= 0:
        return 0.0
    tax = 0.0
    lower = 0.0
    for upper, rate in PIT_BRACKETS:
        if taxable_income > upper:
            tax += (upper - lower) * rate
            lower = upper
        else:
            tax += (taxable_income - lower) * rate
            break
    return round(tax)


def compute_insurance_employee(base_salary: float, grade: SalaryGrade | None, cap: float) -> float:
    """BHXH+BHYT+BHTN phía người lao động, đóng trên lương bậc (có trần)."""
    if base_salary <= 0:
        return 0.0
    base = min(base_salary, cap)
    if grade:
        rate = (grade.bhxh_rate + grade.bhyt_rate + grade.bhtn_rate) / 100.0
    else:
        rate = 0.105  # 8 + 1.5 + 1 (bhxh_rate mặc định 10.5 đã gộp BHXH; giữ nhất quán SalaryGrade)
    return round(base * rate)


def compute_insurance_company(base_salary: float, grade: SalaryGrade | None, cap: float) -> float:
    if base_salary <= 0:
        return 0.0
    base = min(base_salary, cap)
    rate = (grade.bhxh_company_rate / 100.0) if grade else 0.215
    return round(base * rate)


async def _commission_total(db: AsyncSession, user_id: str, period: str) -> float:
    """Tổng hoa hồng đã duyệt của kỳ (status approved, chưa paid)."""
    result = await db.execute(
        select(Commission).where(
            Commission.user_id == user_id,
            Commission.period == period,
            Commission.status == "approved",
        )
    )
    return round(sum(c.commission_amount for c in result.scalars().all()))


async def _pending_advances(db: AsyncSession, user_id: str, period: str) -> tuple[float, list[SalaryAdvance]]:
    """Tạm ứng đã duyệt chưa trừ (hoặc đã gán vào chính kỳ này khi generate lại)."""
    result = await db.execute(
        select(SalaryAdvance).where(
            SalaryAdvance.user_id == user_id,
            SalaryAdvance.status == "approved",
        )
    )
    advances = [a for a in result.scalars().all() if a.period_deducted in (None, period)]
    return round(sum(a.amount for a in advances)), advances


async def build_payroll_row(
    db: AsyncSession,
    user: User,
    period: str,
    settings: dict[str, float],
) -> Payroll:
    """Tính 1 dòng lương draft cho user (chưa add vào session)."""
    grade = await db.get(SalaryGrade, user.salary_grade_id) if user.salary_grade_id else None
    base_salary = grade.base_salary if grade else 0.0
    standard_days = settings["payroll_standard_days"]
    cap = settings["bhxh_salary_cap"]

    summary = await month_summary(db, user.id, period)
    work_days = summary["work_days_fraction"]
    ot_hours = summary["ot_approved_hours"]

    hourly = (base_salary / standard_days / STANDARD_HOURS_PER_DAY) if base_salary else 0.0
    ot_pay = round(hourly * ot_hours * settings["ot_multiplier"])

    commission = await _commission_total(db, user.id, period)
    advance_total, advances = await _pending_advances(db, user.id, period)

    salary_for_days = round(base_salary * min(work_days / standard_days, 1.0)) if base_salary else 0.0
    gross = salary_for_days + ot_pay + commission  # bonus/allowance kế toán bổ sung tay sau

    insurance = compute_insurance_employee(base_salary, grade, cap)
    insurance_company = compute_insurance_company(base_salary, grade, cap)

    taxable = max(
        0.0,
        gross - insurance - settings["pit_personal_deduction"]
        - user.dependents_count * settings["pit_dependent_deduction"],
    )
    pit = compute_pit(taxable)

    net = gross - insurance - pit - advance_total

    notes = None
    if not grade:
        notes = "⚠️ Chưa gán bậc lương — lương cơ bản = 0, cần kế toán cập nhật"

    # Gán tạm ứng vào kỳ này (idempotent khi generate lại)
    for advance in advances:
        advance.period_deducted = period

    return Payroll(
        user_id=user.id,
        period=period,
        base_salary=base_salary,
        work_days=work_days,
        standard_days=standard_days,
        ot_hours=ot_hours,
        ot_pay=ot_pay,
        commission_total=commission,
        bonus=0,
        allowance=0,
        gross_salary=round(gross),
        bhxh_employee=insurance,
        bhxh_company=insurance_company,
        taxable_income=round(taxable),
        pit=pit,
        advance_deduction=advance_total,
        deductions=0,
        net_salary=round(net),
        salary_grade_id=user.salary_grade_id,
        status="draft",
        notes=notes,
    )


async def generate_period(db: AsyncSession, period: str) -> dict:
    """Sinh bảng lương draft cho toàn bộ user active. Xóa draft cũ của kỳ (regenerate an toàn)."""
    # Chặn nếu kỳ đã submit/khóa
    existing = await db.execute(
        select(Payroll).where(
            Payroll.period == period,
            Payroll.status.in_(("pending_approval", "approved", "paid")),
        ).limit(1)
    )
    if existing.first():
        raise ValueError(f"Kỳ {period} đã submit/khóa — không thể generate lại")

    # Xóa draft cũ
    old = await db.execute(
        select(Payroll).where(Payroll.period == period, Payroll.status == "draft")
    )
    for row in old.scalars().all():
        await db.delete(row)
    await db.flush()

    settings = await get_payroll_settings(db)
    users = (await db.execute(
        select(User).where(User.is_active == True).order_by(User.full_name)  # noqa: E712
    )).scalars().all()

    created = 0
    total_net = 0.0
    missing_grade = 0
    for user in users:
        row = await build_payroll_row(db, user, period, settings)
        db.add(row)
        created += 1
        total_net += row.net_salary
        if not row.salary_grade_id:
            missing_grade += 1
    await db.flush()

    return {
        "period": period,
        "created": created,
        "total_net": round(total_net),
        "missing_grade": missing_grade,
    }


def format_payslip(row: Payroll, full_name: str) -> str:
    """Phiếu lương gửi Telegram chat riêng — TUYỆT ĐỐI không gửi vào nhóm."""
    def fmt(v: float) -> str:
        return f"{v:,.0f}đ"

    lines = [
        f"🧾 <b>Phiếu lương kỳ {row.period}</b> — {full_name}",
        "",
        f"Lương cơ bản: {fmt(row.base_salary)}",
        f"Công thực tế: {row.work_days:g}/{row.standard_days:g} ngày",
    ]
    if row.ot_pay:
        lines.append(f"Tăng ca ({row.ot_hours:g}h): +{fmt(row.ot_pay)}")
    if row.commission_total:
        lines.append(f"Hoa hồng: +{fmt(row.commission_total)}")
    if row.bonus:
        lines.append(f"Thưởng: +{fmt(row.bonus)}")
    if row.allowance:
        lines.append(f"Phụ cấp: +{fmt(row.allowance)}")
    lines.append(f"<b>Tổng thu nhập (gross): {fmt(row.gross_salary)}</b>")
    lines.append("")
    lines.append(f"BHXH/BHYT/BHTN: −{fmt(row.bhxh_employee)}")
    lines.append(f"Thuế TNCN: −{fmt(row.pit)}")
    if row.advance_deduction:
        lines.append(f"Trừ tạm ứng: −{fmt(row.advance_deduction)}")
    if row.deductions:
        lines.append(f"Khấu trừ khác: −{fmt(row.deductions)}")
    lines.append("")
    lines.append(f"💵 <b>THỰC LĨNH: {fmt(row.net_salary)}</b>")
    if row.notes:
        lines.append(f"\nGhi chú: {row.notes}")
    lines.append("\n<i>Phiếu lương bảo mật — vui lòng không chia sẻ. Thắc mắc liên hệ Kế toán.</i>")
    return "\n".join(lines)


async def send_payslips(db: AsyncSession, period: str) -> dict:
    """Gửi phiếu lương từng người qua Telegram CHAT RIÊNG. Trả về danh sách chưa gửi được."""
    from app.services.telegram_notify import send_telegram

    result = await db.execute(
        select(Payroll, User).join(User, User.id == Payroll.user_id).where(
            Payroll.period == period,
            Payroll.status == "paid",
        )
    )
    sent = 0
    no_telegram: list[str] = []
    now = datetime.now(timezone.utc)
    for row, user in result.all():
        if row.payslip_sent_at:
            continue  # idempotent — không gửi trùng
        if not user.telegram_user_id:
            no_telegram.append(user.full_name)
            continue
        ok = await send_telegram(user.telegram_user_id, format_payslip(row, user.full_name))
        if ok:
            row.payslip_sent_at = now
            sent += 1
        else:
            no_telegram.append(user.full_name)
    await db.flush()
    return {"sent": sent, "manual_delivery": no_telegram}
