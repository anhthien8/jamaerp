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
