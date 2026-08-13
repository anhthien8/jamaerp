"""Lõi quyền backend — làm cho ma trận trên trang Phân quyền có hiệu lực THẬT.

Trước 13/08/2026, ma trận phân quyền chỉ điều khiển giao diện (ẩn/hiện menu);
backend gác cửa bằng danh sách role viết cứng trong từng endpoint. Hệ quả: sếp
tắt quyền trên trang Phân quyền nhưng ai biết gọi API vẫn đọc được dữ liệu
(hoa hồng, chi phí, nhà cung cấp...). Module này là nguồn sự thật duy nhất
phía máy chủ:

- ``_ROLE_PERMISSION_DEFAULTS``: mặc định 6 vai trò hệ thống. CHÉP LÀM 3 BẢN —
  phải khớp từng ô với ``frontend/src/lib/roles.ts`` và ``permissions/page.tsx``;
  test ``test_ma_tran_phan_quyen_dong_bo.py`` sẽ đỏ nếu lệch.
- ``quyen_hieu_luc(user, db)``: quyền có hiệu lực của một người =
  mặc định vai trò (vai trò tùy chỉnh: nền data_entry + quyền lưu ở custom_roles)
  → đè override ``role_permissions_{role}`` (sếp sửa trên trang Phân quyền)
  → đè override cá nhân ``user.custom_permissions``.
  Riêng ``admin`` LUÔN full quyền, bỏ qua mọi override — không ai được phép
  tự khóa cửa căn phòng chứa chìa khóa (prod đang có admin dính override cũ).
- ``yeu_cau("canViewPnL")``: dependency FastAPI — thiếu quyền thì 403 kèm tên
  quyền tiếng Việt đúng như nhãn trên trang Phân quyền, để người bị chặn biết
  phải nhờ mở đúng ô nào.

Cấu hình (override + vai trò tùy chỉnh) đọc từ system_settings, cache 60 giây;
users.py gọi ``xoa_cache_quyen()`` ngay khi sếp lưu ma trận nên quyền mới có
hiệu lực tức thì, không phải chờ hết cache.
"""

import json
import time

from fastapi import Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.auth import get_current_user
from app.models.notification import SystemSetting
from app.models.user import User

