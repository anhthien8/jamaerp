"""Users API — admin CRUD for employees & teams."""

import json
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func, update as sa_update
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.auth import get_current_user, hash_password
# _ROLE_PERMISSION_DEFAULTS đã dời sang middleware/permissions.py (lõi quyền backend).
# Import lại tại đây để test đồng bộ 3 bản ma trận (test_ma_tran_phan_quyen_dong_bo.py)
# vẫn `from app.api.users import _ROLE_PERMISSION_DEFAULTS` được như cũ.
from app.middleware.permissions import (  # noqa: F401 — re-export có chủ đích
    _ROLE_PERMISSION_DEFAULTS,
    quyen_hieu_luc,
    xoa_cache_quyen,
)
from app.middleware.rbac import can_assign_leads, is_sales_coordinator, is_team_lead
from app.models.user import User, Team
from app.models.lead import Lead
from app.models.notification import SystemSetting
from app.schemas.user import (
    UserCreate, UserUpdate, CustomRoleCreate, TeamCreate, TeamUpdate,
    TeamMembersUpdate, VALID_ROLES,
)
from app.services.audit import log_action

router = APIRouter(prefix="/users", tags=["users"])


async def _dong_bo_nhan_doi_cua_lead(
    db: AsyncSession, user_ids: list[str] | set[str], team_id: str | None
) -> int:
    """Gắn lại nhãn đội cho lead theo đội MỚI của người phụ trách.

    `Lead.team_id` là bản sao đội của người đang phụ trách (assign_lead đặt
    `lead.team_id = target_user.team_id`), mà phạm vi của trưởng nhóm lại đọc
    đúng cột này. Đổi đội của người mà không gắn lại lead thì nhãn trôi:
      - Sale nhận lead lúc chưa có đội → lead mang team_id NULL. Xếp vào đội sau
        thì trưởng nhóm KHÔNG BAO GIỜ thấy số lead đó (lỗi user báo 27/08).
      - Sale chuyển sang đội khác → lead cũ vẫn đeo nhãn đội cũ, trưởng nhóm đội
        cũ còn thấy data của người đã rời đi.
    Trả về số lead đã gắn lại.
    """
    ids = [u for u in user_ids if u]
    if not ids:
        return 0
    res = await db.execute(
        sa_update(Lead).where(Lead.assigned_to.in_(ids)).values(team_id=team_id)
    )
    return res.rowcount or 0


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
    page_size: int = Query(50, ge=1, le=500),
):
    """List users — gate theo ma trận phân quyền, không hardcode role.

    Cần «Xem Nhân sự» (canViewHR) hoặc «Quản lý Users» (canManageUsers) trong
    ma trận hiệu lực. Trưởng nhóm (leader/sale_leader) chỉ thấy nhân sự nhóm
    mình + chính mình — luồng data 14/08/2026.
    """
    perms = await quyen_hieu_luc(current_user, db)
    if not (perms.get("canViewHR") or perms.get("canManageUsers")):
        raise HTTPException(status_code=403, detail="Không có quyền xem danh sách nhân viên")

    q = select(User).order_by(User.full_name)
    if current_user.role != "admin" and is_team_lead(current_user):
        if current_user.team_id is None:
            q = q.where(User.id == current_user.id)
        else:
            q = q.where((User.team_id == current_user.team_id) | (User.id == current_user.id))
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
                "resign_date": str(u.resign_date) if u.resign_date else None,
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


