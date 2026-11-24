"""Hiểu câu sale gõ tự do cho bot Telegram (R00 mục 8, 15/11/2026).

«gặp anh Nam Vinhomes xong, khách xin 3 ngày» → việc vừa làm (gọi / gặp / Zoom / khách lên
văn phòng / ghi chú / chỉ hẹn), giờ hẹn tiếp, và lead nào — chỉ trong số lead CỦA CHÍNH NGƯỜI GÕ.

Không ghi mù: ở đây chỉ ĐOÁN. Bot hỏi lại «Ghi vào lead X: …?» [Đúng] [Chọn lead khác]; sale
bấm Đúng thì bot mới gọi `POST /telegram/lead/{id}/touch`.

Bộ luật chạy trước và tự đủ dùng khi không có AI. Có model AI thì nhờ AI đọc lại câu — chỉ gửi
câu của sale, KHÔNG gửi danh sách lead; AI trả sai khuôn, hẹn đã qua hoặc quá xa thì bỏ phần đó.
Dò lead luôn làm ở server, trong phạm vi lead người gõ đang phụ trách.

Chữ có dấu so có dấu: «gói» ≠ «gọi», «năm» ≠ «Nam». Ai gõ không dấu thì so không dấu.
"""

from __future__ import annotations

import asyncio
import json
import logging
import math
import re
import unicodedata
from collections import Counter
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from functools import lru_cache

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.middleware.rbac import duoc_xem_lead
from app.models.lead import Lead
from app.models.user import User
from app.services.automation import gio_vn_naive
from app.services.lead_touch import GIO_HEN_MAC_DINH, NHAN_LOAI_HEN, THU_VN, nhan_viec
from app.services.llm_config import llm_available, llm_complete

logger = logging.getLogger(__name__)

HEN_XA_NHAT_NGAY = 180   # hẹn xa hơn coi như đọc nhầm
AI_CHO_GIAY = 8.0
NGUONG_DIEM = 1.0        # điểm tối thiểu để một lead thành ứng viên
SO_UNG_VIEN = 5
SO_GOI_Y = 6
SO_LEAD_DO = 500         # dò trong 500 lead cập nhật gần nhất của người gõ
GIAI_DOAN_KHONG_GOI_Y = frozenset({"lost", "dormant", "signed_design"})


# ── Chữ ──────────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class Tu:
    goc: str     # chữ thường, có dấu
    tron: str    # bỏ dấu, đ → d
    dau: str     # các dấu đã sắp xếp («hòa» và «hoà» cùng dấu); rỗng = gõ không dấu
    loai: str    # tu | gio | ngay
    vi_tri: int
    ve: int      # vế câu, ngăn bởi , . ; ! ? xuống dòng


def _tach_dau(s: str) -> tuple[str, str]:
    nfd = unicodedata.normalize("NFD", s.lower())
    dau = "".join(sorted(c for c in nfd if unicodedata.category(c) == "Mn"))
    tron = "".join(c for c in nfd if unicodedata.category(c) != "Mn")
    return tron.replace("đ", "d"), dau + "đ" * tron.count("đ")


_TACH = re.compile(
    r"(?P<ngay>\b\d{1,2}/\d{1,2}(?:/\d{2,4})?\b)"
    r"|(?P<gio>\b\d{1,2}(?:[h:g]\d{2}p?|[hg])(?!\w))"
    r"|(?P<tu>\w+)"
    r"|(?P<ngat>[,.;!?\n])"
)


def tach_tu(text: str) -> list[Tu]:
    tus: list[Tu] = []
    ve = 0
    for m in _TACH.finditer(unicodedata.normalize("NFC", text)):
        if m.lastgroup == "ngat":
            ve += 1
            continue
        tron, dau = _tach_dau(m.group())
        tus.append(Tu(m.group().lower(), tron, dau, m.lastgroup or "tu", len(tus), ve))
    return tus


@lru_cache(maxsize=1024)
def _mau(w: str) -> tuple[str, str]:
    return _tach_dau(w)


def la(t: Tu | None, *mau: str) -> bool:
    """`t` là một trong các chữ `mau`: gõ đúng dấu, hoặc gõ không dấu."""
    if t is None or t.loai != "tu":
        return False
    for w in mau:
        tron, dau = _mau(w)
        if t.tron == tron and (t.dau == dau or not t.dau):
            return True
    return False


def _bo(chu: str) -> tuple[str, ...]:
    return tuple(chu.split())


