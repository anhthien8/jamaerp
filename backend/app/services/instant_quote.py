"""Instant Quote — báo giá sơ bộ tức thì từ yêu cầu mơ hồ của khách.

Cách hoạt động:
1. Input: diện tích + loại nhà + số phòng ngủ (hoặc text Zalo mơ hồ → AI parse)
2. Template hạng mục theo loại nhà × bảng đơn giá 3 phân khúc (PriceItem)
3. Output: 3 phương án (Cơ bản / Tiêu chuẩn / Cao cấp) với khoảng giá ±15%

⚠️ Đây là BÁO GIÁ SƠ BỘ để sale phản hồi khách trong vài phút — giá chính xác
vẫn do Thu mua/Kế toán lập sau khảo sát (đúng brief: không thay thế 2 phòng này).
Seed đơn giá là số tham khảo thị trường HCM — Thu mua PHẢI rà lại trước khi dùng.
"""

import logging
from datetime import datetime, timezone

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.pricing import PriceItem

logger = logging.getLogger(__name__)

TIERS = ("basic", "standard", "premium")
TIER_LABELS = {"basic": "Cơ bản", "standard": "Tiêu chuẩn", "premium": "Cao cấp"}
RANGE_PCT = 0.15  # ±15%

# ---------------------------------------------------------------------------
# Seed đơn giá — GIÁ BÁN tham khảo HCM (VND). Thu mua cập nhật qua UI/API.
# (code, name, category, unit, basic, standard, premium, note)
# ---------------------------------------------------------------------------

DEFAULT_PRICE_ITEMS: list[tuple] = [
    # Trần & vách
    ("TRAN-01", "Trần thạch cao khung chìm", "tran_vach", "m2", 165_000, 225_000, 330_000, "Gồm sơn hoàn thiện"),
    ("TRAN-02", "Vách thạch cao / vách trang trí", "tran_vach", "m2", 185_000, 260_000, 420_000, None),
    ("TRAN-03", "Chỉ tường, phào trang trí", "tran_vach", "md", 45_000, 85_000, 160_000, None),
    # Sàn
    ("SAN-01", "Sàn gỗ công nghiệp / SPC", "san", "m2", 285_000, 460_000, 880_000, "Premium = gỗ kỹ thuật/engineered"),
    ("SAN-02", "Len chân tường", "san", "md", 35_000, 55_000, 95_000, None),
    # Sơn & giấy
    ("SON-01", "Sơn nước hoàn thiện", "son_giay", "m2", 62_000, 95_000, 155_000, "Diện tích sơn ≈ 2.8 lần diện tích sàn"),
    ("SON-02", "Giấy dán tường / tường điểm nhấn", "son_giay", "m2", 155_000, 260_000, 480_000, None),
    # Tủ bếp
    ("BEP-01", "Tủ bếp trên + dưới (mét dài)", "tu_bep", "md", 3_600_000, 5_600_000, 9_200_000, "Basic MFC, Standard MDF chống ẩm, Premium gỗ tự nhiên/acrylic"),
    ("BEP-02", "Đá mặt bếp + ốp tường bếp", "tu_bep", "md", 1_250_000, 2_300_000, 4_600_000, None),
    ("BEP-03", "Phụ kiện tủ bếp (ray, bản lề, kệ)", "tu_bep", "bo", 3_200_000, 8_500_000, 21_000_000, "Premium = Blum/Hafele full"),
    # Tủ áo & đồ gỗ
    ("GO-01", "Tủ áo âm tường / cánh mở (m2 mặt tủ)", "tu_ao_go", "m2", 2_850_000, 4_300_000, 6_800_000, None),
    ("GO-02", "Kệ tivi + vách tivi", "tu_ao_go", "bo", 4_200_000, 8_500_000, 19_000_000, None),
    ("GO-03", "Tủ giày / tủ trang trí lối vào", "tu_ao_go", "bo", 3_100_000, 6_200_000, 12_500_000, None),
    ("GO-04", "Bàn làm việc + kệ sách", "tu_ao_go", "bo", 3_400_000, 6_500_000, 14_500_000, None),
    # Sofa & bàn ghế
    ("SOFA-01", "Sofa phòng khách", "sofa_ban_ghe", "bo", 12_500_000, 26_000_000, 62_000_000, "Premium = da thật/nhập khẩu"),
    ("SOFA-02", "Bàn trà", "sofa_ban_ghe", "cai", 2_200_000, 5_200_000, 12_500_000, None),
    ("SOFA-03", "Bàn ăn + ghế", "sofa_ban_ghe", "bo", 8_500_000, 18_500_000, 46_000_000, None),
    # Giường & nệm
    ("GIUONG-01", "Giường ngủ (khung + đầu giường)", "giuong_nem", "cai", 6_200_000, 12_500_000, 26_000_000, None),
    ("GIUONG-02", "Nệm", "giuong_nem", "cai", 4_200_000, 9_500_000, 26_000_000, None),
    ("GIUONG-03", "Tab đầu giường (cặp)", "giuong_nem", "bo", 1_800_000, 3_600_000, 8_200_000, None),
    # Đèn & điện
    ("DEN-01", "Đèn trang trí (thả, ốp, spotlight...)", "den_dien", "tron_goi", 5_500_000, 13_500_000, 38_000_000, "Trọn gói theo căn"),
    ("DEN-02", "Điều chỉnh điện + công tắc ổ cắm", "den_dien", "m2", 85_000, 135_000, 215_000, "Theo m2 sàn"),
    # Rèm & trang trí
    ("REM-01", "Rèm cửa (bộ/cửa sổ)", "rem_trang_tri", "bo", 2_600_000, 4_800_000, 9_500_000, None),
    ("DECOR-01", "Decor: tranh, gương, cây, thảm...", "rem_trang_tri", "tron_goi", 4_500_000, 11_500_000, 34_000_000, "Trọn gói theo căn"),
    # Thiết bị
    ("TB-01", "Thiết bị bếp (bếp từ + hút mùi)", "thiet_bi", "bo", 8_500_000, 19_000_000, 46_000_000, None),
    # Khác
    ("KHAC-01", "Vận chuyển + lắp đặt + vệ sinh bàn giao", "khac", "tron_goi", 4_500_000, 7_500_000, 12_000_000, None),
    ("KHAC-02", "Thi công điện nước điều chỉnh (nhà phố/villa)", "khac", "tron_goi", 18_000_000, 32_000_000, 62_000_000, "Chỉ áp dụng nhà phố/villa"),
    ("KHAC-03", "Cầu thang: tay vịn, ốp bậc, trang trí", "khac", "tron_goi", 12_000_000, 24_000_000, 55_000_000, "Chỉ áp dụng nhà phố/villa"),
]


