"""Leads API — CRUD, pipeline, activities."""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func, case
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.middleware.auth import get_current_user
from app.middleware.rbac import can_view_lead, can_modify_lead
from app.models.user import User, Team
from app.models.lead import Lead, Activity, VALID_STAGE_TRANSITIONS, LEAD_STAGES
from app.models.customer import Customer
from app.cache import cache
from app.models.project import Project, Task
from app.models.contract import Contract
from app.models.notification import Notification
import random
import uuid
from app.schemas.lead import (
    LeadCreate, LeadUpdate, LeadResponse, LeadStageChange, LeadAssign,
    ActivityCreate, ActivityResponse, PipelineStats, PipelineKanban,
)

def _escape_like(term: str) -> str:
    return term.replace("%", "\\%").replace("_", "\\_")


router = APIRouter(prefix="/leads", tags=["leads"])

STAGE_LABELS = {
    "new": "Tiếp nhận mới",
    "interested": "Đang tư vấn",
    "survey_scheduled": "Khảo sát",
    "potential": "Dự toán & tư vấn",
    "signed_design": "Ký HĐ Thiết kế",
    "lost": "Mất",
    "dormant": "Ngủ đông",
}


_PHONE_UNMASK_ROLES = {"admin", "leader", "data_entry"}


def _mask_phone(phone: str | None, current_user=None) -> str | None:
    """Mask phone for non-privileged roles: show first 3 digits + '***'."""
    if not phone or not current_user or current_user.role in _PHONE_UNMASK_ROLES:
        return phone
    return phone[:3] + "***" if len(phone) >= 3 else "***"


def _lead_response(lead: Lead, user_name: str = None, team_name: str = None, act_count: int = 0, current_user=None) -> LeadResponse:
    return LeadResponse(
        id=lead.id, name=lead.name, phone=_mask_phone(lead.phone, current_user), email=lead.email,
        contact_person=lead.contact_person, address=lead.address, needs=lead.needs,
        source=lead.source, channel=lead.channel,
        property_type=lead.property_type,
        area_sqm=lead.area_sqm, estimated_budget=lead.estimated_budget,
        contact_status=lead.contact_status,
        survey_date=lead.survey_date, survey_photos=lead.survey_photos,
        property_class=lead.property_class, price_per_sqm=lead.price_per_sqm,
        region=lead.region, segment=lead.segment,
        plan_type=lead.plan_type, tags=lead.tags, deal_value=lead.deal_value,
        stage=lead.stage, priority=lead.priority,
        assigned_to=lead.assigned_to, team_id=lead.team_id,
        ai_score=lead.ai_score, ai_notes=lead.ai_notes,
        design_contract_value=lead.design_contract_value,
        notes=lead.notes, created_at=lead.created_at, updated_at=lead.updated_at,
        last_contacted_at=lead.last_contacted_at,
        assigned_user_name=user_name, team_name=team_name,
        activity_count=act_count,
    )


@router.get("")
async def list_leads(
    stage: str | None = None,
    source: str | None = None,
    priority: str | None = None,
    assigned_to: str | None = None,
    search: str | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
):
    """List leads with optional filters."""
    q = (
        select(
            Lead,
            User.full_name.label("user_name"),
            Team.name.label("team_name"),
        )
        .outerjoin(User, Lead.assigned_to == User.id)
        .outerjoin(Team, Lead.team_id == Team.id)
    )

    # RBAC filter
    if current_user.role == "data_entry":
        q = q.where(Lead.assigned_to == current_user.id)
    elif current_user.role == "leader":
        q = q.where(Lead.team_id == current_user.team_id)
    elif current_user.role in ("accountant", "executive", "supervisor"):
        return {"items": [], "total": 0, "page": page, "page_size": page_size, "total_pages": 0}

    if stage:
        q = q.where(Lead.stage == stage)
    if source:
        q = q.where(Lead.source == source)
    if priority:
        q = q.where(Lead.priority == priority)
    if assigned_to:
        q = q.where(Lead.assigned_to == assigned_to)
    if search:
        escaped = _escape_like(search)
        q = q.where(
            Lead.name.ilike(f"%{escaped}%", escape="\\")
            | Lead.phone.ilike(f"%{escaped}%", escape="\\")
            | Lead.address.ilike(f"%{escaped}%", escape="\\")
        )

    # Count total (before pagination)
    count_q = select(func.count()).select_from(q.subquery())
    total = (await db.execute(count_q)).scalar() or 0

    # Build activity count subquery to avoid N+1 queries
    act_count_sq = (
        select(Activity.lead_id, func.count(Activity.id).label("activity_count"))
        .group_by(Activity.lead_id)
        .subquery()
    )

    q = q.outerjoin(act_count_sq, Lead.id == act_count_sq.c.lead_id)
    q = q.add_columns(act_count_sq.c.activity_count)

    q = q.order_by(Lead.updated_at.desc())
    q = q.offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(q)
    rows = result.all()

    leads = []
    for lead, user_name, team_name, act_count in rows:
        leads.append(_lead_response(lead, user_name, team_name, act_count or 0, current_user))

    return {
        "items": leads,
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": (total + page_size - 1) // page_size,
    }


