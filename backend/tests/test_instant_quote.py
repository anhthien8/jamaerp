"""Tests for Instant Quote — engine, tiers, templates, public lead magnet, price book RBAC."""

import pytest
from httpx import AsyncClient
from sqlalchemy import select, func

from app.models.lead import Lead
from app.models.pricing import PriceItem
from app.services.instant_quote import (
    DEFAULT_PRICE_ITEMS,
    ensure_price_items,
    format_quote_for_zalo,
    generate_quote,
    suggest_tier,
)
from tests.conftest import auth_header


# ── Engine ───────────────────────────────────────────────────────────────

@pytest.mark.asyncio
class TestQuoteEngine:
    async def test_seed_price_items(self, db_session):
        await ensure_price_items(db_session)
        count = (await db_session.execute(select(func.count(PriceItem.id)))).scalar()
        assert count == len(DEFAULT_PRICE_ITEMS)

    async def test_seed_idempotent(self, db_session):
        await ensure_price_items(db_session)
        await ensure_price_items(db_session)
        count = (await db_session.execute(select(func.count(PriceItem.id)))).scalar()
        assert count == len(DEFAULT_PRICE_ITEMS)

    async def test_apartment_quote_has_three_tiers(self, db_session):
        quote = await generate_quote(db_session, 75, "apartment", 2)
        assert set(quote["tiers"].keys()) == {"basic", "standard", "premium"}
        for tier in quote["tiers"].values():
            assert tier["total"] > 0
            assert tier["range_low"] < tier["total"] < tier["range_high"]
            assert len(tier["items"]) > 10

    async def test_tier_prices_ascending(self, db_session):
        quote = await generate_quote(db_session, 75, "apartment", 2)
        assert (
            quote["tiers"]["basic"]["total"]
            < quote["tiers"]["standard"]["total"]
            < quote["tiers"]["premium"]["total"]
        )

    async def test_larger_area_costs_more(self, db_session):
        small = await generate_quote(db_session, 50, "apartment", 1)
        big = await generate_quote(db_session, 120, "apartment", 3)
        assert big["tiers"]["standard"]["total"] > small["tiers"]["standard"]["total"]

    async def test_bedrooms_estimated_when_missing(self, db_session):
        quote = await generate_quote(db_session, 100, "apartment", None)
        assert quote["bedrooms"] == 3  # ~100/33

    async def test_office_has_no_bedrooms(self, db_session):
        quote = await generate_quote(db_session, 100, "office", None)
        assert quote["bedrooms"] == 0

    async def test_townhouse_includes_stairs_and_mep(self, db_session):
        quote = await generate_quote(db_session, 200, "townhouse", 3)
        codes = {i["code"] for i in quote["tiers"]["standard"]["items"]}
        assert "KHAC-02" in codes and "KHAC-03" in codes

    async def test_apartment_excludes_stairs(self, db_session):
        quote = await generate_quote(db_session, 75, "apartment", 2)
        codes = {i["code"] for i in quote["tiers"]["standard"]["items"]}
        assert "KHAC-03" not in codes

    async def test_villa_multiplier_applied(self, db_session):
        townhouse = await generate_quote(db_session, 200, "townhouse", 3)
        villa = await generate_quote(db_session, 200, "villa", 3)
        assert villa["tiers"]["standard"]["total"] > townhouse["tiers"]["standard"]["total"]

    async def test_area_clamped(self, db_session):
        quote = await generate_quote(db_session, 5, "apartment", 1)  # < 15 → clamp
        assert quote["area_sqm"] == 15.0

    async def test_suggest_tier_matches_budget(self, db_session):
        quote = await generate_quote(db_session, 75, "apartment", 2)
        low_budget = quote["tiers"]["basic"]["total"]
        assert suggest_tier(quote, low_budget) == "basic"
        assert suggest_tier(quote, None) == "standard"

    async def test_zalo_text_format(self, db_session):
        quote = await generate_quote(db_session, 75, "apartment", 2)
        text = format_quote_for_zalo(quote, "standard")
        assert "JAMA HOME" in text
        assert "75m²" in text
        assert "KHẢO SÁT MIỄN PHÍ" in text


# ── API: /generate (auth) ────────────────────────────────────────────────

