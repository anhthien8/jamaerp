"""Nhà cung cấp dùng chung cho Vật tư (26/10/2026).

- Gõ tên NCC ở mẫu / báo giá / bot → tìm NCC trùng tên (không phân biệt hoa thường, khoảng trắng,
  kiểu bỏ dấu, chữ loại hình đứng đầu «Công ty TNHH…» — xem `khoa_ncc`), chưa có thì tự tạo trong
  mục Nhà cung cấp.
- Tra mã số thuế qua API công khai VietQR (dữ liệu Cục Thuế) → tên công ty + địa chỉ.
"""

import logging
import re

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.chuan_hoa_unicode import nfc
from app.models.supplier import Supplier

logger = logging.getLogger(__name__)

TEN_KHONG_RO = "ncc chưa rõ"
GHI_CHU_TU_TAO = "Tự tạo khi nhập vật tư — bổ sung liên hệ sau"

# Chữ chỉ loại hình doanh nghiệp đứng ĐẦU tên: «Công ty TNHH TM & DV Hiệp Phát», «Cty Hiệp Phát»
# và «Hiệp Phát» là MỘT nhà cung cấp (22/11/2026 — trước đó mỗi cách gõ sinh một NCC).
_LOAI_HINH = (
    "công ty", "cty", "ctcp", "tnhh", "cổ phần", "cp", "mtv", "một thành viên", "1 thành viên", "1tv",
    "doanh nghiệp tư nhân", "dntn", "hộ kinh doanh", "hkd", "cửa hàng",
)
_NGANH = (
    "thương mại", "tm", "dịch vụ", "dv", "sản xuất", "sx", "xuất nhập khẩu", "xnk",
    "tmdv", "sxtm", "tmsx", "sxtmdv",
)


def _tu(ds: tuple[str, ...]) -> str:
    return "|".join(sorted(ds, key=len, reverse=True))


_NOI = r"[\s.,&/+-]*"  # dấu nối giữa các chữ loại hình: «TM & DV», «TM-DV», «Cty.»
# Chuỗi chữ loại hình trọn từ ở đầu tên. Chữ «và»: sau chữ NGÀNH NGHỀ thì luôn là chữ nối («Thương mại
# và Xây dựng …»); sau chữ khác chỉ bỏ khi nó nối sang một chữ loại hình nữa («Công ty Và Cộng Sự» là tên riêng).
_RE_LOAI_HINH_DAU = re.compile(
    rf"^(?:(?:{_tu(_NGANH)})(?!\w){_NOI}(?:và )?"
    rf"|(?:{_tu(_LOAI_HINH)})(?!\w){_NOI}(?:và (?=(?:{_tu(_LOAI_HINH + _NGANH)})(?!\w)))?)+"
)
# Hai kiểu bỏ dấu đều đúng chính tả («hoà»/«hòa», «thuỷ»/«thủy», «quý»/«qúy»), NFC không gộp —
# bộ gõ kiểu cũ và kiểu mới cho ra hai chuỗi khác nhau của cùng một tên. Khoá so trùng đưa về một kiểu.
_DAU = {
    "òa": "oà", "óa": "oá", "ỏa": "oả", "õa": "oã", "ọa": "oạ",
    "òe": "oè", "óe": "oé", "ỏe": "oẻ", "õe": "oẽ", "ọe": "oẹ",
    "ùy": "uỳ", "úy": "uý", "ủy": "uỷ", "ũy": "uỹ", "ụy": "uỵ",
}
_RE_DAU = re.compile("|".join(_DAU))


def chuan_ten(s: str | None) -> str:
    # NFC trước (21/11/2026): tên gõ bằng bộ gõ «Unicode tổ hợp» phải khớp NCC đã lưu dạng
    # dựng sẵn — không thì BoNcc.lay tạo NCC trùng tên (trông y hệt)
    return re.sub(r"\s+", " ", nfc(s or "").strip()).lower()


def khoa_ncc(ten: str | None) -> str:
    """Khoá so trùng tên NCC = `chuan_ten`, một kiểu bỏ dấu, bỏ dấu chấm/phẩy cuối tên, rồi bỏ hết
    chữ loại hình đứng đầu.

    Tên chỉ gồm chữ loại hình («Công ty Thương mại») → giữ nguyên, không để khoá rỗng.
    """
    goc = _RE_DAU.sub(lambda m: _DAU[m[0]], chuan_ten(ten)).rstrip(" .,")
    return _RE_LOAI_HINH_DAU.sub("", goc) or goc