# ── Ma trận mặc định 6 vai trò hệ thống (bản backend) ─────────────────────
# Keys = toàn bộ field trong RolePermissions (roles.ts)
_ROLE_PERMISSION_DEFAULTS: dict[str, dict] = {
    "admin": {
        "canViewDashboard": True, "dashboardType": "executive",
        "canViewLeads": True, "leadsScope": "all",
        "canViewAccounting": True, "canViewPayroll": True, "canViewCommissionOthers": True,
        "canViewHR": True, "canManageUsers": True,
        "canViewProjects": True, "canViewContracts": True, "canViewQuotations": True,
        "canCreateQuotations": True, "canViewInventory": True,
        "canViewReports": True, "canViewPnL": True,
        "canCreateProjects": True, "canCreateContracts": True,
        "canCreateTasks": True, "canEditTasks": True,
        "canViewAttendance": True, "canViewKPI": True,
        "canViewApprovals": True, "canViewFeedback": True, "canViewSettings": True,
    },
    "leader": {
        "canViewDashboard": True, "dashboardType": "team",
        "canViewLeads": True, "leadsScope": "team",
        "canViewAccounting": True, "canViewPayroll": False, "canViewCommissionOthers": False,
        "canViewHR": True, "canManageUsers": False,
        "canViewProjects": True, "canViewContracts": True, "canViewQuotations": True,
        "canCreateQuotations": True, "canViewInventory": False,
        "canViewReports": True, "canViewPnL": False,
        "canCreateProjects": True, "canCreateContracts": True,
        "canCreateTasks": True, "canEditTasks": True,
        "canViewAttendance": True, "canViewKPI": True,
        "canViewApprovals": True, "canViewFeedback": False, "canViewSettings": False,
    },
    "data_entry": {
        "canViewDashboard": True, "dashboardType": "personal",
        "canViewLeads": True, "leadsScope": "own",
        "canViewAccounting": True, "canViewPayroll": False, "canViewCommissionOthers": False,
        "canViewHR": False, "canManageUsers": False,
        "canViewProjects": True, "canViewContracts": True, "canViewQuotations": True,
        "canCreateQuotations": True, "canViewInventory": False,
        "canViewReports": True, "canViewPnL": False,
        "canCreateProjects": False, "canCreateContracts": True,
        "canCreateTasks": False, "canEditTasks": False,
        # canViewKPI bật 12/08/2026 (chủ dự án chốt) — phải khớp roles.ts, nếu lệch thì
        # trang Phân quyền hiện một đằng mà nhân viên trải nghiệm một nẻo.
        "canViewAttendance": True, "canViewKPI": True,
        "canViewApprovals": True, "canViewFeedback": False, "canViewSettings": False,
    },
    "accountant": {
        "canViewDashboard": True, "dashboardType": "financial",
        "canViewLeads": False, "leadsScope": "none",
        "canViewAccounting": True, "canViewPayroll": True, "canViewCommissionOthers": True,
        "canViewHR": True, "canManageUsers": True,
        # Kế toán XEM được Báo giá nhưng không tạo — bản này trước đây ghi False,
        # lệch với roles.ts (bản thật sự điều khiển giao diện). Sửa 12/08/2026.
        "canViewProjects": True, "canViewContracts": True, "canViewQuotations": True,
        "canCreateQuotations": False, "canViewInventory": True,
        "canViewReports": True, "canViewPnL": True,
        "canCreateProjects": False, "canCreateContracts": True,
        "canCreateTasks": False, "canEditTasks": False,
        "canViewAttendance": True, "canViewKPI": False,
        "canViewApprovals": True, "canViewFeedback": False, "canViewSettings": False,
    },
    "executive": {
        "canViewDashboard": True, "dashboardType": "executive",
        "canViewLeads": False, "leadsScope": "none",
        "canViewAccounting": False, "canViewPayroll": False, "canViewCommissionOthers": False,
        "canViewHR": False, "canManageUsers": False,
        "canViewProjects": True, "canViewContracts": True, "canViewQuotations": False,
        "canCreateQuotations": False, "canViewInventory": False,
        "canViewReports": True, "canViewPnL": True,
        "canCreateProjects": True, "canCreateContracts": False,
        "canCreateTasks": False, "canEditTasks": False,
        "canViewAttendance": False, "canViewKPI": True,
        "canViewApprovals": False, "canViewFeedback": True, "canViewSettings": True,
    },
    "supervisor": {
        "canViewDashboard": True, "dashboardType": "team",
        "canViewLeads": False, "leadsScope": "none",
        "canViewAccounting": False, "canViewPayroll": False, "canViewCommissionOthers": False,
        "canViewHR": False, "canManageUsers": False,
        "canViewProjects": True, "canViewContracts": True, "canViewQuotations": True,
        "canCreateQuotations": True, "canViewInventory": True,
        "canViewReports": True, "canViewPnL": False,
        "canCreateProjects": True, "canCreateContracts": True,
        "canCreateTasks": True, "canEditTasks": True,
        "canViewAttendance": True, "canViewKPI": True,
        "canViewApprovals": True, "canViewFeedback": False, "canViewSettings": False,
    },
}

# Nhãn tiếng Việt cho từng quyền — khớp ALL_PERMISSION_KEYS trong roles.ts
# để câu báo 403 gọi đúng tên ô mà sếp thấy trên trang Phân quyền.
NHAN_QUYEN: dict[str, str] = {
    "canViewDashboard": "Xem Dashboard",
    "canViewLeads": "Xem Leads",
    "canViewAccounting": "Xem Kế toán",
    "canViewPayroll": "Xem Lương",
    "canViewCommissionOthers": "Xem hoa hồng người khác",
    "canViewHR": "Xem Nhân sự",
    "canManageUsers": "Quản lý Users",
    "canViewProjects": "Xem Dự án",
    "canViewContracts": "Xem Hợp đồng",
    "canViewQuotations": "Xem Báo giá",
    "canCreateQuotations": "Tạo Báo giá",
    "canViewInventory": "Xem Kho",
    "canViewReports": "Xem Báo cáo",
    "canViewPnL": "Xem Lợi nhuận (P&L)",
    "canCreateProjects": "Tạo Dự án",
    "canCreateContracts": "Tạo Hợp đồng",
    "canCreateTasks": "Tạo Công việc",
    "canEditTasks": "Sửa Công việc",
    "canViewAttendance": "Xem Chấm công",
    "canViewKPI": "Xem KPI (kèm Bảng xếp hạng)",
    "canViewApprovals": "Xem Phê duyệt",
    "canViewFeedback": "Xem Góp ý (đọc + trả lời)",
    "canViewSettings": "Xem Cài đặt",
}

