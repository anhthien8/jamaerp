"""Zalo Listener API (spec 09).

2 nhóm endpoint:
- ADMIN (JWT, role=admin): cấu hình QR login, quản lý nhóm theo dõi, xem tín hiệu.
- INGEST SERVICE (header X-Zalo-Secret): Node zca-js đẩy QR/heartbeat + tin nhắn vào.

Nguyên tắc: listen-only — backend KHÔNG có endpoint nào để gửi tin ra Zalo.
"""

import hmac
import json
from datetime import date, datetime, timezone

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.database import get_db
from app.middleware.auth import get_current_user
from app.models.user import User
from app.models.zalo import ZaloSession, ZaloGroup, ZaloMessage, ZaloSignal, ZaloDigest
from app.services.audit import log_action
from app.services.zalo_analysis import analyze_and_store
from app.services import zalo_assistant as tro_ly

router = APIRouter(prefix="/zalo", tags=["zalo"])
settings = get_settings()

SESSION_ID = "default"


# ---------------------------------------------------------------------------
# Auth helpers
# ---------------------------------------------------------------------------

def _require_admin(current_user: User) -> None:
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Chỉ Admin mới cấu hình Zalo Listener")


def _verify_ingest_secret(x_zalo_secret: str | None = Header(default=None)) -> None:
    """Xác thực Ingest Service qua bí mật chia sẻ (giống pattern Telegram)."""
    secret = settings.ZALO_INGEST_SECRET
    if not secret:
        raise HTTPException(status_code=503, detail="ZALO_INGEST_SECRET chưa cấu hình ở backend")
    if not x_zalo_secret or not hmac.compare_digest(x_zalo_secret, secret):
        raise HTTPException(status_code=401, detail="Bí mật Zalo không hợp lệ")


async def _get_session(db: AsyncSession) -> ZaloSession:
    sess = await db.get(ZaloSession, SESSION_ID)
    if not sess:
        sess = ZaloSession(id=SESSION_ID, status="logged_out")
        db.add(sess)
        await db.flush()
    return sess


# ---------------------------------------------------------------------------
# ADMIN — QR login / session
# ---------------------------------------------------------------------------

