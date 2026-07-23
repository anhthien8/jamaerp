"""Customers API — CRUD for converted clients."""

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.auth import get_current_user
from app.models.user import User
from app.models.customer import Customer
from app.models.project import Project
from app.schemas.customer import CustomerCreate, CustomerUpdate, CustomerResponse

def _escape_like(term: str) -> str:
    return term.replace("%", "\\%").replace("_", "\\_")

_PHONE_UNMASK_ROLES = {"admin", "leader", "data_entry"}


def _mask_phone(phone: str | None, current_user=None) -> str | None:
    """Mask phone for non-privileged roles: show first 3 digits + '***'."""
    if not phone or not current_user or current_user.role in _PHONE_UNMASK_ROLES:
        return phone
    return phone[:3] + "***" if len(phone) >= 3 else "***"


router = APIRouter(prefix="/customers", tags=["customers"])


def require_customer_write(current_user: User = Depends(get_current_user)) -> User:
    """Only admin, accountant, sales (data_entry/leader) can create/update customers."""
    if current_user.role not in ("admin", "accountant", "sales", "data_entry", "leader"):
        raise HTTPException(
            status_code=403,
            detail="Không có quyền chỉnh sửa thông tin khách hàng",
        )
    return current_user


@router.get("")
async def list_customers(
    type: str | None = None,
    search: str | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
):
    """List all customers."""
    q = select(Customer).order_by(Customer.created_at.desc())
    if type:
        q = q.where(Customer.type == type)
    if search:
        escaped = _escape_like(search)
        q = q.where(
            Customer.name.ilike(f"%{escaped}%", escape="\\") | Customer.phone.ilike(f"%{escaped}%", escape="\\")
        )

    # Count total (before pagination)
    count_q = select(func.count()).select_from(q.subquery())
    total = (await db.execute(count_q)).scalar() or 0

    q = q.offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(q)
    customers = result.scalars().all()

    items = []
    for c in customers:
        resp = CustomerResponse.model_validate(c).model_dump()
        resp["phone"] = _mask_phone(resp.get("phone"), current_user)
        items.append(resp)
    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": (total + page_size - 1) // page_size,
    }


@router.get("/{customer_id}")
async def get_customer(
    customer_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get customer detail with linked projects."""
    if current_user.role not in ("admin", "executive", "leader", "accountant", "data_entry", "supervisor"):
        raise HTTPException(status_code=403, detail="Không có quyền xem thông tin khách hàng")
    result = await db.execute(select(Customer).where(Customer.id == customer_id))
    customer = result.scalar_one_or_none()
    if not customer:
        raise HTTPException(status_code=404, detail="Khách hàng không tồn tại")

    # Get all projects linked to this customer (direct customer_id or via lead)
    proj_conditions = [Project.customer_id == customer.id]
    if customer.lead_id:
        proj_conditions.append(Project.lead_id == customer.lead_id)

    proj_result = await db.execute(
        select(Project).where(or_(*proj_conditions)).order_by(Project.created_at.desc())
    )
    projects = [
        {"id": p.id, "code": p.code, "name": p.name, "status": p.status,
         "stage": p.stage, "total_value": p.total_value, "spent": p.spent,
         "progress": p.progress, "created_at": p.created_at.isoformat()}
        for p in proj_result.scalars().all()
    ]

    resp = CustomerResponse.model_validate(customer).model_dump()
    resp["phone"] = _mask_phone(resp.get("phone"), current_user)
    resp["projects"] = projects
    resp["project_count"] = len(projects)
    return resp


@router.post("", response_model=CustomerResponse)
async def create_customer(
    data: CustomerCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_customer_write),
):
    """Create new customer."""
    customer = Customer(**data.model_dump())
    db.add(customer)
    await db.flush()
    resp = CustomerResponse.model_validate(customer).model_dump()
    resp["phone"] = _mask_phone(resp.get("phone"), current_user)
    return resp


@router.post("/{customer_id}/generate-portal-link")
async def generate_portal_link(
    customer_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Generate portal link for customer (admin/leader only)."""
    if current_user.role not in ("admin", "leader"):
        raise HTTPException(status_code=403, detail="Không có quyền thực hiện thao tác này")

    result = await db.execute(select(Customer).where(Customer.id == customer_id))
    customer = result.scalar_one_or_none()
    if not customer:
        raise HTTPException(status_code=404, detail="Khách hàng không tồn tại")

    portal_token = str(uuid.uuid4())
    customer.portal_token = portal_token
    customer.portal_enabled = True
    await db.flush()

    return {
        "portal_token": portal_token,
        "portal_url": f"/portal/{portal_token}",
    }


@router.put("/{customer_id}", response_model=CustomerResponse)
async def update_customer(
    customer_id: str,
    data: CustomerUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_customer_write),
):
    """Update customer."""
    result = await db.execute(select(Customer).where(Customer.id == customer_id))
    customer = result.scalar_one_or_none()
    if not customer:
        raise HTTPException(status_code=404, detail="Khách hàng không tồn tại")

    for k, v in data.model_dump(exclude_unset=True).items():
        setattr(customer, k, v)
    customer.updated_at = datetime.now(timezone.utc)
    await db.flush()
    resp = CustomerResponse.model_validate(customer).model_dump()
    resp["phone"] = _mask_phone(resp.get("phone"), current_user)
    return resp