# ---------------------------------------------------------------------------
# Template hạng mục theo loại nhà
# Công thức số lượng: qty = base + per_sqm × area + per_bedroom × bedrooms
# (code, base, per_sqm, per_bedroom)
# ---------------------------------------------------------------------------

QUOTE_TEMPLATES: dict[str, list[tuple]] = {
    "apartment": [
        ("TRAN-01", 0, 0.75, 0),
        ("SAN-01", 0, 0.82, 0),
        ("SAN-02", 0, 0.85, 0),
        ("SON-01", 0, 2.4, 0),       # diện tích sơn ≈ 2.4× sàn (căn hộ trần thấp)
        ("SON-02", 6, 0.05, 2),      # tường điểm nhấn
        ("BEP-01", 3.2, 0.015, 0),   # ~3.5-4.5 md tùy diện tích
        ("BEP-02", 3.2, 0.015, 0),
        ("BEP-03", 1, 0, 0),
        ("GO-01", 0, 0, 4.5),        # ~4.5 m2 mặt tủ / phòng ngủ
        ("GO-02", 1, 0, 0),
        ("GO-03", 1, 0, 0),
        ("SOFA-01", 1, 0, 0),
        ("SOFA-02", 1, 0, 0),
        ("SOFA-03", 1, 0, 0),
        ("GIUONG-01", 0, 0, 1),
        ("GIUONG-02", 0, 0, 1),
        ("GIUONG-03", 0, 0, 1),
        ("DEN-01", 1, 0, 0),
        ("DEN-02", 0, 1.0, 0),
        ("REM-01", 1, 0, 1),         # 1 cửa phòng khách + 1/phòng ngủ
        ("DECOR-01", 1, 0, 0),
        ("TB-01", 1, 0, 0),
        ("KHAC-01", 1, 0, 0),
    ],
    "townhouse": [
        ("TRAN-01", 0, 0.7, 0),
        ("TRAN-03", 0, 0.9, 0),
        ("SAN-01", 0, 0.6, 0),       # tầng trệt thường gạch sẵn
        ("SAN-02", 0, 0.7, 0),
        ("SON-01", 0, 2.8, 0),
        ("SON-02", 8, 0.05, 2),
        ("BEP-01", 3.8, 0.008, 0),
        ("BEP-02", 3.8, 0.008, 0),
        ("BEP-03", 1, 0, 0),
        ("GO-01", 0, 0, 5.0),
        ("GO-02", 1, 0, 0),
        ("GO-03", 1, 0, 0),
        ("GO-04", 1, 0, 0),
        ("SOFA-01", 1, 0, 0),
        ("SOFA-02", 1, 0, 0),
        ("SOFA-03", 1, 0, 0),
        ("GIUONG-01", 0, 0, 1),
        ("GIUONG-02", 0, 0, 1),
        ("GIUONG-03", 0, 0, 1),
        ("DEN-01", 1.4, 0, 0),       # nhiều tầng → nhiều đèn hơn
        ("DEN-02", 0, 1.0, 0),
        ("REM-01", 2, 0, 1),
        ("DECOR-01", 1.3, 0, 0),
        ("TB-01", 1, 0, 0),
        ("KHAC-01", 1.3, 0, 0),
        ("KHAC-02", 1, 0, 0),
        ("KHAC-03", 1, 0, 0),
    ],
}
# Villa = townhouse nhân hệ số; office/shophouse = template rút gọn
QUOTE_TEMPLATES["villa"] = QUOTE_TEMPLATES["townhouse"]
QUOTE_TEMPLATES["office"] = [
    ("TRAN-01", 0, 0.85, 0),
    ("SAN-01", 0, 0.9, 0),
    ("SON-01", 0, 2.5, 0),
    ("GO-04", 0, 0.12, 0),           # bàn làm việc theo m2
    ("GO-02", 1, 0, 0),
    ("SOFA-01", 1, 0, 0),
    ("DEN-01", 1, 0, 0),
    ("DEN-02", 0, 1.0, 0),
    ("REM-01", 2, 0.02, 0),
    ("DECOR-01", 1, 0, 0),
    ("KHAC-01", 1, 0, 0),
]
QUOTE_TEMPLATES["shophouse"] = QUOTE_TEMPLATES["office"]
QUOTE_TEMPLATES["other"] = QUOTE_TEMPLATES["apartment"]

