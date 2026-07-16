"""Instant Quote API — báo giá sơ bộ tức thì.

- /instant-quote/generate (auth): sale nhập số liệu hoặc paste text Zalo (AI parse)
- /instant-quote/public (KHÔNG auth, rate-limit): mini-app cho khách tự báo giá
  → chỉ trả KHOẢNG GIÁ (không lộ chi tiết đơn giá cho đối thủ) + tự tạo lead
- /instant-quote/price-items (admin/purchasing): quản lý bảng đơn giá
"""

import time
from collections import defaultdict
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.auth import get_current_user
from app.models.user import User
from app.models.lead import Lead
from app.models.pricing import PriceItem, PRICE_CATEGORIES, PRICE_UNITS
from app.services.instant_quote import (
    ensure_price_items,
    format_quote_for_zalo,
    format_renovation_quote_for_zalo,
    generate_quote,
    generate_renovation_quote,
    suggest_tier,
)

router = APIRouter(prefix="/instant-quote", tags=["instant-quote"])

# ── Rate limit cho endpoint public (chống spam/cào giá) ──────────────────
_public_hits: dict[str, list[float]] = defaultdict(list)
_PUBLIC_MAX = 5          # 5 lần
_PUBLIC_WINDOW = 3600    # mỗi giờ / IP


def _check_public_rate_limit(ip: str) -> None:
    now = time.time()
    _public_hits[ip] = [t for t in _public_hits[ip] if now - t < _PUBLIC_WINDOW]
    if not _public_hits[ip]:
        del _public_hits[ip]
    elif len(_public_hits[ip]) >= _PUBLIC_MAX:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Bạn đã dùng hết lượt báo giá. Vui lòng để lại SĐT, JAMA HOME sẽ liên hệ tư vấn!",
        )
    _public_hits[ip].append(now)


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class QuoteRequest(BaseModel):
    # Mode: "new" = xây mới, "renovation" = cải tạo
    mode: str = "new"
    # Cách 1: số liệu trực tiếp
    area_sqm: float | None = Field(default=None, gt=0, le=5000)
    property_type: str = "apartment"
    bedrooms: int | None = Field(default=None, ge=0, le=10)
    budget: float | None = Field(default=None, ge=0)
    # Cách 2: text mơ hồ từ Zalo → AI parse
    raw_text: str | None = Field(default=None, max_length=3000)
    # Renovation-specific
    floors: int = Field(default=3, ge=1, le=4)
    scope: str = "full"  # full or partial


class PublicQuoteRequest(BaseModel):
    name: str = Field(min_length=1, max_length=150)
    phone: str = Field(min_length=8, max_length=20)
    mode: str = "new"
    area_sqm: float = Field(gt=0, le=5000)
    property_type: str = "apartment"
    bedrooms: int | None = Field(default=None, ge=0, le=10)
    budget: float | None = Field(default=None, ge=0)
    floors: int = Field(default=3, ge=1, le=4)
    note: str | None = Field(default=None, max_length=500)


class PriceItemUpdate(BaseModel):
    name: str | None = Field(default=None, max_length=255)
    category: str | None = None
    unit: str | None = None
    price_basic: float | None = Field(default=None, ge=0)
    price_standard: float | None = Field(default=None, ge=0)
    price_premium: float | None = Field(default=None, ge=0)
    note: str | None = Field(default=None, max_length=500)
    is_active: bool | None = None


class PriceItemCreate(PriceItemUpdate):
    code: str = Field(min_length=2, max_length=30)
    name: str = Field(min_length=1, max_length=255)
    category: str = "khac"
    unit: str = "m2"
    price_basic: float = Field(ge=0)
    price_standard: float = Field(ge=0)
    price_premium: float = Field(ge=0)


# ---------------------------------------------------------------------------
# Sale endpoint — full chi tiết
# ---------------------------------------------------------------------------