@router.get("/assignable")
async def list_assignable_users(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Danh sách người nhận data lead — cho dropdown «Giao data».

    Mở cho ai được phân chia data (admin/trưởng nhóm/điều phối KD), KHÔNG cần
    quyền Nhân sự: chỉ trả tên/vai trò/nhóm, không có SĐT hay lương.
    Phạm vi tự cắt ở backend: admin & điều phối KD thấy toàn bộ nhân sự KD +
    trưởng nhóm; trưởng nhóm chỉ thấy người nhóm mình + chính mình.
    """
    if not can_assign_leads(current_user):
        raise HTTPException(status_code=403, detail="Chỉ admin/trưởng nhóm/điều phối KD được xem danh sách phân công")

    q = select(User).where(User.is_active == True).order_by(User.full_name)  # noqa: E712
    if current_user.role == "admin" or is_sales_coordinator(current_user):
        q = q.where((User.department == "SALES") | (User.role.in_(("data_entry", "leader"))))
    else:  # trưởng nhóm (leader/sale_leader)
        if current_user.team_id is None:
            q = q.where(User.id == current_user.id)
        else:
            q = q.where((User.team_id == current_user.team_id) | (User.id == current_user.id))

    users = (await db.execute(q)).scalars().all()
    return [
        {
            "id": u.id, "full_name": u.full_name, "role": u.role,
            "department": u.department, "team_id": u.team_id, "is_active": u.is_active,
        }
        for u in users
    ]


@router.get("/task-assignable")
async def list_task_assignable_users(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Danh sách người nhận việc dự án — cho dropdown «Đảm nhận» trang Dự án.

    Trang Dự án từng dùng GET /users nên dính hai phạm vi sai ngữ cảnh: trưởng
    nhóm KD bị cắt về «nhóm mình + chính mình» (không ai thuộc Thiết kế/Thi công/
    Thu mua → dropdown rỗng), còn vai trò tùy chỉnh không có canViewHR
    (quan_ly_du_an/thiet_ke/giam_sat_thi_cong) dính thẳng 403. Việc dự án vốn
    giao CHÉO phòng ban nên endpoint này gate theo «Xem Dự án»/«Tạo Công việc»
    và trả đủ nhân sự đang làm việc — nhưng CHỈ danh tính tối thiểu
    (tên/vai trò/bộ phận), không SĐT, không bậc lương. Scope GET /users giữ nguyên
    cho ngữ cảnh Nhân sự.
    """
    perms = await quyen_hieu_luc(current_user, db)
    if not (perms.get("canViewProjects") or perms.get("canCreateTasks")):
        raise HTTPException(status_code=403, detail="Không có quyền xem danh sách phân công dự án")

    q = select(User).where(User.is_active == True).order_by(User.full_name)  # noqa: E712
    users = (await db.execute(q)).scalars().all()
    return [
        {
            "id": u.id, "full_name": u.full_name, "role": u.role,
            "department": u.department, "is_active": u.is_active,
        }
        for u in users
    ]


@router.get("/teams")
async def list_teams(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List all teams — kèm tên trưởng nhóm + sĩ số để UI vẽ thẳng, khỏi join tay."""
    result = await db.execute(select(Team).order_by(Team.name))
    teams = result.scalars().all()

    counts: dict[str, int] = dict(
        (await db.execute(
            select(User.team_id, func.count())
            .where(User.team_id.isnot(None), User.is_active == True)  # noqa: E712
            .group_by(User.team_id)
        )).all()
    )
    leader_ids = [t.leader_id for t in teams if t.leader_id]
    leader_names: dict[str, str] = {}
    if leader_ids:
        leader_names = {
            u.id: u.full_name
            for u in (await db.execute(select(User).where(User.id.in_(leader_ids)))).scalars().all()
        }

    return [
        {
            "id": t.id, "name": t.name, "code": t.code,
            "department": t.department, "leader_id": t.leader_id,
            "leader_name": leader_names.get(t.leader_id) if t.leader_id else None,
            "member_count": counts.get(t.id, 0),
        }
        for t in teams
    ]


@router.post("/teams")
async def create_team(
    data: TeamCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Tạo đội mới — cần «Quản lý Users» trong ma trận hiệu lực.

    Nếu chỉ định trưởng nhóm (leader_id) thì người đó được tự động chuyển
    team_id về đội này để phạm vi nhóm có hiệu lực ngay.
    """
    perms = await quyen_hieu_luc(current_user, db)
    if not perms.get("canManageUsers"):
        raise HTTPException(status_code=403, detail="Không có quyền quản lý đội nhóm")

    code = data.code.strip().upper()
    existing = await db.execute(select(Team).where(Team.code == code))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail=f"Mã đội '{code}' đã tồn tại")

    leader = None
    if data.leader_id:
        leader = await db.get(User, data.leader_id)
        if not leader or not leader.is_active:
            raise HTTPException(status_code=404, detail="Trưởng nhóm được chỉ định không tồn tại hoặc đã nghỉ")
        # Không lấy trưởng nhóm đội khác — đội bên kia sẽ mồ côi leader (review 14/08)
        other = (await db.execute(select(Team).where(Team.leader_id == leader.id))).scalars().first()
        if other:
            raise HTTPException(status_code=400, detail=f"{leader.full_name} đang làm trưởng nhóm đội {other.name} — đổi trưởng nhóm đội đó trước")
        # Tự lập đội lấy mình làm trưởng nhóm = tự chuyển đội — đường vòng qua guard
        # của update_team/set_team_members, chặn nốt (phản biện vá 14/08)
        if leader.id == current_user.id and current_user.role not in ("admin", "accountant"):
            raise HTTPException(status_code=403, detail="Chỉ admin/kế toán mới được chuyển nhóm nhân sự")

    team = Team(
        name=data.name.strip(), code=code,
        department=(data.department or "SALES").strip().upper(),
        leader_id=data.leader_id,
    )
    db.add(team)
    await db.flush()
    if leader:
        leader.team_id = team.id
        await _dong_bo_nhan_doi_cua_lead(db, [leader.id], team.id)
    await db.flush()

    await log_action(
        db, actor=current_user, action="team.create", entity_type="team",
        entity_id=team.id, note=f"Tạo đội {team.name} ({team.code})",
    )
    return {
        "id": team.id, "name": team.name, "code": team.code,
        "department": team.department, "leader_id": team.leader_id,
    }


@router.put("/teams/{team_id}")
async def update_team(
    team_id: str,
    data: TeamUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Sửa đội (tên/bộ phận/trưởng nhóm) — cần «Quản lý Users».

    Đổi trưởng nhóm thì người mới được tự động chuyển team_id về đội này.
    """
    perms = await quyen_hieu_luc(current_user, db)
    if not perms.get("canManageUsers"):
        raise HTTPException(status_code=403, detail="Không có quyền quản lý đội nhóm")

    team = await db.get(Team, team_id)
    if not team:
        raise HTTPException(status_code=404, detail="Đội không tồn tại")

    provided = data.model_dump(exclude_unset=True)
    if "name" in provided and provided["name"]:
        team.name = provided["name"].strip()
    if "department" in provided and provided["department"]:
        team.department = provided["department"].strip().upper()
    if "leader_id" in provided:
        if provided["leader_id"] == team.leader_id:
            pass  # giữ nguyên trưởng nhóm (kể cả đã nghỉ) — vẫn cho sửa tên/bộ phận đội
        elif provided["leader_id"]:
            leader = await db.get(User, provided["leader_id"])
            if not leader or not leader.is_active:
                raise HTTPException(status_code=404, detail="Trưởng nhóm được chỉ định không tồn tại hoặc đã nghỉ")
            # Không lấy trưởng nhóm đội khác — đội bên kia sẽ mồ côi leader (review 14/08)
            other = (await db.execute(
                select(Team).where(Team.leader_id == leader.id, Team.id != team.id)
            )).scalars().first()
            if other:
                raise HTTPException(status_code=400, detail=f"{leader.full_name} đang làm trưởng nhóm đội {other.name} — đổi trưởng nhóm đội đó trước")
            # Gán mình làm trưởng nhóm = tự chuyển đội, tự mở rộng phạm vi lead — chặn như update_user
            if (
                leader.id == current_user.id
                and current_user.role not in ("admin", "accountant")
                and current_user.team_id != team.id
            ):
                raise HTTPException(status_code=403, detail="Chỉ admin/kế toán mới được chuyển nhóm nhân sự")
            team.leader_id = leader.id
            leader.team_id = team.id
            await _dong_bo_nhan_doi_cua_lead(db, [leader.id], team.id)
        else:
            team.leader_id = None
    await db.flush()

    await log_action(
        db, actor=current_user, action="team.update", entity_type="team",
        entity_id=team.id, note=f"Cập nhật đội {team.name} ({team.code})",
    )
    return {
        "id": team.id, "name": team.name, "code": team.code,
        "department": team.department, "leader_id": team.leader_id,
    }


@router.put("/teams/{team_id}/members")
async def set_team_members(
    team_id: str,
    data: TeamMembersUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Xếp thành viên cho đội — nhận danh sách ĐẦY ĐỦ user_ids sau khi lưu.

    Cần «Quản lý Users». Trưởng nhóm của đội luôn được giữ lại (muốn gỡ thì đổi
    trưởng nhóm trước). Người đang làm trưởng nhóm đội KHÁC không kéo về được —
    tránh đội bên kia mồ côi leader đứng ngoài đội.
    """
    perms = await quyen_hieu_luc(current_user, db)
    if not perms.get("canManageUsers"):
        raise HTTPException(status_code=403, detail="Không có quyền quản lý đội nhóm")

    team = await db.get(Team, team_id)
    if not team:
        raise HTTPException(status_code=404, detail="Đội không tồn tại")

    # Tự thêm mình vào đội khác = tự mở rộng phạm vi lead — chặn như update_user (review 14/08)
    if (
        current_user.id in data.user_ids
        and current_user.role not in ("admin", "accountant")
        and current_user.team_id != team.id
    ):
        raise HTTPException(status_code=403, detail="Chỉ admin/kế toán mới được chuyển nhóm nhân sự")

    wanted = set(data.user_ids)
    if team.leader_id:
        # Chỉ auto-giữ trưởng nhóm còn làm việc — leader đã nghỉ mà auto-add sẽ
        # dính chốt chặn «người nghỉ việc» ở dưới, khoá cứng cả đội (review 14/08)
        leader_row = await db.get(User, team.leader_id)
        if leader_row and leader_row.is_active:
            wanted.add(team.leader_id)
        else:
            wanted.discard(team.leader_id)

    found: dict[str, User] = {}
    if wanted:
        rows = (await db.execute(select(User).where(User.id.in_(wanted)))).scalars().all()
        found = {u.id: u for u in rows}
        missing = wanted - set(found)
        if missing:
            raise HTTPException(status_code=400, detail=f"{len(missing)} nhân sự trong danh sách không tồn tại — tải lại trang rồi thử lại")
        inactive = [u.full_name for u in found.values() if not u.is_active]
        if inactive:
            raise HTTPException(status_code=400, detail=f"Không xếp người đã nghỉ việc vào đội: {', '.join(inactive)}")

        other_teams = (await db.execute(
            select(Team).where(Team.leader_id.in_(wanted), Team.id != team.id)
        )).scalars().all()
        if other_teams:
            details = ", ".join(f"{found[t.leader_id].full_name} (trưởng nhóm {t.name})" for t in other_teams)
            raise HTTPException(status_code=400, detail=f"Đang làm trưởng nhóm đội khác — đổi trưởng nhóm đội đó trước: {details}")

    current_members = (await db.execute(select(User).where(User.team_id == team.id))).scalars().all()
    # Người đã nghỉ GIỮ NGUYÊN nhãn đội: không có checkbox trên FE, gỡ im lặng sẽ làm
    # leader nghỉ quay lại bị mất đội (drift với teams.leader_id) và thành viên nghỉ
    # mất nhãn chỉ vì admin đổi tên đội (phản biện vá 14/08)
    removed = [u for u in current_members if u.id not in wanted and u.is_active]
    added = [u for u in found.values() if u.team_id != team.id]
    for u in removed:
        u.team_id = None
    for u in found.values():
        u.team_id = team.id
    # Lead đi theo người: vào đội thì data cũ của họ mang nhãn đội mới, rời đội thì
    # nhãn bị gỡ. Không có bước này thì trưởng nhóm không thấy data của quân mình.
    await _dong_bo_nhan_doi_cua_lead(db, [u.id for u in removed], None)
    await _dong_bo_nhan_doi_cua_lead(db, [u.id for u in found.values()], team.id)
    await db.flush()

    await log_action(
        db, actor=current_user, action="team.set_members", entity_type="team", entity_id=team.id,
        before={"member_count": len(current_members)},
        after={
            "member_count": len(wanted),
            "added": [u.full_name for u in added],
            "removed": [u.full_name for u in removed],
        },
        note=f"Xếp thành viên đội {team.name} ({team.code})",
    )
    return {"team_id": team.id, "member_count": len(wanted), "added": len(added), "removed": len(removed)}


@router.delete("/teams/{team_id}")
async def delete_team(
    team_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Giải tán đội — cần «Quản lý Users», FE bắt buộc confirm trước khi gọi.

    Thành viên (kể cả trưởng nhóm) về «chưa xếp đội»; data lead đang gắn đội chỉ
    mất nhãn đội (người phụ trách + toàn bộ lịch sử chăm sóc giữ nguyên).
    """
    perms = await quyen_hieu_luc(current_user, db)
    if not perms.get("canManageUsers"):
        raise HTTPException(status_code=403, detail="Không có quyền quản lý đội nhóm")

    team = await db.get(Team, team_id)
    if not team:
        raise HTTPException(status_code=404, detail="Đội không tồn tại")

    members = (await db.execute(select(User).where(User.team_id == team.id))).scalars().all()
    lead_count = (await db.execute(
        select(func.count()).select_from(Lead).where(Lead.team_id == team.id)
    )).scalar() or 0

    team_name, team_code = team.name, team.code
    for m in members:
        m.team_id = None
    await db.execute(sa_update(Lead).where(Lead.team_id == team.id).values(team_id=None))
    await db.delete(team)
    await db.flush()

    await log_action(
        db, actor=current_user, action="team.delete", entity_type="team", entity_id=team_id,
        before={"name": team_name, "code": team_code, "member_count": len(members), "lead_count": lead_count},
        note=f"Giải tán đội {team_name} ({team_code}) — {len(members)} thành viên, {lead_count} data về kho chung",
    )
    return {
        "message": f"Đã giải tán đội {team_name}",
        "members_cleared": len(members),
        "leads_cleared": lead_count,
    }


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
    xoa_cache_quyen()

    await log_action(
        db, actor=current_user, action="custom_role.create",
        entity_type="custom_role", entity_id=key,
        after={"role_name": data.role_name, "department": data.department},
    )

    return {"role": new_role, "message": "Đã tạo vai trò mới"}


# ── Role-level permissions (matrix admin) ────────────────────────────────

@router.get("/permissions/me")
async def get_my_permissions(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Quyền có hiệu lực của CHÍNH người đang đăng nhập — mở cho mọi người.

    Trước đây chỉ admin đọc được /permissions/roles, nên người thường không bao
    giờ thấy override sếp đặt trên trang Phân quyền — menu của họ vẽ theo mặc định
    viết cứng trong roles.ts. Endpoint này cho FE vẽ menu đúng với quyền backend
    đang thực thi (một nguồn sự thật).
    """
    perms = await quyen_hieu_luc(current_user, db)
    return {"role": current_user.role, "permissions": perms}


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

    # Vai trò tùy chỉnh: đưa vào ma trận như vai trò hệ thống (quyền nằm ngay
    # trong định nghĩa role — không có defaults/overrides riêng)
    for r in await _load_custom_roles(db):
        roles_data[r["role_key"]] = {
            "permissions": r.get("permissions", {}),
            "overrides": None,
            "custom": True,
            "role_name": r.get("role_name", r["role_key"]),
            "department": r.get("department"),
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
        # Vai trò tùy chỉnh: quyền nằm NGAY trong định nghĩa (system_settings.custom_roles)
        customs = await _load_custom_roles(db)
        target = next((r for r in customs if r["role_key"] == role), None)
        if target is None:
            raise HTTPException(status_code=400, detail="Vai trò không hợp lệ")
        custom_perms = data.get("permissions", {})
        if custom_perms:
            target["permissions"] = {**target.get("permissions", {}), **custom_perms}
            setting = await db.get(SystemSetting, "custom_roles")
            if setting:
                setting.value = json.dumps(customs, ensure_ascii=False)
                setting.updated_at = datetime.now(timezone.utc)
                await db.flush()
            xoa_cache_quyen()
        await log_action(
            db, actor=current_user, action="custom_role.update_permissions",
            entity_type="custom_role", entity_id=role,
            after={"permissions": custom_perms or None},
        )
        return {
            "role": role,
            "permissions": target.get("permissions"),
            "message": "Đã cập nhật phân quyền vai trò tùy chỉnh",
        }

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
    xoa_cache_quyen()

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
    """Get user detail — chính mình, hoặc người có quyền Nhân sự/Quản lý Users.

    Trưởng nhóm (leader/sale_leader) chỉ xem được hồ sơ người trong nhóm mình.
    Trước đây endpoint này KHÔNG gác — lộ SĐT/bậc lương/quyền cá nhân cho mọi
    người đăng nhập (vá 14/08/2026).
    """
    if current_user.id != user_id:
        perms = await quyen_hieu_luc(current_user, db)
        if not (perms.get("canViewHR") or perms.get("canManageUsers")):
            raise HTTPException(status_code=403, detail="Không có quyền xem hồ sơ nhân viên khác")

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="Nhân viên không tồn tại")

    if (
        current_user.id != user_id
        and current_user.role != "admin"
        and is_team_lead(current_user)
        and (current_user.team_id is None or user.team_id != current_user.team_id)
    ):
        raise HTTPException(status_code=403, detail="Trưởng nhóm chỉ xem được hồ sơ nhân sự nhóm mình")
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

    # Đội quyết định phạm vi thấy lead/nhân sự — tự đổi team_id là tự mở rộng quyền.
    # Chỉ chặn khi giá trị THAY ĐỔI thật (form tự sửa hồ sơ có thể echo giá trị cũ).
    if (
        "team_id" in provided
        and provided["team_id"] != user.team_id
        and current_user.role not in ("admin", "accountant")
    ):
        raise HTTPException(status_code=403, detail="Chỉ admin/kế toán mới được chuyển nhóm nhân sự")

    # Trưởng nhóm đương nhiệm không rời đội qua đường sửa hồ sơ — kể cả admin.
    # Nếu cho rời, teams.leader_id thành mồ côi: sĩ số sai, phạm vi lead lệch (review 14/08)
    if "team_id" in provided and provided["team_id"] != user.team_id:
        # .all() chứ không .first(): dữ liệu bẩn cũ có thể để 1 người lãnh 2 đội —
        # .first() sẽ che mất đội thứ hai và cho chuyển lọt (phản biện vá 14/08)
        leading = (await db.execute(
            select(Team).where(Team.leader_id == user.id)
        )).scalars().all()
        blocked = [t for t in leading if provided["team_id"] != t.id]
        if blocked:
            raise HTTPException(
                status_code=400,
                detail=f"{user.full_name} đang là trưởng nhóm đội {blocked[0].name} — đổi trưởng nhóm đội đó trước rồi mới chuyển đội",
            )

    # Bộ phận cũng quyết định phạm vi: vai trò tùy chỉnh + department SALES là
    # điều phối KD (thấy toàn bộ lead, đủ SĐT, export). Tự đổi department của
    # chính mình = tự leo thang — chặn như team_id (review đối kháng 14/08).
    if (
        "department" in provided
        and provided["department"] != user.department
        and current_user.role not in ("admin", "accountant")
    ):
        raise HTTPException(status_code=403, detail="Chỉ admin/kế toán mới được chuyển bộ phận nhân sự")

    allowed = ["full_name", "phone", "role", "department", "team_id", "is_active", "telegram_user_id", "telegram_username", "salary_grade_id", "dependents_count"]
    before_sensitive = {
        "role": user.role, "is_active": user.is_active, "team_id": user.team_id,
        "department": user.department, "telegram_user_id": user.telegram_user_id,
    }
    doi_cu = user.team_id
    for k in allowed:
        if k in provided:
            setattr(user, k, provided[k])
    if "password" in provided and data.password:
        user.password_hash = hash_password(data.password)
    user.updated_at = datetime.now(timezone.utc)
    # Chuyển đội qua đường sửa hồ sơ cũng phải kéo lead đi theo, y như xếp thành viên.
    if user.team_id != doi_cu:
        await _dong_bo_nhan_doi_cua_lead(db, [user.id], user.team_id)
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

    if user.role in _ROLE_PERMISSION_DEFAULTS:
        combined = _get_combined_permissions(user.role, custom)
    else:
        # Vai trò tùy chỉnh: defaults là quyền trong định nghĩa role —
        # KHÔNG được rơi về data_entry (sai phân quyền)
        customs = await _load_custom_roles(db)
        target = next((r for r in customs if r["role_key"] == user.role), None)
        if target:
            combined = dict(target.get("permissions", {}))
            if custom:
                combined.update(custom)
        else:
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
