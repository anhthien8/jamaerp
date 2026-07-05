"""RBAC helpers — role-based access control."""

from fastapi import HTTPException
from app.models.user import User
from app.models.lead import Lead


def can_view_lead(user: User, lead: Lead) -> bool:
    """Check if user can view this lead."""
    if user.role == "admin":
        return True
    if user.role == "leader":
        return lead.team_id == user.team_id
    if user.role == "executive":
        return True
    return lead.assigned_to == user.id


def can_modify_lead(user: User, lead: Lead) -> bool:
    """Check if user can modify this lead."""
    if user.role == "admin":
        return True
    if user.role == "leader":
        return lead.team_id == user.team_id
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