@router.post("/generate")
async def generate(
    payload: QuoteRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    area = payload.area_sqm
    ptype = payload.property_type
    bedrooms = payload.bedrooms
    budget = payload.budget
    parsed = None

    # Text mơ hồ → AI parse (fallback regex có sẵn trong agent)
    if payload.raw_text and not area:
        from app.agents.lead_intake import parse_lead_text

        parsed_resp = await parse_lead_text(payload.raw_text)
        area = float(parsed_resp.area_sqm) if parsed_resp.area_sqm else None
        ptype = parsed_resp.property_type or ptype
        budget = budget or (float(parsed_resp.estimated_budget) if parsed_resp.estimated_budget else None)
        parsed = {
            "name": parsed_resp.name, "phone": parsed_resp.phone,
            "area_sqm": area, "property_type": ptype, "budget": budget,
        }

    if not area:
        raise HTTPException(
            status_code=400,
            detail="Không xác định được diện tích — nhập số m² hoặc text có kèm diện tích",
        )

    # Route to correct engine based on mode
    if payload.mode == "renovation":
        quote = generate_renovation_quote(area, payload.floors, payload.scope)
        return {
            **quote,
            "customer_budget": budget,
            "zalo_text": format_renovation_quote_for_zalo(quote),
            "parsed": parsed,
        }

    # Default: new construction mode
    quote = await generate_quote(db, area, ptype, bedrooms)
    tier = suggest_tier(quote, budget)
    return {
        **quote,
        "suggested_tier": tier,
        "customer_budget": budget,
        "zalo_text": format_quote_for_zalo(quote, tier),
        "parsed": parsed,
    }


# ---------------------------------------------------------------------------
# Public endpoint — lead magnet, chỉ trả khoảng giá
# ---------------------------------------------------------------------------

@router.post("/public")
async def public_quote(
    request: Request,
    payload: PublicQuoteRequest,
    db: AsyncSession = Depends(get_db),
):
    client_ip = request.client.host if request.client else "unknown"
    _check_public_rate_limit(client_ip)

    # Route to correct engine
    if payload.mode == "renovation":
        quote = generate_renovation_quote(payload.area_sqm, payload.floors)
        # Tạo lead
        phone_clean = "".join(c for c in payload.phone if c.isdigit() or c == "+")
        existing = await db.execute(
            select(Lead).where(Lead.phone == phone_clean, Lead.stage.notin_(["lost"]))
        )
        if not existing.scalars().first():
            db.add(Lead(
                name=payload.name.strip(),
                phone=phone_clean,
                source="website",
                property_type="townhouse",
                area_sqm=payload.area_sqm,
                estimated_budget=payload.budget,
                needs=(payload.note or f"Cải tạo {payload.floors} tầng").strip() or None,
                notes=(
                    f"🤖 Báo giá cải tạo tự động ({datetime.now(timezone.utc).strftime('%d/%m/%Y')}). "
                    f"~{quote['total'] / 1_000_000:,.0f} triệu ({payload.floors} tầng)."
                ),
                priority="high",
            ))
            await db.commit()
        return {
            "mode": "renovation",
            "area_sqm": quote["area_sqm"],
            "floors": quote["floors"],
            "total": quote["total"],
            "range_low": quote["range_low"],
            "range_high": quote["range_high"],
            "per_sqm": quote["per_sqm"],
            "disclaimer": quote["disclaimer"],
            "message": "JAMA HOME sẽ liên hệ trong 24h để đặt lịch khảo sát miễn phí!",
        }

    # Default: new construction
    quote = await generate_quote(db, payload.area_sqm, payload.property_type, payload.bedrooms)
    tier = suggest_tier(quote, payload.budget)

    # Tạo lead
    phone_clean = "".join(c for c in payload.phone if c.isdigit() or c == "+")
    existing = await db.execute(
        select(Lead).where(Lead.phone == phone_clean, Lead.stage.notin_(["lost"]))
    )
    if not existing.scalars().first():
        db.add(Lead(
            name=payload.name.strip(),
            phone=phone_clean,
            source="website",
            property_type=payload.property_type,
            area_sqm=payload.area_sqm,
            estimated_budget=payload.budget,
            needs=(payload.note or "").strip() or None,
            notes=(
                f"🤖 Từ công cụ báo giá tự động ({datetime.now(timezone.utc).strftime('%d/%m/%Y')}). "
                f"Phương án gợi ý: {quote['tiers'][tier]['label']} "
                f"~{quote['tiers'][tier]['total'] / 1_000_000:,.0f} triệu."
            ),
            priority="high",
        ))
        await db.commit()

    return {
        "mode": "new",
        "area_sqm": quote["area_sqm"],
        "property_type": quote["property_type"],
        "bedrooms": quote["bedrooms"],
        "suggested_tier": tier,
        "tiers": {
            t: {
                "label": v["label"],
                "range_low": v["range_low"],
                "range_high": v["range_high"],
                "per_sqm": v["per_sqm"],
            }
            for t, v in quote["tiers"].items()
        },
        "disclaimer": quote["disclaimer"],
        "message": "JAMA HOME sẽ liên hệ trong 24h để đặt lịch khảo sát miễn phí!",
    }


# ---------------------------------------------------------------------------
# Price book CRUD — admin + purchasing
# ---------------------------------------------------------------------------

def _require_pricing_role(current_user: User = Depends(get_current_user)) -> User:
    if current_user.role not in ("admin", "supervisor"):
        raise HTTPException(status_code=403, detail="Chỉ Admin/Thu mua được quản lý đơn giá")
    return current_user


@router.get("/price-items")
async def list_price_items(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Mọi user đăng nhập xem được bảng giá (sale cần để tư vấn)."""
    await ensure_price_items(db)
    await db.commit()
    result = await db.execute(
        select(PriceItem).order_by(PriceItem.category, PriceItem.code)
    )
    items = result.scalars().all()
    return [
        {
            "id": p.id, "code": p.code, "name": p.name, "category": p.category,
            "unit": p.unit, "price_basic": p.price_basic,
            "price_standard": p.price_standard, "price_premium": p.price_premium,
            "note": p.note, "is_active": p.is_active,
            "updated_at": p.updated_at.isoformat() if p.updated_at else None,
        }
        for p in items
    ]


@router.post("/price-items", status_code=201)
async def create_price_item(
    payload: PriceItemCreate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(_require_pricing_role),
):
    if payload.category not in PRICE_CATEGORIES:
        raise HTTPException(status_code=400, detail="Danh mục không hợp lệ")
    if payload.unit not in PRICE_UNITS:
        raise HTTPException(status_code=400, detail="Đơn vị không hợp lệ")
    existing = await db.execute(select(PriceItem).where(PriceItem.code == payload.code))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Mã hạng mục đã tồn tại")

    item = PriceItem(**payload.model_dump())
    db.add(item)
    await db.commit()
    return {"id": item.id, "code": item.code}


@router.put("/price-items/{item_id}")
async def update_price_item(
    item_id: str,
    payload: PriceItemUpdate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(_require_pricing_role),
):
    item = await db.get(PriceItem, item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Hạng mục không tồn tại")

    updates = payload.model_dump(exclude_none=True)
    if "category" in updates and updates["category"] not in PRICE_CATEGORIES:
        raise HTTPException(status_code=400, detail="Danh mục không hợp lệ")
    if "unit" in updates and updates["unit"] not in PRICE_UNITS:
        raise HTTPException(status_code=400, detail="Đơn vị không hợp lệ")

    for k, v in updates.items():
        setattr(item, k, v)
    await db.commit()
    return {"status": "ok", "id": item.id}