@pytest.mark.asyncio
class TestGenerateAPI:
    async def test_generate_with_numbers(self, client: AsyncClient, sales_user):
        resp = await client.post(
            "/api/v1/instant-quote/generate",
            json={"area_sqm": 75, "property_type": "apartment", "bedrooms": 2},
            headers=auth_header(sales_user),
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["suggested_tier"] in ("basic", "standard", "premium")
        assert "zalo_text" in body

    async def test_generate_with_raw_text(self, client: AsyncClient, sales_user):
        resp = await client.post(
            "/api/v1/instant-quote/generate",
            json={"raw_text": "chung cư 75m2 2 phòng ngủ quận 9, ngân sách 300 triệu"},
            headers=auth_header(sales_user),
        )
        # AI fallback = regex parse — diện tích 75m2 phải bắt được
        assert resp.status_code == 200
        assert resp.json()["area_sqm"] == 75

    async def test_generate_requires_area(self, client: AsyncClient, sales_user):
        resp = await client.post(
            "/api/v1/instant-quote/generate",
            json={"raw_text": "làm nội thất đẹp giá rẻ"},
            headers=auth_header(sales_user),
        )
        assert resp.status_code == 400

    async def test_generate_requires_auth(self, client: AsyncClient):
        resp = await client.post(
            "/api/v1/instant-quote/generate", json={"area_sqm": 75}
        )
        assert resp.status_code in (401, 403)


# ── API: /public (lead magnet) ───────────────────────────────────────────

@pytest.mark.asyncio
class TestPublicAPI:
    async def test_public_quote_creates_lead(self, client: AsyncClient, db_session):
        resp = await client.post(
            "/api/v1/instant-quote/public",
            json={
                "name": "Anh Khách Web", "phone": "0909123456",
                "area_sqm": 80, "property_type": "apartment", "bedrooms": 2,
                "budget": 350_000_000,
            },
        )
        assert resp.status_code == 200
        body = resp.json()
        # Chỉ trả khoảng giá — KHÔNG lộ chi tiết đơn giá
        assert "items" not in str(body["tiers"])
        assert body["tiers"]["standard"]["range_low"] > 0

        lead = (await db_session.execute(
            select(Lead).where(Lead.phone == "0909123456")
        )).scalars().first()
        assert lead is not None
        assert lead.source == "website"
        assert lead.priority == "high"

    async def test_public_no_duplicate_lead(self, client: AsyncClient, db_session):
        payload = {
            "name": "Chị Trùng", "phone": "0911222333",
            "area_sqm": 60, "property_type": "apartment",
        }
        await client.post("/api/v1/instant-quote/public", json=payload)
        await client.post("/api/v1/instant-quote/public", json=payload)
        count = (await db_session.execute(
            select(func.count(Lead.id)).where(Lead.phone == "0911222333")
        )).scalar()
        assert count == 1

    async def test_public_validates_input(self, client: AsyncClient):
        resp = await client.post(
            "/api/v1/instant-quote/public",
            json={"name": "X", "phone": "123", "area_sqm": 80},  # phone quá ngắn
        )
        assert resp.status_code == 422


# ── API: price book RBAC ─────────────────────────────────────────────────

@pytest.mark.asyncio
class TestPriceBookAPI:
    async def test_all_logged_in_can_view(self, client: AsyncClient, sales_user):
        resp = await client.get(
            "/api/v1/instant-quote/price-items", headers=auth_header(sales_user)
        )
        assert resp.status_code == 200
        assert len(resp.json()) == len(DEFAULT_PRICE_ITEMS)

    async def test_sales_cannot_edit_prices(self, client: AsyncClient, db_session, sales_user):
        await ensure_price_items(db_session)
        await db_session.commit()
        item = (await db_session.execute(select(PriceItem).limit(1))).scalars().first()
        resp = await client.put(
            f"/api/v1/instant-quote/price-items/{item.id}",
            json={"price_basic": 999_999},
            headers=auth_header(sales_user),
        )
        assert resp.status_code == 403

    async def test_purchasing_can_edit_prices(self, client: AsyncClient, db_session, purchasing_user):
        await ensure_price_items(db_session)
        await db_session.commit()
        item = (await db_session.execute(select(PriceItem).limit(1))).scalars().first()
        resp = await client.put(
            f"/api/v1/instant-quote/price-items/{item.id}",
            json={"price_basic": 200_000},
            headers=auth_header(purchasing_user),
        )
        assert resp.status_code == 200

    async def test_admin_can_create_item(self, client: AsyncClient, admin_user):
        resp = await client.post(
            "/api/v1/instant-quote/price-items",
            json={
                "code": "TEST-01", "name": "Hạng mục test", "category": "khac",
                "unit": "m2", "price_basic": 100_000, "price_standard": 200_000,
                "price_premium": 300_000,
            },
            headers=auth_header(admin_user),
        )
        assert resp.status_code == 201

    async def test_create_rejects_bad_category(self, client: AsyncClient, admin_user):
        resp = await client.post(
            "/api/v1/instant-quote/price-items",
            json={
                "code": "TEST-02", "name": "X", "category": "khong_ton_tai",
                "unit": "m2", "price_basic": 1, "price_standard": 2, "price_premium": 3,
            },
            headers=auth_header(admin_user),
        )
        assert resp.status_code == 400
