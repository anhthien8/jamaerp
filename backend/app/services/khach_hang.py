"""Khách hàng: doanh thu mang lại, đọc ảnh CCCD, nhắc sinh nhật (25/10/2026).

- Doanh thu khách = giá trị các dự án của khách (gắn thẳng hoặc qua lead), bỏ dự án
  đã hủy. Cùng quy ước với «doanh số» ở Chế độ thưởng: total_value, thiếu thì thiết
  kế + thi công — vì HĐ trên prod còn nháp, chưa lấy được tiền HĐ đã ký.
- Số HĐ = hợp đồng không hủy của các dự án đó.
- CCCD: ảnh → model vision trích họ tên/số/ngày sinh/địa chỉ. Ảnh không lưu.
- Sinh nhật: 08:00 VN mỗi ngày, nhắc sale phụ trách trước 3 ngày và đúng ngày.
"""

from __future__ import annotations

import base64
import json
import logging
import re
from datetime import date, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models.contract import Contract
from app.models.customer import Customer
from app.models.lead import Lead
from app.models.project import Project
from app.models.user import User

logger = logging.getLogger(__name__)

NHAC_TRUOC_NGAY = (3, 0)


class CccdError(Exception):
    def __init__(self, msg: str, status: int = 422):
        super().__init__(msg)
        self.status = status


# ── Doanh thu + số hợp đồng ────────────────────────────────────────────────

async def thong_ke_khach(db: AsyncSession, khach: list[Customer]) -> dict[str, dict]:
    """{customer_id: {doanh_thu, so_hop_dong, so_du_an}} cho danh sách khách."""
    kq = {c.id: {"doanh_thu": 0.0, "so_hop_dong": 0, "so_du_an": 0} for c in khach}
    if not khach:
        return kq
    theo_lead = {c.lead_id: c.id for c in khach if c.lead_id}
    ids = list(kq.keys())
    dk = Project.customer_id.in_(ids)
    if theo_lead:
        dk = dk | Project.lead_id.in_(list(theo_lead.keys()))
    du_an = (await db.execute(
        select(Project.id, Project.customer_id, Project.lead_id, Project.total_value,
               Project.design_value, Project.construction_value)
        .where(dk, Project.status != "cancelled")
    )).all()
    du_an_cua: dict[str, str] = {}
    for pid, cid, lid, tong, tk, tc in du_an:
        chu = cid if cid in kq else theo_lead.get(lid)
        if not chu:
            continue
        du_an_cua[pid] = chu
        kq[chu]["so_du_an"] += 1
        kq[chu]["doanh_thu"] += float(tong or 0) or float(tk or 0) + float(tc or 0)
    if du_an_cua:
        hd = (await db.execute(
            select(Contract.project_id).where(
                Contract.project_id.in_(list(du_an_cua.keys())), Contract.status != "cancelled",
            )
        )).scalars().all()
        for pid in hd:
            kq[du_an_cua[pid]]["so_hop_dong"] += 1
    return kq


# ── Đọc ảnh CCCD ───────────────────────────────────────────────────────────

_PROMPT_CCCD = (
    "Đây là ảnh căn cước công dân / CMND Việt Nam. Trích đúng chữ in trên thẻ, "
    "KHÔNG đoán. Trả JSON: {\"ho_ten\": str|null, \"so_cccd\": str|null, "
    "\"ngay_sinh\": \"DD/MM/YYYY\"|null, \"gioi_tinh\": str|null, "
    "\"dia_chi\": str|null (nơi thường trú), \"la_cccd\": bool}. "
    "Nếu ảnh không phải giấy tờ tùy thân thì la_cccd=false."
)


def _ngay(v: Any) -> date | None:
    if not v:
        return None
    m = re.search(r"(\d{1,2})[/\-.](\d{1,2})[/\-.](\d{4})", str(v))
    if not m:
        return None
    try:
        return date(int(m.group(3)), int(m.group(2)), int(m.group(1)))
    except ValueError:
        return None


def chuan_hoa_cccd(raw: Any) -> dict:
    """Kết quả model → {name, national_id, birthday(ISO), gender, address}."""
    if isinstance(raw, str):
        m = re.search(r"\{.*\}", raw, re.S)
        try:
            raw = json.loads(m.group(0) if m else raw)
        except (ValueError, AttributeError):
            raw = {}
    if not isinstance(raw, dict) or raw.get("la_cccd") is False:
        raise CccdError("Ảnh này không giống căn cước — chụp rõ mặt trước thẻ rồi thử lại")
    so = re.sub(r"\D", "", str(raw.get("so_cccd") or ""))
    so = so if len(so) in (9, 12) else None
    ns = _ngay(raw.get("ngay_sinh"))
    ten = (raw.get("ho_ten") or "").strip() or None
    if ten:
        ten = " ".join(w.capitalize() for w in ten.split())
    kq = {
        "name": ten,
        "national_id": so,
        "birthday": ns.isoformat() if ns else None,
        "gender": (raw.get("gioi_tinh") or "").strip() or None,
        "address": (raw.get("dia_chi") or "").strip() or None,
    }
    if not any(kq[k] for k in ("name", "national_id", "birthday")):
        raise CccdError("Không đọc được chữ trên thẻ — chụp gần, đủ sáng, không lóa rồi thử lại")
    return kq


