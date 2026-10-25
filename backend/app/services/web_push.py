"""Web Push — đẩy thông báo ra điện thoại/máy tính (25/10/2026).

Mọi `Notification` (quả chuông trong app) tạo trong một request web đều được
đẩy luôn tới các máy người nhận đã bấm «Bật thông báo trên máy này»:
- `after_flush` gom Notification mới vào `session.info["web_push"]`;
- `get_db` commit xong mới gọi `day_sau_commit` → chạy nền, không làm chậm
  request; request lỗi (rollback) thì không đẩy gì.

Thiếu VAPID_PUBLIC_KEY/VAPID_PRIVATE_KEY (máy dev, test) → bỏ qua êm.
iPhone/iPad chỉ nhận push khi đã «Thêm vào MH chính» (iOS 16.4+).
"""

import asyncio
import hashlib
import json
import logging

from sqlalchemy import delete, event, select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models.notification import Notification
from app.models.push_subscription import PushSubscription

logger = logging.getLogger(__name__)

KHOA_HANG_DOI = "web_push"
_viec_nen: set[asyncio.Task] = set()


def bat() -> bool:
    s = get_settings()
    return bool(s.VAPID_PUBLIC_KEY and s.VAPID_PRIVATE_KEY)


def bam_endpoint(endpoint: str) -> str:
    return hashlib.sha256(endpoint.encode()).hexdigest()


@event.listens_for(Session, "after_flush")
def _gom_thong_bao(session: Session, _ctx) -> None:
    moi = [o for o in session.new if isinstance(o, Notification)]
    if not moi:
        return
    hang = session.info.setdefault(KHOA_HANG_DOI, [])
    for n in moi:
        hang.append({
            "user_id": n.user_id, "title": n.title, "body": (n.body or "")[:300],
            "url": n.link or "/", "tag": n.ref_id or n.id,
        })


@event.listens_for(Session, "after_rollback")
def _bo_hang_doi(session: Session) -> None:
    session.info.pop(KHOA_HANG_DOI, None)


def day_sau_commit(session) -> None:
    """Gọi sau commit: lấy hàng đợi của session, đẩy ở việc nền."""
    hang = session.info.pop(KHOA_HANG_DOI, None)
    if not hang or not bat():
        return
    try:
        task = asyncio.get_running_loop().create_task(day_nhieu(hang))
    except RuntimeError:
        return
    _viec_nen.add(task)
    task.add_done_callback(_viec_nen.discard)


def _gui_mot(sub: dict, payload: str) -> int:
    """Gửi một máy (đồng bộ, chạy trong thread). Trả mã HTTP (0 = lỗi mạng)."""
    from pywebpush import WebPushException, webpush

    s = get_settings()
    try:
        resp = webpush(
            subscription_info={"endpoint": sub["endpoint"], "keys": {"p256dh": sub["p256dh"], "auth": sub["auth"]}},
            data=payload.encode("utf-8"),
            vapid_private_key=s.VAPID_PRIVATE_KEY,
            vapid_claims={"sub": s.VAPID_SUBJECT},
            ttl=86400,
            timeout=10,
        )
        ma = getattr(resp, "status_code", 201)
        if not 200 <= ma < 300:
            logger.warning("web push %s: %s", ma, (getattr(resp, "text", "") or "")[:200])
        return ma
    except WebPushException as exc:
        ma = getattr(exc.response, "status_code", 0) or 0
        than = (getattr(exc.response, "text", "") or str(exc))[:200]
        # 404/410 = máy đã gỡ đăng ký (bình thường); còn lại là lỗi cấu hình/VAPID cần thấy trong log
        (logger.info if ma in (404, 410) else logger.warning)("web push lỗi %s: %s", ma, than)
        return ma
    except Exception as exc:  # mạng chập chờn — không làm hỏng việc khác
        logger.warning("web push lỗi: %s", type(exc).__name__)
        return 0


async def day_nhieu(hang: list[dict], session_factory=None) -> int:
    """Đẩy danh sách thông báo; xoá đăng ký chết (404/410). Trả số lượt gửi được."""
    ma = await day_nhieu_chi_tiet(hang, session_factory)
    return sum(1 for m in ma if 200 <= m < 300)


async def day_nhieu_chi_tiet(hang: list[dict], session_factory=None, db=None) -> list[int]:
    """Như `day_nhieu` nhưng trả mã HTTP từng lượt gửi (để «Gửi thử» báo lỗi thật).
    `db`: dùng lại session của request (endpoint /push/test); không có thì tự mở."""
    if not hang or not bat():
        return []
    if db is not None:
        return await _day_voi_session(hang, db)
    if session_factory is None:
        from app.database import async_session as session_factory
    async with session_factory() as db:
        return await _day_voi_session(hang, db)


async def _day_voi_session(hang: list[dict], db) -> list[int]:
    user_ids = {h["user_id"] for h in hang}
    subs = (await db.execute(
        select(PushSubscription).where(PushSubscription.user_id.in_(user_ids))
    )).scalars().all()
    theo_nguoi: dict[str, list[dict]] = {}
    for s in subs:
        theo_nguoi.setdefault(s.user_id, []).append(
            {"id": s.id, "endpoint": s.endpoint, "p256dh": s.p256dh, "auth": s.auth}
        )

    viec = []
    for h in hang:
        payload = json.dumps(
            {"title": h["title"], "body": h["body"], "url": h["url"], "tag": h["tag"]},
            ensure_ascii=False,
        )
        for sub in theo_nguoi.get(h["user_id"], []):
            viec.append((sub["id"], asyncio.to_thread(_gui_mot, sub, payload)))
    if not viec:
        return []
    ma = list(await asyncio.gather(*(v for _, v in viec)))
    chet = {sid for (sid, _), m in zip(viec, ma) if m in (404, 410)}
    if chet:
        await db.execute(delete(PushSubscription).where(PushSubscription.id.in_(chet)))
        await db.commit()
    return ma
