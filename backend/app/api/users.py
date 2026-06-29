"""Users API — admin CRUD for employees & teams."""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.auth import get_current_user, hash_password
from app.models.user import User, Team

router = APIRouter(prefix="/users", tags=["users"])


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
        "created_at": str(user.created_at),
    }


@router.post("")
async def create_user(
    data: dict,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create new user (admin only)."""
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Chỉ admin mới được tạo user")

    # Check email exists
    existing = await db.execute(select(User).where(User.email == data.get("email")))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Email đã tồn tại")

    user = User(
        full_name=data["full_name"],
        email=data["email"],
        phone=data.get("phone"),
        password_hash=hash_password(data.get("password", "jama2026")),
        role=data.get("role", "data_entry"),
        department=data.get("department", "SALES"),
        team_id=data.get("team_id"),
        is_active=True,
    )
    db.add(user)
    await db.flush()
    return {
        "id": user.id, "full_name": user.full_name, "email": user.email,
        "role": user.role, "department": user.department,
    }


@router.put("/{user_id}")
async def update_user(
    user_id: str,
    data: dict,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update user."""
    if current_user.role != "admin" and current_user.id != user_id:
        raise HTTPException(status_code=403, detail="Không có quyền")

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="Nhân viên không tồn tại")

    # Role escalation protection
    if "role" in data and current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Chỉ Admin mới có quyền thay đổi vai trò")
    if "is_active" in data and current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Chỉ Admin mới có quyền thay đổi trạng thái")

    allowed = ["full_name", "phone", "role", "department", "team_id", "is_active", "telegram_username"]
    for k in allowed:
        if k in data:
            setattr(user, k, data[k])
    if "password" in data and data["password"]:
        user.password_hash = hash_password(data["password"])
    user.updated_at = datetime.now(timezone.utc)
    await db.flush()

    return {
        "id": user.id, "full_name": user.full_name, "email": user.email,
        "role": user.role, "department": user.department, "is_active": user.is_active,
    }