async def doc_cccd(anh: bytes, mime: str | None = "image/jpeg") -> dict:
    from litellm import acompletion

    from app.services.llm_config import get_llm_config
    from app.services.vat_tu_bao_gia_tep import MODEL_VISION_MAC_DINH

    cfg = await get_llm_config()
    model = get_settings().LLM_VISION_MODEL or MODEL_VISION_MAC_DINH
    key = cfg.get("llm_api_key", "")
    if not key or cfg.get("llm_model", "").split("/")[0] != model.split("/")[0]:
        raise CccdError("Cấu hình AI hiện tại chưa đọc được ảnh — nhập tay giúp nhé", 503)
    url = f"data:{mime or 'image/jpeg'};base64,{base64.b64encode(anh).decode()}"
    try:
        raw = await acompletion(
            model=model, api_key=key, temperature=0.0, max_tokens=600,
            response_format={"type": "json_object"},
            messages=[{"role": "user", "content": [
                {"type": "text", "text": _PROMPT_CCCD},
                {"type": "image_url", "image_url": {"url": url}},
            ]}],
        )
        noi_dung = raw.choices[0].message.content
    except Exception as exc:  # noqa: BLE001 — model/khóa/quota
        logger.warning("Vision đọc CCCD lỗi: %s", exc)
        raise CccdError("AI chưa đọc được ảnh lúc này — thử lại hoặc nhập tay", 503) from exc
    return chuan_hoa_cccd(noi_dung)


# ── Nhắc sinh nhật ─────────────────────────────────────────────────────────

def _sinh_nhat_nam(bd: date, nam: int) -> date:
    try:
        return bd.replace(year=nam)
    except ValueError:  # 29/02 năm thường → 28/02
        return date(nam, 2, 28)


async def sale_phu_trach(db: AsyncSession, khach: list[Customer]) -> dict[str, str]:
    """{customer_id: user_id}: sale của lead, không có thì sale dự án mới nhất."""
    kq: dict[str, str] = {}
    lead_ids = [c.lead_id for c in khach if c.lead_id]
    if lead_ids:
        rows = (await db.execute(select(Lead.id, Lead.assigned_to).where(Lead.id.in_(lead_ids)))).all()
        theo = {lid: uid for lid, uid in rows if uid}
        for c in khach:
            if c.lead_id in theo:
                kq[c.id] = theo[c.lead_id]
    con = [c.id for c in khach if c.id not in kq]
    if con:
        rows = (await db.execute(
            select(Project.customer_id, Project.sales_id)
            .where(Project.customer_id.in_(con), Project.sales_id.is_not(None))
            .order_by(Project.created_at.desc())
        )).all()
        for cid, sid in rows:
            kq.setdefault(cid, sid)
    return kq


async def nhac_sinh_nhat(db: AsyncSession, hom_nay: date) -> int:
    """Gửi thông báo cho sale phụ trách khách có sinh nhật sau 3 ngày / hôm nay.
    Không có sale thì báo admin. Trả số thông báo đã tạo."""
    from app.services.automation import _notify

    khach = (await db.execute(select(Customer).where(Customer.birthday.is_not(None)))).scalars().all()
    can: list[tuple[Customer, int, date]] = []
    for c in khach:
        for truoc in NHAC_TRUOC_NGAY:
            ngay = hom_nay + timedelta(days=truoc)
            if _sinh_nhat_nam(c.birthday, ngay.year) == ngay:
                can.append((c, truoc, ngay))
    if not can:
        return 0
    sale = await sale_phu_trach(db, [c for c, _, _ in can])
    ids = set(sale.values())
    users = {u.id: u for u in (await db.execute(select(User).where(User.id.in_(ids)))).scalars().all()} if ids else {}
    admins = (await db.execute(
        select(User).where(User.role == "admin", User.is_active == True)  # noqa: E712
    )).scalars().all()
    from app.models.notification import Notification

    # _notify chỉ chống trùng với thông báo CHƯA đọc — redeploy trong ngày sau khi
    # sale đã đọc sẽ nhắc lại, nên tự lọc ref_id đã từng gửi.
    refs = [f"sn-{c.id}-{ngay.isoformat()}-{truoc}" for c, truoc, ngay in can]
    da_gui = set((await db.execute(
        select(Notification.ref_id).where(Notification.ref_id.in_(refs))
    )).scalars().all())
    da = 0
    for c, truoc, ngay in can:
        if f"sn-{c.id}-{ngay.isoformat()}-{truoc}" in da_gui:
            continue
        u = users.get(sale.get(c.id))
        nhan = [u] if (u and u.is_active) else list(admins)
        tuoi = ngay.year - c.birthday.year
        khi = "HÔM NAY" if truoc == 0 else f"sau {truoc} ngày ({ngay.strftime('%d/%m')})"
        for n in nhan:
            ok = await _notify(
                db, n, type_="customer_birthday",
                title=f"Sinh nhật khách {c.name} {khi}",
                body=(f"{c.name} tròn {tuoi} tuổi ngày {ngay.strftime('%d/%m')}. "
                      "Tranh thủ gọi chúc mừng / gửi quà nhỏ để giữ mối."),
                link=f"/customers?id={c.id}",
                ref_id=f"sn-{c.id}-{ngay.isoformat()}-{truoc}",
            )
            da += 1 if ok else 0
    return da


def sinh_nhat_sap_toi(bd: date | None, hom_nay: date) -> int | None:
    """Số ngày tới sinh nhật kế tiếp (0 = hôm nay)."""
    if not bd:
        return None
    sn = _sinh_nhat_nam(bd, hom_nay.year)
    if sn < hom_nay:
        sn = _sinh_nhat_nam(bd, hom_nay.year + 1)
    return (sn - hom_nay).days


__all__ = ["thong_ke_khach", "doc_cccd", "chuan_hoa_cccd", "nhac_sinh_nhat", "sinh_nhat_sap_toi",
           "CccdError", "sale_phu_trach"]
