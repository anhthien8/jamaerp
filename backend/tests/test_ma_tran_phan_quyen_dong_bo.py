"""Ma trận Phân quyền không được lệch giữa backend và frontend.

Ma trận đang bị CHÉP LÀM 3 BẢN:
  1. `frontend/src/lib/roles.ts`            → quyết định người dùng thật thấy gì
  2. `frontend/src/app/permissions/page.tsx` → bảng hiển thị ở trang Phân quyền
  3. `backend/app/api/users.py`              → trả về qua GET /users/permissions/roles

Lệch một bản là ra đúng loại lỗi đã gặp ngày 12/08/2026: trang Phân quyền nói vai trò
CÓ quyền, còn nhân viên bấm vào thì bị đá về Tổng quan (hoặc ngược lại). Test này so
bản backend với bản `roles.ts` — bản duy nhất thật sự điều khiển giao diện.

Nếu định dạng `roles.ts` đổi làm test không đọc được: sửa parser bên dưới, ĐỪNG xoá test.
"""

import re
from pathlib import Path

import pytest

from app.api.users import _ROLE_PERMISSION_DEFAULTS

_FE = Path(__file__).resolve().parents[2] / "frontend" / "src"
_ROLES_TS = _FE / "lib" / "roles.ts"
_TRANG_PHAN_QUYEN = _FE / "app" / "permissions" / "page.tsx"

# Khoá không phải boolean (chuỗi) — so riêng, không nằm trong phép so bool
_KHOA_CHUOI = {"dashboardType", "leadsScope"}


def _doc_ma_tran_frontend() -> dict[str, dict[str, bool]]:
    """Bóc ROLE_PERMISSIONS trong roles.ts thành dict {vai_tro: {khoa: bool}}."""
    src = _ROLES_TS.read_text(encoding="utf-8")
    start = src.index("export const ROLE_PERMISSIONS")
    # Kết thúc ở dòng "};" đầu tiên nằm sát lề trái sau khi bắt đầu
    end = src.index("\n};", start)
    than = src[start:end]

    ma_tran: dict[str, dict[str, bool]] = {}
    for m in re.finditer(r"^  (\w+): \{\n(.*?)^  \},", than, re.S | re.M):
        vai_tro, noi_dung = m.group(1), m.group(2)
        ma_tran[vai_tro] = {
            k: v == "true" for k, v in re.findall(r"(\w+):\s*(true|false)\b", noi_dung)
        }
    return ma_tran


def _doc_ma_tran_trang_phan_quyen() -> dict[str, dict[str, bool]]:
    """Bóc DEFAULTS trong permissions/page.tsx — bảng nền của trang Phân quyền."""
    src = _TRANG_PHAN_QUYEN.read_text(encoding="utf-8")
    start = src.index("const DEFAULTS")
    end = src.index("\n};", start)
    than = src[start:end]

    ma_tran: dict[str, dict[str, bool]] = {}
    for dong in than.splitlines()[1:]:
        m = re.match(r"\s*(\w+): \{(.*)\},\s*$", dong)
        if not m:
            continue
        ma_tran[m.group(1)] = {
            k: v == "true" for k, v in re.findall(r"(\w+):\s*(true|false)\b", m.group(2))
        }
    return ma_tran


def test_doc_duoc_roles_ts():
    """Chốt chặn cho chính parser — đọc hụt thì các test dưới sẽ 'xanh giả'."""
    if not _ROLES_TS.exists():
        pytest.skip(f"Không có {_ROLES_TS} (chạy ngoài repo đầy đủ)")

    ma_tran = _doc_ma_tran_frontend()
    thieu = set(_ROLE_PERMISSION_DEFAULTS) - set(ma_tran)
    assert not thieu, (
        f"Parser không đọc được vai trò {sorted(thieu)} trong roles.ts. "
        "Định dạng file đã đổi — sửa parser trong test này, đừng xoá test."
    )
    # Mỗi vai trò phải có ít nhất chục khoá boolean, không thì là bóc trượt
    for vai_tro, quyen in ma_tran.items():
        assert len(quyen) >= 10, f"Bóc trượt quyền của {vai_tro}: chỉ ra {len(quyen)} khoá"


def test_backend_khop_frontend():
    if not _ROLES_TS.exists():
        pytest.skip(f"Không có {_ROLES_TS} (chạy ngoài repo đầy đủ)")

    fe = _doc_ma_tran_frontend()
    lech: list[str] = []
    for vai_tro, quyen_be in _ROLE_PERMISSION_DEFAULTS.items():
        quyen_fe = fe.get(vai_tro, {})
        for khoa, gia_tri_be in quyen_be.items():
            if khoa in _KHOA_CHUOI or khoa not in quyen_fe:
                continue
            if quyen_fe[khoa] != gia_tri_be:
                lech.append(
                    f"{vai_tro}.{khoa}: backend={gia_tri_be} nhưng roles.ts={quyen_fe[khoa]}"
                )

    assert not lech, "Ma trận Phân quyền lệch giữa 2 phía:\n  " + "\n  ".join(lech)


def test_trang_phan_quyen_khop_roles_ts():
    """Bản thứ 3 (bảng hiển thị) phải khớp bản thật — nếu không, admin bật/tắt theo
    một bảng sai và tưởng mình đã sửa đúng."""
    if not _ROLES_TS.exists() or not _TRANG_PHAN_QUYEN.exists():
        pytest.skip("Chạy ngoài repo đầy đủ")

    fe = _doc_ma_tran_frontend()
    trang = _doc_ma_tran_trang_phan_quyen()
    assert set(trang) == set(fe), (
        f"Trang Phân quyền liệt kê vai trò {sorted(set(trang) ^ set(fe))} lệch với roles.ts"
    )

    lech: list[str] = []
    for vai_tro, quyen_trang in trang.items():
        quyen_fe = fe[vai_tro]
        for khoa, gia_tri in quyen_trang.items():
            if khoa in _KHOA_CHUOI or khoa not in quyen_fe:
                continue
            if quyen_fe[khoa] != gia_tri:
                lech.append(
                    f"{vai_tro}.{khoa}: trang Phân quyền={gia_tri} nhưng roles.ts={quyen_fe[khoa]}"
                )

    assert not lech, "Bảng trang Phân quyền lệch với roles.ts:\n  " + "\n  ".join(lech)


def test_sale_xem_duoc_kpi():
    """Chốt quyết định 12/08/2026 — sale mở được trang KPI (kèm Bảng xếp hạng).

    Trước đó `/kpi` được ghim vào menu chính của sale mà quyền lại tắt ⇒ link chết.
    """
    assert _ROLE_PERMISSION_DEFAULTS["data_entry"]["canViewKPI"] is True
