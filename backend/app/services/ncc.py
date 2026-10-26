"""Nhà cung cấp dùng chung cho Vật tư (26/10/2026).

- Gõ tên NCC ở mẫu / báo giá / bot → tìm NCC trùng tên (không phân biệt hoa thường, khoảng trắng),
  chưa có thì tự tạo trong mục Nhà cung cấp.
- Tra mã số thuế qua API công khai VietQR (dữ liệu Cục Thuế) → tên công ty + địa chỉ.
"""

import logging
import re

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.supplier import Supplier

logger = logging.getLogger(__name__)

TEN_KHONG_RO = "ncc chưa rõ"


def chuan_ten(s: str | None) -> str:
    return re.sub(r"\s+", " ", (s or "").strip()).lower()


def chuan_mst(s: str | None) -> str | None:
    """MST 10 số hoặc 10 số + '-' + 3 số (chi nhánh)."""
    m = re.sub(r"[^\d-]", "", s or "")
    return m if re.fullmatch(r"\d{10}(-\d{3})?", m) else None


async def tra_mst(mst: str) -> dict | None:
    mst = chuan_mst(mst)
    if not mst:
        return None
    try:
        async with httpx.AsyncClient(timeout=8) as c:
            r = await c.get(f"https://api.vietqr.io/v2/business/{mst}")
        j = r.json()
    except Exception as exc:  # noqa: BLE001 — mạng/JSON
        logger.warning("Tra MST lỗi: %s", exc)
        return None
    d = j.get("data") if isinstance(j, dict) and j.get("code") == "00" else None
    if not d:
        return None
    return {"ma_so_thue": mst, "ten_cong_ty": d.get("name"), "ten_ngan": d.get("shortName"),
            "dia_chi": d.get("address"), "trang_thai": d.get("status")}


class BoNcc:
    """Bộ nhớ đệm NCC theo tên/MST trong một request (nhập sheet hàng trăm dòng chỉ query 1 lần)."""

    def __init__(self, db: AsyncSession):
        self.db = db
        self._theo_ten: dict[str, Supplier] | None = None
        self._theo_mst: dict[str, Supplier] = {}

    async def _nap(self):
        if self._theo_ten is None:
            self._theo_ten = {}
            for s in (await self.db.execute(select(Supplier))).scalars():
                self._theo_ten.setdefault(chuan_ten(s.name), s)
                if s.ma_so_thue:
                    self._theo_mst.setdefault(s.ma_so_thue, s)

    async def lay(self, ten: str | None, mst: str | None = None, dia_chi: str | None = None) -> Supplier | None:
        """Tìm theo MST rồi theo tên; chưa có thì tạo. Tên rỗng/«NCC chưa rõ» → None."""
        await self._nap()
        mst = chuan_mst(mst)
        k = chuan_ten(ten)
        s = (self._theo_mst.get(mst) if mst else None) or (self._theo_ten.get(k) if k else None)
        if s is None:
            if not k or k == TEN_KHONG_RO:
                return None
            s = Supplier(name=re.sub(r"\s+", " ", ten.strip())[:255], category="general",
                         notes="Tự tạo khi nhập vật tư — bổ sung liên hệ sau")
            self.db.add(s)
            await self.db.flush()
            self._theo_ten[k] = s
        # Bổ sung thông tin còn trống, không ghi đè cái người dùng đã nhập
        if mst and not s.ma_so_thue:
            s.ma_so_thue = mst
            self._theo_mst[mst] = s
        if dia_chi and not s.address:
            s.address = dia_chi.strip()[:500]
        return s