# ── Cache cấu hình (override + vai trò tùy chỉnh) ─────────────────────────
_CACHE_TTL_GIAY = 60
# (hạn dùng, override theo vai trò, danh sách vai trò tùy chỉnh)
_cau_hinh_cache: tuple[float, dict[str, dict], list[dict]] | None = None


def xoa_cache_quyen() -> None:
    """Gọi ngay khi lưu ma trận / vai trò tùy chỉnh để quyền mới ăn tức thì."""
    global _cau_hinh_cache
    _cau_hinh_cache = None


async def _tai_cau_hinh(db: AsyncSession) -> tuple[dict[str, dict], list[dict]]:
    """Đọc override role_permissions_* và custom_roles từ system_settings (cache 60s)."""
    global _cau_hinh_cache
    if _cau_hinh_cache is not None and _cau_hinh_cache[0] > time.time():
        return _cau_hinh_cache[1], _cau_hinh_cache[2]

    result = await db.execute(
        select(SystemSetting).where(SystemSetting.key.like("role_permissions_%"))
    )
    role_overrides: dict[str, dict] = {}
    for s in result.scalars().all():
        try:
            data = json.loads(s.value)
            if isinstance(data, dict):
                role_overrides[s.key.removeprefix("role_permissions_")] = data
        except (json.JSONDecodeError, TypeError):
            continue

    custom_roles: list[dict] = []
    setting = await db.get(SystemSetting, "custom_roles")
    if setting:
        try:
            data = json.loads(setting.value)
            if isinstance(data, list):
                custom_roles = data
        except (json.JSONDecodeError, TypeError):
            pass

    _cau_hinh_cache = (time.time() + _CACHE_TTL_GIAY, role_overrides, custom_roles)
    return role_overrides, custom_roles


async def quyen_hieu_luc(user: User, db: AsyncSession) -> dict:
    """Quyền có hiệu lực của một người — cùng công thức với getEffectivePermissions (FE)."""
    # Admin luôn full quyền: có admin trên prod đang dính override cá nhân cũ
    # (di tích lúc test giao diện) — enforce mù quáng là tự khóa mình khỏi
    # trang Phân quyền, không còn đường mở lại.
    if user.role == "admin":
        return dict(_ROLE_PERMISSION_DEFAULTS["admin"])

    role_overrides, custom_roles = await _tai_cau_hinh(db)

    vai_tro_tuy_chinh = next(
        (r for r in custom_roles if r.get("role_key") == user.role), None
    )
    if vai_tro_tuy_chinh is not None:
        # Vai trò tùy chỉnh: nền data_entry + quyền lưu trong định nghĩa role
        # (giống getPermissions trong roles.ts).
        perms = dict(_ROLE_PERMISSION_DEFAULTS["data_entry"])
        perms.update(vai_tro_tuy_chinh.get("permissions") or {})
    else:
        perms = dict(
            _ROLE_PERMISSION_DEFAULTS.get(user.role, _ROLE_PERMISSION_DEFAULTS["data_entry"])
        )
        ghi_de = role_overrides.get(user.role)
        if ghi_de:
            perms.update(ghi_de)

    # Override cá nhân (trang Nhân viên → Quyền riêng)
    if user.custom_permissions:
        try:
            rieng = json.loads(user.custom_permissions)
            if isinstance(rieng, dict):
                perms.update(rieng)
        except (json.JSONDecodeError, TypeError):
            pass

    return perms


def yeu_cau(quyen: str):
    """Dependency factory: chặn endpoint bằng một ô trong ma trận phân quyền.

    Dùng: ``current_user: User = Depends(yeu_cau("canViewPnL"))``.
    Thiếu quyền → 403 kèm đúng tên ô trên trang Phân quyền.
    """
    if quyen not in NHAN_QUYEN:
        raise ValueError(f"Quyền không tồn tại trong ma trận: {quyen}")

    async def _kiem_tra(
        current_user: User = Depends(get_current_user),
        db: AsyncSession = Depends(get_db),
    ) -> User:
        perms = await quyen_hieu_luc(current_user, db)
        if not perms.get(quyen):
            raise HTTPException(
                status_code=403,
                detail=(
                    f"Bạn chưa được cấp quyền «{NHAN_QUYEN[quyen]}». "
                    "Nếu công việc cần, nhờ quản trị viên mở quyền này trên trang Phân quyền."
                ),
            )
        return current_user

    return _kiem_tra