XUNG_HO = _bo("anh chị em cô chú bác ông bà cậu dì a c e sếp")
# Chữ đứng sau «anh/chị…» mà không phải tên người.
KHONG_PHAI_TEN = _bo(
    "gặp gọi hẹn xin nói bảo hỏi muốn cần chưa không ko có đã vừa sẽ đi lên qua về ơi ạ à nhé "
    "ấy đó này kia bên ở tại vẫn cũng thì là và với cho được đang bị mới rồi xong ta"
)
# Chữ thường gặp trong câu báo việc — không dùng để dò tên lead.
TU_DEM = _bo(
    "khách kh gặp gọi điện lại rồi xong đã vừa sẽ hẹn xin ngày hôm nay mai mốt kia tuần tháng năm "
    "sau tới nữa thứ chủ nhật sáng trưa chiều tối đêm giờ phút lúc vào và với của cho là thì mà "
    "nhé nha ạ à ơi nhưng vẫn còn cũng được đc không ko chưa có bên ở tại qua lên đến về đi để "
    "thêm muốn cần nói bảo báo hỏi trả lời nghe máy bắt thuê bao nhắn tin zalo zoom online meet "
    "call video văn phòng vp công ty cty showroom khảo sát xem nhà trình cafe cà phê tư vấn đo "
    "giá gửi gói trọn thiết kế hợp đồng hđ deal chốt ok oke dạ vâng chút sớm muộn trước sắp "
    "định dự kiến lịch số đt sđt đuôi anh chị em ấy đó này luôn liền ngay hết quá rất lắm lần mình"
)
# Dạng không dấu của TU_DEM trùng tên người hay gặp → gõ không dấu thì vẫn coi là tên.
TEN_KHONG_DAU = frozenset(
    "nam mai tuan thu hoa lan an binh ha hai ba tu sau bay tam nhat phong cong van tin gia chi "
    "trinh ky dat thanh khanh minh".split()
)
_DEM_DAU = frozenset(_mau(w) for w in TU_DEM)
_TRON_DEM = frozenset(tron for tron, _ in _DEM_DAU)
_DEM_TRON = _TRON_DEM - TEN_KHONG_DAU
TU_DIA_CHI = frozenset(
    "duong pho phuong quan huyen xa tinh thanh tp so ap thon khu chung cu toa can ho block tang "
    "lo kdt khu do thi".split()
)


def la_tu_dem(t: Tu) -> bool:
    return (t.tron, t.dau) in _DEM_DAU if t.dau else t.tron in _DEM_TRON


def _chu_so(s: str | None) -> str:
    so = re.sub(r"\D", "", s or "")
    return "0" + so[2:] if so.startswith("84") and len(so) >= 11 else so


# ── Thời gian hẹn ────────────────────────────────────────────────────────────

SO_CHU = {"một": 1, "hai": 2, "ba": 3, "bốn": 4, "tư": 4, "năm": 5, "sáu": 6, "bảy": 7,
          "bẩy": 7, "tám": 8, "chín": 9, "mười": 10, "vài": 3}
GIO_BUOI = {"sáng": 9, "trưa": 12, "chiều": 14, "tối": 19}


def _so(t: Tu | None, truoc: Tu | None = None) -> int | None:
    """Số viết bằng chữ số, hoặc bằng chữ gõ ĐÚNG dấu («năm ngày»; «anh Nam», «chị Năm» là tên)."""
    if t is None or t.loai != "tu":
        return None
    if t.goc.isdigit():
        return int(t.goc) if len(t.goc) <= 3 else None
    if la(truoc, *XUNG_HO):
        return None
    return next((n for w, n in SO_CHU.items() if (t.tron, t.dau) == _mau(w)), None)


def _don_vi(t: Tu | None) -> int | None:
    if la(t, "ngày", "hôm"):
        return 1
    if la(t, "tuần"):
        return 7
    if la(t, "tháng"):
        return 30
    return None


def _buoi(t: Tu | None) -> str | None:
    return next((w for w in GIO_BUOI if la(t, w)), None)


# «qua công ty / qua nhà» = ghé tới, không phải «tối qua»
DIEM_DEN = _bo("công cty văn vp showroom nhà bên chỗ đây đó")
# «lần thứ 2», «phương án thứ 2», «tầng thứ 2» = thứ tự, không phải thứ trong tuần
THU_TU_TRUOC = _bo("lần đợt án bản tầng người cái căn phòng")
# «12/5» chỉ là ngày khi vế câu có ngữ cảnh hẹn; không thì là phân số («cọc 1/2»), địa chỉ («số 12/5»)
CANH_NGAY = _bo("hẹn lịch ngày thứ chủ nhật sáng trưa chiều tối gặp gọi khảo sát zoom lúc")
KHONG_PHAI_NGAY = _bo("số ngõ ngách hẻm kiệt nhà căn tầng lô phòng cọc đợt ở tại đường phố")


def _ve_qua_khu(tus: list[Tu]) -> set[int]:
    """Vế câu kể chuyện đã qua: «hôm qua/kia», «tối qua gặp…», «3 hôm trước», «tuần qua/rồi»,
    «cách đây 2 ngày». Chữ thời gian trong các vế này không được thành giờ hẹn."""
    ve: set[int] = set()
    for i, t in enumerate(tus):
        truoc = tus[i - 1] if i and tus[i - 1].ve == t.ve else None
        sau = tus[i + 1] if i + 1 < len(tus) and tus[i + 1].ve == t.ve else None
        if la(t, "qua") and la(sau, *DIEM_DEN):
            continue
        if ((la(t, "trước", "qua") and _don_vi(truoc) is not None)
                or (la(t, "kia") and la(truoc, "hôm"))
                or (la(t, "qua") and _buoi(truoc))
                or (la(t, "rồi") and la(truoc, "tuần", "tháng"))
                or (la(t, "cách") and la(sau, "đây"))):
            ve.add(t.ve)
    return ve


