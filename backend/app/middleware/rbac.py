"""RBAC helpers — role-based access control."""

from fastapi import HTTPException
from app.models.user import User
from app.models.lead import Lead

# 6 vai trò hệ thống — mọi role khác là vai trò tùy chỉnh (system_settings.custom_roles)
SYSTEM_ROLES = {"admin", "leader", "data_entry", "accountant", "executive", "supervisor"}

# Vai trò tùy chỉnh "Trưởng nhóm Kinh doanh" — seed idempotent trong seed.py nên
# role_key này là hằng số code-owned. Cùng bộ phận SALES nhưng KHÁC điều phối:
# trưởng nhóm bị giới hạn trong nhóm mình.
SALE_LEADER_ROLE = "sale_leader"


def is_team_lead(user: User) -> bool:
    """Trưởng nhóm KD — vai trò hệ thống `leader` hoặc vai trò tùy chỉnh `sale_leader`.

    Luồng data (14/08/2026): Admin CSKH chia data cho trưởng nhóm → trưởng nhóm
    chia cho sale trong nhóm. Trưởng nhóm CHỈ thấy & giao data trong nhóm mình.
    """
    return user.role in ("leader", SALE_LEADER_ROLE)


def is_sales_coordinator(user: User) -> bool:
    """Vai trò tùy chỉnh thuộc bộ phận Kinh doanh (vd: Admin CSKH) — TRỪ sale_leader.

    Đây là nhóm nhập lead từ marketing rồi phân chia cho trưởng nhóm/nhân viên KD,
    nên được đối xử như điều phối viên: thấy toàn bộ lead, đủ SĐT, được gắn/đổi
    người phụ trách bất kỳ (feedback team KD 12/08/2026). `sale_leader` cũng là
    vai trò tùy chỉnh + SALES nhưng là TRƯỞNG NHÓM — phạm vi nhóm, không phải điều phối.
    """
    return (
        user.role not in SYSTEM_ROLES
        and user.role != SALE_LEADER_ROLE
        and (user.department or "").upper() == "SALES"
    )


def can_assign_leads(user: User) -> bool:
    """Ai được phân chia data lead: admin, trưởng nhóm, hoặc điều phối KD (CSKH)."""
    return user.role == "admin" or is_team_lead(user) or is_sales_coordinator(user)


# ── Phạm vi xem DỰ ÁN theo bộ phận (05/09/2026) ─────────────────────────────
# Trước đây list_projects KHÔNG lọc gì: mọi tài khoản đăng nhập thấy toàn bộ
# 113 dự án. Nay soi gương luồng lead của Kinh doanh: nhân viên thấy dự án mình
# phụ trách, trưởng phòng thấy toàn bộ dự án của bộ phận mình.

# Cột PIC trên bảng projects ứng với từng bộ phận.
PIC_THEO_PHONG_BAN: dict[str, str] = {
    "OPS": "pm_id",              # Giám sát / PM
    "DESIGN": "designer_id",     # Thiết kế
    "SALES": "sales_id",         # Kinh doanh
    "PURCHASING": "purchasing_id",  # Dự toán – Thu mua
}

# Vai trò TRƯỞNG PHÒNG thật sự — chốt với chủ dự án 05/09 sau khi đối chiếu cơ
# cấu thật trên prod. Cố ý KHÔNG gồm `design_leader` (5 người) và `2d_leader`:
# theo sơ đồ trong JD Thiết kế họ là CHỦ TRÌ, không phải trưởng phòng.
VAI_TRO_TRUONG_PHONG: dict[str, set[str]] = {
    "DESIGN": {"leader"},
    "OPS": {"operation_leader"},
    "PURCHASING": {"dutoan_thumua_leader"},
    "SALES": {"leader", SALE_LEADER_ROLE},
}


def la_truong_phong(user: User) -> bool:
    """Trưởng phòng của CHÍNH bộ phận mình (vai trò `leader` ở phòng khác không tính)."""
    dept = (user.department or "").upper()
    return user.role in VAI_TRO_TRUONG_PHONG.get(dept, set())


def pham_vi_du_an(user: User) -> str:
    """'tat_ca' | 'phong_ban' | 'cua_toi' — dùng chung cho list và guard chi tiết."""
    # Kế toán giữ toàn quyền xem: cần đối chiếu công nợ/thanh toán/P&L mọi dự án
    # (chốt 05/09). Executive xem toàn bộ để nắm tình hình.
    if user.role in ("admin", "executive", "accountant"):
        return "tat_ca"
    if la_truong_phong(user):
        return "phong_ban"
    return "cua_toi"


