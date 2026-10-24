"""Nhập danh sách nhân sự từ Excel của phòng HCNS (dựng 24/10/2026).

File mẫu công ty: 1 sheet, dòng tiêu đề nằm trong 5 dòng đầu (cột «HỌ VÀ TÊN»).
Không tạo tài khoản mới — chỉ khớp người đã có trong hệ thống theo họ tên (bỏ
dấu, không phân biệt hoa thường) rồi điền Hồ sơ 360°. Ai không khớp/khớp trùng
được liệt kê để admin sửa tên rồi nhập lại.

Quy tắc ghi: ô Excel CÓ giá trị mới ghi đè; ô trống giữ nguyên dữ liệu đang có
(nhập lại nhiều lần không làm mất gì). SĐT chỉ điền khi tài khoản chưa có SĐT.

Dữ liệu cá nhân CHỈ đi file → API → Postgres; không log giá trị, không lưu file.
"""

from __future__ import annotations

import io
import re
import unicodedata
from datetime import date, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.employee_profile import EmployeeProfile
from app.models.user import User

MAX_ROWS = 1000

# khóa nội bộ → các cụm (đã bỏ dấu) nhận diện tiêu đề cột; thứ tự quan trọng:
# cụm dài/đặc thù kiểm trước để «mức lương tham gia BHXH» không rơi vào «mã số BHXH».
COT = [
    ("insurance_salary", ("muc luong tham gia bhxh", "luong bhxh", "luong dong bhxh")),
    ("contract_salary", ("muc luong ky hdld", "luong hdld", "luong hop dong")),
    ("insurance_start_date", ("ngay dong bhxh", "thang dong bhxh")),
    ("social_insurance_no", ("ma so bhxh", "so so bhxh")),
    ("full_name", ("ho va ten", "ho ten")),
    ("department_text", ("phong ban", "bo phan")),
    ("title_text", ("chuc danh", "chuc vu")),
    ("date_of_birth", ("nam sinh", "ngay sinh")),
    ("national_id", ("cccd", "can cuoc")),
    ("address", ("dia chi",)),
    ("phone", ("so dien thoai", "sdt")),
    ("tax_code", ("ma so thue", "mst")),
    ("contract_signed_date", ("ngay ky hdld", "ngay ky hd")),
    ("contract_term", ("thoi han hdld", "thoi han hd")),
]

TEN_O = {
    "national_id": "CCCD", "date_of_birth": "Ngày sinh", "address": "Địa chỉ",
    "tax_code": "Mã số thuế", "social_insurance_no": "Mã số BHXH",
    "insurance_start_date": "Ngày đóng BHXH", "contract_signed_date": "Ngày ký HĐLĐ",
    "contract_type": "Loại HĐLĐ", "contract_end_date": "Ngày hết hạn HĐLĐ",
    "contract_salary": "Lương HĐ", "insurance_salary": "Lương đóng BHXH", "phone": "SĐT",
}


class LoiNhap(ValueError):
    pass


def bo_dau(s: str) -> str:
    s = unicodedata.normalize("NFD", str(s or ""))
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    s = s.replace("đ", "d").replace("Đ", "D").lower()
    return re.sub(r"\s+", " ", s).strip()


def _ngay(v) -> date | None:
    """dd/mm/yyyy, mm/yyyy (→ ngày 1), datetime Excel; nhiều ngày cách dấu phẩy
    (HĐ ký lại) → lấy ngày CUỐI."""
    if v is None or v == "":
        return None
    if isinstance(v, datetime):
        return v.date()
    if isinstance(v, date):
        return v
    parts = [p.strip() for p in re.split(r"[,;\n]+", str(v)) if p.strip()]
    for p in reversed(parts):
        m = re.fullmatch(r"(\d{1,2})[/.-](\d{1,2})[/.-](\d{4})", p)
        try:
            if m:
                return date(int(m[3]), int(m[2]), int(m[1]))
            m = re.fullmatch(r"(\d{1,2})[/.-](\d{4})", p)
            if m:
                return date(int(m[2]), int(m[1]), 1)
            m = re.fullmatch(r"(\d{4})-(\d{1,2})-(\d{1,2})", p)
            if m:
                return date(int(m[1]), int(m[2]), int(m[3]))
        except ValueError:
            continue
    return None


def _so(v) -> float | None:
    if v is None or v == "":
        return None
    if isinstance(v, (int, float)):
        return float(v) if v > 0 else None
    s = re.sub(r"[^\d]", "", str(v))
    return float(s) if s else None


def _chu(v, toi_da: int) -> str | None:
    if v is None:
        return None
    if isinstance(v, float) and v.is_integer():
        v = int(v)
    s = str(v).strip()
    return s[:toi_da] if s else None


def _loai_hd(v) -> str | None:
    t = bo_dau(v or "")
    if not t:
        return None
    if "thu viec" in t:
        return "probation"
    if "khong" in t and "thoi han" in t or "vo thoi han" in t:
        return "indefinite"
    if t.startswith("2") or "2 nam" in t:
        return "fixed_2y"
    if t.startswith("1") or "1 nam" in t or "12 thang" in t:
        return "fixed_1y"
    return None