def chuan_mst(s: str | None) -> str | None:
    """MST 10 số hoặc 10 số + '-' + 3 số (chi nhánh)."""
    m = re.sub(r"[^\d-]", "", s or "")
    return m if re.fullmatch(r"\d{10}(-\d{3})?", m) else None


def khac_phap_nhan(mst_a: str | None, mst_b: str | None) -> bool:
    """Hai MST hợp lệ khác nhau ở 10 số đầu = hai pháp nhân khác nhau (chi nhánh «-001» chung 10 số
    đầu với trụ sở). Thiếu hoặc sai dạng một bên → không kết luận được → False."""
    a, b = chuan_mst(mst_a), chuan_mst(mst_b)
    return bool(a and b and a[:10] != b[:10])


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
        self._theo_ten: dict[str, list[Supplier]] | None = None  # theo `khoa_ncc`
        self._theo_ten_dung: dict[str, Supplier] = {}  # theo tên y hệt (`chuan_ten`)
        self._theo_mst: dict[str, Supplier] = {}

    def _nho(self, s: Supplier) -> None:
        self._theo_ten_dung.setdefault(chuan_ten(s.name), s)
        self._theo_ten.setdefault(khoa_ncc(s.name), []).append(s)
        if s.ma_so_thue:
            self._theo_mst.setdefault(chuan_mst(s.ma_so_thue) or s.ma_so_thue, s)

    async def _nap(self):
        if self._theo_ten is None:
            self._theo_ten = {}
            # Hai NCC cùng tên / cùng khoá (dữ liệu trước 22/11): NCC ĐANG DÙNG trước — không về cái đã
            # «Ngừng dùng» mà mọi danh sách đều ẩn —, rồi tới NCC tạo trước.
            q = select(Supplier).order_by(Supplier.is_active.desc(), Supplier.created_at, Supplier.id)
            for s in (await self.db.execute(q)).scalars():
                self._nho(s)

    async def lay(self, ten: str | None, mst: str | None = None, dia_chi: str | None = None) -> Supplier | None:
        """Tìm theo MST, rồi tên gõ y hệt, rồi khoá; chưa có thì tạo. Tên rỗng/«NCC chưa rõ» → None.

        Tên y hệt đi trước khoá: chọn «Cửa hàng Minh Phát» ở ô gợi ý thì ra đúng nó, không bị kéo về
        «Công ty TNHH Minh Phát» cùng khoá. Khớp theo khoá chỉ là đoán: bỏ qua NCC mà MST chứng tỏ là
        pháp nhân khác («Công ty TNHH An Phát» ≠ «Công ty CP An Phát»).
        """
        await self._nap()
        mst = chuan_mst(mst)
        k = khoa_ncc(ten)
        s = self._theo_mst.get(mst) if mst else None
        if s is None and k:
            # Tên y hệt thắng (kể cả khi tệp ghi MST khác — thường là đọc nhầm số, không sinh hai NCC
            # trùng tên), TRỪ khi NCC đó đã ngừng mà cùng khoá còn NCC đang dùng: không để báo giá rơi
            # vào NCC mọi danh sách đều ẩn.
            dung = self._theo_ten_dung.get(chuan_ten(ten))
            ung = [x for x in self._theo_ten.get(k, ()) if not khac_phap_nhan(mst, x.ma_so_thue)]
            if dung and dung.is_active:
                s = dung
            elif ung and ung[0].is_active:
                s = ung[0]
            else:
                s = dung or (ung[0] if ung else None)
        if s is None:
            if not k or chuan_ten(ten) == TEN_KHONG_RO:
                return None
            s = Supplier(name=re.sub(r"\s+", " ", ten.strip())[:255], category="general",
                         notes=GHI_CHU_TU_TAO)
            self.db.add(s)
            await self.db.flush()
            self._nho(s)
        # Bổ sung thông tin còn trống, không ghi đè cái người dùng đã nhập
        if mst and not s.ma_so_thue:
            s.ma_so_thue = mst
            self._theo_mst[mst] = s
        if dia_chi and not s.address:
            s.address = dia_chi.strip()[:500]
        return s
