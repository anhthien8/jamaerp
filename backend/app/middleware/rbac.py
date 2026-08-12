"""RBAC helpers — role-based access control."""

from fastapi import HTTPException
from app.models.user import User
from app.models.lead import Lead

# 6 vai trò hệ thống — mọi role khác là vai trò tùy chỉnh (system_settings.custom_roles)
SYSTEM_ROLES = {"admin", "leader", "data_entry", "accountant", "executive", "supervisor"}


def is_sales_coordinator(user: User) -> bool:
    """Vai trò tùy chỉnh thuộc bộ phận Kinh doanh (vd: Admin CSKH).

    Đây là nhóm nhập lead từ marketing rồi phân chia cho nhân viên KD,
    nên được đối xử như điều phối viên: thấy toàn bộ lead, đủ SĐT,
    được gắn/đổi người phụ trách (feedback team KD 12/08/2026).
    """
    return user.role not in SYSTEM_ROLES and (user.department or "").upper() == "SALES"


def can_assign_leads(user: User) -> bool:
    """Ai được phân chia data lead: admin, leader, hoặc điều phối KD (CSKH)."""
    return user.role in ("admin", "leader") or is_sales_coordinator(user)


def can_view_lead(user: User, lead: Lead) -> bool:
    """Check if user can view this lead."""
    if user.role == "admin":
        return True
    if user.role == "leader":
        return lead.team_id == user.team_id
    if user.role == "executive":
        return True
    if is_sales_coordinator(user):
        return True
    return lead.assigned_to == user.id


def can_modify_lead(user: User, lead: Lead) -> bool:
    """Check if user can modify this lead."""
    if user.role == "admin":
        return True
    if user.role == "leader":
        return lead.team_id == user.team_id
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
