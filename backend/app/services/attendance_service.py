"""Attendance service — logic chấm công dùng chung cho web API và Telegram bot.

Quy tắc:
- 1 người 1 bản ghi/ngày (giờ VN). Check-in lần đầu tạo record, các lần sau bỏ qua.
- Check-out cập nhật giờ ra; giờ công = min(ra - vào, 8h); phần vượt → ot_hours (chờ duyệt).
- Quên checkout → job đêm tự đóng ca 8h, đánh dấu needs_review.
- Kỳ lương đã khóa (Payroll approved/paid) → mọi sửa đổi bị từ chối.
"""

import logging
from datetime import datetime, date, timezone
from zoneinfo import ZoneInfo

from sqlalchemy import select, func, case
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.attendance import AttendanceRecord
from app.models.payroll import Payroll
from app.models.user import User

logger = logging.getLogger(__name__)

VN_TZ = ZoneInfo("Asia/Ho_Chi_Minh")

STANDARD_HOURS_PER_DAY = 8.0
# OT dưới 30 phút không tính (tránh nhiễu do checkout muộn vài phút)
OT_MIN_HOURS = 0.5
# Số công chuẩn/tháng — dùng khi tính lương (có thể chuyển vào SystemSetting sau)
STANDARD_DAYS_PER_MONTH = 22.0


def vn_now() -> datetime:
    return datetime.now(VN_TZ)


def vn_today() -> date:
    return vn_now().date()


def period_of(d: date) -> str:
    """'2026-07' từ ngày công."""
    return d.strftime("%Y-%m")


async def is_period_locked(db: AsyncSession, period: str) -> bool:
    """Kỳ đã khóa khi tồn tại bảng lương approved/paid của kỳ đó."""
    result = await db.execute(
        select(Payroll.id).where(
            Payroll.period == period,
            Payroll.status.in_(("approved", "paid")),
        ).limit(1)
    )
    return result.first() is not None


async def get_or_none_today(db: AsyncSession, user_id: str) -> AttendanceRecord | None:
    result = await db.execute(
        select(AttendanceRecord).where(
            AttendanceRecord.user_id == user_id,
            AttendanceRecord.work_date == vn_today(),
        )
    )
    return result.scalar_one_or_none()


async def record_checkin(
    db: AsyncSession,
    user: User,
    *,
    source: str = "web",
    project_id: str | None = None,
    lat: float | None = None,
    lng: float | None = None,
) -> tuple[AttendanceRecord, bool]:
    """Check-in. Trả về (record, created) — created=False nếu hôm nay đã check-in."""
    existing = await get_or_none_today(db, user.id)
    if existing:
        return existing, False

    record = AttendanceRecord(
        user_id=user.id,
        work_date=vn_today(),
        check_in=datetime.now(timezone.utc),
        check_in_lat=lat,
        check_in_lng=lng,
        project_id=project_id,
        source=source,
    )
    db.add(record)
    await db.flush()
    return record, True


def _compute_hours(record: AttendanceRecord, out_at: datetime) -> None:
    check_in = record.check_in
    if check_in is None:
        record.work_hours = 0
        return
    if check_in.tzinfo is None:
        check_in = check_in.replace(tzinfo=timezone.utc)
    elapsed = max(0.0, (out_at - check_in).total_seconds() / 3600.0)
    record.work_hours = round(min(elapsed, STANDARD_HOURS_PER_DAY), 2)
    ot = elapsed - STANDARD_HOURS_PER_DAY
    if ot >= OT_MIN_HOURS:
        record.ot_hours = round(ot, 2)
        record.ot_status = "pending"
    else:
        record.ot_hours = 0
        record.ot_status = "none"


async def record_checkout(db: AsyncSession, user: User) -> AttendanceRecord | None:
    """Check-out — trả về record hoặc None nếu hôm nay chưa check-in."""
    record = await get_or_none_today(db, user.id)
    if not record or record.check_in is None:
        return None

    now = datetime.now(timezone.utc)
    record.check_out = now
    _compute_hours(record, now)
    await db.flush()
    return record