def _cong_nam(d: date, nam: int) -> date:
    try:
        return d.replace(year=d.year + nam)
    except ValueError:  # 29/02
        return d.replace(year=d.year + nam, day=28)


def doc_file(noi_dung: bytes) -> list[dict]:
    """Đọc xlsx → list dòng {khóa: giá trị thô}. Raise LoiNhap nếu sai mẫu."""
    try:
        import openpyxl
        wb = openpyxl.load_workbook(io.BytesIO(noi_dung), read_only=True, data_only=True)
    except Exception as e:  # file hỏng / không phải xlsx
        raise LoiNhap("Không đọc được file — cần file Excel .xlsx") from e
    ws = wb.worksheets[0]
    rows = ws.iter_rows(values_only=True)

    vi_tri: dict[str, int] = {}
    for _ in range(5):
        hdr = next(rows, None)
        if hdr is None:
            break
        nhan = [bo_dau(h) if h is not None else "" for h in hdr]
        if any(n in ("ho va ten", "ho ten") for n in nhan):
            for i, n in enumerate(nhan):
                if not n:
                    continue
                for khoa, cum in COT:
                    if khoa not in vi_tri and any(c == n or c in n for c in cum):
                        vi_tri[khoa] = i
                        break
            break
    if "full_name" not in vi_tri:
        raise LoiNhap("Không thấy cột «HỌ VÀ TÊN» trong 5 dòng đầu — dùng đúng mẫu danh sách nhân sự")

    ket_qua = []
    for so_dong, row in enumerate(rows, start=1):
        if so_dong > MAX_ROWS:
            raise LoiNhap(f"File quá {MAX_ROWS} dòng")
        ten = row[vi_tri["full_name"]] if vi_tri["full_name"] < len(row) else None
        if not ten or not str(ten).strip():
            continue
        ket_qua.append({k: (row[i] if i < len(row) else None) for k, i in vi_tri.items()})
    wb.close()
    return ket_qua


def _gia_tri_ho_so(r: dict) -> dict:
    """Dòng thô → các ô sẽ ghi vào hồ sơ (bỏ ô trống)."""
    out = {
        "national_id": _chu(r.get("national_id"), 20),
        "date_of_birth": _ngay(r.get("date_of_birth")),
        "address": _chu(r.get("address"), 255),
        "tax_code": _chu(r.get("tax_code"), 20),
        "social_insurance_no": _chu(r.get("social_insurance_no"), 20),
        "insurance_start_date": _ngay(r.get("insurance_start_date")),
        "contract_signed_date": _ngay(r.get("contract_signed_date")),
        "contract_type": _loai_hd(r.get("contract_term")),
        "contract_salary": _so(r.get("contract_salary")),
        "insurance_salary": _so(r.get("insurance_salary")),
    }
    ky, loai = out["contract_signed_date"], out["contract_type"]
    if ky and loai in ("fixed_1y", "fixed_2y"):
        out["contract_end_date"] = _cong_nam(ky, 1 if loai == "fixed_1y" else 2) - timedelta(days=1)
    return {k: v for k, v in out.items() if v not in (None, "")}


async def nhap(db: AsyncSession, noi_dung: bytes, ap_dung: bool) -> dict:
    dong = doc_file(noi_dung)
    users = (await db.execute(select(User))).scalars().all()
    theo_ten: dict[str, list[User]] = {}
    for u in users:
        theo_ten.setdefault(bo_dau(u.full_name), []).append(u)

    khop, khong_khop, trung = [], [], []
    for r in dong:
        ten = str(r["full_name"]).strip()
        ung_vien = theo_ten.get(bo_dau(ten), [])
        if len(ung_vien) > 1:
            dang_lam = [u for u in ung_vien if u.is_active]
            ung_vien = dang_lam if len(dang_lam) == 1 else ung_vien
        if not ung_vien:
            khong_khop.append({"ten": ten, "phong_ban": _chu(r.get("department_text"), 60)})
            continue
        if len(ung_vien) > 1:
            trung.append({"ten": ten, "so_tai_khoan": len(ung_vien)})
            continue
        u = ung_vien[0]
        moi = _gia_tri_ho_so(r)
        profile = (await db.execute(
            select(EmployeeProfile).where(EmployeeProfile.user_id == u.id)
        )).scalar_one_or_none()
        doi = [k for k, v in moi.items() if getattr(profile, k, None) != v]
        sdt = _chu(r.get("phone"), 20)
        doi_sdt = bool(sdt and not u.phone)
        if doi_sdt:
            doi.append("phone")
        khop.append({
            "user_id": u.id, "ten": u.full_name, "phong_ban": u.department,
            "o_thay_doi": [TEN_O.get(k, k) for k in doi],
            "co_luong": "contract_salary" in moi,
        })
        if ap_dung and doi:
            if not profile:
                profile = EmployeeProfile(user_id=u.id)
                db.add(profile)
            for k, v in moi.items():
                setattr(profile, k, v)
            if doi_sdt:
                u.phone = sdt
    if ap_dung:
        await db.flush()

    return {
        "tong_dong": len(dong),
        "khop": khop,
        "khong_khop": khong_khop,
        "trung_ten": trung,
        "se_cap_nhat": sum(1 for k in khop if k["o_thay_doi"]),
        "da_ap_dung": ap_dung,
    }
