"""Cài đặt Shopee Affiliate — chỉ Admin nhập App ID / Secret (26/10/2026)."""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.ai_settings import _mask, _require_admin
from app.database import get_db
from app.models.user import User
from app.services import shopee_affiliate as sa
from app.services.automation import set_automation_setting

router = APIRouter(prefix="/shopee-settings", tags=["shopee"])


class ShopeeIn(BaseModel):
    app_id: str | None = Field(default=None, max_length=100)
    secret: str | None = Field(default=None, max_length=200)


async def _tra(db: AsyncSession) -> dict:
    app_id, secret = await sa.lay_khoa(db)
    return {"app_id": app_id or "", "secret_masked": _mask(secret) if secret else "",
            "secret_set": bool(secret), "san_sang": bool(app_id and secret)}


@router.get("")
async def doc(db: AsyncSession = Depends(get_db), _: User = Depends(_require_admin)):
    return await _tra(db)


@router.put("")
async def luu(body: ShopeeIn, db: AsyncSession = Depends(get_db), _: User = Depends(_require_admin)):
    if body.app_id is not None:
        await set_automation_setting(db, sa.KEY_APP_ID, body.app_id.strip())
    if body.secret:
        await set_automation_setting(db, sa.KEY_SECRET, body.secret.strip())
    await db.commit()
    return await _tra(db)


@router.post("/thu")
async def thu(db: AsyncSession = Depends(get_db), _: User = Depends(_require_admin)):
    """Gọi thử Shopee với một từ khoá mẫu để biết khoá chạy chưa."""
    try:
        items = await sa.tim_san_pham(db, "gạch ốp lát", limit=3)
    except sa.ShopeeError as exc:
        raise HTTPException(exc.status, str(exc))
    return {"ok": True, "so_ket_qua": len(items), "vi_du": items[:3]}