# Villa: đơn giá nghiêng premium + khối lượng lớn hơn
PROPERTY_MULTIPLIER = {"villa": 1.25}


# ---------------------------------------------------------------------------
# Seed helper — nạp đơn giá mặc định nếu bảng trống
# ---------------------------------------------------------------------------

async def ensure_price_items(db: AsyncSession) -> None:
    count = (await db.execute(select(func.count(PriceItem.id)))).scalar() or 0
    if count > 0:
        return
    for code, name, category, unit, basic, standard, premium, note in DEFAULT_PRICE_ITEMS:
        db.add(PriceItem(
            code=code, name=name, category=category, unit=unit,
            price_basic=basic, price_standard=standard, price_premium=premium,
            note=note,
        ))
    await db.flush()
    logger.info("Seeded %d default price items (Thu mua cần rà lại đơn giá!)", len(DEFAULT_PRICE_ITEMS))


# ---------------------------------------------------------------------------
# Core: generate quote
# ---------------------------------------------------------------------------

def _estimate_bedrooms(area_sqm: float, property_type: str) -> int:
    """Ước lượng số phòng ngủ khi khách không nói rõ."""
    if property_type in ("office", "shophouse"):
        return 0
    return max(1, min(6, round(area_sqm / 33)))


async def generate_quote(
    db: AsyncSession,
    area_sqm: float,
    property_type: str = "apartment",
    bedrooms: int | None = None,
) -> dict:
    """Tính báo giá 3 phương án cho một căn."""
    await ensure_price_items(db)

    area_sqm = max(15.0, min(2000.0, float(area_sqm)))
    if property_type not in QUOTE_TEMPLATES:
        property_type = "other"
    if bedrooms is None:
        bedrooms = _estimate_bedrooms(area_sqm, property_type)
    bedrooms = max(0, min(10, int(bedrooms)))

    # Load bảng giá đang active
    result = await db.execute(select(PriceItem).where(PriceItem.is_active == True))  # noqa: E712
    price_map = {p.code: p for p in result.scalars().all()}

    multiplier = PROPERTY_MULTIPLIER.get(property_type, 1.0)
    template = QUOTE_TEMPLATES[property_type]

    tiers: dict[str, dict] = {}
    for tier in TIERS:
        items = []
        total = 0.0
        for code, base, per_sqm, per_bedroom in template:
            p = price_map.get(code)
            if p is None:
                continue
            qty = base + per_sqm * area_sqm + per_bedroom * bedrooms
            qty = round(qty * multiplier, 1)
            if qty <= 0:
                continue
            unit_price = getattr(p, f"price_{tier}")
            line_total = round(qty * unit_price)
            total += line_total
            items.append({
                "code": p.code, "name": p.name, "category": p.category,
                "unit": p.unit, "qty": qty, "unit_price": unit_price,
                "total": line_total,
            })
        total = round(total, -5)  # làm tròn trăm nghìn
        tiers[tier] = {
            "label": TIER_LABELS[tier],
            "items": items,
            "total": total,
            "range_low": round(total * (1 - RANGE_PCT), -6),
            "range_high": round(total * (1 + RANGE_PCT), -6),
            "per_sqm": round(total / area_sqm) if area_sqm else 0,
        }

    return {
        "area_sqm": area_sqm,
        "property_type": property_type,
        "bedrooms": bedrooms,
        "tiers": tiers,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "disclaimer": (
            "Báo giá sơ bộ ±15% dựa trên đơn giá chuẩn JAMA HOME. "
            "Giá chính xác sẽ được lập sau khảo sát thực tế miễn phí."
        ),
    }