def _gio_tu_chu(goc: str) -> tuple[int, int] | None:
    m = re.match(r"(\d{1,2})(?:[h:g](\d{2})?p?)?$", goc)
    if not m:
        return None
    h, p = int(m.group(1)), int(m.group(2) or 0)
    return (h, p) if h < 24 and p < 60 else None


def _ngay_hop_le(nam: int, thang: int, ngay: int) -> date | None:
    try:
        return date(nam, thang, ngay)
    except ValueError:
        return None


@dataclass
class _Hen:
    luc: datetime | None = None
    vi_tri: set[int] = field(default_factory=set)   # chữ thuộc biểu thức thời gian


def doc_hen(tus: list[Tu], now: datetime) -> _Hen:
    """Mốc hẹn trong câu (naive giờ VN). Chỉ nhận mốc ở phía trước, trong HEN_XA_NHAT_NGAY ngày."""
    hom_nay = now.date()
    ngay: date | None = None
    gio: tuple[int, int] | None = None
    buoi: str | None = None
    thu: int | None = None
    tuan_sau = False
    dung: set[int] = set()
    n = len(tus)
    qua = _ve_qua_khu(tus)

    def lay(i: int) -> Tu | None:
        return tus[i] if 0 <= i < n else None

    i = 0
    while i < n:
        t, sau, truoc = tus[i], lay(i + 1), lay(i - 1)
        an = 1  # số chữ đã dùng
        if t.ve in qua:
            i += 1
            continue
        if t.loai == "ngay":
            cung_ve = [x for x in tus if x.ve == t.ve]
            if la(truoc, *KHONG_PHAI_NGAY) or not any(la(x, *CANH_NGAY) or x.loai == "gio" for x in cung_ve):
                i += 1  # «cọc 1/2», «số 12/5 Lê Lợi»: không phải ngày
                continue
            so = [int(x) for x in t.goc.split("/")]
            nam = so[2] if len(so) == 3 else hom_nay.year
            nam = nam + 2000 if nam < 100 else nam
            d = _ngay_hop_le(nam, so[1], so[0])
            if d and len(so) == 2 and d < hom_nay:
                d = _ngay_hop_le(nam + 1, so[1], so[0])
            if d and ngay is None:
                ngay = d
            dung.add(i)
        elif t.loai == "gio":
            g = _gio_tu_chu(t.goc)
            if g and gio is None:
                gio = g
            dung.add(i)
        elif _so(t, truoc) is not None and la(sau, "giờ"):
            h, p, an = _so(t, truoc), 0, 2
            if _so(lay(i + 2)) is not None and (lay(i + 2).goc.isdigit()):
                p, an = _so(lay(i + 2)), 3
                if la(lay(i + 3), "phút"):
                    an = 4
            elif la(lay(i + 2), "rưỡi"):
                p, an = 30, 3
            if gio is None and h is not None and h < 24 and p < 60:
                gio = (h, p)
            dung.update(range(i, i + an))
        elif la(t, "thứ") and 2 <= (_so(sau, t) or 0) <= 7 and not la(truoc, *THU_TU_TRUOC) and (
                t.dau or not (la(truoc, *XUNG_HO) or la(lay(i + 2), "lần", "đợt"))):
            thu, an = (_so(sau, t) or 2) - 2, 2
            dung.update((i, i + 1))
        elif la(t, "chủ") and la(sau, "nhật"):
            thu, an = 6, 2
            dung.update((i, i + 1))
        elif t.loai == "tu" and (t.tron == "cn" or re.fullmatch(r"t[2-7]", t.tron)) and not (
                (truoc is not None and truoc.tron in TU_DIA_CHI)
                or (sau is not None and sau.loai == "tu" and not sau.goc.isdigit()
                    and sau.tron not in _TRON_DEM and not la(sau, *XUNG_HO)
                    and not any(la(x, *KE_HOACH) for x in tus[:i] if x.ve == t.ve))):
            thu = 6 if t.tron == "cn" else int(t.tron[1]) - 2
            dung.add(i)
        elif ((la(t, "ngày", "mùng") or (la(t, "mồng") and t.dau)) and sau is not None and sau.goc.isdigit()) or (
                t.goc.isdigit() and la(sau, "tháng") and lay(i + 2) is not None
                and lay(i + 2).goc.isdigit() and 1 <= int(lay(i + 2).goc) <= 12):
            # «ngày 20», «ngày 20 tháng 11», «mùng 1 tháng sau», «5 tháng 12» («mong» không dấu = mong muốn)
            k = i if t.goc.isdigit() else i + 1  # vị trí số ngày
            dn, th, mm = int(tus[k].goc), lay(k + 1), lay(k + 2)
            thang_sau = hom_nay.replace(day=1) + timedelta(days=32)
            if la(th, "tháng") and mm is not None and mm.goc.isdigit():
                d = _ngay_hop_le(hom_nay.year, int(mm.goc), dn)
                if d and d < hom_nay:
                    d = _ngay_hop_le(hom_nay.year + 1, d.month, dn)
                an = k - i + 3
            elif la(th, "tháng") and la(mm, "sau", "tới"):
                d = _ngay_hop_le(thang_sau.year, thang_sau.month, dn)
                an = k - i + 3
            else:
                d = _ngay_hop_le(hom_nay.year, hom_nay.month, dn)
                if d and d < hom_nay:
                    d = _ngay_hop_le(thang_sau.year, thang_sau.month, dn)
                an = k - i + 1
            if d and ngay is None:
                ngay = d
            dung.update(range(i, i + an))
        elif la(t, "mai") and not la(truoc, *XUNG_HO):
            if ngay is None:
                ngay = hom_nay + timedelta(days=1)
            dung.add(i)
            if la(truoc, "ngày"):
                dung.add(i - 1)
        elif la(t, "mốt") and t.dau:   # «mot» không dấu có thể là «một»
            if ngay is None:
                ngay = hom_nay + timedelta(days=2)
            dung.add(i)
        elif la(t, "ngày") and la(sau, "kia"):
            if ngay is None:
                ngay = hom_nay + timedelta(days=2)
            an = 2
            dung.update((i, i + 1))
        elif la(t, "nay") and (truoc is None or la(truoc, "hôm") or _buoi(truoc)):
            if ngay is None:
                ngay = hom_nay
            dung.add(i)
            if la(truoc, "hôm"):
                dung.add(i - 1)
        elif _so(t, truoc) is not None and _don_vi(sau) is not None and not la(truoc, "thứ", "ngày"):
            if ngay is None:
                ngay = hom_nay + timedelta(days=(_so(t, truoc) or 0) * (_don_vi(sau) or 1))
            an = 3 if la(lay(i + 2), "nữa", "sau", "tới") else 2
            dung.update(range(i, i + an))
        elif la(t, "tuần") and la(sau, "sau", "tới", "nữa"):
            tuan_sau, an = True, 2
            dung.update((i, i + 1))
        elif la(t, "tháng") and la(sau, "sau", "tới"):
            if ngay is None:
                ngay = hom_nay + timedelta(days=30)
            an = 2
            dung.update((i, i + 1))
        elif _buoi(t):
            buoi = buoi or _buoi(t)
            dung.add(i)
        i += an

    if ngay is None and thu is not None:
        if tuan_sau:
            ngay = hom_nay + timedelta(days=7 - hom_nay.weekday() + thu)
        else:
            ngay = hom_nay + timedelta(days=(thu - hom_nay.weekday()) % 7 or 7)
    elif ngay is None and tuan_sau:
        ngay = hom_nay + timedelta(days=7)
    elif ngay is None and (gio or buoi):
        ngay = hom_nay
    if ngay is None or (ngay == hom_nay and gio is None and buoi is None):
        return _Hen()   # «hôm nay» không kèm giờ là kể việc, không phải hẹn

    if gio is not None:
        h, p = gio
        if buoi in ("chiều", "tối") and h < 12:
            h += 12
        elif buoi == "trưa" and h < 5:
            h += 12
        elif buoi is None and 1 <= h <= 6:   # «hẹn 2h» trong giờ làm việc = 14:00
            h += 12
    else:
        h, p = GIO_BUOI.get(buoi or "", GIO_HEN_MAC_DINH), 0
    luc = datetime(ngay.year, ngay.month, ngay.day, h, p)
    if not (now < luc <= now + timedelta(days=HEN_XA_NHAT_NGAY)):
        return _Hen()
    return _Hen(luc, dung)


