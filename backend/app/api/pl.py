"""P&L (Profit & Loss) API — company-wide and per-project financials."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.auth import get_current_user
from app.models.user import User
from app.models.project import Project
from app.models.contract import Contract
from app.models.payroll import Transaction
from app.models.inventory import MaterialUsage
from app.schemas.pl import PLProjectItem, PLProjectDetail, PLCostCategory, PLSummary

router = APIRouter(prefix="/pl", tags=["pl"])

# Only C-level roles may access P&L data
_CLEVEL_ROLES = ("admin", "executive", "accountant")


def _require_clevel(current_user: User = Depends(get_current_user)) -> User:
    """Dependency that blocks non-C-level users."""
    if current_user.role not in _CLEVEL_ROLES:
        raise HTTPException(
            status_code=403,
            detail="Only admin, executive, or accountant roles may access P&L data",
        )
    return current_user


# ---------------------------------------------------------------------------
# Helper: build per-project cost dict  {project_id: {material: x, transaction: y}}
# ---------------------------------------------------------------------------

async def _build_project_costs(
    db: AsyncSession,
) -> dict[str, dict[str, float]]:
    """Return {project_id: {'material': total, 'transaction': total}} for all projects."""
    # Material usage costs
    mat_q = (
        select(
            MaterialUsage.project_id,
            func.coalesce(func.sum(MaterialUsage.total_cost), 0).label("total"),
        )
        .group_by(MaterialUsage.project_id)
    )
    mat_rows = (await db.execute(mat_q)).all()

    # Transaction expense costs
    txn_q = (
        select(
            Transaction.project_id,
            func.coalesce(func.sum(Transaction.amount), 0).label("total"),
        )
        .where(Transaction.type == "expense", Transaction.status != "cancelled")
        .group_by(Transaction.project_id)
    )
    txn_rows = (await db.execute(txn_q)).all()

    costs: dict[str, dict[str, float]] = {}
    for project_id, total in mat_rows:
        costs.setdefault(project_id, {"material": 0.0, "transaction": 0.0})
        costs[project_id]["material"] = float(total)
    for project_id, total in txn_rows:
        costs.setdefault(project_id, {"material": 0.0, "transaction": 0.0})
        costs[project_id]["transaction"] = float(total)

    return costs


# ---------------------------------------------------------------------------
# Helper: build per-project revenue dict  {project_id: total_value}
# ---------------------------------------------------------------------------

async def _build_project_revenues(db: AsyncSession) -> dict[str, float]:
    """Return {project_id: sum of signed contract total_value}."""
    q = (
        select(
            Contract.project_id,
            func.coalesce(func.sum(Contract.total_value), 0).label("total"),
        )
        .where(Contract.status == "signed")
        .group_by(Contract.project_id)
    )
    rows = (await db.execute(q)).all()
    return {project_id: float(total) for project_id, total in rows}


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get("/summary", response_model=PLSummary)
async def company_pl_summary(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(_require_clevel),
):
    """Company-wide P&L: total revenue, total costs, net profit, margin %."""
    revenues = await _build_project_revenues(db)
    costs = await _build_project_costs(db)

    total_revenue = sum(revenues.values())
    total_cost_material = sum(c["material"] for c in costs.values())
    total_cost_transaction = sum(c["transaction"] for c in costs.values())
    total_cost = total_cost_material + total_cost_transaction
    net_profit = total_revenue - total_cost
    margin = (net_profit / total_revenue * 100) if total_revenue else 0.0

    return PLSummary(
        total_revenue=total_revenue,
        total_cost_material=total_cost_material,
        total_cost_transaction=total_cost_transaction,
        total_cost=total_cost,
        net_profit=net_profit,
        margin=round(margin, 2),
        project_count=len(revenues) + len(costs.keys() - revenues.keys()),
    )


@router.get("/projects", response_model=list[PLProjectItem])
async def project_pl_list(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(_require_clevel),
):
    """Per-project P&L list showing revenue, costs, profit and margin."""
    revenues = await _build_project_revenues(db)
    costs = await _build_project_costs(db)

    # Merge all known project IDs
    all_project_ids = set(revenues.keys()) | set(costs.keys())

    result = await db.execute(select(Project))
    projects_map = {p.id: p for p in result.scalars().all()}

    items: list[PLProjectItem] = []
    for pid in sorted(all_project_ids):
        p = projects_map.get(pid)
        rev = revenues.get(pid, 0.0)
        c = costs.get(pid, {"material": 0.0, "transaction": 0.0})
        total_cost = c["material"] + c["transaction"]
        profit = rev - total_cost
        margin = (profit / rev * 100) if rev else 0.0

        items.append(
            PLProjectItem(
                project_id=pid,
                project_code=p.code if p else "N/A",
                project_name=p.name if p else "Unknown",
                revenue=rev,
                cost_material=c["material"],
                cost_transaction=c["transaction"],
                total_cost=total_cost,
                profit=profit,
                margin=round(margin, 2),
            )
        )

    return items


@router.get("/projects/{project_id}", response_model=PLProjectDetail)
async def project_pl_detail(
    project_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(_require_clevel),
):
    """Detailed P&L for one project with cost breakdown by category."""
    # Verify project exists
    proj_result = await db.execute(select(Project).where(Project.id == project_id))
    project = proj_result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    # Revenue from signed contracts
    rev_result = await db.execute(
        select(func.coalesce(func.sum(Contract.total_value), 0))
        .where(Contract.project_id == project_id, Contract.status == "signed")
    )
    revenue = float(rev_result.scalar())

    # Material usage costs
    mat_result = await db.execute(
        select(func.coalesce(func.sum(MaterialUsage.total_cost), 0))
        .where(MaterialUsage.project_id == project_id)
    )
    cost_material = float(mat_result.scalar())

    # Transaction expenses by category
    txn_cat_q = (
        select(
            Transaction.category,
            func.coalesce(func.sum(Transaction.amount), 0).label("total"),
            func.count(Transaction.id).label("count"),
        )
        .where(
            Transaction.project_id == project_id,
            Transaction.type == "expense",
            Transaction.status != "cancelled",
        )
        .group_by(Transaction.category)
    )
    txn_cat_rows = (await db.execute(txn_cat_q)).all()

    cost_by_category: list[PLCostCategory] = []
    cost_transaction = 0.0
    for category, total, count in txn_cat_rows:
        total_f = float(total)
        cost_transaction += total_f
        cost_by_category.append(
            PLCostCategory(category=category, total=total_f, count=count)
        )

    # Also add material as a category entry for consistency
    if cost_material > 0:
        mat_count_result = await db.execute(
            select(func.count(MaterialUsage.id))
            .where(MaterialUsage.project_id == project_id)
        )
        mat_count = mat_count_result.scalar() or 0
        cost_by_category.append(
            PLCostCategory(category="material", total=cost_material, count=mat_count)
        )

    total_cost = cost_material + cost_transaction
    profit = revenue - total_cost
    margin = (profit / revenue * 100) if revenue else 0.0

    return PLProjectDetail(
        project_id=project.id,
        project_code=project.code,
        project_name=project.name,
        revenue=revenue,
        cost_material=cost_material,
        cost_transaction=cost_transaction,
        total_cost=total_cost,
        profit=profit,
        margin=round(margin, 2),
        cost_by_category=cost_by_category,
    )