@router.get("/pipeline/stats", response_model=PipelineStats)
async def pipeline_stats(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Pipeline summary stats."""
    q = select(Lead.stage, func.count(Lead.id), func.sum(Lead.estimated_budget))
    if current_user.role == "data_entry":
        q = q.where(Lead.assigned_to == current_user.id)
    elif current_user.role == "leader":
        q = q.where(Lead.team_id == current_user.team_id)
    q = q.group_by(Lead.stage)

    result = await db.execute(q)
    rows = result.all()

    by_stage = {}
    total = 0
    pipeline_value = 0
    signed = 0
    for stage, count, budget_sum in rows:
        by_stage[stage] = count
        total += count
        pipeline_value += (budget_sum or 0)
        if stage == "signed_design":
            signed = count

    conversion_rate = (signed / total * 100) if total > 0 else 0

    return PipelineStats(
        total_leads=total,
        by_stage=by_stage,
        conversion_rate=round(conversion_rate, 1),
        pipeline_value=pipeline_value,
    )


@router.get("/pipeline/kanban", response_model=list[PipelineKanban])
async def pipeline_kanban(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Kanban board data — leads grouped by stage."""
    stages = ["new", "interested", "survey_scheduled", "potential", "signed_design"]
    kanban = []

    for stage in stages:
        q = (
            select(Lead, User.full_name.label("user_name"), Team.name.label("team_name"))
            .outerjoin(User, Lead.assigned_to == User.id)
            .outerjoin(Team, Lead.team_id == Team.id)
            .where(Lead.stage == stage)
            .order_by(Lead.updated_at.desc())
        )
        if current_user.role == "data_entry":
            q = q.where(Lead.assigned_to == current_user.id)
        elif current_user.role == "leader":
            q = q.where(Lead.team_id == current_user.team_id)

        result = await db.execute(q)
        rows = result.all()
        leads = [_lead_response(lead, un, tn, 0, current_user) for lead, un, tn in rows]

        kanban.append(PipelineKanban(
            stage=stage,
            stage_label=STAGE_LABELS.get(stage, stage),
            leads=leads,
            count=len(leads),
        ))

    return kanban


@router.get("/workload")
async def team_workload(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Team workload distribution — leads per user with pipeline value and overdue count.
    Admin and leader only."""
    if current_user.role not in ("admin", "leader"):
        raise HTTPException(status_code=403, detail="Chỉ admin/leader được xem phân công workload")

    # Overdue = active leads not contacted in >7 days (or never contacted)
    from datetime import timedelta
    overdue_threshold = datetime.now(timezone.utc) - timedelta(days=7)
    active_stages = ["new", "interested", "survey_scheduled", "potential"]

    # Base query: group by assigned_to
    q = (
        select(
            Lead.assigned_to.label("user_id"),
            User.full_name.label("user_name"),
            func.count(Lead.id).label("lead_count"),
            func.coalesce(func.sum(Lead.estimated_budget), 0).label("pipeline_value"),
            func.count(
                case(
                    (
                        Lead.stage.in_(active_stages),
                        case(
                            (
                                (Lead.last_contacted_at.is_(None)) | (Lead.last_contacted_at < overdue_threshold),
                                1,
                            ),
                            else_=None,
                        ),
                    ),
                    else_=None,
                )
            ).label("overdue_count"),
        )
        .outerjoin(User, Lead.assigned_to == User.id)
        .where(Lead.assigned_to.isnot(None))
        .where(Lead.stage.notin_(["signed_design", "lost"]))
        .group_by(Lead.assigned_to, User.full_name)
        .order_by(func.count(Lead.id).desc())
    )

    # RBAC: leader sees only their team
    if current_user.role == "leader":
        q = q.where(Lead.team_id == current_user.team_id)

    result = await db.execute(q)
    rows = result.all()

    return [
        {
            "user_id": r.user_id,
            "user_name": r.user_name or "Chua phan cong",
            "lead_count": r.lead_count,
            "pipeline_value": float(r.pipeline_value),
            "overdue_count": r.overdue_count,
        }
        for r in rows
    ]

# ── CSV Export (must be before /{lead_id} to avoid route conflict) ───────

import csv
import io
from fastapi.responses import StreamingResponse


@router.get("/export")
async def export_leads_csv(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Export all leads as CSV."""
    result = await db.execute(select(Lead).order_by(Lead.created_at.desc()))
    leads = result.scalars().all()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Tên", "SĐT", "Email", "Nguồn", "Kênh", "Giai đoạn", "Ưu tiên", "Người phụ trách", "Ngày tạo"])
    for lead in leads:
        writer.writerow([
            lead.name, lead.phone, lead.email or "",
            lead.source or "", lead.channel or "",
            STAGE_LABELS.get(lead.stage, lead.stage), lead.priority,
            lead.assigned_to or "", lead.created_at.strftime("%d/%m/%Y") if lead.created_at else "",
        ])

    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=leads_{datetime.now(timezone.utc).strftime('%Y%m%d')}.csv"},
    )


@router.get("/{lead_id}", response_model=LeadResponse)
async def get_lead(
    lead_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get single lead with details."""
    q = (
        select(Lead, User.full_name.label("user_name"), Team.name.label("team_name"))
        .outerjoin(User, Lead.assigned_to == User.id)
        .outerjoin(Team, Lead.team_id == Team.id)
        .where(Lead.id == lead_id)
    )
    result = await db.execute(q)
    row = result.first()
    if not row:
        raise HTTPException(status_code=404, detail="Lead không tồn tại")

    lead, user_name, team_name = row
    if not can_view_lead(current_user, lead):
        raise HTTPException(status_code=403, detail="Không có quyền xem lead này")
    act_q = select(func.count(Activity.id)).where(Activity.lead_id == lead.id)
    act_count = (await db.execute(act_q)).scalar() or 0
    return _lead_response(lead, user_name, team_name, act_count, current_user)


@router.post("", response_model=LeadResponse)
async def create_lead(
    data: LeadCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create new lead."""
    lead = Lead(
        name=data.name, phone=data.phone, email=data.email,
        contact_person=data.contact_person, address=data.address,
        needs=data.needs, source=data.source, channel=data.channel,
        property_type=data.property_type, area_sqm=data.area_sqm,
        estimated_budget=data.estimated_budget,
        contact_status=data.contact_status,
        survey_date=data.survey_date, survey_photos=data.survey_photos,
        property_class=data.property_class, price_per_sqm=data.price_per_sqm,
        region=data.region, segment=data.segment,
        plan_type=data.plan_type, tags=data.tags, deal_value=data.deal_value,
        priority=data.priority, notes=data.notes,
        assigned_to=current_user.id, team_id=current_user.team_id,
    )
    db.add(lead)
    await db.flush()

    # Activity log
    db.add(Activity(
        lead_id=lead.id, user_id=current_user.id,
        type="note", content=f"Tạo lead mới: {lead.name} — {lead.phone}",
    ))
    await db.flush()

    return _lead_response(lead, current_user.full_name, None, 1, current_user)


@router.put("/{lead_id}", response_model=LeadResponse)
async def update_lead(
    lead_id: str,
    data: LeadUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update lead fields."""
    result = await db.execute(select(Lead).where(Lead.id == lead_id))
    lead = result.scalar_one_or_none()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead không tồn tại")
    if not can_modify_lead(current_user, lead):
        raise HTTPException(status_code=403, detail="Không có quyền chỉnh sửa lead này")

    update_fields = data.model_dump(exclude_unset=True)
    for k, v in update_fields.items():
        setattr(lead, k, v)
    lead.updated_at = datetime.now(timezone.utc)
    await db.flush()

    return _lead_response(lead, current_user=current_user)


@router.put("/{lead_id}/stage", response_model=LeadResponse)
async def change_stage(
    lead_id: str,
    data: LeadStageChange,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Move lead to new pipeline stage."""
    result = await db.execute(select(Lead).where(Lead.id == lead_id))
    lead = result.scalar_one_or_none()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead không tồn tại")
    if not can_modify_lead(current_user, lead):
        raise HTTPException(status_code=403, detail="Không có quyền chỉnh sửa lead này")

    valid = VALID_STAGE_TRANSITIONS.get(lead.stage, [])
    if data.new_stage not in valid:
        raise HTTPException(
            status_code=400,
            detail=f"Không thể chuyển từ {lead.stage} sang {data.new_stage}",
        )

    old_stage = lead.stage
    lead.stage = data.new_stage
    if data.design_contract_value:
        lead.design_contract_value = data.design_contract_value
    lead.updated_at = datetime.now(timezone.utc)
    await db.flush()

    # Auto-convert to Customer & Project when signed_design is reached
    if data.new_stage == "signed_design":
        # 1. Create/get Customer
        cust_q = select(Customer).where((Customer.lead_id == lead.id) | (Customer.phone == lead.phone))
        cust_res = await db.execute(cust_q)
        customer = cust_res.scalar_one_or_none()
        if not customer:
            customer = Customer(
                name=lead.name,
                phone=lead.phone,
                email=lead.email,
                address=lead.address,
                lead_id=lead.id,
                type="individual",
            )
            db.add(customer)
            await db.flush()

        # 2. Create Project
        proj_q = select(Project).where(Project.lead_id == lead.id)
        proj_res = await db.execute(proj_q)
        project = proj_res.scalar_one_or_none()
        if not project:
            year = datetime.now(timezone.utc).year
            # Ensure unique project code (max 100 attempts to avoid infinite loop)
            code = None
            for _attempt in range(100):
                candidate = f"PRJ-{year}-{random.randint(1000, 9999)}"
                code_q = select(Project).where(Project.code == candidate)
                code_res = await db.execute(code_q)
                if not code_res.scalar_one_or_none():
                    code = candidate
                    break
            if not code:
                code = f"PRJ-{year}-{uuid.uuid4().hex[:8]}"

            project = Project(
                code=code,
                name=f"Dự án {lead.name}",
                lead_id=lead.id,
                customer_id=customer.id,
                client_name=lead.name,
                client_phone=lead.phone,
                address=lead.address,
                project_type="design_build",
                design_value=lead.design_contract_value or lead.estimated_budget,
                total_value=lead.design_contract_value or lead.estimated_budget,
                status="active",
                stage="design",
                sales_id=lead.assigned_to,
            )
            db.add(project)
            await db.flush()

            # 3. Create 19 default tasks for Project
            default_tasks = [
                # Thiết kế
                ("2D Concept", "Bố trí công năng, layout sơ bộ", "design", 1),
                ("3D Demo", "Phối cảnh ý tưởng để khách duyệt hướng", "design", 2),
                ("3D Render", "Phối cảnh hoàn chỉnh chất lượng cao", "design", 3),
                ("Triển khai bản vẽ kỹ thuật", "TK Kiến trúc, kết cấu, điện nước, 2D nội thất", "design", 4),
                ("Thiết kế Final", "Chủ trì duyệt & up file đã chốt", "design", 5),
                # Báo giá
                ("Báo giá 2D", "Báo giá theo bản vẽ 2D", "quotation", 6),
                ("Báo giá 3D", "Báo giá theo phương án 3D", "quotation", 7),
                ("Báo giá Nội thất", "Báo giá hạng mục nội thất", "quotation", 8),
                ("Báo giá chốt khách (Final)", "File báo giá thống nhất với khách", "quotation", 9),
                # Thu mua
                ("Chuẩn bị vật liệu", "Danh mục vật tư theo thiết kế & báo giá", "procurement", 10),
                ("Hoàn thành SPECS", "Chốt quy cách kỹ thuật từng vật tư", "procurement", 11),
                ("Đặt hàng", "Đơn đặt hàng + theo dõi tiến độ hàng về", "procurement", 12),
                # Thi công
                ("Xin phép (nếu có)", "Thủ tục pháp lý / nội quy tòa nhà trước khi vào việc", "construction", 13),
                ("Lập bảng tiến độ", "Tiến độ tổng chia theo hạng mục & deadline", "construction", 14),
                ("Thi công thô", "Tháo dỡ, kết cấu, xây tô, điện–nước âm", "construction", 15),
                ("Thi công nội thất", "Lắp đặt & hoàn thiện nội thất", "construction", 16),
                # Nghiệm thu
                ("Bàn giao công trình", "Biên bản bàn giao cho khách + hình ảnh", "acceptance", 17),
                ("Nghiệm thu khối lượng", "Đối chiếu khối lượng thực tế vs hợp đồng", "acceptance", 18),
                ("Bảo hành – Bảo trì", "Thiết lập kỳ bảo hành; tiếp nhận & xử lý yêu cầu", "acceptance", 19),
            ]

            tasks_created = 0
            for title, desc, tstage, order in default_tasks:
                try:
                    task = Task(
                        project_id=project.id,
                        title=title,
                        description=desc,
                        stage=tstage,
                        status="not_started",
                        order=order,
                    )
                    db.add(task)
                    await db.flush()
                    tasks_created += 1
                except Exception as e:
                    print(f"[WARN] Failed to create task '{title}' for project {code}: {e}")

            if tasks_created == 0:
                print(f"[ERROR] No tasks created for project {code} — lead {lead.id}")

            # 4. Auto-create Contract to connect lead to revenue pipeline
            contract_q = select(Contract).where(Contract.project_id == project.id)
            contract_res = await db.execute(contract_q)
            existing_contract = contract_res.scalar_one_or_none()
            if not existing_contract:
                contract_code = f"HD-{project.code}"
                contract = Contract(
                    code=contract_code,
                    project_id=project.id,
                    title=f"Hợp đồng thiết kế - {lead.name}",
                    status="draft",
                    total_value=lead.estimated_budget or lead.design_contract_value or 0,
                    payment_terms={
                        "installments": [
                            {"name": "Đợt 1 (Đặt cọc)", "percentage": 25, "milestone": "signing", "status": "pending"},
                            {"name": "Đợt 2 (Nghiệm thu phần thô)", "percentage": 25, "milestone": "rough_complete", "status": "pending"},
                            {"name": "Đợt 3 (Nghiệm thu nội thất)", "percentage": 25, "milestone": "interior_complete", "status": "pending"},
                            {"name": "Đợt 4 (Bàn giao)", "percentage": 25, "milestone": "handover", "status": "pending"},
                        ]
                    },
                )
                db.add(contract)
                await db.flush()

        # 5. Notify PM (if assigned) and team Leader about new project
        notif_body = (
            f"Khách hàng {lead.name} đã ký HĐ. "
            f"Dự án {project.code} được tạo. PM vui lòng quản lý dự án."
        )
        notif_users: list[str] = []
        if project.pm_id:
            notif_users.append(project.pm_id)
        # Find team leader
        if lead.team_id:
            team_res = await db.execute(select(Team).where(Team.id == lead.team_id))
            team = team_res.scalar_one_or_none()
            if team and team.leader_id and team.leader_id not in notif_users:
                notif_users.append(team.leader_id)
        for uid in notif_users:
            db.add(Notification(
                user_id=uid,
                type="contract_signed",
                title="Khách hàng đã ký HĐ",
                body=notif_body,
                link=f"/projects/{project.id}",
                ref_id=project.id,
            ))
        if notif_users:
            await db.flush()

    # Log activity
    content = f"Chuyển stage: {STAGE_LABELS.get(old_stage)} → {STAGE_LABELS.get(data.new_stage)}"
    if data.note:
        content += f" — {data.note}"
    db.add(Activity(
        lead_id=lead.id, user_id=current_user.id,
        type="stage_change", content=content,
    ))
    await db.flush()

    # Invalidate caches affected by lead stage changes
    cache.clear_prefix("dashboard")

    return _lead_response(lead, current_user=current_user)


@router.post("/{lead_id}/assign", response_model=LeadResponse)
async def assign_lead(
    lead_id: str,
    data: LeadAssign,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Assign lead to a user."""
    result = await db.execute(select(Lead).where(Lead.id == lead_id))
    lead = result.scalar_one_or_none()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead không tồn tại")
    if current_user.role not in ("admin", "leader"):
        raise HTTPException(status_code=403, detail="Chỉ admin hoặc leader được phân công lead")

    # Get target user
    target = await db.execute(select(User).where(User.id == data.user_id))
    target_user = target.scalar_one_or_none()
    if not target_user:
        raise HTTPException(status_code=404, detail="User không tồn tại")

    lead.assigned_to = data.user_id
    lead.team_id = target_user.team_id
    lead.updated_at = datetime.now(timezone.utc)
    await db.flush()

    content = f"Phân công cho {target_user.full_name}"
    if data.note:
        content += f" — {data.note}"
    db.add(Activity(
        lead_id=lead.id, user_id=current_user.id,
        type="assignment", content=content,
    ))
    await db.flush()

    return _lead_response(lead, target_user.full_name, None, 0, current_user)


# ── Activities ──

@router.get("/{lead_id}/activities")
async def list_activities(
    lead_id: str,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get activity history for a lead (paginated)."""
    base_q = (
        select(Activity, User.full_name.label("user_name"))
        .outerjoin(User, Activity.user_id == User.id)
        .where(Activity.lead_id == lead_id)
    )

    # Count total
    count_q = select(func.count(Activity.id)).where(Activity.lead_id == lead_id)
    total = (await db.execute(count_q)).scalar() or 0

    # Paginated results
    q = base_q.order_by(Activity.created_at.desc())
    q = q.offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(q)
    rows = result.all()

    items = [
        ActivityResponse(
            id=act.id, lead_id=act.lead_id, user_id=act.user_id,
            type=act.type, content=act.content, created_at=act.created_at,
            user_name=user_name,
        )
        for act, user_name in rows
    ]

    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": (total + page_size - 1) // page_size,
    }


@router.post("/{lead_id}/activities", response_model=ActivityResponse)
async def create_activity(
    lead_id: str,
    data: ActivityCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Add activity to lead."""
    # Verify lead exists
    result = await db.execute(select(Lead).where(Lead.id == lead_id))
    lead = result.scalar_one_or_none()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead không tồn tại")

    activity = Activity(
        lead_id=lead_id, user_id=current_user.id,
        type=data.type, content=data.content,
    )
    db.add(activity)

    # Update last contacted
    lead.last_contacted_at = datetime.now(timezone.utc)
    lead.updated_at = datetime.now(timezone.utc)
    await db.flush()

    return ActivityResponse(
        id=activity.id, lead_id=activity.lead_id, user_id=activity.user_id,
        type=activity.type, content=activity.content, created_at=activity.created_at,
        user_name=current_user.full_name,
    )


# ── Bulk operations ──────────────────────────────────────────────────────

from pydantic import BaseModel as _BaseModel


class BulkAssign(_BaseModel):
    lead_ids: list[str]
    user_id: str


class BulkStageChange(_BaseModel):
    lead_ids: list[str]
    new_stage: str


@router.post("/bulk/assign")
async def bulk_assign_leads(
    data: BulkAssign,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Bulk assign leads to a user (admin/leader only)."""
    if current_user.role not in ("admin", "leader"):
        raise HTTPException(status_code=403, detail="Chỉ admin/leader được giao lead hàng loạt")
    result = await db.execute(
        select(Lead).where(Lead.id.in_(data.lead_ids))
    )
    leads = result.scalars().all()
    for lead in leads:
        lead.assigned_to = data.user_id
        lead.updated_at = datetime.now(timezone.utc)
    await db.flush()
    return {"updated": len(leads)}


@router.post("/bulk/stage")
async def bulk_change_stage(
    data: BulkStageChange,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Bulk change lead stage (admin/leader only)."""
    if current_user.role not in ("admin", "leader"):
        raise HTTPException(status_code=403, detail="Chỉ admin/leader được chuyển stage hàng loạt")
    if data.new_stage not in LEAD_STAGES:
        raise HTTPException(status_code=400, detail=f"Giai đoạn không hợp lệ: {data.new_stage}")
    result = await db.execute(
        select(Lead).where(Lead.id.in_(data.lead_ids))
    )
    leads = result.scalars().all()
    for lead in leads:
        lead.stage = data.new_stage
        lead.updated_at = datetime.now(timezone.utc)
    await db.flush()
    return {"updated": len(leads)}