# ── Việc đã làm ──────────────────────────────────────────────────────────────

# (cụm chữ, loại). goi! = có gọi (kể cả khách không nghe máy) → luôn là đã gọi.
_CUM_VIEC: list[tuple[tuple[str, ...], str]] = sorted(
    [
        (("gọi", "video"), "zoom"), (("call", "video"), "zoom"), (("video", "call"), "zoom"),
        (("google", "meet"), "zoom"), (("zoom",), "zoom"), (("meet",), "zoom"),
        (("online",), "zoom"), (("teams",), "zoom"),
        (("khảo", "sát"), "ks"),
        (("xem", "nhà"), "gap"), (("xem", "công", "trình"), "gap"), (("đo", "nhà"), "gap"),
        (("cà", "phê"), "gap"), (("cafe",), "gap"), (("café",), "gap"), (("gặp",), "gap"),
        (("nghe", "máy"), "goi!"), (("bắt", "máy"), "goi!"), (("thuê", "bao"), "goi!"),
        (("gọi", "điện"), "goi"), (("gọi",), "goi"), (("call",), "goi"), (("alo",), "goi"),
        (("văn", "phòng"), "noi_vp"), (("vp",), "noi_vp"), (("công", "ty"), "noi_vp"),
        (("cty",), "noi_vp"), (("showroom",), "noi_vp"),
    ],
    key=lambda x: -len(x[0]),
)
DI_VP = _bo("lên qua tới đến ghé vào ra")
PHU_DINH = _bo("chưa không ko k hông chẳng chả")
KE_HOACH = _bo("hẹn sẽ định dự lịch sắp")
HUY_BO = ("hoãn", "huỷ", "lỡ")  # chỉ tính khi gõ CÓ dấu: «Huy», «Hoan» không dấu là tên người
THAT_BAI = (("chưa", "được"), ("chưa", "đc"), ("không", "được"), ("ko", "được"), ("không", "đc"),
            ("ko", "đc"), ("không", "thành"), ("ko", "thành"), ("hụt",))
