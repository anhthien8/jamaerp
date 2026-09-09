"""Attendance API — chấm công web, bảng công cá nhân/team, duyệt OT, sửa công,
đối chiếu văn phòng (IP + GPS) và webhook máy chấm công."""

import secrets
from datetime import datetime, date, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.auth import get_current_user
from app.middleware.rbac import is_team_lead
from app.models.attendance import AttendanceRecord
from app.models.user import User
from app.services.attendance_service import (
    DEVICE_SETTINGS_KEY,
    OFFICE_SETTINGS_KEY,
    VN_TZ,
    _compute_hours,
    _empty_summary,
    get_setting_json,
    is_period_locked,
    month_records,
    month_summary,
    period_bounds,
    period_of,
    record_checkin,
    record_checkout,
    set_setting_json,
    team_month_summary,
    verify_office,
    vn_today,
)
from app.services.audit import log_action

router = APIRouter(prefix="/attendance", tags=["attendance"])


def _client_ip(request: Request) -> str | None:
    """IP thật của client sau proxy Railway.

    X-Forwarded-For dạng "client, proxy1, …" — proxy TIN CẬY nối IP của kết nối
    tới nó vào CUỐI chuỗi, nên lấy phần tử CUỐI để client không giả được bằng
    cách tự gửi header. Chạy local không có header thì dùng IP socket.
    """
    xff = request.headers.get("x-forwarded-for")
    if xff:
        return xff.split(",")[-1].strip() or None
    return request.client.host if request.client else None


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class CheckinBody(BaseModel):
    project_id: str | None = None
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)


class EditAttendanceBody(BaseModel):
    check_in: datetime | None = None
    check_out: datetime | None = None
    work_hours: float | None = Field(default=None, ge=0, le=24)
    note: str = Field(..., min_length=3, max_length=500)  # bắt buộc ghi lý do sửa


def _serialize(r: AttendanceRecord) -> dict:
    return {
        "id": r.id,
        "user_id": r.user_id,
        "work_date": str(r.work_date),
        "check_in": str(r.check_in) if r.check_in else None,
        "check_out": str(r.check_out) if r.check_out else None,
        "project_id": r.project_id,
        "source": r.source,
        "ip_ok": r.ip_ok,
        "gps_ok": r.gps_ok,
        "work_hours": r.work_hours,
        "ot_hours": r.ot_hours,
        "ot_status": r.ot_status,
        "ot_decided_by_name": r.ot_decided_by_name,
        "ot_decided_at": str(r.ot_decided_at) if r.ot_decided_at else None,
        "needs_review": r.needs_review,
        "note": r.note,
    }


async def _get_record(db: AsyncSession, record_id: str) -> AttendanceRecord:
    record = await db.get(AttendanceRecord, record_id)
    if not record:
        raise HTTPException(status_code=404, detail="Bản ghi chấm công không tồn tại")
    return record


async def _require_unlocked(db: AsyncSession, work_date: date) -> None:
    if await is_period_locked(db, period_of(work_date)):
        raise HTTPException(
            status_code=409,
            detail=f"Kỳ lương {period_of(work_date)} đã khóa — không thể sửa chấm công",
        )


async def _require_team_scope(db: AsyncSession, current_user: User, target_user_id: str) -> User:
    """Trưởng nhóm/phòng chỉ thao tác trong team mình; admin/accountant toàn quyền.

    is_team_lead = leader HOẶC sale_leader (chốt 09/09/2026: trưởng nhóm KD
    được duyệt OT của nhóm mình như trưởng phòng).
    """
    target = await db.get(User, target_user_id)
    if not target:
        raise HTTPException(status_code=404, detail="Nhân viên không tồn tại")
    if current_user.role in ("admin", "accountant"):
        return target
    if is_team_lead(current_user) and current_user.team_id and target.team_id == current_user.team_id:
        return target
    raise HTTPException(status_code=403, detail="Không có quyền thao tác chấm công của nhân viên này")