def la_pic_du_an(user: User, project) -> bool:
    """Người này có phải PIC của dự án không (bất kể bộ phận nào)."""
    return user.id in {
        project.pm_id, project.designer_id, project.sales_id,
        getattr(project, "purchasing_id", None),
    }


def can_approve_quotation(user: User) -> bool:
    """Ai được DUYỆT báo giá — chốt với chủ dự án 29/08/2026: Giám đốc + Trưởng
    nhóm/phòng + Giám sát.

    Tách quyền SOẠN với quyền DUYỆT: sale vẫn tạo/sửa báo giá bình thường nhưng
    không tự duyệt bản của chính mình (trước QC 29/08 mọi tài khoản đăng nhập đều
    duyệt được — backend không kiểm, nút trên FE cũng không ẩn).
    """
    return user.role == "admin" or is_team_lead(user) or user.role == "supervisor"


def can_confirm_payment(user: User) -> bool:
    """Ai được đánh dấu ĐÃ THU TIỀN một đợt thanh toán hợp đồng — chốt 29/08/2026:
    Kế toán + Giám đốc + Trưởng nhóm/phòng.

    Ghi nhận tiền về là việc kế toán (tài liệu công ty: «Kế toán nhận thông báo HĐ
    mới → kiểm tra → tạo phiếu thu»); thêm trưởng nhóm để không tắc khi kế toán nghỉ.
    Sale vẫn XEM được trạng thái thanh toán, chỉ không tự tích.
    """
    return user.role in ("admin", "accountant") or is_team_lead(user)


def can_write_cskh_note(user: User) -> bool:
    """Ai được ghi lognote CSKH (đánh giá chất lượng chăm sóc của team KD).

    CHỈ điều phối KD (Admin CSKH) + admin — chốt 27/08/2026. Cố tình KHÔNG cho
    trưởng nhóm và sale: đây là đánh giá VỀ họ, tự viết được thì mất ý nghĩa
    kiểm soát. Ai xem được lead vẫn ĐỌC được ghi chú (minh bạch để sale tự sửa).
    """
    return user.role == "admin" or is_sales_coordinator(user)


def can_assign_lead_to(user: User, target: User) -> bool:
    """Được giao lead cho `target` không?

    Admin/điều phối KD: bất kỳ ai đang làm việc. Trưởng nhóm: chính mình hoặc
    người CÙNG nhóm — chưa được xếp nhóm thì chỉ giao được cho chính mình.
    """
    if not target.is_active:
        return False
    if user.role == "admin" or is_sales_coordinator(user):
        return True
    if is_team_lead(user):
        return target.id == user.id or (
            user.team_id is not None and target.team_id == user.team_id
        )
    return False


def can_touch_lead_assignment(user: User, lead: Lead) -> bool:
    """Được đổi phân công của lead này không?

    Admin/điều phối KD: mọi lead. Trưởng nhóm: chỉ lead đã thuộc nhóm mình
    (CSKH giao về nhóm trước, trưởng nhóm chia tiếp trong nhóm).
    """
    if user.role == "admin" or is_sales_coordinator(user):
        return True
    if is_team_lead(user):
        return user.team_id is not None and lead.team_id == user.team_id
    return False


def _team_lead_lead_scope(user: User, lead: Lead) -> bool:
    """Phạm vi lead của trưởng nhóm: lead nhóm mình HOẶC lead giao cho chính mình.

    Vế sau bắt buộc: trưởng nhóm chưa xếp đội (team_id NULL) vẫn được list cho
    thấy lead của mình — thiếu vế này thì thấy trong danh sách nhưng mở/sửa bị
    403 (review đối kháng 14/08 bắt được, đúng 2 sale_leader teamless trên prod).
    """
    return (
        user.team_id is not None and lead.team_id == user.team_id
    ) or lead.assigned_to == user.id


def can_view_lead(user: User, lead: Lead) -> bool:
    """Check if user can view this lead."""
    if user.role == "admin":
        return True
    if is_team_lead(user):
        return _team_lead_lead_scope(user, lead)
    if user.role == "executive":
        return True
    if is_sales_coordinator(user):
        return True
    return lead.assigned_to == user.id


def can_modify_lead(user: User, lead: Lead) -> bool:
    """Check if user can modify this lead."""
    if user.role == "admin":
        return True
    if is_team_lead(user):
        return _team_lead_lead_scope(user, lead)
    if is_sales_coordinator(user):
        return True
    return lead.assigned_to == user.id


def require_roles(*roles):
    """Factory for role checking."""
    def check(user: User):
        if user.role not in roles:
            raise HTTPException(
                status_code=403,
                detail=f"Cần quyền {', '.join(roles)} để thực hiện thao tác này",
            )
        return True
    return check