def suggest_tier(quote: dict, budget: float | None) -> str:
    """Gợi ý phương án gần ngân sách khách nhất."""
    if not budget or budget <= 0:
        return "standard"
    best, best_diff = "standard", float("inf")
    for tier in TIERS:
        diff = abs(quote["tiers"][tier]["total"] - budget)
        if diff < best_diff:
            best, best_diff = tier, diff
    return best


def format_quote_for_zalo(quote: dict, tier: str = "standard") -> str:
    """Text thân thiện để sale copy gửi khách qua Zalo."""
    t = quote["tiers"][tier]
    ptype_label = {
        "apartment": "Căn hộ", "townhouse": "Nhà phố", "villa": "Biệt thự",
        "office": "Văn phòng", "shophouse": "Shophouse", "other": "Công trình",
    }.get(quote["property_type"], "Công trình")

    def fmt(v: float) -> str:
        return f"{v / 1_000_000:,.0f} triệu" if v < 1_000_000_000 else f"{v / 1_000_000_000:,.2f} tỷ"

    lines = [
        f"🏠 JAMA HOME — Báo giá sơ bộ nội thất",
        f"📐 {ptype_label} {quote['area_sqm']:g}m²"
        + (f" · {quote['bedrooms']} phòng ngủ" if quote["bedrooms"] else ""),
        "",
        f"✨ Phương án {t['label']}: khoảng {fmt(t['range_low'])} – {fmt(t['range_high'])}",
        f"(≈ {t['per_sqm'] / 1_000_000:,.1f} triệu/m², trọn gói thiết kế + thi công nội thất)",
        "",
        "Bao gồm: trần thạch cao, sàn, sơn, tủ bếp, tủ áo, sofa, giường, đèn, rèm...",
        "",
        "📋 Giá chính xác sẽ có sau buổi KHẢO SÁT MIỄN PHÍ tại nhà.",
        "Anh/chị cho em xin lịch rảnh tuần này để bên em qua đo đạc tư vấn chi tiết nhé!",
    ]
    return "\n".join(lines)
