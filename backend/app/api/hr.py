"""HR API — resignation & work handover endpoints."""

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.auth import get_current_user
from app.models.user import User
from app.models.lead import Lead, Activity
from app.models.project import Task, Project
from app.services.audit import log_action

router = APIRouter(prefix="/hr", tags=["hr"])

# ---------------------------------------------------------------------------
# RBAC helper
# ---------------------------------------------------------------------------
_ALLOWED_ROLES = {"admin", "leader"}


def _require_admin_or_leader(current_user: User):
    if current_user.role not in _ALLOWED_ROLES:
        raise HTTPException(status_code=403, detail="Chỉ admin/leader mới có quyền thực hiện thao tác này")


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class ResignPreviewRequest(BaseModel):
    user_id: str


class ResignRequest(BaseModel):
    user_id: str
    transfer_leads_to: str | None = None
    transfer_tasks_to: str | None = None


class UndoResignRequest(BaseModel):
    user_id: str


# ---------------------------------------------------------------------------
# Helper: find the user with least assigned leads in the same team
# ---------------------------------------------------------------------------

async def _least_loaded_teammate(
    db: AsyncSession, user: User
) -> User | None:
    """Return the active teammate with the fewest assigned leads (same team)."""
    if not user.team_id:
        return None

    # Count leads per active user in same team
    stmt = (
        select(
            User.id,
            func.count(Lead.id).label("lead_count"),
        )
        .join(Lead, Lead.assigned_to == User.id, isouter=True)
        .where(
            User.team_id == user.team_id,
            User.is_active == True,  # noqa: E712
            User.id != user.id,
        )
        .group_by(User.id)
        .order_by(func.count(Lead.id).asc())
    )
    result = await db.execute(stmt)
    row = result.first()
    if row:
        return await db.get(User, row.id)
    return None


# ---------------------------------------------------------------------------
# 1. POST /hr/resign-preview
# ---------------------------------------------------------------------------