THAT_BAI_GOI = (("chưa", "được"), ("chưa", "đc"))  # «gọi … không được» vẫn là đã gọi (như «không nghe máy»)


def _co_dau(t: Tu, *mau: str) -> bool:
    return t.loai == "tu" and any((t.tron, t.dau) == _mau(w) for w in mau)


def _co_cum(tus: list[Tu], cums) -> bool:
    return any(j + len(c) <= len(tus) and all(la(tus[j + k], w) for k, w in enumerate(c))
               for c in cums for j in range(len(tus)))
XONG = _bo("đã xong rồi vừa nãy")
UU_TIEN = {"vp": 4, "zoom": 3, "gap": 2, "ks": 2, "goi": 1, "goi!": 1}
VIEC_CUA = {"vp": "vp", "zoom": "zoom", "gap": "gap", "ks": "gap", "goi": "goi", "goi!": "goi"}
LOAI_HEN_CUA = {"vp": "offline", "gap": "offline", "zoom": "online", "ks": "survey"}


@dataclass(frozen=True)
class _Dong:
    loai: str
    vi_tri: int
    ve: int


def _tim_viec(tus: list[Tu]) -> list[_Dong]:
    ra: list[_Dong] = []
    i = 0
    while i < len(tus):
        cum, loai = next(
            ((c, lo) for c, lo in _CUM_VIEC
             if i + len(c) <= len(tus) and all(la(tus[i + k], w) for k, w in enumerate(c))),
            ((), ""),
        )
        if loai == "noi_vp":
            truoc = [t for t in tus[max(0, i - 3):i] if t.ve == tus[i].ve]
            di = next((t for t in reversed(truoc) if la(t, *DI_VP)), None)
            if di is not None or (truoc and la(truoc[-1], "tại", "ở") and not any(la(t, "làm") for t in truoc[:-1])):
                ra.append(_Dong("vp", di.vi_tri if di else i, tus[i].ve))
        elif loai:
            ra.append(_Dong(loai, i, tus[i].ve))
        i += len(cum) or 1
    return ra


def _phan_loai(tus: list[Tu], dongs: list[_Dong], cho_hen: set[int]) -> tuple[list[_Dong], list[_Dong]]:
    """Tách việc ĐÃ làm và việc mới HẸN (chưa diễn ra)."""
    da, hen = [], []
    for d in dongs:
        cung_ve = [t for t in tus if t.ve == d.ve]
        truoc = [t for t in cung_ve if t.vi_tri < d.vi_tri]
        sau = [t for t in cung_ve if t.vi_tri > d.vi_tri]
        that_bai = not any(la(t, *XONG) for t in cung_ve) and _co_cum(
            sau, THAT_BAI_GOI if d.loai == "goi" else THAT_BAI)
        if d.loai == "goi!":
            da.append(d)
        elif any(la(t, *PHU_DINH) for t in truoc[-2:]) or any(_co_dau(t, *HUY_BO) for t in truoc) or that_bai:
            continue
        elif any(la(t, *KE_HOACH) for t in truoc) or any(t.vi_tri in cho_hen for t in truoc[-2:]):
            hen.append(d)
        elif any(la(t, *XONG) for t in cung_ve):
            da.append(d)
        elif any(t.vi_tri in cho_hen for t in cung_ve):
            hen.append(d)
        else:
            da.append(d)
    return da, hen


# ── Đọc câu (bộ luật) ────────────────────────────────────────────────────────

_SDT = re.compile(r"(?<!\d)(?:\+?84|0)(?:[\s.\-]?\d){8,10}(?!\d)")
_DUOI = re.compile(r"(?:đuôi|duoi)\s*(\d{3,6})(?!\d)", re.IGNORECASE)


