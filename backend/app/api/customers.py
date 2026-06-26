"""Customers API — CRUD for converted clients."""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.auth import get_current_user
from app.models.user import User
from app.models.customer import Customer
from app.models.project import Project
from app.schemas.customer import CustomerCreate, CustomerUpdate, CustomerResponse

router = APIRouter(prefix="/customers", tags=["customers"])


@router.get("", response_model=list[CustomerResponse])
async def list_customers(
    type: str | None = None,
    search: str | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List all customers."""
    q = select(Customer).order_by(Customer.created_at.desc())
    if type:
        q = q.where(Customer.type == type)
    if search:
        q = q.where(
            Customer.name.ilike(f"%{search}%") | Customer.phone.ilike(f"%{search}%")
        )
    result = await db.execute(q)
    customers = result.scalars().all()
    return [CustomerResponse.model_validate(c) for c in customers]


@router.get("/{customer_id}")
async def get_customer(
    customer_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get customer detail with linked projects."""
    result = await db.execute(select(Customer).where(Customer.id == customer_id))
    customer = result.scalar_one_or_none()
    if not customer:
        raise HTTPException(status_code=404, detail="Khách hàng không tồn tại")

    # Get linked projects via lead_id
    projects = []
    if customer.lead_id:
        proj_result = await db.execute(
            select(Project).where(Project.lead_id == customer.lead_id)
        )
        proj = proj_result.scalars().all()
        projects = [
            {"id": p.id, "code": p.code, "name": p.name, "status": p.status,
             "total_value": p.total_value, "progress": p.progress}
            for p in proj
        ]

    resp = CustomerResponse.model_validate(customer).model_dump()
    resp["projects"] = projects
    return resp


@router.post("", response_model=CustomerResponse)
async def create_customer(
    data: CustomerCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create new customer."""
    customer = Customer(**data.model_dump())
    db.add(customer)
    await db.flush()
    return CustomerResponse.model_validate(customer)


@router.put("/{customer_id}", response_model=CustomerResponse)
async def update_customer(
    customer_id: str,
    data: CustomerUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
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
    return CustomerResponse.model_validate(customer)
