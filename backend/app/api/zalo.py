"""Zalo Listener API (spec 09).

2 nhóm endpoint:
- ADMIN (JWT, role=admin): cấu hình QR login, quản lý nhóm theo dõi, xem tín hiệu.
- INGEST SERVICE (header X-Zalo-Secret): Node zca-js đẩy QR/heartbeat + tin nhắn vào.

Nguyên tắc: listen-only — backend KHÔNG có endpoint nào để gửi tin ra Zalo.
"""

import hmac
import json
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.database import get_db
from app.middleware.auth import get_current_user
from app.models.user import User
from app.models.zalo import ZaloSession, ZaloGroup, ZaloMessage, ZaloSignal
from app.services.audit import log_action
from app.services.zalo_analysis import analyze_and_store

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
        setattr(group, k, v)
    await db.flush()
    return {"id": group.id, "monitoring": group.monitoring, "kind": group.kind}


# ---------------------------------------------------------------------------
# ADMIN/SALE — tín hiệu
# ---------------------------------------------------------------------------

@router.get("/signals")
async def list_signals(
    status: str = Query("new", pattern=r"^(new|actioned|dismissed|all)$"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Tín hiệu Zalo. Admin/leader thấy hết; role khác chỉ thấy tín hiệu gán cho mình (spec 09 §5.4)."""
    q = select(ZaloSignal, ZaloGroup.name).join(ZaloGroup, ZaloGroup.id == ZaloSignal.group_id)
    if status != "all":
        q = q.where(ZaloSignal.status == status)
    if current_user.role not in ("admin", "leader"):
        q = q.where(ZaloSignal.assigned_user_id == current_user.id)
    q = q.order_by(ZaloSignal.created_at.desc()).limit(100)
    rows = (await db.execute(q)).all()
    return {"items": [
        {
            "id": s.id, "type": s.type, "summary": s.summary, "status": s.status,
            "group_name": group_name, "assigned_user_id": s.assigned_user_id,
            "payload": json.loads(s.payload_json) if s.payload_json else {},
            "created_at": str(s.created_at),
        }
        for s, group_name in rows
    ]}


class SignalAction(BaseModel):
    action: str = Field(pattern=r"^(actioned|dismissed)$")


@router.post("/signals/{signal_id}/action")
async def act_signal(signal_id: str, body: SignalAction, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    signal = await db.get(ZaloSignal, signal_id)
    if not signal:
        raise HTTPException(status_code=404, detail="Tín hiệu không tồn tại")
    if current_user.role not in ("admin", "leader") and signal.assigned_user_id != current_user.id:
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


@router.post("/ingest/session", dependencies=[Depends(_verify_ingest_secret)])
async def ingest_report_session(body: SessionReport, db: AsyncSession = Depends(get_db)):
    """Ingest Service đẩy QR / trạng thái đăng nhập về cho admin xem."""
    sess = await _get_session(db)
    sess.status = body.status
    sess.qr_image = body.qr_image
    sess.error_msg = body.error_msg
    if body.account_name:
        sess.account_name = body.account_name
    if body.status == "logged_in":
        sess.login_requested = False  # đã đăng nhập xong
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

    # Tìm/tạo nhóm (mới thấy lần đầu → tạo, mặc định internal + monitoring bật)
    result = await db.execute(select(ZaloGroup).where(ZaloGroup.zalo_group_id == body.zalo_group_id))
    group = result.scalar_one_or_none()
    if not group:
        group = ZaloGroup(zalo_group_id=body.zalo_group_id, name=body.group_name, kind="internal", monitoring=True)
        db.add(group)
        await db.flush()

    if not group.monitoring:
        return {"stored": False, "reason": "Nhóm đang tắt theo dõi"}

    message = ZaloMessage(
        group_id=group.id,
        sender_zalo_id=body.sender_zalo_id,
        sender_name=body.sender_name,
        text=body.text,
        media_ref=body.media_ref,
    )
    db.add(message)
    await db.flush()

    signals = await analyze_and_store(db, message, group, use_llm=True)

    # Đẩy tín hiệu quan trọng về Telegram cho người phụ trách (nếu đã gán + có Telegram)
    if signals and group.assigned_user_id:
        assignee = await db.get(User, group.assigned_user_id)
        if assignee and assignee.telegram_user_id:
            from app.services.telegram_notify import send_telegram
            for sig in signals:
                if sig.type in ("lead_candidate", "quote_request", "deal_risk", "unanswered"):
                    await send_telegram(
                        assignee.telegram_user_id,
                        f"🔔 <b>Zalo: {group.name}</b>\n{sig.summary}",
                    )

    return {"stored": True, "signals_created": len(signals)}
