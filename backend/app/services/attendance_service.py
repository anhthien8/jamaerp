"""Attendance service — logic chấm công dùng chung cho web API và Telegram bot.

Quy tắc:
- 1 người 1 bản ghi/ngày (giờ VN). Check-in lần đầu tạo record, các lần sau bỏ qua.
- Check-out cập nhật giờ ra; giờ công = min(ra - vào, 8h); phần vượt → ot_hours (chờ duyệt).
- Quên checkout → job đêm tự đóng ca 8h, đánh dấu needs_review.
- Kỳ lương đã khóa (Payroll approved/paid) → mọi sửa đổi bị từ chối.
"""

import ipaddress
import json
import logging
import math
from datetime import datetime, date, timezone
from zoneinfo import ZoneInfo

from sqlalchemy import select, func, case
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.attendance import AttendanceRecord
from app.models.notification import SystemSetting
from app.models.payroll import Payroll
from app.models.user import User

logger = logging.getLogger(__name__)

VN_TZ = ZoneInfo("Asia/Ho_Chi_Minh")

# SystemSetting keys — cấu hình chấm công văn phòng (admin sửa ở Cài đặt)
OFFICE_SETTINGS_KEY = "office_checkin"      # {"networks": ["1.2.3.4","5.6.7.0/24"], "lat":…, "lng":…, "radius_m":…}
DEVICE_SETTINGS_KEY = "attendance_device"   # {"api_key": "...", "enabled": bool}

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


async def get_setting_json(db: AsyncSession, key: str) -> dict:
    """Đọc SystemSetting dạng JSON — trả {} nếu chưa cấu hình/hỏng."""
    setting = await db.get(SystemSetting, key)
    if not setting or not setting.value:
        return {}
    try:
        parsed = json.loads(setting.value)
        return parsed if isinstance(parsed, dict) else {}
    except (ValueError, TypeError):
        return {}


async def set_setting_json(db: AsyncSession, key: str, value: dict) -> None:
    setting = await db.get(SystemSetting, key)
    payload = json.dumps(value, ensure_ascii=False)
    if setting:
        setting.value = payload
    else:
        db.add(SystemSetting(key=key, value=payload))
    await db.flush()


def ip_in_networks(ip: str | None, networks: list[str]) -> bool | None:
    """IP có thuộc mạng văn phòng? None = không đối chiếu được (thiếu IP/cấu hình)."""
    if not ip or not networks:
        return None
    try:
        addr = ipaddress.ip_address(ip)
    except ValueError:
        return None
    for net in networks:
        net = (net or "").strip()
        if not net:
            continue
        try:
            if "/" in net:
                if addr in ipaddress.ip_network(net, strict=False):
                    return True
            elif addr == ipaddress.ip_address(net):
                return True
        except ValueError:
            continue  # dòng cấu hình hỏng — bỏ qua, không làm chết cả check
    return False


def _haversine_m(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    r = 6371000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = math.radians(lat2 - lat1), math.radians(lng2 - lng1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def gps_within_office(lat: float | None, lng: float | None, cfg: dict) -> bool | None:
    """GPS có trong bán kính văn phòng? None = thiếu GPS hoặc chưa cấu hình tọa độ."""
    if lat is None or lng is None:
        return None
    o_lat, o_lng = cfg.get("lat"), cfg.get("lng")
    if o_lat is None or o_lng is None:
        return None
    try:
        radius = float(cfg.get("radius_m") or 200)
        return _haversine_m(float(lat), float(lng), float(o_lat), float(o_lng)) <= radius
    except (TypeError, ValueError):
        # Cấu hình hỏng (radius/tọa độ không phải số) → coi như không đối chiếu
        # được, KHÔNG được làm chết cả endpoint check-in
        return None


async def verify_office(
    db: AsyncSession, *, ip: str | None, lat: float | None, lng: float | None
) -> tuple[bool | None, bool | None]:
    """Đối chiếu check-in với văn phòng: (ip_ok, gps_ok) — None = không có gì để so."""
    cfg = await get_setting_json(db, OFFICE_SETTINGS_KEY)
    if not cfg:
        return None, None
    return ip_in_networks(ip, cfg.get("networks") or []), gps_within_office(lat, lng, cfg)


async def record_checkin(
    db: AsyncSession,
    user: User,
    *,
    source: str = "web",
    project_id: str | None = None,
    lat: float | None = None,
    lng: float | None = None,
    ip: str | None = None,
    ip_ok: bool | None = None,
    gps_ok: bool | None = None,
    at: datetime | None = None,
) -> tuple[AttendanceRecord, bool]:
    """Check-in. Trả về (record, created) — created=False nếu hôm nay đã check-in."""
    when = at or datetime.now(timezone.utc)
    existing = await get_or_none_today(db, user.id)
    if existing:
        return existing, False

    record = AttendanceRecord(
        user_id=user.id,
        work_date=vn_today(),
        check_in=when,
        check_in_lat=lat,
        check_in_lng=lng,
        check_in_ip=ip,
        ip_ok=ip_ok,
        gps_ok=gps_ok,
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
    # Giờ vừa tính LẠI → quyết định duyệt cũ (nếu có) không còn ứng với số giờ này.
    # Không xóa thì FE hiện «từ chối bởi X» ngay trên OT đang ⏳ chờ duyệt.
    record.ot_decided_by = None
    record.ot_decided_by_name = None
    record.ot_decided_at = None


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