@dataclass
class Doc:
    viec: str | None = None          # goi | gap | zoom | vp | hen (ghi_chu quyết sau khi dò lead)
    hen: datetime | None = None
    plan_type: str | None = None
    nguoi: list[Tu] = field(default_factory=list)    # chữ ngay sau «anh/chị…»: tên người
    tu_do: list[Tu] = field(default_factory=list)    # chữ dùng để dò tên/địa chỉ lead
    sdt: list[str] = field(default_factory=list)     # SĐT đầy đủ trong câu
    duoi: list[str] = field(default_factory=list)    # «đuôi 111»
    so_chu: int = 0
    la_cau_hoi: bool = False


def doc_cau(text: str, now: datetime) -> Doc:
    text = unicodedata.normalize("NFC", text or "").strip()
    sdt = [s for s in (_chu_so(m.group()) for m in _SDT.finditer(text)) if 10 <= len(s) <= 11]
    duoi = _DUOI.findall(text)
    tus = tach_tu(_DUOI.sub(" ", _SDT.sub(" ", text)))
    hen = doc_hen(tus, now)
    da, sap = _phan_loai(tus, _tim_viec(tus), hen.vi_tri)

    nguoi = [
        tus[i + 1] for i, t in enumerate(tus[:-1])
        if la(t, *XUNG_HO) and tus[i + 1].ve == t.ve and tus[i + 1].loai == "tu"
        and not tus[i + 1].goc.isdigit() and not la(tus[i + 1], *XUNG_HO, *KHONG_PHAI_TEN)
    ]
    id_nguoi = {t.vi_tri for t in nguoi}
    tu_do = nguoi + [
        t for t in tus
        if t.vi_tri not in id_nguoi and t.vi_tri not in hen.vi_tri and t.loai == "tu"
        and not t.goc.isdigit() and len(t.tron) >= 2 and not la(t, *XUNG_HO) and not la_tu_dem(t)
    ]

    viec = VIEC_CUA[max(da, key=lambda d: UU_TIEN[d.loai]).loai] if da else None
    plan = LOAI_HEN_CUA.get(max(sap, key=lambda d: UU_TIEN[d.loai]).loai) if sap else None
    return Doc(
        viec=viec or ("hen" if hen.luc else None), hen=hen.luc, plan_type=plan if hen.luc else None,
        nguoi=nguoi, tu_do=tu_do, sdt=sdt, duoi=duoi,
        so_chu=sum(1 for t in tus if t.loai == "tu"), la_cau_hoi=text.endswith("?"),
    )


# ── Dò lead ──────────────────────────────────────────────────────────────────


def _khop(u: Tu, l: Tu, lead_khong_dau: bool) -> float:
    """Mức giống giữa chữ sale gõ `u` và chữ trong lead `l`."""
    if u.tron == l.tron:
        if u.dau == l.dau:
            return 1.0
        return 0.8 if (not u.dau or lead_khong_dau) else 0.0   # «năm» ≠ «Nam», «gói» ≠ «gọi»
    ngan, dai = sorted((u.tron, l.tron), key=len)
    if len(ngan) >= 4 and dai.startswith(ngan) and not u.dau and not l.dau:
        return 0.6   # «vinhome» ~ «vinhomes»
    return 0.0


@dataclass
class _ChuLead:
    ten: list[Tu]
    lien_he: list[Tu]
    dia_chi: list[Tu]
    sdt: str

    def cac_truong(self) -> list[tuple[list[Tu], bool, int]]:
        """(chữ, lead gõ không dấu, trọng số): tên ×3, người liên hệ ×2, địa chỉ ×1."""
        return [(ds, not any(t.dau for t in ds), w)
                for ds, w in ((self.ten, 3), (self.lien_he, 2), (self.dia_chi, 1))]


def _chu_lead(lead: Lead) -> _ChuLead:
    def lay(s: str | None, bo_dia_chi: bool = False) -> list[Tu]:
        return [t for t in tach_tu(s or "")
                if t.loai == "tu" and not t.goc.isdigit() and not la(t, *XUNG_HO)
                and not (bo_dia_chi and t.tron in TU_DIA_CHI)]
    return _ChuLead(lay(lead.name), lay(lead.contact_person), lay(lead.address, True),
                    _chu_so(lead.phone))


@dataclass
class UngVien:
    lead: Lead
    diem: float
    khop_sdt: bool
    khop_ro: bool = False  # khớp SĐT, hoặc tên/người liên hệ khớp đúng chữ (sale gõ không dấu cũng tính)


def _khop_ro(u: Tu, l: Tu, lead_khong_dau: bool) -> bool:
    """«Năm» (có dấu) ≈ «Nam» chỉ đủ để GỢI Ý, không đủ để CHẮC; «nam» gõ không dấu thì đủ."""
    return _khop(u, l, lead_khong_dau) == 1.0 or (not u.dau and u.tron == l.tron)


