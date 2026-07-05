"""Task Coordinator Agent — auto-generate and assign project tasks from stage blueprints.

Uses litellm acompletion for LLM-assisted context enrichment with a deterministic
rule-based fallback that always produces the full 19-task blueprint.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any

from litellm import acompletion
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models.project import Project, Task, TaskActivity
from app.models.user import User

logger = logging.getLogger(__name__)
settings = get_settings()

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

STAGE_DESIGN = "design"
STAGE_QUOTATION = "quotation"
STAGE_PROCUREMENT = "procurement"
STAGE_CONSTRUCTION = "construction"
STAGE_ACCEPTANCE = "acceptance"

_DEPT_DESIGN = "design"
_DEPT_QUOTATION = "quotation"
_DEPT_PROCUREMENT = "procurement"
_DEPT_CONSTRUCTION = "construction"
_DEPT_SALES = "sales"

# ---------------------------------------------------------------------------
# Task Blueprint — 19 tasks per project
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class TaskBlueprint:
    """Immutable description of a single task within the project blueprint."""

    title: str
    description: str
    stage: str
    department: str
    order: int
    # Default role used for rule-based assignment; overridden by LLM if available.
    preferred_role: str


TASK_BLUEPRINT: list[TaskBlueprint] = [
    # ── Stage I: Design (5) ──────────────────────────────────────────────
    TaskBlueprint(
        title="2D Concept",
        description="Phat trien concept phang 2D: mat bang cong nang, phoi canh, mau sac.",
        stage=STAGE_DESIGN,
        department=_DEPT_DESIGN,
        order=1,
        preferred_role="designer",
    ),
    TaskBlueprint(
        title="3D Demo",
        description="Xay dung mo hinh 3D demo de trinh phuong an voi khach hang.",
        stage=STAGE_DESIGN,
        department=_DEPT_DESIGN,
        order=2,
        preferred_role="designer",
    ),
    TaskBlueprint(
        title="3D Render",
        description="Render 3D cuoi cung voi chat luong cao, dung vat lieu va anh sang that.",
        stage=STAGE_DESIGN,
        department=_DEPT_DESIGN,
        order=3,
        preferred_role="designer",
    ),
    TaskBlueprint(
        title="Technical Drawing",
        description="Ve ky thuat chi tiet: mat bang, cat, phoi, chi tiet lap dat.",
        stage=STAGE_DESIGN,
        department=_DEPT_DESIGN,
        order=4,
        preferred_role="designer",
    ),
    TaskBlueprint(
        title="Final Design",
        description="Hoan thien goi thiet ke cuoi cung: ban ve, render, tai lieu ky thuat.",
        stage=STAGE_DESIGN,
        department=_DEPT_DESIGN,
        order=5,
        preferred_role="designer",
    ),

    # ── Stage II: Quotation (4) ──────────────────────────────────────────
    TaskBlueprint(
        title="2D Quotation",
        description="Lap bang gia tri cong viec thiet ke phang 2D.",
        stage=STAGE_QUOTATION,
        department=_DEPT_QUOTATION,
        order=6,
        preferred_role="pm",
    ),
    TaskBlueprint(
        title="3D Quotation",
        description="Lap bang gia cho phan thiet ke va render 3D.",
        stage=STAGE_QUOTATION,
        department=_DEPT_QUOTATION,
        order=7,
        preferred_role="pm",
    ),
    TaskBlueprint(
        title="Interior Quotation",
        description="Lap bang gia noi that: van go, da, kim loai, thiet bi dien.",
        stage=STAGE_QUOTATION,
        department=_DEPT_QUOTATION,
        order=8,
        preferred_role="pm",
    ),
    TaskBlueprint(
        title="Final Quotation",
        description="Tong hop va chot bang gia cuoi cung, gui khach hang phe duyet.",
        stage=STAGE_QUOTATION,
        department=_DEPT_QUOTATION,
        order=9,
        preferred_role="pm",
    ),

    # ── Stage III: Procurement (3) ───────────────────────────────────────
    TaskBlueprint(
        title="Prepare Materials",
        description="Chuan bi nguyen vat lieu theo thong so ky thuat da duyet.",
        stage=STAGE_PROCUREMENT,
        department=_DEPT_PROCUREMENT,
        order=10,
        preferred_role="pm",
    ),
    TaskBlueprint(
        title="SPECS",
        description="Lap chi tiet ky thuat (specifications) cho tung loai vat lieu.",
        stage=STAGE_PROCUREMENT,
        department=_DEPT_PROCUREMENT,
        order=11,
        preferred_role="pm",
    ),
    TaskBlueprint(
        title="Place Order",
        description="Dat hang nha cung cap, xac nhan giao hang va lich van chuyen.",
        stage=STAGE_PROCUREMENT,
        department=_DEPT_PROCUREMENT,
        order=12,
        preferred_role="pm",
    ),

    # ── Stage IV: Construction (4) ───────────────────────────────────────
    TaskBlueprint(
        title="Permits",
        description="Lam ho so xin phep xay dung / noi that (neu can).",
        stage=STAGE_CONSTRUCTION,
        department=_DEPT_CONSTRUCTION,
        order=13,
        preferred_role="pm",
    ),
    TaskBlueprint(
        title="Schedule",
        description="Lap lich trinh thi cong chi tiet, phan cong nhan cong.",
        stage=STAGE_CONSTRUCTION,
        department=_DEPT_CONSTRUCTION,
        order=14,
        preferred_role="pm",
    ),
    TaskBlueprint(
        title="Rough",
        description="Thi cong tho: hoan thien, dien nuoc, mang luoi.",
        stage=STAGE_CONSTRUCTION,
        department=_DEPT_CONSTRUCTION,
        order=15,
        preferred_role="pm",
    ),
    TaskBlueprint(
        title="Interior",
        description="Thi cong noi that hoan chinh: lap dat noi that, trang tri.",
        stage=STAGE_CONSTRUCTION,
        department=_DEPT_CONSTRUCTION,
        order=16,
        preferred_role="pm",
    ),

    # ── Stage V: Acceptance (3) ──────────────────────────────────────────
    TaskBlueprint(
        title="Handover",
        description="Nghiem thu va ban giao cong trinh cho khach hang.",
        stage=STAGE_ACCEPTANCE,
        department=_DEPT_SALES,
        order=17,
        preferred_role="sales",
    ),
    TaskBlueprint(
        title="Quantity Acceptance",
        description="Kiem tra kho luong, chat luong vat lieu va thi cong.",
        stage=STAGE_ACCEPTANCE,
        department=_DEPT_SALES,
        order=18,
        preferred_role="sales",
    ),
    TaskBlueprint(
        title="Warranty",
        description="Cap phieu bao hanh, huong dan su dung va bao tri.",
        stage=STAGE_ACCEPTANCE,
        department=_DEPT_SALES,
        order=19,
        preferred_role="sales",
    ),
]


# ---------------------------------------------------------------------------
# LLM prompt
# ---------------------------------------------------------------------------

_SYSTEM_PROMPT = """\
Ban la Task Coordinator AI cua JAMA HOME (cong ty noi that cao cap).
Nhiem vu: Xem thong tin du an va goi y cach phan cong 19 nhiem vu theo 5 giai doan.

