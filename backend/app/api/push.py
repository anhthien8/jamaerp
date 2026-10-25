"""Bật/tắt Web Push trên từng máy (25/10/2026). Xem app/services/web_push.py."""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.database import get_db
from app.middleware.auth import get_current_user
from app.models.notification import Notification
from app.models.push_subscription import PushSubscription
from app.models.user import User
from app.services import web_push

router = APIRouter(prefix="/push", tags=["push"])

TOI_DA_MAY_MOT_NGUOI = 10


class Keys(BaseModel):
    p256dh: str = Field(..., min_length=10, max_length=255)
    auth: str = Field(..., min_length=4, max_length=255)


class DangKy(BaseModel):
    endpoint: str = Field(..., min_length=10, max_length=2000)
    keys: Keys
    user_agent: str | None = Field(None, max_length=255)


class HuyDangKy(BaseModel):
    endpoint: str = Field(..., min_length=10, max_length=2000)


@router.get("/public-key")
async def public_key(current_user: User = Depends(get_current_user)):
    return {"enabled": web_push.bat(), "public_key": get_settings().VAPID_PUBLIC_KEY or None}


@router.post("/subscribe", status_code=201)
async def subscribe(
    body: DangKy,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not web_push.bat():
        raise HTTPException(status_code=503, detail="Máy chủ chưa cấu hình thông báo đẩy (VAPID)")
    if not body.endpoint.startswith("https://"):
        raise HTTPException(status_code=400, detail="Địa chỉ đăng ký không hợp lệ")
    bam = web_push.bam_endpoint(body.endpoint)
    cu = (await db.execute(
        select(PushSubscription).where(PushSubscription.endpoint_hash == bam)
    )).scalar_one_or_none()
    if cu:
        # Cùng máy, người khác đăng nhập → chuyển sang người đang dùng
        cu.user_id, cu.p256dh, cu.auth = current_user.id, body.keys.p256dh, body.keys.auth
        cu.user_agent = body.user_agent
    else:
        db.add(PushSubscription(
            user_id=current_user.id, endpoint_hash=bam, endpoint=body.endpoint,
            p256dh=body.keys.p256dh, auth=body.keys.auth, user_agent=body.user_agent,
        ))
    await db.flush()
    # Giữ tối đa 10 máy/người — máy cũ nhất bị bỏ
    ids = (await db.execute(
        select(PushSubscription.id).where(PushSubscription.user_id == current_user.id)
        .order_by(PushSubscription.created_at.desc())
    )).scalars().all()
    if len(ids) > TOI_DA_MAY_MOT_NGUOI:
        await db.execute(delete(PushSubscription).where(PushSubscription.id.in_(ids[TOI_DA_MAY_MOT_NGUOI:])))
    await db.commit()
    return {"ok": True}


@router.post("/unsubscribe")
async def unsubscribe(
    body: HuyDangKy,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await db.execute(delete(PushSubscription).where(
        PushSubscription.endpoint_hash == web_push.bam_endpoint(body.endpoint),
        PushSubscription.user_id == current_user.id,
    ))
    await db.commit()
    return {"ok": True}


@router.get("/status")
async def status(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    so = (await db.execute(
        select(func.count()).select_from(PushSubscription).where(PushSubscription.user_id == current_user.id)
    )).scalar_one()
    return {"enabled": web_push.bat(), "devices": so}


@router.post("/test")
async def test_push(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Gửi thử: đẩy NGAY tới mọi máy của người bấm và trả kết quả thật
    (số máy, số gửi được, mã lỗi) — không đi đường chuông nền để màn hình
    Cài đặt nói được vì sao không thấy gì (25/10/2026, feedback «Gửi thử không thấy gì»)."""
    so_may = (await db.execute(
        select(func.count()).select_from(PushSubscription).where(PushSubscription.user_id == current_user.id)
    )).scalar_one()
    if not web_push.bat():
        return {"ok": False, "devices": so_may, "sent": 0, "codes": [], "reason": "Máy chủ chưa cấu hình khoá VAPID"}
    if so_may == 0:
        return {"ok": False, "devices": 0, "sent": 0, "codes": [], "reason": "Máy này chưa đăng ký nhận thông báo — bấm Tắt rồi Bật lại"}
    ket_qua = await web_push.day_nhieu_chi_tiet([{
        "user_id": current_user.id, "title": "Thử thông báo JAMA",
        "body": "Máy này đã nhận được thông báo từ ERP.", "url": "/", "tag": f"test-{current_user.id}",
    }], db=db)
    gui = sum(1 for m in ket_qua if 200 <= m < 300)
    return {"ok": gui > 0, "devices": so_may, "sent": gui, "codes": ket_qua}