def cham_diem(doc: Doc, leads: list[Lead]) -> list[UngVien]:
    """Lead của người gõ khớp câu, điểm cao trước. Có tên người trong câu thì lead phải khớp tên đó."""
    chu = [_chu_lead(l) for l in leads]
    df = Counter(tron for c in chu for tron in {t.tron for ds, _, _ in c.cac_truong() for t in ds})
    tong = max(len(leads), 1)
    ra: list[UngVien] = []
    for lead, c in zip(leads, chu):
        khop_sdt = bool(c.sdt) and (
            any(c.sdt[-9:] == s[-9:] for s in doc.sdt) or any(c.sdt.endswith(d) for d in doc.duoi)
        )
        truong = c.cac_truong()
        if doc.nguoi and not khop_sdt and not any(
            _khop(u, l, kd) > 0 for u in doc.nguoi for ds, kd, _ in truong[:2] for l in ds
        ):
            continue
        diem = 100.0 if khop_sdt else 0.0
        for u in doc.tu_do:
            diem += max(
                (_khop(u, l, kd) * w * math.log(1 + tong / df[l.tron])
                 for ds, kd, w in truong for l in ds),
                default=0.0,
            )
        if lead.stage in ("lost", "dormant"):
            diem *= 0.7
        if diem >= NGUONG_DIEM:
            ro = khop_sdt or any(_khop_ro(u, l, kd) for u in doc.tu_do for ds, kd, _ in truong[:2] for l in ds)
            ra.append(UngVien(lead, diem, khop_sdt, ro))
    ra.sort(key=lambda u: -u.diem)
    return ra


# ── AI đọc lại câu ───────────────────────────────────────────────────────────

_PROMPT_AI = """Bạn đọc câu một nhân viên kinh doanh công ty nội thất gõ cho bot sau khi làm việc với khách.
Hôm nay là {thu} {ngay:%d/%m/%Y}, bây giờ {ngay:%H:%M} giờ Việt Nam.
Chỉ trả về MỘT đối tượng JSON với đúng các khoá:
- "la_bao_cham": true nếu câu báo đã làm gì với một khách hoặc hẹn khách; ngoài ra false.
- "viec": việc ĐÃ làm: "goi" (gọi điện, kể cả khách không nghe máy), "gap" (gặp trực tiếp, khảo sát, xem nhà),
  "zoom" (Zoom/online), "vp" (khách lên văn phòng), "ghi_chu" (chỉ thông tin về khách), "hen" (chưa làm gì, chỉ hẹn), "khac".
  Buổi hẹn chưa diễn ra KHÔNG phải việc đã làm.
- "khach": tên khách như trong câu (ví dụ "anh Nam Vinhomes"), không có thì "".
- "hen_ngay": ngày hẹn làm việc tiếp với khách dạng YYYY-MM-DD ("khách xin 3 ngày" = 3 ngày nữa), không có thì "".
- "hen_gio": giờ hẹn dạng HH:MM, không có thì "".
- "hen_loai": buổi hẹn tới là "online", "offline" (gặp trực tiếp, lên văn phòng) hay "survey" (khảo sát), không rõ thì ""."""

VIEC_AI = frozenset({"goi", "gap", "zoom", "vp", "ghi_chu", "hen", "khac"})


def kiem_ai(raw: object, now: datetime) -> dict | None:
    """Kết quả AI hợp khuôn → dict; sai khuôn → None (dùng bộ luật)."""
    if not isinstance(raw, dict) or not isinstance(raw.get("viec"), str) or raw["viec"] not in VIEC_AI:
        return None
    co = raw.get("la_bao_cham")
    if isinstance(co, str) and co.strip().lower() in ("true", "false"):
        co = co.strip().lower() == "true"
    if not isinstance(co, bool):
        return None  # thiếu / sai kiểu → dùng bộ luật
    if not co or raw["viec"] == "khac":
        return {"la_bao_cham": False}
    hen = None
    ngay = str(raw.get("hen_ngay") or "").strip()
    if ngay:
        gio = _gio_tu_chu(str(raw.get("hen_gio") or "").strip()) or (GIO_HEN_MAC_DINH, 0)
        try:
            d = date.fromisoformat(ngay)
            hen = datetime(d.year, d.month, d.day, *gio)
        except (TypeError, ValueError):
            hen = None
        if hen is not None and not (now < hen <= now + timedelta(days=HEN_XA_NHAT_NGAY)):
            hen = None
    if raw["viec"] == "hen" and hen is None:
        return None
    loai = raw.get("hen_loai")
    return {
        "la_bao_cham": True, "viec": raw["viec"], "hen": hen,
        "plan_type": loai if hen is not None and loai in NHAN_LOAI_HEN else None,
        "khach": str(raw.get("khach") or "")[:120],
    }