# ---------------------------------------------------------------------------
# Check-in / Check-out (web — mọi role)
# ---------------------------------------------------------------------------

@router.post("/checkin")
async def checkin(
    body: CheckinBody,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    ip = _client_ip(request)
    ip_ok, gps_ok = await verify_office(db, ip=ip, lat=body.latitude, lng=body.longitude)
    record, created = await record_checkin(
        db, current_user, source="web",
        project_id=body.project_id, lat=body.latitude, lng=body.longitude,
        ip=ip, ip_ok=ip_ok, gps_ok=gps_ok,
    )
    if created and (ip_ok or gps_ok):
        message = "Check-in thành công — ✓ tại văn phòng"
    elif created:
        message = "Check-in thành công"
    else:
        message = "Hôm nay bạn đã check-in rồi"
    return {"record": _serialize(record), "created": created, "message": message}


@router.post("/checkout")
async def checkout(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    record = await record_checkout(db, current_user)
    if not record:
        raise HTTPException(status_code=400, detail="Hôm nay bạn chưa check-in")
    return {"record": _serialize(record), "message": "Check-out thành công"}


@router.get("/today")
async def today_status(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Trạng thái chấm công hôm nay của chính mình (cho nút checkin/checkout trên UI)."""
    result = await db.execute(
        select(AttendanceRecord).where(
            AttendanceRecord.user_id == current_user.id,
            AttendanceRecord.work_date == vn_today(),
        )
    )
    record = result.scalar_one_or_none()
    return {"record": _serialize(record) if record else None}


# ---------------------------------------------------------------------------
# Bảng công
# ---------------------------------------------------------------------------

@router.get("/me")
async def my_attendance(
    period: str = Query(default=None, pattern=r"^\d{4}-\d{2}$"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    period = period or period_of(vn_today())
    records = await month_records(db, current_user.id, period)
    summary = await month_summary(db, current_user.id, period)
    return {"summary": summary, "records": [_serialize(r) for r in records]}


@router.get("/team")
async def team_attendance(
    period: str = Query(default=None, pattern=r"^\d{4}-\d{2}$"),
    team_id: str | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Bảng công team (trưởng nhóm/phòng: team mình; admin/accountant: mọi team/toàn cty)."""
    if current_user.role in ("admin", "accountant"):
        pass  # toàn quyền, tôn trọng team_id truyền vào (hoặc toàn công ty)
    elif is_team_lead(current_user):
        team_id = current_user.team_id
        # Trưởng nhóm chưa xếp đội: trả bảng RỖNG thay vì 400 — FE gộp lời gọi này
        # trong Promise.all với bảng công cá nhân, 400 làm toast lỗi đỏ che luôn
        # phần cá nhân vốn tải được (QC 27/08, tài khoản leader prod chưa có đội).
        if not team_id:
            return {"period": period or period_of(vn_today()), "items": []}
    else:
        raise HTTPException(status_code=403, detail="Không có quyền xem bảng công team")

    period = period or period_of(vn_today())

    q = select(User).where(User.is_active == True)  # noqa: E712
    if team_id:
        q = q.where(User.team_id == team_id)
    users = (await db.execute(q.order_by(User.full_name))).scalars().all()

    # 1 aggregate cho cả team thay vì N query per-user (spec 05 Track B)
    summaries = await team_month_summary(db, [u.id for u in users], period)
    rows = [
        {
            "user_id": u.id,
            "full_name": u.full_name,
            "role": u.role,
            "team_id": u.team_id,
            **(summaries.get(u.id) or _empty_summary(period)),
        }
        for u in users
    ]
    return {"period": period, "items": rows}


# ---------------------------------------------------------------------------
# Sửa công (quên chấm) — bắt buộc note, ghi audit, chặn kỳ khóa
# ---------------------------------------------------------------------------

@router.patch("/{record_id}")
async def edit_attendance(
    record_id: str,
    body: EditAttendanceBody,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    record = await _get_record(db, record_id)
    await _require_team_scope(db, current_user, record.user_id)
    await _require_unlocked(db, record.work_date)

    before = {
        "check_in": str(record.check_in), "check_out": str(record.check_out),
        "work_hours": record.work_hours,
    }
    if body.check_in is not None:
        record.check_in = body.check_in
    if body.check_out is not None:
        record.check_out = body.check_out
    if body.work_hours is not None:
        record.work_hours = body.work_hours
    record.needs_review = False
    record.note = ((record.note + " | ") if record.note else "") + f"Sửa bởi {current_user.full_name}: {body.note}"
    await db.flush()

    await log_action(
        db, actor=current_user, action="attendance.edit", entity_type="attendance",
        entity_id=record.id, before=before,
        after={"check_in": str(record.check_in), "check_out": str(record.check_out), "work_hours": record.work_hours},
        note=body.note,
    )
    return {"record": _serialize(record)}


# ---------------------------------------------------------------------------
# Duyệt OT
# ---------------------------------------------------------------------------

@router.get("/ot/pending")
async def pending_ot(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role not in ("admin", "accountant") and not is_team_lead(current_user):
        raise HTTPException(status_code=403, detail="Không có quyền duyệt OT")

    # Join + lọc team trong SQL — không N+1, không lọc Python (spec 05 Track B)
    q = (
        select(AttendanceRecord, User.full_name)
        .join(User, User.id == AttendanceRecord.user_id)
        .where(AttendanceRecord.ot_status == "pending")
    )
    if current_user.role not in ("admin", "accountant"):
        # Trưởng nhóm/phòng (kể cả sale_leader) chỉ thấy OT của team mình;
        # chưa xếp đội thì danh sách rỗng (so với None sẽ match nhầm người teamless)
        if not current_user.team_id:
            return {"items": []}
        q = q.where(User.team_id == current_user.team_id)
    result = await db.execute(q.order_by(AttendanceRecord.work_date.desc()))

    items = [
        {**_serialize(record), "full_name": full_name}
        for record, full_name in result.all()
    ]
    return {"items": items}


@router.post("/{record_id}/ot-approve")
async def approve_ot(
    record_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    record = await _get_record(db, record_id)
    target = await _require_team_scope(db, current_user, record.user_id)
    if current_user.id == record.user_id:
        raise HTTPException(status_code=403, detail="Không thể tự duyệt OT của chính mình")
    if record.ot_status != "pending":
        raise HTTPException(status_code=409, detail="OT này đã được xử lý")
    await _require_unlocked(db, record.work_date)

    record.ot_status = "approved"
    # Vết duyệt hiển thị thẳng trên bảng công (chốt 09/09): ai duyệt + lúc nào
    record.ot_decided_by = current_user.id
    record.ot_decided_by_name = current_user.full_name
    record.ot_decided_at = datetime.now(timezone.utc)
    await db.flush()
    await log_action(
        db, actor=current_user, action="ot.approve", entity_type="attendance",
        entity_id=record.id, after={"ot_hours": record.ot_hours, "user": target.full_name},
    )
    return {"record": _serialize(record)}


@router.post("/{record_id}/ot-reject")
async def reject_ot(
    record_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    record = await _get_record(db, record_id)
    target = await _require_team_scope(db, current_user, record.user_id)
    if current_user.id == record.user_id:
        raise HTTPException(status_code=403, detail="Không thể tự xử lý OT của chính mình")
    if record.ot_status != "pending":
        raise HTTPException(status_code=409, detail="OT này đã được xử lý")
    await _require_unlocked(db, record.work_date)

    record.ot_status = "rejected"
    record.ot_decided_by = current_user.id
    record.ot_decided_by_name = current_user.full_name
    record.ot_decided_at = datetime.now(timezone.utc)
    await db.flush()
    await log_action(
        db, actor=current_user, action="ot.reject", entity_type="attendance",
        entity_id=record.id, after={"ot_hours": record.ot_hours, "user": target.full_name},
    )
    return {"record": _serialize(record)}


# ---------------------------------------------------------------------------
# Cấu hình chấm công văn phòng + máy chấm công (admin — Cài đặt)
# ---------------------------------------------------------------------------

class OfficeConfigBody(BaseModel):
    networks: list[str] = Field(default_factory=list, max_length=20)  # IP hoặc CIDR
    lat: float | None = Field(default=None, ge=-90, le=90)
    lng: float | None = Field(default=None, ge=-180, le=180)
    radius_m: int = Field(default=200, ge=50, le=2000)


class DeviceToggleBody(BaseModel):
    enabled: bool


def _require_admin(current_user: User) -> None:
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Chỉ quản trị viên cấu hình được chấm công văn phòng")


def _mask_key(key: str | None) -> str | None:
    if not key:
        return None
    return f"{key[:6]}****{key[-4:]}" if len(key) > 12 else "****"


@router.get("/office-config")
async def get_office_config(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_admin(current_user)
    office = await get_setting_json(db, OFFICE_SETTINGS_KEY)
    device = await get_setting_json(db, DEVICE_SETTINGS_KEY)
    return {
        "office": {
            "networks": office.get("networks") or [],
            "lat": office.get("lat"),
            "lng": office.get("lng"),
            "radius_m": office.get("radius_m") or 200,
        },
        "device": {
            "enabled": bool(device.get("enabled")),
            "api_key_masked": _mask_key(device.get("api_key")),
            "webhook_path": "/api/v1/attendance/device-webhook",
        },
    }


@router.put("/office-config")
async def update_office_config(
    body: OfficeConfigBody,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_admin(current_user)
    before = await get_setting_json(db, OFFICE_SETTINGS_KEY)
    value = {
        "networks": [n.strip() for n in body.networks if n.strip()],
        "lat": body.lat,
        "lng": body.lng,
        "radius_m": body.radius_m,
    }
    await set_setting_json(db, OFFICE_SETTINGS_KEY, value)
    await log_action(
        db, actor=current_user, action="attendance.office_config", entity_type="system_setting",
        entity_id=OFFICE_SETTINGS_KEY, before=before, after=value,
    )
    return {"office": value}


@router.post("/device-key/rotate")
async def rotate_device_key(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Sinh khóa API mới cho máy chấm công — khóa chỉ hiện MỘT LẦN ở response này."""
    _require_admin(current_user)
    new_key = secrets.token_urlsafe(32)
    device = await get_setting_json(db, DEVICE_SETTINGS_KEY)
    device["api_key"] = new_key
    device["enabled"] = True
    await set_setting_json(db, DEVICE_SETTINGS_KEY, device)
    # KHÔNG ghi khóa vào audit — chỉ ghi sự kiện đổi khóa
    await log_action(
        db, actor=current_user, action="attendance.device_key_rotate", entity_type="system_setting",
        entity_id=DEVICE_SETTINGS_KEY, after={"enabled": True},
    )
    return {"api_key": new_key, "enabled": True}


@router.put("/device-config")
async def toggle_device(
    body: DeviceToggleBody,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_admin(current_user)
    device = await get_setting_json(db, DEVICE_SETTINGS_KEY)
    device["enabled"] = body.enabled
    await set_setting_json(db, DEVICE_SETTINGS_KEY, device)
    await log_action(
        db, actor=current_user, action="attendance.device_toggle", entity_type="system_setting",
        entity_id=DEVICE_SETTINGS_KEY, after={"enabled": body.enabled},
    )
    return {"enabled": body.enabled}


# ---------------------------------------------------------------------------
# Webhook máy chấm công — xác thực bằng khóa thiết bị, KHÔNG dùng JWT người dùng
# ---------------------------------------------------------------------------

class DeviceEventBody(BaseModel):
    email: str = Field(..., max_length=100)          # máy chấm công map nhân viên theo email
    event_time: str = Field(..., max_length=40)      # ISO 8601; không kèm múi giờ = giờ VN
    direction: str = Field(default="auto", pattern=r"^(in|out|auto)$")


def _parse_event_time(value: str) -> datetime:
    """Chuẩn hóa giờ sự kiện về UTC naive (quy ước cột check_in/check_out).

    Máy chấm công thường gửi giờ VN local không kèm tz — coi naive = Asia/Ho_Chi_Minh.
    """
    try:
        dt = datetime.fromisoformat(value)
    except ValueError:
        raise HTTPException(status_code=422, detail="event_time không đúng định dạng ISO 8601")
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=VN_TZ)
    return dt.astimezone(timezone.utc).replace(tzinfo=None)


@router.post("/device-webhook")
async def device_webhook(
    body: DeviceEventBody,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    device = await get_setting_json(db, DEVICE_SETTINGS_KEY)
    api_key = device.get("api_key") or ""
    given = request.headers.get("x-device-key") or ""
    if not device.get("enabled") or not api_key or not secrets.compare_digest(api_key, given):
        raise HTTPException(status_code=401, detail="Khóa thiết bị không hợp lệ hoặc chưa bật")

    result = await db.execute(
        select(User).where(User.email == body.email.strip().lower(), User.is_active == True)  # noqa: E712
    )
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail=f"Không tìm thấy nhân viên với email {body.email}")

    event_utc = _parse_event_time(body.event_time)
    work_date = (event_utc.replace(tzinfo=timezone.utc).astimezone(VN_TZ)).date()

    # Chỉ nhận sự kiện quanh hôm nay (máy offline đẩy bù vài ngày là hợp lệ) —
    # key lộ cũng không rải được bản ghi khắp tương lai/quá khứ chưa khóa kỳ.
    today = vn_today()
    if not (-3 <= (today - work_date).days <= 1):
        raise HTTPException(
            status_code=422,
            detail=f"event_time {work_date} ngoài cửa sổ nhận (hôm nay ±3 ngày) — kiểm tra đồng hồ máy chấm công",
        )
    if await is_period_locked(db, period_of(work_date)):
        raise HTTPException(status_code=409, detail=f"Kỳ lương {period_of(work_date)} đã khóa")

    record = (
        await db.execute(
            select(AttendanceRecord).where(
                AttendanceRecord.user_id == user.id,
                AttendanceRecord.work_date == work_date,
            )
        )
    ).scalar_one_or_none()

    if record is not None and record.source == "leave":
        # Ngày nghỉ phép đã duyệt: giờ công là GIỜ PHÉP (đã trừ số dư) — lượt quẹt
        # thẻ không được ghi đè. Trả 200 để máy không retry vô hạn.
        return {"record": _serialize(record), "applied": "ignored_leave"}

    if record is None:
        record = AttendanceRecord(
            user_id=user.id, work_date=work_date, check_in=event_utc, source="device",
        )
        db.add(record)
        await db.flush()
        return {"record": _serialize(record), "applied": "check_in"}

    # Gộp nhiều lượt quẹt/ngày KHÔNG phụ thuộc thứ tự đến: sớm nhất = vào ca,
    # muộn nhất = tan ca. Máy offline đẩy bù lộn thứ tự (out đến trước in) từng
    # làm MẤT lượt quẹt ra + không tính lại giờ công (finding vòng phản biện).
    times = sorted({t for t in (record.check_in, record.check_out, event_utc) if t is not None})
    new_in, new_out = times[0], (times[-1] if len(times) > 1 else None)
    if new_in == record.check_in and new_out == record.check_out:
        applied = "ignored"
    else:
        applied = "check_in" if record.check_in != new_in else "check_out"
        record.check_in = new_in
        record.check_out = new_out
        if new_out is not None:
            _compute_hours(record, new_out.replace(tzinfo=timezone.utc))
    await db.flush()
    return {"record": _serialize(record), "applied": applied}