@router.get("/session")
async def get_session(db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Trạng thái phiên đăng nhập Zalo (admin theo dõi để quét QR)."""
    _require_admin(current_user)
    sess = await _get_session(db)
    # ingest service "sống" nếu heartbeat trong 90s
    online = False
    if sess.last_seen:
        last = sess.last_seen if sess.last_seen.tzinfo else sess.last_seen.replace(tzinfo=timezone.utc)
        online = (datetime.now(timezone.utc) - last).total_seconds() < 90
    return {
        "status": sess.status,
        "qr_image": sess.qr_image if sess.status in ("awaiting_qr", "qr_ready") else None,
        "account_name": sess.account_name,
        "error_msg": sess.error_msg,
        "ingest_online": online,
        "last_seen": str(sess.last_seen) if sess.last_seen else None,
    }


@router.post("/session/login")
async def request_login(db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Admin bấm 'Đăng nhập Zalo' → đặt cờ để Ingest Service khởi động login + đẩy QR về."""
    _require_admin(current_user)
    sess = await _get_session(db)
    sess.status = "awaiting_qr"
    sess.login_requested = True
    sess.qr_image = None
    sess.error_msg = None
    await db.flush()
    await log_action(db, actor=current_user, action="zalo.login_requested", entity_type="zalo", entity_id=SESSION_ID)
    return {"status": sess.status, "message": "Đang chờ Ingest Service tạo mã QR — làm mới sau vài giây"}


@router.post("/session/logout")
async def logout(db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Admin đăng xuất tài khoản Zalo listener."""
    _require_admin(current_user)
    sess = await _get_session(db)
    sess.status = "logged_out"
    sess.login_requested = False
    sess.qr_image = None
    sess.account_name = None
    sess.credentials_enc = None  # listener thấy logged_out sẽ ngắt + bỏ phiên
    await db.flush()
    await log_action(db, actor=current_user, action="zalo.logout", entity_type="zalo", entity_id=SESSION_ID)
    return {"status": "logged_out"}


# ---------------------------------------------------------------------------
# ADMIN — nhóm theo dõi
# ---------------------------------------------------------------------------

class GroupPatch(BaseModel):
    kind: str | None = Field(default=None, pattern=r"^(internal|customer)$")
    assigned_user_id: str | None = None
    monitoring: bool | None = None
    consent_ref: str | None = None
    department: str | None = Field(default=None, pattern=r"^(|EXEC|SALES|DESIGN|ACCT|OPS|PURCHASING|HR|PM)$")


@router.get("/groups")
async def list_groups(db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    _require_admin(current_user)
    result = await db.execute(select(ZaloGroup).order_by(ZaloGroup.kind, ZaloGroup.name))
    groups = result.scalars().all()
    # đếm tín hiệu mới theo nhóm
    counts = dict(
        (await db.execute(
            select(ZaloSignal.group_id, func.count(ZaloSignal.id))
            .where(ZaloSignal.status == "new")
            .group_by(ZaloSignal.group_id)
        )).all()
    )
    return {"items": [
        {
            "id": g.id, "zalo_group_id": g.zalo_group_id, "name": g.name, "kind": g.kind,
            "assigned_user_id": g.assigned_user_id, "monitoring": g.monitoring,
            "consent_ref": g.consent_ref, "new_signals": int(counts.get(g.id, 0)),
            "department": g.department, "member_count": g.member_count,
            "last_message_at": str(g.last_message_at) if g.last_message_at else None,
        }
        for g in groups
    ]}


@router.patch("/groups/{group_id}")
async def update_group(group_id: str, body: GroupPatch, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    _require_admin(current_user)
    group = await db.get(ZaloGroup, group_id)
    if not group:
        raise HTTPException(status_code=404, detail="Nhóm không tồn tại")
    for k, v in body.model_dump(exclude_unset=True).items():
        if k in ("department", "assigned_user_id") and v == "":
            v = None
        setattr(group, k, v)
    await db.flush()
    return {"id": group.id, "monitoring": group.monitoring, "kind": group.kind, "department": group.department}


# ---------------------------------------------------------------------------
# ADMIN/SALE — tín hiệu
# ---------------------------------------------------------------------------

@router.get("/signals")
async def list_signals(
    status: str = Query("new", pattern=r"^(new|actioned|dismissed|all)$"),
    type: str | None = Query(None, max_length=30),
    department: str | None = Query(None, max_length=20),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Tín hiệu Zalo theo phạm vi: BGĐ thấy hết, trưởng phòng thấy nhóm phòng mình,
    người khác chỉ thấy tín hiệu gán cho mình (spec 09 §5.4)."""
    q = (
        select(ZaloSignal, ZaloGroup.name, ZaloGroup.department, ZaloGroup.kind)
        .join(ZaloGroup, ZaloGroup.id == ZaloSignal.group_id)
    )
    if status != "all":
        q = q.where(ZaloSignal.status == status)
    if type:
        q = q.where(ZaloSignal.type == type)
    if department:
        q = q.where(ZaloGroup.department == department.upper())
    q = tro_ly.loc_tin_hieu(q, current_user)
    q = q.order_by(ZaloSignal.created_at.desc()).limit(200)
    rows = (await db.execute(q)).all()
    return {"items": [
        {
            "id": s.id, "type": s.type, "summary": s.summary, "status": s.status,
            "group_name": group_name, "group_department": dept, "group_kind": kind,
            "assigned_user_id": s.assigned_user_id,
            "payload": json.loads(s.payload_json) if s.payload_json else {},
            "created_at": str(s.created_at),
        }
        for s, group_name, dept, kind in rows
    ]}


def _chi_quan_ly(user: User) -> tuple[str, str | None]:
    pv, dept = tro_ly.pham_vi_zalo(user)
    if pv == "ca_nhan":
        raise HTTPException(status_code=403, detail="Trợ lý Zalo dành cho trưởng phòng và Ban giám đốc")
    return pv, dept


@router.get("/overview")
async def overview(db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Trang Trợ lý Zalo: phạm vi người xem + đếm tín hiệu mới theo loại."""
    pv, dept = _chi_quan_ly(current_user)
    q = (
        select(ZaloSignal.type, func.count(ZaloSignal.id))
        .join(ZaloGroup, ZaloGroup.id == ZaloSignal.group_id)
        .where(ZaloSignal.status == "new")
    )
    q = tro_ly.loc_tin_hieu(q, current_user).group_by(ZaloSignal.type)
    counts = {t: int(n) for t, n in (await db.execute(q)).all()}
    gq = select(func.count(ZaloGroup.id)).where(ZaloGroup.monitoring.is_(True))
    if pv == "phong":
        gq = gq.where(ZaloGroup.department == dept)
    sess = await _get_session(db)
    return {
        "scope": pv,
        "department": dept,
        "new_by_type": counts,
        "groups_monitored": int((await db.execute(gq)).scalar() or 0),
        "listener_status": sess.status,
    }


@router.get("/digests")
async def list_digests(
    day: date | None = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Tóm tắt cuối ngày theo nhóm (mặc định ngày gần nhất đã có)."""
    pv, dept = _chi_quan_ly(current_user)
    days = [d for (d,) in (await db.execute(
        select(ZaloDigest.day).distinct().order_by(ZaloDigest.day.desc()).limit(14)
    )).all()]
    if day is None:
        if not days:
            return {"day": None, "days": [], "items": []}
        day = days[0]
    q = (
        select(ZaloDigest, ZaloGroup)
        .join(ZaloGroup, ZaloGroup.id == ZaloDigest.group_id)
        .where(ZaloDigest.day == day)
    )
    if pv == "phong":
        q = q.where(ZaloGroup.department == dept)
    rows = (await db.execute(q.order_by(ZaloDigest.msg_count.desc()))).all()
    return {
        "day": str(day),
        "days": [str(d) for d in days],
        "items": [
            {
                "group_id": g.id, "group_name": g.name, "kind": g.kind, "department": g.department,
                "msg_count": d.msg_count, "summary": d.summary, "by_llm": d.by_llm,
            }
            for d, g in rows
        ],
    }


@router.post("/digests/run")
async def run_digest_now(
    day: date | None = Query(None),
    send: bool = Query(False),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Admin: làm tóm tắt ngay (mặc định hôm nay), tùy chọn gửi Telegram."""
    _require_admin(current_user)
    day = day or datetime.now(tro_ly.VN_TZ).date()
    if send:
        result = await tro_ly.gui_tom_tat_ngay(db, day)
    else:
        result = {"groups": len(await tro_ly.tao_tom_tat_ngay(db, day)), "sent": 0}
    return {"day": str(day), **result}


class SignalAction(BaseModel):
    action: str = Field(pattern=r"^(actioned|dismissed)$")


@router.post("/signals/{signal_id}/action")
async def act_signal(signal_id: str, body: SignalAction, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    signal = await db.get(ZaloSignal, signal_id)
    if not signal:
        raise HTTPException(status_code=404, detail="Tín hiệu không tồn tại")
    pv, dept = tro_ly.pham_vi_zalo(current_user)
    group = await db.get(ZaloGroup, signal.group_id)
    duoc = (
        pv == "tat_ca"
        or signal.assigned_user_id == current_user.id
        or (pv == "phong" and group is not None and group.department == dept)
    )
    if not duoc:
        raise HTTPException(status_code=403, detail="Không có quyền xử lý tín hiệu này")
    signal.status = body.action
    signal.resolved_at = datetime.now(timezone.utc)
    await db.flush()
    return {"id": signal.id, "status": signal.status}


# ---------------------------------------------------------------------------
# INGEST SERVICE — chỉ Node zca-js gọi (secret-authed)
# ---------------------------------------------------------------------------

class SessionReport(BaseModel):
    status: str = Field(pattern=r"^(awaiting_qr|qr_ready|logged_in|error)$")
    qr_image: str | None = None        # data URI base64
    account_name: str | None = None
    error_msg: str | None = None


@router.get("/ingest/pending-login", dependencies=[Depends(_verify_ingest_secret)])
async def ingest_pending_login(db: AsyncSession = Depends(get_db)):
    """Ingest Service poll: admin có yêu cầu đăng nhập mới không?"""
    sess = await _get_session(db)
    # heartbeat
    sess.last_seen = datetime.now(timezone.utc)
    await db.flush()
    return {"login_requested": sess.login_requested, "current_status": sess.status}


class CredentialsBody(BaseModel):
    cookie: list | dict | str
    imei: str = Field(max_length=200)
    user_agent: str = Field(max_length=500)


@router.get("/ingest/credentials", dependencies=[Depends(_verify_ingest_secret)])
async def ingest_get_credentials(db: AsyncSession = Depends(get_db)):
    """Listener khởi động lại → lấy phiên đã lưu để khỏi quét QR."""
    sess = await _get_session(db)
    if sess.status == "logged_out":
        return {"credentials": None}
    return {"credentials": tro_ly.giai_ma_phien(sess.credentials_enc)}


@router.post("/ingest/credentials", dependencies=[Depends(_verify_ingest_secret)])
async def ingest_save_credentials(body: CredentialsBody, db: AsyncSession = Depends(get_db)):
    """Lưu phiên Zalo (cookie + imei) đã mã hóa."""
    sess = await _get_session(db)
    sess.credentials_enc = tro_ly.ma_hoa_phien(
        {"cookie": body.cookie, "imei": body.imei, "userAgent": body.user_agent}
    )
    await db.flush()
    return {"ok": True}


@router.delete("/ingest/credentials", dependencies=[Depends(_verify_ingest_secret)])
async def ingest_clear_credentials(db: AsyncSession = Depends(get_db)):
    """Phiên lưu hết hạn/bị đẩy ra → bỏ để chờ admin quét QR lại."""
    sess = await _get_session(db)
    sess.credentials_enc = None
    await db.flush()
    return {"ok": True}


class GroupSyncItem(BaseModel):
    zalo_group_id: str = Field(max_length=64)
    name: str = Field(max_length=200)
    member_count: int | None = None


class GroupSyncBody(BaseModel):
    groups: list[GroupSyncItem] = Field(max_length=1000)


@router.post("/ingest/groups", dependencies=[Depends(_verify_ingest_secret)])
async def ingest_sync_groups(body: GroupSyncBody, db: AsyncSession = Depends(get_db)):
    """Đồng bộ danh sách nhóm sau đăng nhập. Nhóm mới vào ở trạng thái TẮT theo
    dõi — admin tự chọn nhóm nào nghe, gắn phòng ban, loại nội bộ/khách."""
    existing = {g.zalo_group_id: g for g in (await db.execute(select(ZaloGroup))).scalars().all()}
    created = 0
    for item in body.groups:
        g = existing.get(item.zalo_group_id)
        if g:
            g.name = item.name or g.name
            if item.member_count is not None:
                g.member_count = item.member_count
        else:
            db.add(ZaloGroup(
                zalo_group_id=item.zalo_group_id, name=item.name or item.zalo_group_id,
                kind="internal", monitoring=False, member_count=item.member_count,
            ))
            created += 1
    await db.flush()
    return {"ok": True, "created": created, "total": len(body.groups)}


@router.post("/ingest/session", dependencies=[Depends(_verify_ingest_secret)])
async def ingest_report_session(body: SessionReport, db: AsyncSession = Depends(get_db)):
    """Ingest Service đẩy QR / trạng thái đăng nhập về cho admin xem."""
    sess = await _get_session(db)
    sess.status = body.status
    sess.qr_image = body.qr_image
    sess.error_msg = body.error_msg
    if body.account_name:
        sess.account_name = body.account_name
    if body.status in ("logged_in", "error"):
        # xong hoặc hỏng (QR hết hạn, bị từ chối) → hạ cờ, admin bấm lại khi cần
        sess.login_requested = False
        sess.qr_image = None
    sess.last_seen = datetime.now(timezone.utc)
    await db.flush()
    return {"ok": True}


class IngestMessage(BaseModel):
    zalo_group_id: str
    group_name: str
    sender_zalo_id: str | None = None
    sender_name: str | None = None
    text: str | None = None
    media_ref: str | None = None


@router.post("/ingest/message", dependencies=[Depends(_verify_ingest_secret)])
async def ingest_message(body: IngestMessage, db: AsyncSession = Depends(get_db)):
    """Nhận 1 tin nhắn nhóm từ Ingest Service → lưu + phân tích → tạo tín hiệu."""
    sess = await _get_session(db)
    sess.last_seen = datetime.now(timezone.utc)

    # Tìm/tạo nhóm. Mới thấy lần đầu → tạo ở trạng thái TẮT (như /ingest/groups):
    # admin phải chủ động bật nhóm nào được nghe, không nghe lén nhóm lạ.
    result = await db.execute(select(ZaloGroup).where(ZaloGroup.zalo_group_id == body.zalo_group_id))
    group = result.scalar_one_or_none()
    if not group:
        group = ZaloGroup(zalo_group_id=body.zalo_group_id, name=body.group_name, kind="internal", monitoring=False)
        db.add(group)
        await db.flush()
    elif body.group_name and group.name.startswith("Nhom ") and body.group_name != group.name:
        group.name = body.group_name  # thay tên tạm bằng tên thật

    if not group.monitoring:
        return {"stored": False, "reason": "Nhóm đang tắt theo dõi"}

    # Ai nói trong nhóm nội bộ = nhân viên → nhóm khách biết tin nào là của mình
    if group.kind == "internal":
        await tro_ly.ghi_nhan_nhan_vien(db, body.sender_zalo_id, body.sender_name)
        is_staff = True
    else:
        is_staff = await tro_ly.la_nhan_vien(db, body.sender_zalo_id)

    message = ZaloMessage(
        group_id=group.id,
        sender_zalo_id=body.sender_zalo_id,
        sender_name=body.sender_name,
        text=body.text,
        media_ref=body.media_ref,
        is_staff=is_staff,
    )
    db.add(message)
    group.last_message_at = datetime.now(timezone.utc).replace(tzinfo=None)
    await db.flush()

    signals = await analyze_and_store(
        db, message, group, use_llm=True, tu_nhan_vien=is_staff and group.kind == "customer"
    )

    # Báo gấp Telegram: người phụ trách + trưởng phòng; khách phàn nàn/khách chờ thêm BGĐ
    await tro_ly.bao_gap(db, group, signals)

    return {"stored": True, "signals_created": len(signals)}