async def auto_close_open_shifts(db: AsyncSession) -> int:
    """Job đêm: đóng mọi ca quên checkout của NGÀY HÔM NAY (giờ VN).

    Giờ công = min(thực tế, 8h), đánh dấu needs_review cho leader xác nhận.
    """
    today = vn_today()
    result = await db.execute(
        select(AttendanceRecord).where(
            AttendanceRecord.work_date == today,
            AttendanceRecord.check_in.is_not(None),
            AttendanceRecord.check_out.is_(None),
        )
    )
    records = list(result.scalars().all())
    now = datetime.now(timezone.utc)
    for record in records:
        record.check_out = now
        _compute_hours(record, now)
        # Ca tự đóng không tự sinh OT — giờ vượt do quên checkout không đáng tin
        record.ot_hours = 0
        record.ot_status = "none"
        record.needs_review = True
        record.note = ((record.note + " | ") if record.note else "") + "auto-close: quên checkout"
    await db.flush()
    logger.info("auto_close_open_shifts: closed %d shifts for %s", len(records), today)
    return len(records)


def period_bounds(period: str) -> tuple[date, date]:
    """('2026-07') -> (2026-07-01, 2026-08-01) — end exclusive."""
    year, month = int(period[:4]), int(period[5:7])
    start = date(year, month, 1)
    end = date(year + 1, 1, 1) if month == 12 else date(year, month + 1, 1)
    return start, end


async def month_records(db: AsyncSession, user_id: str, period: str) -> list[AttendanceRecord]:
    start, end = period_bounds(period)
    result = await db.execute(
        select(AttendanceRecord).where(
            AttendanceRecord.user_id == user_id,
            AttendanceRecord.work_date >= start,
            AttendanceRecord.work_date < end,
        ).order_by(AttendanceRecord.work_date)
    )
    return list(result.scalars().all())


def _empty_summary(period: str) -> dict:
    return {
        "period": period, "records": 0, "work_days": 0, "work_days_fraction": 0.0,
        "total_hours": 0.0, "ot_approved_hours": 0.0, "needs_review": 0,
    }


async def team_month_summary(db: AsyncSession, user_ids: list[str], period: str) -> dict[str, dict]:
    """Tổng hợp công tháng cho NHIỀU người bằng 1 aggregate query (spec 05 Track B —
    thay vòng lặp month_summary per-user vốn tốn N query với 200 nhân sự).

    Trả về {user_id: summary} — cùng schema với month_summary(); user không có
    bản ghi trong kỳ sẽ KHÔNG có key (caller tự điền _empty_summary).
    """
    if not user_ids:
        return {}
    start, end = period_bounds(period)

    day_fraction = case(
        (AttendanceRecord.work_hours >= STANDARD_HOURS_PER_DAY, 1.0),
        else_=AttendanceRecord.work_hours / STANDARD_HOURS_PER_DAY,
    )
    result = await db.execute(
        select(
            AttendanceRecord.user_id,
            func.count(AttendanceRecord.id),
            func.sum(case((AttendanceRecord.work_hours > 0, 1), else_=0)),
            func.sum(day_fraction),
            func.sum(AttendanceRecord.work_hours),
            func.sum(case((AttendanceRecord.ot_status == "approved", AttendanceRecord.ot_hours), else_=0.0)),
            func.sum(case((AttendanceRecord.needs_review == True, 1), else_=0)),  # noqa: E712
        )
        .where(
            AttendanceRecord.user_id.in_(user_ids),
            AttendanceRecord.work_date >= start,
            AttendanceRecord.work_date < end,
        )
        .group_by(AttendanceRecord.user_id)
    )
    summaries: dict[str, dict] = {}
    for user_id, records, work_days, fraction, hours, ot_hours, review in result.all():
        summaries[user_id] = {
            "period": period,
            "records": int(records or 0),
            "work_days": int(work_days or 0),
            "work_days_fraction": round(float(fraction or 0), 2),
            "total_hours": round(float(hours or 0), 2),
            "ot_approved_hours": round(float(ot_hours or 0), 2),
            "needs_review": int(review or 0),
        }
    return summaries


async def month_summary(db: AsyncSession, user_id: str, period: str) -> dict:
    """Tổng hợp công tháng của 1 người: work_days, total_hours, ot_approved_hours."""
    records = await month_records(db, user_id, period)
    work_days = sum(1 for r in records if r.work_hours > 0)
    # Ngày đủ 8h = 1 công; ngày thiếu tính theo tỷ lệ
    work_days_fraction = round(sum(min(r.work_hours / STANDARD_HOURS_PER_DAY, 1.0) for r in records), 2)
    total_hours = round(sum(r.work_hours for r in records), 2)
    ot_hours = round(sum(r.ot_hours for r in records if r.ot_status == "approved"), 2)
    return {
        "period": period,
        "records": len(records),
        "work_days": work_days,
        "work_days_fraction": work_days_fraction,
        "total_hours": total_hours,
        "ot_approved_hours": ot_hours,
        "needs_review": sum(1 for r in records if r.needs_review),
    }
