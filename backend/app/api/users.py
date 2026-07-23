"""Users API — admin CRUD for employees & teams."""

import json
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.auth import get_current_user, hash_password
from app.models.user import User, Team
from app.models.notification import SystemSetting
from app.schemas.user import UserCreate, UserUpdate, CustomRoleCreate, VALID_ROLES
from app.services.audit import log_action

router = APIRouter(prefix="/users", tags=["users"])


# ── Role permission defaults (mirrors frontend/src/lib/roles.ts) ───────────
# Keys = all fields in RolePermissions interface
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
        "canViewAttendance": True, "canViewKPI": False,
        "canViewApprovals": True, "canViewFeedback": False, "canViewSettings": False,
    },
    "accountant": {
        "canViewDashboard": True, "dashboardType": "financial",
        "canViewLeads": False, "leadsScope": "none",
        "canViewAccounting": True, "canViewPayroll": True, "canViewCommissionOthers": True,
        "canViewHR": True, "canManageUsers": True,
        "canViewProjects": True, "canViewContracts": True, "canViewQuotations": False,
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


def _get_combined_permissions(role: str, custom: dict | None) -> dict:
    """Merge role defaults with custom overrides. Custom overrides take precedence."""
    defaults = _ROLE_PERMISSION_DEFAULTS.get(role, _ROLE_PERMISSION_DEFAULTS["data_entry"])
    if not custom:
        return dict(defaults)
    merged = dict(defaults)
    merged.update(custom)
    return merged


@router.get("")
async def list_users(
    role: str | None = None,
    department: str | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
):
    """List all users."""
    # Only admin, accountant, leader can list users
    if current_user.role not in ("admin", "accountant", "leader"):
        raise HTTPException(status_code=403, detail="Không có quyền xem danh sách nhân viên")

    q = select(User).order_by(User.full_name)
    if role:
        q = q.where(User.role == role)
    if department:
        q = q.where(User.department == department)

    # Count total (before pagination)
    count_q = select(func.count()).select_from(q.subquery())
    total = (await db.execute(count_q)).scalar() or 0

    q = q.offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(q)
    users = result.scalars().all()

    return {
        "items": [
            {
                "id": u.id, "full_name": u.full_name, "email": u.email,
                "phone": u.phone, "role": u.role, "department": u.department,
                "team_id": u.team_id, "is_active": u.is_active,
                "salary_grade_id": u.salary_grade_id, "dependents_count": u.dependents_count,
                "custom_permissions": json.loads(u.custom_permissions) if u.custom_permissions else None,
                "created_at": str(u.created_at),
            }
            for u in users
        ],
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": (total + page_size - 1) // page_size,
    }


@router.get("/teams")
async def list_teams(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List all teams."""
    result = await db.execute(select(Team).order_by(Team.name))
    teams = result.scalars().all()
    return [
        {
            "id": t.id, "name": t.name, "code": t.code,
            "department": t.department, "leader_id": t.leader_id,
        }
        for t in teams
    ]


# ── Custom roles (stored in system_settings) ─────────────────────────────

async def _load_custom_roles(db: AsyncSession) -> list[dict]:
    """Load custom roles from system_settings (key=custom_roles)."""
    setting = await db.get(SystemSetting, "custom_roles")
    if not setting:
        return []
    try:
        roles = json.loads(setting.value)
        return roles if isinstance(roles, list) else []
    except (json.JSONDecodeError, TypeError):
        return []


@router.get("/roles/custom")
async def get_custom_roles(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return all custom roles from system_settings."""
    roles = await _load_custom_roles(db)
    return {"roles": roles}


@router.post("/roles")
async def create_custom_role(
    data: CustomRoleCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create a custom role. Only admin. Saved to system_settings."""
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Chỉ admin mới được tạo vai trò mới")

    key = data.role_key.strip().lower().replace(" ", "_")

    # Must not collide with built-in roles
    if key in VALID_ROLES:
        raise HTTPException(status_code=400, detail=f"Role key '{key}' trùng với vai trò hệ thống")

    existing = await _load_custom_roles(db)
    if any(r["role_key"] == key for r in existing):
        raise HTTPException(status_code=400, detail=f"Role '{key}' đã tồn tại")

    # Default: all 23 permissions = true (admin can toggle later)
    perms = data.permissions if data.permissions else {
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
    }

    new_role = {
        "role_key": key,
        "role_name": data.role_name.strip(),
        "department": data.department,
        "permissions": perms,
    }
    existing.append(new_role)

    setting = await db.get(SystemSetting, "custom_roles")
    value = json.dumps(existing, ensure_ascii=False)
    if setting:
        setting.value = value
        setting.updated_at = datetime.now(timezone.utc)
    else:
        db.add(SystemSetting(key="custom_roles", value=value))

    await db.flush()

    await log_action(
        db, actor=current_user, action="custom_role.create",
        entity_type="custom_role", entity_id=key,
        after={"role_name": data.role_name, "department": data.department},
    )

    return {"role": new_role, "message": "Đã tạo vai trò mới"}


# ── Role-level permissions (matrix admin) ────────────────────────────────

@router.get("/permissions/roles")
async def get_role_permissions(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return all roles with their current permissions (defaults + overrides).

    Only admin can manage role permissions.
    """
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Chỉ admin mới được xem phân quyền vai trò")

    result = await db.execute(
        select(SystemSetting).where(SystemSetting.key.like("role_permissions_%"))
    )
    stored = {s.key: s.value for s in result.scalars().all()}

    roles_data = {}
    for role in VALID_ROLES:
        defaults = _ROLE_PERMISSION_DEFAULTS.get(role, {})
        stored_key = f"role_permissions_{role}"
        overrides = None
        if stored_key in stored:
            try:
                overrides = json.loads(stored[stored_key])
            except (json.JSONDecodeError, TypeError):
                overrides = None

        # Merge: defaults + overrides (overrides take precedence)
        merged = dict(defaults)
        if overrides:
            merged.update(overrides)
        roles_data[role] = {
            "permissions": merged,
            "overrides": overrides,
        }

    return {"roles": roles_data}


@router.put("/permissions/roles/{role}")
async def set_role_permissions(
    role: str,
    data: dict,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Save role-level permission overrides.

    Body: { "permissions": { "canViewAccounting": true, "canViewLeads": false, ... } }
    An empty object {} resets to defaults.
    """
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Chỉ admin mới được thay đổi phân quyền vai trò")

    if role not in VALID_ROLES:
        raise HTTPException(status_code=400, detail="Vai trò không hợp lệ")

    perms = data.get("permissions", {})
    setting_key = f"role_permissions_{role}"

    setting = await db.get(SystemSetting, setting_key)
    if perms:
        value = json.dumps(perms, ensure_ascii=False)
        if setting:
            setting.value = value
            setting.updated_at = datetime.now(timezone.utc)
        else:
            db.add(SystemSetting(key=setting_key, value=value))
    else:
        # Empty: remove override (reset to defaults)
        if setting:
            await db.delete(setting)

    await db.flush()

    await log_action(
        db, actor=current_user, action="role_permissions.update",
        entity_type="role", entity_id=role,
        after={"permissions": perms or None},
    )

    return {"role": role, "permissions": perms or None, "message": "Đã cập nhật phân quyền vai trò"}


@router.get("/{user_id}")
async def get_user(
    user_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get user detail."""
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="Nhân viên không tồn tại")
    return {
        "id": user.id, "full_name": user.full_name, "email": user.email,
        "phone": user.phone, "role": user.role, "department": user.department,
        "team_id": user.team_id, "is_active": user.is_active,
        "telegram_username": user.telegram_username,
        "salary_grade_id": user.salary_grade_id, "dependents_count": user.dependents_count,
        "custom_permissions": json.loads(user.custom_permissions) if user.custom_permissions else None,
        "created_at": str(user.created_at),
    }


@router.post("")
async def create_user(
    data: UserCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create new user (admin only)."""
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Chỉ admin mới được tạo user")

    # Accept built-in or custom role keys
    custom_roles = await _load_custom_roles(db)
    custom_role_keys = {r["role_key"] for r in custom_roles}
    if data.role not in VALID_ROLES and data.role not in custom_role_keys:
        raise HTTPException(status_code=400, detail="Vai trò không hợp lệ")

    # Check email exists
    existing = await db.execute(select(User).where(User.email == data.email.lower()))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Email đã tồn tại")

    user = User(
        full_name=data.full_name.strip(),
        email=data.email.lower(),
        phone=data.phone,
        password_hash=hash_password(data.password),
        role=data.role,
        department=data.department,
        team_id=data.team_id,
        is_active=True,
    )
    db.add(user)
    await db.flush()
    await log_action(
        db, actor=current_user, action="user.create", entity_type="user", entity_id=user.id,
        after={"email": user.email, "role": user.role, "department": user.department},
    )
    return {
        "id": user.id, "full_name": user.full_name, "email": user.email,
        "role": user.role, "department": user.department,
    }


@router.put("/{user_id}")
async def update_user(
    user_id: str,
    data: UserUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update user."""
    # Admin/kế toán-nhân sự sửa được người khác; user thường chỉ sửa chính mình
    # (bản cũ chặn accountant dù UI /users hiện nút Sửa — audit 22/07)
    if current_user.role not in ("admin", "accountant") and current_user.id != user_id:
        raise HTTPException(status_code=403, detail="Không có quyền")

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="Nhân viên không tồn tại")

    # Use exclude_unset to detect which fields were explicitly provided
    provided = data.model_dump(exclude_unset=True)

    # Role escalation protection
    if "role" in provided and current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Chỉ Admin mới có quyền thay đổi vai trò")
    if "is_active" in provided and current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Chỉ Admin mới có quyền thay đổi trạng thái")
    if "role" in provided and data.role not in VALID_ROLES:
        custom_roles = await _load_custom_roles(db)
        custom_role_keys = {r["role_key"] for r in custom_roles}
        if data.role not in custom_role_keys:
            raise HTTPException(status_code=400, detail="Vai trò không hợp lệ")

    # Liên kết Telegram (tự phục vụ tại Cài đặt): chặn 1 Telegram ID gắn 2 tài khoản
    if "telegram_user_id" in provided and provided["telegram_user_id"] is not None:
        dup = await db.execute(
            select(User).where(
                User.telegram_user_id == provided["telegram_user_id"],
                User.id != user.id,
            )
        )
        if dup.scalar_one_or_none():
            raise HTTPException(
                status_code=400,
                detail="Telegram ID này đã được liên kết với tài khoản khác — liên hệ Admin nếu cần chuyển",
            )

    # Trường lương: chỉ admin/kế toán (tự sửa hồ sơ mình cũng không được đổi bậc lương)
    if ("salary_grade_id" in provided or "dependents_count" in provided) and current_user.role not in ("admin", "accountant"):
        raise HTTPException(status_code=403, detail="Chỉ admin/kế toán mới được gán bậc lương")

    allowed = ["full_name", "phone", "role", "department", "team_id", "is_active", "telegram_user_id", "telegram_username", "salary_grade_id", "dependents_count"]
    before_sensitive = {
        "role": user.role, "is_active": user.is_active, "team_id": user.team_id,
        "telegram_user_id": user.telegram_user_id,
    }
    for k in allowed:
        if k in provided:
            setattr(user, k, provided[k])
    if "password" in provided and data.password:
        user.password_hash = hash_password(data.password)
    user.updated_at = datetime.now(timezone.utc)
    await db.flush()

    # Audit các thay đổi nhạy cảm (quyền, trạng thái, đội)
    changed_sensitive = {
        k: v for k, v in before_sensitive.items()
        if k in provided and provided[k] != v
    }
    if changed_sensitive or ("password" in provided and data.password):
        after = {k: getattr(user, k) for k in changed_sensitive}
        if "password" in provided and data.password:
            after["password"] = "***changed***"
        await log_action(
            db, actor=current_user, action="user.update", entity_type="user", entity_id=user.id,
            before=changed_sensitive or None, after=after,
        )

    return {
        "id": user.id, "full_name": user.full_name, "email": user.email,
        "role": user.role, "department": user.department, "is_active": user.is_active,
    }


# ── Per-user permission overrides ─────────────────────────────────────────

@router.get("/{user_id}/permissions")
async def get_user_permissions(
    user_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return combined permissions for a user (role defaults + custom overrides).

    Only admin and accountant can view permissions for other users.
    Any user can view their own.
    """
    if current_user.role not in ("admin", "accountant") and current_user.id != user_id:
        raise HTTPException(status_code=403, detail="Không có quyền xem phân quyền")

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="Nhân viên không tồn tại")

    custom = None
    if user.custom_permissions:
        try:
            custom = json.loads(user.custom_permissions)
        except (json.JSONDecodeError, TypeError):
            custom = None

    combined = _get_combined_permissions(user.role, custom)

    return {
        "user_id": user.id,
        "role": user.role,
        "custom_permissions": custom,
        "combined_permissions": combined,
    }


@router.put("/{user_id}/permissions")
async def set_user_permissions(
    user_id: str,
    data: dict,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Save per-user permission overrides. Only admin can manage permissions.

    Body: { "permissions": { "canViewAccounting": true, "canViewLeads": false, ... } }
    An empty object {} resets to role defaults.
    """
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Chỉ admin mới được thay đổi phân quyền")

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="Nhân viên không tồn tại")

    perms = data.get("permissions", {})

    if perms:
        # Store the full permissions map as the custom override
        user.custom_permissions = json.dumps(perms, ensure_ascii=False)
    else:
        user.custom_permissions = None

    user.updated_at = datetime.now(timezone.utc)
    await db.flush()

    await log_action(
        db, actor=current_user, action="user.permissions.update",
        entity_type="user", entity_id=user.id,
        after={"custom_permissions": user.custom_permissions},
    )

    return {
        "user_id": user.id,
        "custom_permissions": perms or None,
        "message": "Đã cập nhật phân quyền",
    }
