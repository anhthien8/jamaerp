"""Shopee Affiliate Open API (VN) — giá thị trường + link affiliate cho mẫu vật tư (26/10/2026).

Khoá (App ID + Secret) admin nhập ở Cài đặt → lưu system_settings (shopee_aff_app_id /
shopee_aff_secret). API GraphQL, ký SHA256(AppId + Timestamp + Payload + Secret).
Chỉ ra được sản phẩm có tham gia affiliate — vật liệu nặng thường không có, khi đó
trả danh sách rỗng, KHÔNG đoán giá.
"""

from __future__ import annotations

import hashlib
import json
import logging
import time
from typing import Any

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.automation import get_automation_settings

logger = logging.getLogger(__name__)

ENDPOINT = "https://open-api.affiliate.shopee.vn/graphql"
KEY_APP_ID = "shopee_aff_app_id"
KEY_SECRET = "shopee_aff_secret"

_FIELDS = ("itemId productName priceMin priceMax commissionRate sales ratingStar "
           "shopName imageUrl productLink offerLink")


class ShopeeError(Exception):
    def __init__(self, msg: str, status: int = 502):
        super().__init__(msg)
        self.status = status


async def lay_khoa(db: AsyncSession) -> tuple[str, str]:
    s = await get_automation_settings(db)
    return (s.get(KEY_APP_ID) or "").strip(), (s.get(KEY_SECRET) or "").strip()


def ky(app_id: str, secret: str, ts: int, payload: str) -> str:
    return hashlib.sha256(f"{app_id}{ts}{payload}{secret}".encode()).hexdigest()


async def _goi(db: AsyncSession, query: str, variables: dict | None = None) -> dict:
    app_id, secret = await lay_khoa(db)
    if not app_id or not secret:
        raise ShopeeError("Chưa bật tìm giá Shopee — báo Admin", 503)
    payload = json.dumps({"query": query, "variables": variables or {}}, separators=(",", ":"), ensure_ascii=False)
    ts = int(time.time())
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"SHA256 Credential={app_id}, Timestamp={ts}, Signature={ky(app_id, secret, ts, payload)}",
    }
    try:
        async with httpx.AsyncClient(timeout=20) as c:
            r = await c.post(ENDPOINT, content=payload.encode(), headers=headers)
        data = r.json()
    except (httpx.HTTPError, ValueError) as exc:
        logger.warning("Shopee Affiliate lỗi mạng: %s", exc)
        raise ShopeeError("Không kết nối được Shopee lúc này — thử lại sau") from exc
    if data.get("errors"):
        msg = str(data["errors"][0].get("message", "lỗi không rõ"))
        logger.warning("Shopee Affiliate trả lỗi: %s", msg)
        if "auth" in msg.lower() or "sign" in msg.lower() or "credential" in msg.lower():
            raise ShopeeError("Shopee từ chối khoá — kiểm tra lại App ID / Secret ở Cài đặt", 400)
        raise ShopeeError(f"Shopee báo lỗi: {msg}")
    return data.get("data") or {}


def _so(v: Any) -> float | None:
    try:
        return float(v) if v not in (None, "") else None
    except (TypeError, ValueError):
        return None


def chuan_hoa_sp(n: dict) -> dict:
    gia_min, gia_max = _so(n.get("priceMin")), _so(n.get("priceMax"))
    return {
        "item_id": str(n.get("itemId") or ""),
        "ten": n.get("productName") or "",
        "gia": gia_min or gia_max,
        "gia_max": gia_max,
        "da_ban": int(_so(n.get("sales")) or 0),
        "sao": _so(n.get("ratingStar")),
        "shop": n.get("shopName"),
        "anh": n.get("imageUrl"),
        "link": n.get("productLink"),
        "link_aff": n.get("offerLink") or n.get("productLink"),
        "hoa_hong_pct": round((_so(n.get("commissionRate")) or 0) * 100, 2),
    }


async def tim_san_pham(db: AsyncSession, tu_khoa: str, limit: int = 8) -> list[dict]:
    q = f"query($kw:String,$limit:Int){{productOfferV2(keyword:$kw,sortType:1,page:1,limit:$limit){{nodes{{{_FIELDS}}}}}}}"
    d = await _goi(db, q, {"kw": tu_khoa[:120], "limit": limit})
    return [chuan_hoa_sp(n) for n in ((d.get("productOfferV2") or {}).get("nodes") or [])]


async def lay_theo_item(db: AsyncSession, item_id: str) -> dict | None:
    q = f"query($id:Int64){{productOfferV2(itemId:$id,page:1,limit:1){{nodes{{{_FIELDS}}}}}}}"
    d = await _goi(db, q, {"id": int(item_id)})
    nodes = (d.get("productOfferV2") or {}).get("nodes") or []
    return chuan_hoa_sp(nodes[0]) if nodes else None


async def link_aff(db: AsyncSession, url: str) -> str:
    q = "mutation($u:String!){generateShortLink(input:{originUrl:$u,subIds:[\"jamaerp\"]}){shortLink}}"
    d = await _goi(db, q, {"u": url})
    return ((d.get("generateShortLink") or {}).get("shortLink")) or url


def tu_khoa_mau(m) -> str:
    return " ".join(x for x in (m.hang, m.ma, m.ten) if x).strip()


async def cap_nhat_gia_hang_tuan(db: AsyncSession, toi_da: int = 200) -> int:
    """Worker: làm mới giá Shopee các mẫu đã ghép sản phẩm (cũ nhất trước)."""
    from datetime import datetime, timezone

    from sqlalchemy import select

    from app.models.vat_tu import MauVatTu

    app_id, secret = await lay_khoa(db)
    if not app_id or not secret:
        return 0
    ds = (await db.execute(
        select(MauVatTu).where(MauVatTu.shopee_item_id.is_not(None), MauVatTu.is_active == True)  # noqa: E712
        .order_by(MauVatTu.gia_shopee_luc.asc().nulls_first()).limit(toi_da)
    )).scalars().all()
    n = 0
    for m in ds:
        try:
            sp = await lay_theo_item(db, m.shopee_item_id)
        except ShopeeError:
            break  # khoá/quota hỏng — để lần sau
        m.gia_shopee_luc = datetime.now(timezone.utc)
        if sp and sp["gia"]:
            m.gia_shopee = sp["gia"]
            n += 1
    await db.commit()
    return n