@router.post("/resign-preview")
async def resign_preview(
    body: ResignPreviewRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Preview which leads and tasks would be affected by a user's resignation."""
    _require_admin_or_leader(current_user)

    user = await db.get(User, body.user_id)
    if not user:
        raise HTTPException(status_code=404, detail="Nhân viên không tồn tại")

    # Leads
    leads_result = await db.execute(
        select(Lead).where(Lead.assigned_to == user.id)
    )
    leads = leads_result.scalars().all()

    # Tasks
    tasks_result = await db.execute(
        select(Task).where(Task.assigned_to == user.id)
    )
    tasks = tasks_result.scalars().all()

    # Fetch project names for tasks
    project_cache: dict[str, str] = {}
    task_items = []
    for t in tasks:
        if t.project_id not in project_cache:
            proj = await db.get(Project, t.project_id)
            project_cache[t.project_id] = proj.name if proj else ""
        task_items.append({
            "id": t.id,
            "title": t.title,
            "project_name": project_cache[t.project_id],
            "status": t.status,
        })

    return {
        "user_name": user.full_name,
        "leads": [
            {"id": l.id, "name": l.name, "phone": l.phone, "stage": l.stage}
            for l in leads
        ],
        "tasks": task_items,
        "lead_count": len(leads),
        "task_count": len(tasks),
    }


# ---------------------------------------------------------------------------
# 2. POST /hr/resign
# ---------------------------------------------------------------------------

@router.post("/resign")
async def resign(
    body: ResignRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Process an employee's resignation — transfer leads/tasks, deactivate account."""
    _require_admin_or_leader(current_user)

    user = await db.get(User, body.user_id)
    if not user:
        raise HTTPException(status_code=404, detail="Nhân viên không tồn tại")
    if not user.is_active:
        raise HTTPException(status_code=400, detail="Nhân viên đã bị vô hiệu hóa trước đó")

    now = datetime.now(timezone.utc)

    # --- Resolve lead assignee ---
    lead_target_id = body.transfer_leads_to
    if not lead_target_id:
        teammate = await _least_loaded_teammate(db, user)
        if teammate:
            lead_target_id = teammate.id

    # --- Resolve task assignee ---
    task_target_id = body.transfer_tasks_to

    # --- Leads ---
    leads_result = await db.execute(
        select(Lead).where(Lead.assigned_to == user.id)
    )
    leads = leads_result.scalars().all()

    transferred_leads = 0
    for lead in leads:
        target = lead_target_id
        if not target:
            # If still no target, skip but log — no one to assign to
            continue
        old_name = user.full_name
        lead.assigned_to = target
        lead.updated_at = now

        # Resolve target user name for activity log
        target_user = await db.get(User, target)
        target_name = target_user.full_name if target_user else target

        activity = Activity(
            lead_id=lead.id,
            user_id=target,
            type="assignment",
            content=f"Chuyển giao từ {old_name} do nghỉ việc",
        )
        db.add(activity)
        transferred_leads += 1

    # --- Tasks ---
    tasks_result = await db.execute(
        select(Task).where(Task.assigned_to == user.id)
    )
    tasks = tasks_result.scalars().all()

    transferred_tasks = 0
    for task in tasks:
        target = task_target_id
        if not target:
            # Fallback: assign to project PM
            proj = await db.get(Project, task.project_id)
            if proj and proj.pm_id and proj.pm_id != user.id:
                target = proj.pm_id
        if not target:
            continue
        task.assigned_to = target
        transferred_tasks += 1

    # --- Hoa hồng còn treo (pending/approved chưa paid) — báo kế toán chốt kỳ cuối ---
    from app.models.payroll import Commission, Payroll
    comm_result = await db.execute(
        select(Commission).where(
            Commission.user_id == user.id,
            Commission.status.in_(("pending", "approved")),
        )
    )
    pending_commissions = list(comm_result.scalars().all())
    pending_commission_total = round(sum(c.commission_amount for c in pending_commissions))

    # --- Thu hồi liên kết Telegram (chặn nhận thông báo/lệnh bot sau nghỉ việc) ---
    old_telegram_id = user.telegram_user_id
    user.telegram_user_id = None
    user.telegram_username = None

    # --- Kỳ lương cuối pro-rata (draft cho kế toán rà) — nếu kỳ hiện tại chưa có dòng ---
    from app.services.attendance_service import period_of, vn_today
    from app.services import payroll_engine
    final_period = period_of(vn_today())
    existing_payroll = await db.execute(
        select(Payroll).where(Payroll.user_id == user.id, Payroll.period == final_period).limit(1)
    )
    final_payroll_created = False
    if not existing_payroll.first():
        try:
            settings_map = await payroll_engine.get_payroll_settings(db)
            final_row = await payroll_engine.build_payroll_row(db, user, final_period, settings_map)
            final_row.notes = (
                (final_row.notes + " | " if final_row.notes else "")
                + f"Kỳ cuối — nghỉ việc {now.date()}; cộng hoa hồng treo {pending_commission_total:,.0f}đ và phép chưa dùng (kế toán rà)"
            )
            db.add(final_row)
            final_payroll_created = True
        except Exception:
            # Không chặn offboarding nếu tính lương lỗi — kế toán xử lý tay
            final_payroll_created = False

    # --- Thông báo kế toán chốt hoa hồng + lương kỳ cuối ---
    if pending_commissions or final_payroll_created:
        from app.services.automation import _notify
        acct_result = await db.execute(
            select(User).where(User.role.in_(("accountant", "admin")), User.is_active == True)  # noqa: E712
        )
        for acct in acct_result.scalars().all():
            await _notify(
                db, acct,
                type_="offboarding",
                title=f"Chốt lương nghỉ việc: {user.full_name}",
                body=(
                    f"Hoa hồng treo: {len(pending_commissions)} khoản ({pending_commission_total:,.0f}đ). "
                    f"{'Đã tạo dòng lương pro-rata kỳ ' + final_period + ' (draft).' if final_payroll_created else 'Kiểm tra bảng lương kỳ cuối.'}"
                ),
                link="/hr",
                ref_id=f"offboard-{user.id}",
            )

    # --- Deactivate user ---
    user.is_active = False
    user.resign_date = now
    user.resigned_by = current_user.id
    user.updated_at = now

    await db.flush()

    await log_action(
        db, actor=current_user, action="user.resign", entity_type="user", entity_id=user.id,
        after={
            "transferred_leads": transferred_leads,
            "transferred_tasks": transferred_tasks,
            "lead_target_id": lead_target_id,
            "task_target_id": task_target_id,
            "pending_commissions": len(pending_commissions),
            "pending_commission_total": pending_commission_total,
            "telegram_unlinked": old_telegram_id is not None,
            "final_payroll_created": final_payroll_created,
        },
        note=f"Nghỉ việc: {user.full_name}",
    )

    return {
        "transferred_leads": transferred_leads,
        "transferred_tasks": transferred_tasks,
        "pending_commissions": len(pending_commissions),
        "pending_commission_total": pending_commission_total,
        "telegram_unlinked": old_telegram_id is not None,
        "final_payroll_created": final_payroll_created,
        "final_period": final_period,
        "message": f"Đã chuyển giao {transferred_leads} leads và {transferred_tasks} tasks. Nhân viên {user.full_name} đã được nghỉ việc.",
    }


# ---------------------------------------------------------------------------
# 3. POST /hr/undo-resign
# ---------------------------------------------------------------------------

@router.post("/undo-resign")
async def undo_resign(
    body: UndoResignRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Restore a resigned employee within 7 days of resignation."""
    _require_admin_or_leader(current_user)

    user = await db.get(User, body.user_id)
    if not user:
        raise HTTPException(status_code=404, detail="Nhân viên không tồn tại")

    if not user.resign_date:
        raise HTTPException(status_code=400, detail="Nhân viên chưa nghỉ việc")

    # Check 7-day window
    cutoff = datetime.now(timezone.utc) - timedelta(days=7)
    # Make resign_date offset-aware if naive
    resign_dt = user.resign_date
    if resign_dt.tzinfo is None:
        resign_dt = resign_dt.replace(tzinfo=timezone.utc)

    if resign_dt < cutoff:
        raise HTTPException(
            status_code=400,
            detail="Đã quá 7 ngày kể từ khi nghỉ việc, không thể khôi phục",
        )

    user.is_active = True
    user.resign_date = None
    user.resigned_by = None
    user.updated_at = datetime.now(timezone.utc)

    await db.flush()

    await log_action(
        db, actor=current_user, action="user.undo_resign", entity_type="user", entity_id=user.id,
        note=f"Khôi phục nhân viên: {user.full_name}",
    )

    return {
        "status": "restored",
        "message": f"Nhân viên {user.full_name} đã được khôi phục.",
    }