async def _hoi_ai(text: str, now: datetime) -> dict | None:
    try:
        res = await asyncio.wait_for(
            llm_complete(
                messages=[
                    {"role": "system", "content": _PROMPT_AI.format(thu=THU_VN[now.weekday()], ngay=now)},
                    {"role": "user", "content": text},
                ],
                temperature=0.1, max_tokens=300, response_format={"type": "json_object"},
            ),
            AI_CHO_GIAY,
        )
        noi_dung = res.choices[0].message.content or ""
        raw = json.loads(noi_dung[noi_dung.find("{"): noi_dung.rfind("}") + 1])
    except Exception as e:  # AI lỗi, chậm, trả không phải JSON → bộ luật
        logger.info("hieu_cau_sale: không dùng được AI (%s)", type(e).__name__)
        return None
    return kiem_ai(raw, now)


# ── Ghép lại ─────────────────────────────────────────────────────────────────


def _the_lead(lead: Lead, nhan_gd: dict[str, str], diem: float | None = None) -> dict:
    the = {"id": lead.id, "name": lead.name, "stage_label": nhan_gd.get(lead.stage, lead.stage),
           "duoi_sdt": _chu_so(lead.phone)[-3:]}
    if diem is not None:
        the["diem"] = round(diem, 2)
    return the


def _goi_y(leads: list[Lead], now: datetime, bo: set[str]) -> list[Lead]:
    """Lead đang chăm của người gõ: có hẹn hôm nay trước, rồi mới cập nhật gần nhất."""
    hom_nay = now.date()
    song = [l for l in leads if l.stage not in GIAI_DOAN_KHONG_GOI_Y and l.id not in bo]
    song.sort(key=lambda l: not any(m and m.date() == hom_nay for m in (l.hen_tiep_luc, l.survey_date)))
    return song[:SO_GOI_Y]


async def doan_cau_sale(
    db: AsyncSession, user: User, text: str, *, dung_ai: bool = True, now_vn: datetime | None = None,
) -> dict:
    """Đoán câu sale gõ là báo việc gì, cho lead nào. CHỈ ĐOÁN, không ghi gì."""
    from app.api.leads import STAGE_LABELS

    now = now_vn or gio_vn_naive()
    ket_qua = {"la_bao_cham": False, "chac_chan": False, "viec": None, "hen_tiep_luc": None,
               "plan_type": None, "nguon": "luat", "tom_tat": "", "ung_vien": [], "goi_y": []}
    if not duoc_xem_lead(user):
        return ket_qua
    leads = list((await db.execute(
        select(Lead).where(Lead.assigned_to == user.id)
        .order_by(Lead.updated_at.desc()).limit(SO_LEAD_DO)
    )).scalars().all())
    if not leads:
        return ket_qua
    text = (text or "").strip()
    if not text:
        ket_qua["goi_y"] = [_the_lead(l, STAGE_LABELS) for l in _goi_y(leads, now, set())]
        return ket_qua

    doc = doc_cau(text, now)
    if doc.la_cau_hoi:
        return ket_qua
    ung = cham_diem(doc, leads)
    if doc.sdt and not any(u.khop_sdt for u in ung):
        return ket_qua   # SĐT lạ: dán khách mới → để luồng tạo lead lo
    viec, hen, plan, nguon = doc.viec, doc.hen, doc.plan_type, "luat"
    ro_khach = bool(ung) and (ung[0].khop_sdt or bool(doc.nguoi))
    if viec is None and ro_khach and doc.so_chu >= 5:
        viec = "ghi_chu"
    if viec is None and not ung:
        return ket_qua

    if dung_ai and await llm_available():
        # SĐT khách không gửi ra ngoài: so SĐT làm ở máy chủ, AI chỉ cần hiểu việc và giờ hẹn.
        ai = await _hoi_ai(_DUOI.sub("đuôi [SĐT]", _SDT.sub("[SĐT]", text)), now)
        if ai is not None:
            if not ai["la_bao_cham"]:
                return ket_qua
            viec, hen, plan, nguon = ai["viec"], ai["hen"], ai["plan_type"], "ai"
            if ai["khach"]:
                ung = cham_diem(doc_cau(ai["khach"], now), leads) or ung
    if viec is None:
        return ket_qua

    so_khop_sdt = sum(u.khop_sdt for u in ung)
    chac = bool(ung) and ung[0].khop_ro and (
        len(ung) == 1
        or (ung[0].khop_sdt and so_khop_sdt == 1)  # đuôi/SĐT trùng nhiều lead → hỏi chọn
        or (so_khop_sdt <= 1 and ung[0].diem >= 1.5 * ung[1].diem)
    )
    ung = ung[:SO_UNG_VIEN]
    ket_qua.update(
        la_bao_cham=True, chac_chan=chac, viec=viec, nguon=nguon,
        hen_tiep_luc=hen.isoformat() if hen else None, plan_type=plan if hen else None,
        tom_tat=nhan_viec(viec, hen, plan, now),
        ung_vien=[_the_lead(u.lead, STAGE_LABELS, u.diem) for u in ung],
        goi_y=[_the_lead(l, STAGE_LABELS) for l in _goi_y(leads, now, {u.lead.id for u in ung})],
    )
    return ket_qua
