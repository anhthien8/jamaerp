"""Instant Quote — báo giá sơ bộ tức thì từ yêu cầu mơ hồ của khách.

2 chế độ:
1. **Xây mới** (new): diện tích + loại nhà → 3 phương án (Cơ bản/Tiêu chuẩn/Cao cấp)
2. **Cải tạo** (renovation): diện tích + số tầng + hiện trạng → khung tiêu chuẩn, khách chọn vật liệu theo budget

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


# ============================================================================
# RENOVATION MODE — Báo giá cải tạo
# Template từ Excel "JAMA_ baogiaphantho.xlsx" (nhà phố 3 tầng tiêu chuẩn)
# ============================================================================

# Category labels
RENO_CATEGORIES = {
    "thao_do": "A. THÁO DỠ",
    "ket_cau": "B. PHẦN KẾT CẤU",
    "hoan_thien": "C. HOÀN THIỆN XÂY DỰNG",
    "can_thang": "VI. CẦU THANG",
    "cua": "VII. CỬA - ĐÀ Cửa - NGẠCH CỬA",
    "he_thong_ME": "VIII. HỆ THỐNG M.E",
    "khac": "IX. HẠNG MỤC KHÁC",
}

# Renovation items: (code, name, category, unit, unit_price, qty_formula, note)
# qty_formula: "fixed" = always 1, "per_sqm" = area * factor, "per_floor" = floors * factor
RENO_TEMPLATE: list[tuple] = [
    # ── A. THÁO DỠ ──
    ("RD-01", "Tháo dỡ vách tường 100 hiện trạng", "thao_do", "m2", 90_000, "per_sqm:0.35", None),
    ("RD-02", "Tháo dỡ vách tường 200 hiện trạng", "thao_do", "m2", 120_000, "per_sqm:0.15", None),
    ("RD-03", "Tháo dỡ sàn nhựa giả gỗ", "thao_do", "m2", 55_000, "per_sqm:0.2", None),
    ("RD-04", "Tháo dỡ gạch nền + len chân tường", "thao_do", "m2", 140_000, "per_sqm:0.6", None),
    ("RD-05", "Tháo dỡ gạch nền WC + ban công", "thao_do", "m2", 170_000, "per_sqm:0.15", "Tháo tới cotg bê tông"),
    ("RD-06", "Tháo dỡ gạch ốp tường hiện trạng", "thao_do", "m2", 140_000, "per_sqm:0.5", None),
    ("RD-07", "Tháo dỡ trần thạch cao hiện trạng", "thao_do", "m2", 55_000, "per_sqm:0.6", None),
    ("RD-08", "Tháo dỡ hệ tủ bếp + thiết bị WC + cửa cũ", "thao_do", "tron_goi", 8_500_000, "fixed", None),
    ("RD-09", "Tháo dỡ cầu thang bê tông hiện trạng", "thao_do", "tron_goi", 4_500_000, "fixed", "Nếu thay đổi CT"),
    ("RD-10", "Di dời nội thất trong nhà hiện trạng", "thao_do", "tron_goi", 5_000_000, "fixed", None),
    ("RD-11", "Gói bao che + lót bạt thi công", "thao_do", "tron_goi", 3_500_000, "fixed", None),
    ("RD-12", "Vận chuyển xà bần xuống nơi tập kết", "thao_do", "m2", 600_000, "fixed", "1 chuyến"),
    ("RD-13", "Xe vận chuyển rác + xà bần", "thao_do", "chuyen", 500_000, "fixed", None),

    # ── B. KẾT CẤU ──
    ("ST-01", "Bổ 2 trụ cổng mặt tiền", "ket_cau", "cai", 1_200_000, "fixed", None),
    ("ST-02", "Đà cổng", "ket_cau", "cai", 1_350_000, "fixed", None),
    ("ST-03", "Xây bù + tô cột cổng + đà cổng", "ket_cau", "tron_goi", 3_500_000, "fixed", None),
    ("ST-04", "Gia cố sắt I cầu thang", "ket_cau", "m2", 1_800_000, "fixed", "Nếu thay đổi CT"),

    # ── C. HOÀN THIỆN (per floor) ──
    # Tầng 1
    ("CF-1-01", "Nâng cotg nền T1", "hoan_thien", "m2", 430_000, "per_sqm:0.35", None),
    ("CF-1-02", "Tô trám tường sau tháo dỡ T1", "hoan_thien", "m2", 205_000, "per_sqm:0.5", None),
    ("CF-1-03", "Xây tường 100 theo bố trí mới T1", "hoan_thien", "m2", 360_000, "per_sqm:0.3", None),
    ("CF-1-04", "Xây tường 200 theo bố trí mới T1", "hoan_thien", "m2", 720_000, "per_sqm:0.15", None),
    ("CF-1-05", "Tô tường xây mới T1", "hoan_thien", "m2", 205_000, "per_sqm:0.45", None),
    ("CF-1-06", "Đà bê tông đỡ tường xây mới T1", "hoan_thien", "m2", 800_000, "per_sqm:0.05", None),
    ("CF-1-07", "Xây tô hộp gen T1", "hoan_thien", "m2", 565_000, "per_sqm:0.08", None),
    ("CF-1-08", "Tạo hộc âm trong WC T1", "hoan_thien", "cai", 1_500_000, "fixed", None),
    ("CF-1-09", "Lấy cotg cán nền T1", "hoan_thien", "m2", 260_000, "per_sqm:0.35", None),
    ("CF-1-10", "Lát sàn gạch 600x600 T1", "hoan_thien", "m2", 290_000, "per_sqm:0.3", "Nhân công + vật tư"),
    ("CF-1-11", "Ốp tường gạch 300x600 T1", "hoan_thien", "m2", 320_000, "per_sqm:0.2", None),
    ("CF-1-12", "Len gạch tường T1", "hoan_thien", "m2", 150_000, "per_sqm:0.3", None),
    ("CF-1-13", "Đi keo ron gạch WC T1", "hoan_thien", "m2", 1_200_000, "per_sqm:0.08", None),
    ("CF-1-14", "Đóng vách thạch cao 1 mặt T1", "hoan_thien", "m2", 295_000, "per_sqm:0.2", None),
    ("CF-1-15", "Đóng trần thạch cao T1", "hoan_thien", "m2", 195_000, "per_sqm:0.3", None),
    ("CF-1-16", "Đóng trần thạch cao chống ẩm WC T1", "hoan_thien", "m2", 1_050_000, "per_sqm:0.05", None),
    ("CF-1-17", "Sủi tường hiện trạng T1", "hoan_thien", "m2", 35_000, "per_sqm:0.3", None),
    ("CF-1-18", "Sơn trần trong nhà T1", "hoan_thien", "m2", 175_000, "per_sqm:0.3", None),
    ("CF-1-19", "Sơn tường ngoại thất T1", "hoan_thien", "m2", 190_000, "per_sqm:0.2", None),

    # Tầng 2
    ("CF-2-01", "Tô trám tường sau tháo dỡ T2", "hoan_thien", "m2", 205_000, "per_sqm:0.45", None),
    ("CF-2-02", "Xây tường 100 theo bố trí mới T2", "hoan_thien", "m2", 360_000, "per_sqm:0.3", None),
    ("CF-2-03", "Xây tường 200 theo bố trí mới T2", "hoan_thien", "m2", 720_000, "per_sqm:0.15", None),
    ("CF-2-04", "Tô tường xây mới T2", "hoan_thien", "m2", 205_000, "per_sqm:0.45", None),
    ("CF-2-05", "Xây tô hộp gen T2", "hoan_thien", "m2", 565_000, "per_sqm:0.08", None),
    ("CF-2-06", "Tạo hộc âm WC T2", "hoan_thien", "cai", 1_500_000, "fixed", None),
    ("CF-2-07", "Chống thấm WC T2", "hoan_thien", "m2", 3_200_000, "per_sqm:0.06", None),
    ("CF-2-08", "Lấy cotg cán nền T2", "hoan_thien", "m2", 260_000, "per_sqm:0.35", None),
    ("CF-2-09", "Lát sàn gạch 600x600 T2", "hoan_thien", "m2", 290_000, "per_sqm:0.3", None),
    ("CF-2-10", "Ốp tường gạch 300x600 T2", "hoan_thien", "m2", 320_000, "per_sqm:0.2", None),
    ("CF-2-11", "Len gạch tường T2", "hoan_thien", "m2", 150_000, "per_sqm:0.3", None),
    ("CF-2-12", "Đi keo ron gạch WC T2", "hoan_thien", "m2", 1_500_000, "per_sqm:0.08", None),
    ("CF-2-13", "Sàn nhựa giả gỗ T2", "hoan_thien", "m2", 435_000, "per_sqm:0.15", "Ốp thẳng"),
    ("CF-2-14", "Len/nẹp nhựa T2", "hoan_thien", "m2", 70_000, "per_sqm:0.3", None),
    ("CF-2-15", "Đóng vách thạch cao 1 mặt T2", "hoan_thien", "m2", 295_000, "per_sqm:0.2", None),
    ("CF-2-16", "Đóng trần thạch cao T2", "hoan_thien", "m2", 195_000, "per_sqm:0.3", None),
    ("CF-2-17", "Đóng trần thạch cao chống ẩm WC T2", "hoan_thien", "m2", 1_050_000, "per_sqm:0.05", None),
    ("CF-2-18", "Sủi tường hiện trạng T2", "hoan_thien", "m2", 35_000, "per_sqm:0.3", None),
    ("CF-2-19", "Sơn trần trong nhà T2", "hoan_thien", "m2", 175_000, "per_sqm:0.3", None),
    ("CF-2-20", "Sơn tường ngoại thất T2", "hoan_thien", "m2", 190_000, "per_sqm:0.2", None),

    # Tầng 3 (giống T2)
    ("CF-3-01", "Tô trám tường sau tháo dỡ T3", "hoan_thien", "m2", 205_000, "per_sqm:0.45", None),
    ("CF-3-02", "Xây tường 100 theo bố trí mới T3", "hoan_thien", "m2", 360_000, "per_sqm:0.3", None),
    ("CF-3-03", "Xây tường 200 theo bố trí mới T3", "hoan_thien", "m2", 720_000, "per_sqm:0.15", None),
    ("CF-3-04", "Tô tường xây mới T3", "hoan_thien", "m2", 205_000, "per_sqm:0.45", None),
    ("CF-3-05", "Xây tô hộp gen T3", "hoan_thien", "m2", 565_000, "per_sqm:0.08", None),
    ("CF-3-06", "Tạo hộc âm WC T3", "hoan_thien", "cai", 1_500_000, "fixed", None),
    ("CF-3-07", "Chống thấm WC T3", "hoan_thien", "m2", 3_200_000, "per_sqm:0.06", None),
    ("CF-3-08", "Lấy cotg cán nền T3", "hoan_thien", "m2", 260_000, "per_sqm:0.35", None),
    ("CF-3-09", "Lát sàn gạch 600x600 T3", "hoan_thien", "m2", 290_000, "per_sqm:0.3", None),
    ("CF-3-10", "Ốp tường gạch 300x600 T3", "hoan_thien", "m2", 320_000, "per_sqm:0.2", None),
    ("CF-3-11", "Len gạch tường T3", "hoan_thien", "m2", 150_000, "per_sqm:0.3", None),
    ("CF-3-12", "Đi keo ron gạch WC T3", "hoan_thien", "m2", 1_500_000, "per_sqm:0.08", None),
    ("CF-3-13", "Sàn nhựa giả gỗ T3", "hoan_thien", "m2", 435_000, "per_sqm:0.15", None),
    ("CF-3-14", "Len/nẹp nhựa T3", "hoan_thien", "m2", 70_000, "per_sqm:0.3", None),
    ("CF-3-15", "Đóng vách thạch cao 1 mặt T3", "hoan_thien", "m2", 295_000, "per_sqm:0.2", None),
    ("CF-3-16", "Đóng trần thạch cao T3", "hoan_thien", "m2", 195_000, "per_sqm:0.3", None),
    ("CF-3-17", "Đóng trần thạch cao chống ẩm WC T3", "hoan_thien", "m2", 1_050_000, "per_sqm:0.05", None),
    ("CF-3-18", "Sủi tường hiện trạng T3", "hoan_thien", "m2", 35_000, "per_sqm:0.3", None),
    ("CF-3-19", "Sơn trần trong nhà T3", "hoan_thien", "m2", 175_000, "per_sqm:0.3", None),
    ("CF-3-20", "Sơn tường ngoại thất T3", "hoan_thien", "m2", 190_000, "per_sqm:0.2", None),

    # Mái
    ("CF-R-01", "Xây tường 100 mái", "hoan_thien", "m2", 360_000, "per_sqm:0.1", None),
    ("CF-R-02", "Tô tường mái", "hoan_thien", "m2", 205_000, "per_sqm:0.1", None),
    ("CF-R-03", "Chống thấm seno mái", "hoan_thien", "m2", 3_200_000, "per_sqm:0.05", None),
    ("CF-R-04", "Lát sàn gạch 400x400 seno mái", "hoan_thien", "m2", 290_000, "per_sqm:0.1", None),
    ("CF-R-05", "Len gạch seno mái", "hoan_thien", "m2", 150_000, "per_sqm:0.1", None),
    ("CF-R-06", "Sủi tường mái", "hoan_thien", "m2", 35_000, "per_sqm:0.1", None),
    ("CF-R-07", "Sơn tường ngoại thất mái", "hoan_thien", "m2", 190_000, "per_sqm:0.1", None),
    ("CF-R-08", "Sơn chống thấm mái", "hoan_thien", "m2", 275_000, "per_sqm:0.1", None),
    ("CF-R-09", "Mái tôn", "hoan_thien", "m2", 890_000, "per_sqm:0.15", None),
    ("CF-R-10", "Diềm tôn", "hoan_thien", "m", 220_000, "per_sqm:0.3", None),
    ("CF-R-11", "Máng xối", "hoan_thien", "m", 480_000, "per_sqm:0.2", None),

    # Sân trước + mặt tiền
    ("CF-F-01", "Tô trám tường mặt tiền", "hoan_thien", "m2", 205_000, "per_sqm:0.15", None),
    ("CF-F-02", "Xây tường 100 mặt tiền", "hoan_thien", "m2", 360_000, "per_sqm:0.1", None),
    ("CF-F-03", "Xây tường 200 mặt tiền", "hoan_thien", "m2", 720_000, "per_sqm:0.05", None),
    ("CF-F-04", "Tô tường mặt tiền", "hoan_thien", "m2", 205_000, "per_sqm:0.15", None),
    ("CF-F-05", "Chỉ nước 5cm mặt tiền", "hoan_thien", "m", 550_000, "per_sqm:0.3", None),
    ("CF-F-06", "Lát sàn gạch sân trước", "hoan_thien", "m2", 290_000, "per_sqm:0.12", None),
    ("CF-F-07", "Ốp tường gạch mặt tiền", "hoan_thien", "m2", 320_000, "per_sqm:0.1", None),
    ("CF-F-08", "Len gạch mặt tiền", "hoan_thien", "m2", 150_000, "per_sqm:0.15", None),
    ("CF-F-09", "Lam nhựa giả gỗ ốp trần", "hoan_thien", "m2", 450_000, "per_sqm:0.08", None),
    ("CF-F-10", "Sủi tường mặt tiền", "hoan_thien", "m2", 35_000, "per_sqm:0.15", None),
    ("CF-F-11", "Sơn ngoại thất mặt tiền", "hoan_thien", "m2", 190_000, "per_sqm:0.15", None),
    ("CF-F-12", "Sơn chống thấm vách song", "hoan_thien", "m2", 275_000, "per_sqm:0.05", None),

    # ── VI. CẦU THANG ──
    ("ST-CT-01", "GCLD ván khuôn + cốt thép + đổ bê tông CT", "can_thang", "m2", 2_800_000, "per_sqm:0.06", None),
    ("ST-CT-02", "Xây bậc cầu thang (gạch đinh)", "can_thang", "m2", 620_000, "per_sqm:0.04", None),
    ("ST-CT-03", "Tô cầu thang", "can_thang", "m2", 410_000, "per_sqm:0.04", None),
    ("ST-CT-04", "Đóng thạch cao CT mặt đáy + hông", "can_thang", "m2", 195_000, "per_sqm:0.06", None),
    ("ST-CT-05", "Nẹp U liên kết thạch cao CT", "can_thang", "m", 120_000, "per_sqm:0.08", None),
    ("ST-CT-06", "Sơn nước CT (mặt đáy + hông)", "can_thang", "m2", 160_000, "per_sqm:0.06", None),

    # ── VII. CỬA (per floor) ──
    # Tầng 1
    ("DR-1-01", "Cửa đi T1", "cua", "cai", 2_500_000, "fixed", "2 cánh"),
    ("DR-1-02", "Cửa đi WC T1", "cua", "cai", 2_500_000, "fixed", None),
    ("DR-1-03", "Cửa phòng ngủ T1", "cua", "cai", 6_900_000, "fixed", "MDF An Cường"),
    ("DR-1-04", "Cửa sổ lùa T1", "cua", "cai", 3_000_000, "fixed", "Nhôm kính"),
    ("DR-1-05", "Đà cửa 100 + tô trám T1", "cua", "m", 850_000, "per_sqm:0.4", None),
    ("DR-1-06", "Ngạch đá 100 T1", "cua", "m", 350_000, "per_sqm:0.4", None),
    # Tầng 2
    ("DR-2-01", "Cửa đi T2", "cua", "cai", 2_500_000, "fixed", None),
    ("DR-2-02", "Cửa đi WC T2", "cua", "cai", 2_500_000, "fixed", None),
    ("DR-2-03", "Vách kính ngăn WC T2", "cua", "m2", 1_400_000, "per_sqm:0.06", None),
    ("DR-2-04", "Cửa phòng ngủ T2", "cua", "cai", 6_900_000, "fixed", None),
    ("DR-2-05", "Cửa sổ lùa T2", "cua", "cai", 3_000_000, "fixed", None),
    ("DR-2-06", "Đà cửa 100 + tô trám T2", "cua", "m", 850_000, "per_sqm:0.4", None),
    ("DR-2-07", "Ngạch đá 100 T2", "cua", "m", 350_000, "per_sqm:0.4", None),
    # Tầng 3
    ("DR-3-01", "Cửa đi T3", "cua", "cai", 2_500_000, "fixed", None),
    ("DR-3-02", "Cửa đi WC T3", "cua", "cai", 2_500_000, "fixed", None),
    ("DR-3-03", "Vách kính ngăn WC T3", "cua", "m2", 1_400_000, "per_sqm:0.06", None),
    ("DR-3-04", "Cửa phòng ngủ T3", "cua", "cai", 6_900_000, "fixed", None),
    ("DR-3-05", "Cửa sổ lùa T3", "cua", "cai", 3_000_000, "fixed", None),
    ("DR-3-06", "Đà cửa 100 + tô trám T3", "cua", "m", 850_000, "per_sqm:0.4", None),
    ("DR-3-07", "Ngạch đá 100 T3", "cua", "m", 350_000, "per_sqm:0.4", None),

    # ── VIII. HỆ THỐNG M.E ──
    ("ME-01", "Đi hệ thống điện + lắp đặt thiết bị điện", "he_thong_ME", "m2", 440_000, "per_sqm:1.0", "Toàn nhà"),
    ("ME-02", "Gia cố ti sắt cho quạt trần", "he_thong_ME", "cai", 800_000, "fixed", "Phòng khách"),
    ("ME-03", "Đường ống hút mùi bếp", "he_thong_ME", "tron_goi", 2_500_000, "fixed", None),
    ("ME-04", "Đấu nối máy bơm tăng áp", "he_thong_ME", "tron_goi", 2_500_000, "fixed", None),

    # ── IX. KHÁC ──
    ("OT-01", "Vệ sinh công nghiệp", "khac", "m2", 15_000, "per_sqm:1.0", None),
    ("OT-02", "Xử lý tường + trần bị thấm", "khac", "tron_goi", 5_000_000, "fixed", "Nếu có"),
    ("OT-03", "Chi phí giàn giáo mặt tiền", "khac", "tron_goi", 8_000_000, "fixed", "Nếu cần"),
    ("OT-04", "Kiểm tra + xử lý bể phốt", "khac", "tron_goi", 4_000_000, "fixed", None),
]


def _parse_qty_formula(formula: str, area_sqm: float, floors: int) -> float:
    """Parse qty formula like 'per_sqm:0.35' or 'fixed' → actual quantity."""
    if formula == "fixed":
        return 1.0
    parts = formula.split(":")
    if len(parts) == 2:
        factor = float(parts[1])
        if parts[0] == "per_sqm":
            return round(area_sqm * factor, 2)
        elif parts[0] == "per_floor":
            return round(area_sqm * factor * floors, 2)
        elif parts[0] == "per_floor_fixed":
            return round(floors * factor, 2)
    return 1.0


def generate_renovation_quote(
    area_sqm: float,
    floors: int = 3,
    scope: str = "full",
) -> dict:
    """Tính báo giá cải tạo cho nhà phố.

    Args:
        area_sqm: Diện tích mỗi tầng (m2)
        floors: Số tầng (1-4, mặc định 3)
        scope: 'full' (toàn bộ) hoặc 'partial' (chỉ phần chọn)

    Returns:
        dict với categories, items, totals, material_options.
    """
    area_sqm = max(15.0, min(500.0, float(area_sqm)))
    floors = max(1, min(4, int(floors)))

    categories: dict[str, list[dict]] = {}
    total = 0.0

    for code, name, category, unit, unit_price, formula, note in RENO_TEMPLATE:
        # Filter items by floor: T1 items only for 1+ floors, T2 for 2+, T3 for 3+, T4 for 4+
        if "-2-" in code and floors < 2:
            continue
        if "-3-" in code and floors < 3:
            continue
        # Roof items only for 3+ floors
        if code.startswith("CF-R-") and floors < 3:
            continue
        qty = _parse_qty_formula(formula, area_sqm, floors)
        if qty <= 0:
            continue
        line_total = round(qty * unit_price)
        total += line_total

        if category not in categories:
            categories[category] = []
        categories[category].append({
            "code": code, "name": name, "unit": unit,
            "qty": qty, "unit_price": unit_price, "total": line_total,
            "note": note,
        })

    total = round(total, -5)  # làm tròn trăm nghìn

    # Material options for budget fitting
    material_options = [
        {
            "category": "Sàn",
            "options": [
                {"name": "Gạch ceramic 300x600", "price_delta": -40_000, "unit": "m2"},
                {"name": "Gạch porcelain 600x600 (mặc định)", "price_delta": 0, "unit": "m2"},
                {"name": "Sàn gỗ công nghiệp", "price_delta": +190_000, "unit": "m2"},
                {"name": "Sàn gỗ tự nhiên", "price_delta": +500_000, "unit": "m2"},
            ],
        },
        {
            "category": "Cửa phòng ngủ",
            "options": [
                {"name": "Cửa HDF蚁 panels", "price_delta": -2_000_000, "unit": "cai"},
                {"name": "Cửa MDF thường (mặc định)", "price_delta": 0, "unit": "cai"},
                {"name": "Cửa MDF An Cường", "price_delta": +1_500_000, "unit": "cai"},
                {"name": "Cửa gỗ tự nhiên", "price_delta": +5_000_000, "unit": "cai"},
            ],
        },
        {
            "category": "Thiết bị WC",
            "options": [
                {"name": "Inax/COTTO cơ bản", "price_delta": 0, "unit": "bo"},
                {"name": "TOTO trung cấp", "price_delta": +3_000_000, "unit": "bo"},
                {"name": "American Standard cao cấp", "price_delta": +8_000_000, "unit": "bo"},
            ],
        },
        {
            "category": "Sơn",
            "options": [
                {"name": "Sơn Dulux cơ bản", "price_delta": 0, "unit": "m2"},
                {"name": "Sơn Dulux chống nóng", "price_delta": +15_000, "unit": "m2"},
                {"name": "Sơn Jotun cao cấp", "price_delta": +25_000, "unit": "m2"},
            ],
        },
    ]

    # Category summaries
    cat_totals = {}
    for cat, items in categories.items():
        cat_totals[cat] = {
            "label": RENO_CATEGORIES.get(cat, cat),
            "total": sum(i["total"] for i in items),
            "count": len(items),
        }

    return {
        "mode": "renovation",
        "area_sqm": area_sqm,
        "floors": floors,
        "categories": categories,
        "category_totals": cat_totals,
        "total": total,
        "per_sqm": round(total / area_sqm) if area_sqm else 0,
        "range_low": round(total * 0.9, -6),
        "range_high": round(total * 1.1, -6),
        "material_options": material_options,
        "disclaimer": (
            "Báo giá sơ bộ cải tạo ±10% dựa trên khung tiêu chuẩn JAMA HOME. "
            "Giá chính xác sẽ được lập sau khảo sát thực tế miễn phí. "
            "Khách hàng có thể chọn vật liệu phù hợp ngân sách."
        ),
    }


def format_renovation_quote_for_zalo(quote: dict) -> str:
    """Text báo giá cải tạo để sale copy gửi khách."""
    def fmt(v: float) -> str:
        return f"{v / 1_000_000:,.0f} triệu" if v < 1_000_000_000 else f"{v / 1_000_000_000:,.2f} tỷ"

    lines = [
        f"🏠 JAMA HOME — Báo giá cải tạo sơ bộ",
        f"📐 Nhà phố {quote['floors']} tầng · {quote['area_sqm']:g}m²/tầng",
        "",
        f"💰 Tổng dự kiến: khoảng {fmt(quote['range_low'])} – {fmt(quote['range_high'])}",
        f"(≈ {quote['per_sqm'] / 1_000_000:,.1f} triệu/m²)",
        "",
        "Bao gồm: tháo dỡ, kết cấu, hoàn thiện, cửa, điện nước, cầu thang...",
        "",
        "🎨 Khách có thể chọn vật liệu phù hợp ngân sách:",
        "  • Sàn: gạch → gỗ công nghiệp → gỗ tự nhiên",
        "  • Cửa: HDF → MDF → MDF An Cường → gỗ tự nhiên",
        "  • WC: Inax → TOTO → American Standard",
        "",
        "📋 Giá chính xác sẽ có sau khảo sát MIỄN PHÍ.",
        "Anh/chị cho em xin lịch rảnh để bên em qua đo đạc nhé!",
    ]
    return "\n".join(lines)