Giai doan & nhiem vu:
Stage I - Design (5): 2D Concept, 3D Demo, 3D Render, Technical Drawing, Final Design
Stage II - Quotation (4): 2D Quotation, 3D Quotation, Interior Quotation, Final Quotation
Stage III - Procurement (3): Prepare Materials, SPECS, Place Order
Stage IV - Construction (4): Permits, Schedule, Rough, Interior
Stage V - Acceptance (3): Handover, Quantity Acceptance, Warranty

Tra ve JSON voi dinh dang:
{
  "assignments": [
    {
      "order": 1,
      "assignee_email": "email@jama.vn hoac null neu khong phai",
      "description_override": "mo ta tuy chinh neu can (optional)",
      "due_offset_days": so_ngay tu ngay bat dau (optional)
    }
  ],
  "notes": "ghi chu tong quan ve cach phan cong"
}

Quy tac:
1. 2D Concept, 3D Demo, 3D Render, Technical Drawing, Final Design -> designer
2. Quotation tasks -> pm hoac accountant
3. Procurement, Construction -> pm
4. Handover, Quantity Acceptance, Warranty -> sales hoac pm
5. Chi tra ve assignments cho cac task can thay doi, khong can tra toan bo
6. CHI tra JSON, khong giai thich
"""

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _build_project_context(project: Project, assignables: list[User]) -> str:
    """Build a text summary of the project for the LLM."""
    lines = [
        f"Du an: {project.code} - {project.name}",
        f"Khach hang: {project.client_name}",
        f"Loai: {project.project_type}",
        f"Gia tri thiet ke: {project.design_value or 'N/A'} VND",
        f"Gia tri thi cong: {project.construction_value or 'N/A'} VND",
        f"Tong gia tri: {project.total_value or 'N/A'} VND",
    ]
    if project.start_date:
        lines.append(f"Ngay bat dau: {project.start_date.date()}")
    if project.target_end_date:
        lines.append(f"Ngay ket thuc muc tieu: {project.target_end_date.date()}")
    if assignables:
        lines.append("Nhan vien co the phan cong:")
        for u in assignables:
            lines.append(f"  - {u.full_name} ({u.email}) | role={u.role}, dept={u.department}")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Rule-based fallback
# ---------------------------------------------------------------------------

def _resolve_assignee(
    blueprint: TaskBlueprint,
    project: Project,
    users_by_role: dict[str, list[User]],
) -> str | None:
    """Determine who should own a task using deterministic rules."""
    # Design tasks -> project designer
    if blueprint.preferred_role == "designer":
        if project.designer_id:
            return project.designer_id
        designers = users_by_role.get("designer", [])
        return designers[0].id if designers else None

    # Sales / acceptance -> project sales
    if blueprint.preferred_role == "sales":
        if project.sales_id:
            return project.sales_id
        sales_users = users_by_role.get("sales", []) or users_by_role.get("data_entry", [])
        return sales_users[0].id if sales_users else None

    # PM / everything else -> project PM
    if project.pm_id:
        return project.pm_id
    pm_users = users_by_role.get("pm", [])
    return pm_users[0].id if pm_users else None


def _generate_tasks_rule_based(
    project: Project,
    users_by_role: dict[str, list[User]],
) -> list[dict[str, Any]]:
    """Produce the full 19-task list without any LLM call."""
    start = project.start_date or datetime.now(timezone.utc)
    result: list[dict[str, Any]] = []
    for bp in TASK_BLUEPRINT:
        result.append({
            "title": bp.title,
            "description": bp.description,
            "stage": bp.stage,
            "department": bp.department,
            "order": bp.order,
            "assigned_to": _resolve_assignee(bp, project, users_by_role),
            "due_date": None,
        })
    return result


# ---------------------------------------------------------------------------
# LLM-enhanced generation
# ---------------------------------------------------------------------------

async def _apply_llm_enrichment(
    project: Project,
    base_tasks: list[dict[str, Any]],
    assignables: list[User],
) -> list[dict[str, Any]]:
    """Ask the LLM to adjust assignments and descriptions, then merge."""
    if not settings.LLM_API_KEY:
        logger.info("No LLM_API_KEY configured — using rule-based task plan.")
        return base_tasks

    assignables_map = {u.email: u.id for u in assignables if u.email}
    context = _build_project_context(project, assignables)

    try:
        response = await acompletion(
            model=settings.LLM_MODEL,
            api_key=settings.LLM_API_KEY,
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": context},
            ],
            temperature=0.2,
            max_tokens=1500,
            response_format={"type": "json_object"},
        )
        raw = response.choices[0].message.content
        data = json.loads(raw)
        adjustments: dict[int, dict[str, Any]] = {
            item["order"]: item
            for item in data.get("assignments", [])
            if isinstance(item, dict) and "order" in item
        }
    except Exception:
        logger.warning("LLM call failed — falling back to rule-based plan.", exc_info=True)
        return base_tasks

    # Merge LLM suggestions into the base list
    for task in base_tasks:
        adj = adjustments.get(task["order"])
        if not adj:
            continue

        # Override assignee if the LLM provided a known email
        email = adj.get("assignee_email")
        if email and email in assignables_map:
            task["assigned_to"] = assignables_map[email]

        # Override description if provided
        desc_override = adj.get("description_override")
        if desc_override and isinstance(desc_override, str) and desc_override.strip():
            task["description"] = desc_override.strip()

        # Due-date offset
        offset = adj.get("due_offset_days")
        if isinstance(offset, (int, float)) and project.start_date:
            task["due_date"] = project.start_date + timedelta(days=int(offset))

    return base_tasks


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

async def coordinate_tasks(project_id: str, db: AsyncSession) -> dict:
    """Generate and persist the full task blueprint for a project.

    Parameters
    ----------
    project_id:
        UUID of the project.
    db:
        Async SQLAlchemy session.

    Returns
    -------
    dict with keys:
        ``tasks_created``  – list of dicts representing created Task rows
        ``strategy``       – "llm_enriched" or "rule_based"
        ``notes``          – optional human-readable notes
    """
    # ── 1. Load project ───────────────────────────────────────────────────
    result = await db.execute(select(Project).where(Project.id == project_id))
    project = result.scalar_one_or_none()
    if project is None:
        raise ValueError(f"Project {project_id} not found.")

    # Guard: do not re-create tasks if they already exist
    existing_count = await db.execute(
        select(func.count()).select_from(Task).where(Task.project_id == project_id)
    )
    if existing_count.scalar_one() > 0:
        return {
            "tasks_created": [],
            "strategy": "skipped",
            "notes": f"Project already has {existing_count.scalar_one()} tasks.",
        }

    # ── 2. Load users grouped by role ────────────────────────────────────
    users_result = await db.execute(
        select(User).where(User.is_active.is_(True))
    )
    all_users = list(users_result.scalars().all())
    users_by_role: dict[str, list[User]] = {}
    for u in all_users:
        users_by_role.setdefault(u.role, []).append(u)

    # ── 3. Build base task list (rule-based) ─────────────────────────────
    base_tasks = _generate_tasks_rule_based(project, users_by_role)

    # ── 4. Optionally enrich via LLM ─────────────────────────────────────
    strategy = "rule_based"
    notes = ""

    try:
        enriched = await _apply_llm_enrichment(project, base_tasks, all_users)
        if enriched is not base_tasks:
            strategy = "llm_enriched"
            notes = "Tasks generated with LLM-assisted assignment optimisation."
        else:
            notes = "LLM unavailable or declined; using rule-based assignments."
    except Exception:
        logger.warning("LLM enrichment unexpected failure.", exc_info=True)
        enriched = base_tasks
        notes = "LLM enrichment failed; fell back to rule-based plan."

    # ── 5. Persist tasks ──────────────────────────────────────────────────
    created_tasks: list[dict[str, Any]] = []
    now = datetime.now(timezone.utc)

    for task_data in enriched:
        task = Task(
            project_id=project.id,
            title=task_data["title"],
            description=task_data["description"],
            stage=task_data["stage"],
            department=task_data["department"],
            order=task_data["order"],
            status="not_started",
            assigned_to=task_data.get("assigned_to"),
            due_date=task_data.get("due_date"),
            created_at=now,
        )
        db.add(task)
        # Flush so the ID is available before we continue
        await db.flush()

        # Record an activity log entry for the creation
        activity = TaskActivity(
            task_id=task.id,
            user_id=task.assigned_to or project.pm_id or "system",
            content=f"Task '{task.title}' created by Task Coordinator ({strategy}).",
            created_at=now,
        )
        db.add(activity)

        created_tasks.append(
            {
                "id": task.id,
                "title": task.title,
                "stage": task.stage,
                "department": task.department,
                "order": task.order,
                "assigned_to": task.assigned_to,
                "due_date": task.due_date.isoformat() if task.due_date else None,
            }
        )

    # Commit all new tasks at once
    await db.commit()

    logger.info(
        "Coordinate tasks for project %s: created %d tasks (strategy=%s)",
        project.code,
        len(created_tasks),
        strategy,
    )

    return {
        "tasks_created": created_tasks,
        "strategy": strategy,
        "notes": notes,
    }
