# JAMA HOME CRM -- Multi-Tenant Implementation Plan

> Status: READY FOR EXECUTION
> Created: 2026-07-16
> Related: [[Multi-Tenant Strategy]]

---

## Overview

This document details the step-by-step implementation of Phase 1 multi-tenancy for the JAMA HOME CRM. Each section maps to specific file changes, migration steps, and testing requirements.

Estimated effort: 5-7 working days for a single developer familiar with the codebase.

---

## Phase 1 Implementation Steps

### Step 1: New Model -- Tenant & Plan

**Files to create:**
- `backend/app/models/tenant.py`
- `backend/app/schemas/tenant.py`

**File to modify:**
- `backend/app/models/__init__.py` (add imports)

#### `backend/app/models/tenant.py`

Create three new SQLAlchemy models:

```python
"""Tenant & Plan models -- multi-tenant registry."""

import uuid
from datetime import datetime, timezone

from sqlalchemy import String, Text, Integer, Float, Boolean, DateTime, ForeignKey, JSON, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Plan(Base):
    __tablename__ = "plans"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    slug: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    price_monthly: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    price_yearly: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    max_users: Mapped[int] = mapped_column(Integer, nullable=False, default=20)
    max_storage_mb: Mapped[int] = mapped_column(Integer, nullable=False, default=5000)
    max_api_rpm: Mapped[int] = mapped_column(Integer, nullable=False, default=300)
    features: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))


class Tenant(Base):
    __tablename__ = "tenants"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    slug: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    domain: Mapped[str | None] = mapped_column(String(255), unique=True, nullable=True)
    logo_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    favicon_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    primary_color: Mapped[str] = mapped_column(String(7), nullable=False, default="#3B82F6")
    accent_color: Mapped[str] = mapped_column(String(7), nullable=False, default="#10B981")
    tagline: Mapped[str | None] = mapped_column(String(255), nullable=True)
    timezone: Mapped[str] = mapped_column(String(50), nullable=False, default="Asia/Ho_Chi_Minh")
    locale: Mapped[str] = mapped_column(String(10), nullable=False, default="vi")

    plan_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("plans.id"), nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active")
    trial_ends_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    billing_email: Mapped[str | None] = mapped_column(String(255), nullable=True)

    max_users: Mapped[int] = mapped_column(Integer, nullable=False, default=20)
    max_storage_mb: Mapped[int] = mapped_column(Integer, nullable=False, default=5000)
    max_api_rpm: Mapped[int] = mapped_column(Integer, nullable=False, default=300)

    features: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc)
    )

    plan = relationship("Plan", foreign_keys=[plan_id])

    __table_args__ = (
        Index("ix_tenants_slug", "slug"),
        Index("ix_tenants_domain", "domain"),
        Index("ix_tenants_status", "status"),
    )


class TenantInvite(Base):
    __tablename__ = "tenant_invites"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id: Mapped[str] = mapped_column(String(36), ForeignKey("tenants.id"), nullable=False)
    email: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(20), nullable=False, default="data_entry")
    token: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    invited_by: Mapped[str | None] = mapped_column(String(36), ForeignKey("users.id"), nullable=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    used_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))

    tenant = relationship("Tenant", foreign_keys=[tenant_id])
```

#### `backend/app/schemas/tenant.py`

Create Pydantic schemas for tenant API endpoints (TenantResponse, TenantCreate, TenantUpdate, PlanResponse, etc.).

#### Update `backend/app/models/__init__.py`

Add imports for `Plan`, `Tenant`, `TenantInvite` to the models package init.

---

### Step 2: Add `tenant_id` Column to All Business Models

**Files to modify (22 model files):**

| File | Models to modify |
|------|-----------------|
| `backend/app/models/user.py` | `User`, `Team` |
| `backend/app/models/lead.py` | `Lead`, `Activity` |
| `backend/app/models/project.py` | `Project`, `Task`, `TaskActivity` |
| `backend/app/models/payroll.py` | `Transaction`, `Commission`, `Payroll`, `SalaryAdvance` |
| `backend/app/models/customer.py` | `Customer` |
| `backend/app/models/inventory.py` | `Material`, `MaterialUsage` |
| `backend/app/models/salary_grade.py` | `SalaryGrade` |
| `backend/app/models/fixed_cost.py` | `FixedCost` |
| `backend/app/models/variable_cost.py` | `VariableCost` |
| `backend/app/models/commission_structure.py` | `CommissionStructure` |
| `backend/app/models/notification.py` | `Notification`, `SystemSetting` |
| `backend/app/models/pricing.py` | `PriceItem` |
| `backend/app/models/audit.py` | `AuditLog` |
| `backend/app/models/attendance.py` | `AttendanceRecord` |
| `backend/app/models/approval.py` | `ApprovalRequest` |
| `backend/app/models/leave.py` | `LeaveBalance`, `LeaveRequest` |
| `backend/app/models/performance.py` | `KpiSnapshot`, `CoachingNote`, `ReviewCycle` |
| `backend/app/models/zalo.py` | `ZaloSession`, `ZaloGroup`, `ZaloMessage`, `ZaloSignal` |
| `backend/app/models/contract.py` | `Contract` |
| `backend/app/models/quotation.py` | `Quotation` |
| `backend/app/models/feedback.py` | `Feedback` |

**For every model**, add:

```python
# At the top of the column definitions
tenant_id: Mapped[str] = mapped_column(
    String(36), ForeignKey("tenants.id"), nullable=False, index=True
)
```

**Unique constraint changes** -- update `__table_args__` for each model that has unique constraints. Example for `User`:

```python
# Before
# email: unique=True in column definition

# After -- remove unique=True from column, add composite unique in __table_args__
__table_args__ = (
    Index("ix_users_role_dept", "role", "department"),
    Index("ix_users_tenant_email", "tenant_id", "email", unique=True),
)
```

**For SystemSetting** (currently uses `key` as primary key):

```python
# Before
key: Mapped[str] = mapped_column(String(50), primary_key=True)

# After
id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
tenant_id: Mapped[str] = mapped_column(String(36), ForeignKey("tenants.id"), nullable=False)
key: Mapped[str] = mapped_column(String(50), nullable=False)
# Unique constraint: (tenant_id, key)
```

**For ZaloSession** (currently singleton with id='default'):

```python
# Before
id: Mapped[str] = mapped_column(String(36), primary_key=True, default="default")

# After
id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
tenant_id: Mapped[str] = mapped_column(String(36), ForeignKey("tenants.id"), nullable=False, unique=True)
```

---

### Step 3: Alembic Migration

**File to create:**
- `backend/alembic/versions/i01_2026a001_multi_tenant.py`

The migration script must execute in this order:

1. Create `plans` table
2. Create `tenants` table
3. Create `tenant_invites` table
4. Insert default plan ("Enterprise", slug="enterprise")
5. Insert default tenant (slug="jamahome", name="JAMA HOME", plan=enterprise)
6. For each of the 33 business tables:
   a. Add nullable `tenant_id UUID` column
   b. `UPDATE <table> SET tenant_id = '<default_tenant_id>'`
   c. `ALTER TABLE <table> ALTER COLUMN tenant_id SET NOT NULL`
   d. Create index `ix_<table>_tenant_id`
7. Drop old unique constraints, create new composite unique constraints with tenant_id
8. Enable RLS and create policies on all business tables

**Key migration snippet** (conceptual):

```python
"""Multi-tenant: add plans, tenants, tenant_id to all tables.

Revision ID: i01_2026a001
"""
from alembic import op
import sqlalchemy as sa

revision = "i01_2026a001"
down_revision = "h09_2026a001"  # current head

def upgrade():
    # 1. Create plans
    op.create_table("plans", ...)

    # 2. Create tenants
    op.create_table("tenants", ...)

    # 3. Create tenant_invites
    op.create_table("tenant_invites", ...)

    # 4-5. Insert default plan + tenant
    op.execute("""
        INSERT INTO plans (id, name, slug, max_users, max_storage_mb, max_api_rpm)
        VALUES ('00000000-0000-0000-0000-000000000001', 'Enterprise', 'enterprise', 100, 51200, 1000)
    """)
    op.execute("""
        INSERT INTO tenants (id, slug, name, plan_id, max_users, max_storage_mb, max_api_rpm, features)
        VALUES (
            '00000000-0000-0000-0000-000000000001',
            'jamahome', 'JAMA HOME',
            '00000000-0000-0000-0000-000000000001',
            100, 51200, 1000,
            '{"modules": {"leads":true,"projects":true,"customers":true,...}}'::jsonb
        )
    """)

    DEFAULT_TENANT = "'00000000-0000-0000-0000-000000000001'"

    # 6. Add tenant_id to all tables
    tables = [
        "users", "teams", "leads", "activities", "projects", "tasks", "task_activities",
        "transactions", "commissions", "payrolls", "salary_advances",
        "customers", "materials", "material_usages",
        "salary_grades", "fixed_costs", "variable_costs", "commission_structures",
        "notifications", "price_items", "audit_logs",
        "attendance_records", "approval_requests", "leave_balances", "leave_requests",
        "kpi_snapshots", "coaching_notes", "review_cycles",
        "zalo_groups", "zalo_messages", "zalo_signals",
        "contracts", "quotations", "feedbacks",
    ]

    for table in tables:
        op.add_column(table, sa.Column("tenant_id", sa.String(36), nullable=True))
        op.execute(f"UPDATE {table} SET tenant_id = {DEFAULT_TENANT}")
        op.alter_column(table, "tenant_id", nullable=False)
        op.create_index(f"ix_{table}_tenant_id", table, ["tenant_id"])
        op.create_foreign_key(
            f"fk_{table}_tenant_id", table, "tenants", ["tenant_id"], ["id"]
        )

    # Special: system_settings needs restructuring
    # (key was PK, now needs composite (tenant_id, key))
    # ... handled separately

    # Special: zalo_session needs tenant_id as unique (one session per tenant)
    # ... handled separately

    # 7. Drop old unique constraints, add new composite
    # Example for users.email:
    op.drop_index("ix_users_email")  # or drop constraint
    op.create_index("ix_users_tenant_email", "users", ["tenant_id", "email"], unique=True)

    # Repeat for all unique constraints listed in Strategy doc section 3.3

    # 8. Enable RLS
    for table in tables:
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"""
            CREATE POLICY tenant_isolation_{table} ON {table}
            USING (tenant_id = current_setting('app.current_tenant_id')::uuid)
        """)


def downgrade():
    # Reverse order: drop RLS, drop tenant_id columns, drop tenant tables
    for table in reversed(tables):
        op.execute(f"DROP POLICY IF EXISTS tenant_isolation_{table} ON {table}")
        op.execute(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY")
        op.drop_index(f"ix_{table}_tenant_id", table)
        op.drop_constraint(f"fk_{table}_tenant_id", table, type_="foreignkey")
        op.drop_column(table, "tenant_id")

    op.drop_table("tenant_invites")
    op.drop_table("tenants")
    op.drop_table("plans")
```

---

### Step 4: Tenant Middleware & Context

**Files to create:**
- `backend/app/middleware/tenant.py`
- `backend/app/context.py`

**Files to modify:**
- `backend/app/main.py` (register middleware)
- `backend/app/database.py` (add tenant-aware session)

#### `backend/app/middleware/tenant.py`

```python
"""Tenant resolution middleware -- extracts tenant from JWT or header."""

from fastapi import Request, HTTPException
from sqlalchemy import select
from app.models.tenant import Tenant
from app.database import async_session


async def resolve_tenant(request: Request) -> Tenant | None:
    """Resolve tenant from request. Order:
    1. X-Tenant-ID header (for service-to-service: Telegram bot, Zalo ingest)
    2. JWT tenant_id claim (for authenticated user requests)
    3. Subdomain (future)
    """
    # 1. Header-based (service calls)
    tenant_id = request.headers.get("X-Tenant-ID")
    if tenant_id:
        async with async_session() as db:
            result = await db.execute(select(Tenant).where(Tenant.id == tenant_id))
            tenant = result.scalar_one_or_none()
            if not tenant or tenant.status != "active":
                raise HTTPException(400, "Invalid tenant")
            return tenant

    # 2. JWT-based (user requests) -- resolved after auth in get_current_user
    # Return None here; auth middleware will attach tenant
    return None
```

#### `backend/app/context.py`

```python
"""Request-scoped tenant context."""

from contextvars import ContextVar

# Set by middleware, read by any module
current_tenant_id: ContextVar[str | None] = ContextVar("current_tenant_id", default=None)
current_tenant_slug: ContextVar[str | None] = ContextVar("current_tenant_slug", default=None)
```

#### Modify `backend/app/middleware/auth.py`

Update `create_access_token` to include tenant_id:

```python
def create_access_token(user_id: str, role: str, department: str, tenant_id: str, tenant_slug: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES)
    payload = {
        "sub": user_id,
        "tenant_id": tenant_id,
        "tenant_slug": tenant_slug,
        "role": role,
        "department": department,
        "exp": expire,
    }
    return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)
```

Update `get_current_user` to validate tenant:

```python
async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_db),
) -> User:
    payload = decode_token(credentials.credentials)
    user_id = payload.get("sub")
    tenant_id = payload.get("tenant_id")

    if not user_id or not tenant_id:
        raise HTTPException(status_code=401, detail="Token invalid")

    # Set tenant context for RLS
    from app.context import current_tenant_id, current_tenant_slug
    current_tenant_id.set(tenant_id)
    current_tenant_slug.set(payload.get("tenant_slug"))

    result = await db.execute(
        select(User).where(User.id == user_id, User.tenant_id == tenant_id)
    )
    user = result.scalar_one_or_none()

    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="Account not found or disabled")

    return user
```

#### Modify `backend/app/database.py`

Add RLS session setup:

```python
async def get_db():
    """FastAPI dependency -- yields async DB session with tenant RLS context."""
    async with async_session() as session:
        try:
            # Set RLS context if tenant is available
            from app.context import current_tenant_id
            tenant_id = current_tenant_id.get()
            if tenant_id:
                await session.execute(text(f"SET LOCAL app.current_tenant_id = '{tenant_id}'"))

            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


def get_tenant_session(tenant_id: str):
    """Factory for tenant-scoped sessions (used by workers/automation)."""
    async def _get_db():
        async with async_session() as session:
            try:
                await session.execute(text(f"SET LOCAL app.current_tenant_id = '{tenant_id}'"))
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise
            finally:
                await session.close()
    return _get_db
```

---

### Step 5: Update Auth API

**File to modify:**
- `backend/app/api/auth.py`

Changes:
1. Login endpoint: verify user belongs to resolved tenant
2. Token includes tenant_id and tenant_slug
3. Telegram auth: resolve tenant from telegram_user_id's user record
4. New endpoint: `POST /auth/register-tenant` (self-service signup)
5. New endpoint: `GET /auth/me` returns tenant info alongside user

#### Login endpoint changes:

```python
@router.post("/login", response_model=TokenResponse)
async def login(request: Request, data: UserLogin, db: AsyncSession = Depends(get_db)):
    client_ip = request.client.host if request.client else "unknown"
    _check_login_rate_limit(client_ip)

    # If tenant is known (e.g., from subdomain), filter by tenant
    # For now, email lookup is global but user MUST belong to the resolved tenant
    result = await db.execute(select(User).where(User.email == data.email))
    user = result.scalar_one_or_none()

    if not user or not verify_password(data.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    if not user.is_active:
        raise HTTPException(status_code=403, detail="Account disabled")

    # Fetch tenant
    tenant_result = await db.execute(select(Tenant).where(Tenant.id == user.tenant_id))
    tenant = tenant_result.scalar_one_or_none()
    if not tenant or tenant.status != "active":
        raise HTTPException(status_code=403, detail="Tenant suspended")

    token = create_access_token(
        str(user.id), user.role, user.department,
        str(tenant.id), tenant.slug
    )
    return TokenResponse(
        access_token=token,
        user=UserResponse.model_validate(user),
        tenant=TenantBrief.model_validate(tenant),  # new field
    )
```

---

### Step 6: Update Seed Script

**File to modify:**
- `backend/app/seed.py`

The seed script must:
1. Seed plans (if none exist)
2. Seed default tenant (if none exist)
3. All seeded users, teams, leads, etc. must include `tenant_id = default_tenant.id`

```python
async def seed_database(db: AsyncSession):
    result = await db.execute(select(User).limit(1))
    if result.scalar_one_or_none():
        return  # Already seeded

    # 1. Seed plans
    enterprise_plan = Plan(
        name="Enterprise", slug="enterprise",
        max_users=100, max_storage_mb=51200, max_api_rpm=1000,
        features={"modules": {ALL_MODULES_ENABLED}}
    )
    db.add(enterprise_plan)
    await db.flush()

    # 2. Seed default tenant
    default_tenant = Tenant(
        slug="jamahome", name="JAMA HOME",
        plan_id=enterprise_plan.id,
        max_users=100, max_storage_mb=51200, max_api_rpm=1000,
        features={...FULL_FEATURE_SET...}
    )
    db.add(default_tenant)
    await db.flush()

    tenant_id = default_tenant.id

    # 3. All existing seed data gets tenant_id
    team_exec = Team(id=_id(), name="Ban Giam Doc", code="BGD",
                     department="EXEC", tenant_id=tenant_id)
    # ... all other seed data ...
```

---

### Step 7: Update All API Routers

**30+ files in `backend/app/api/`**

Every query in every router must include `tenant_id` filtering. The pattern:

```python
# Before
result = await db.execute(select(Lead).where(Lead.assigned_to == user.id))

# After -- filter by tenant_id
result = await db.execute(
    select(Lead).where(Lead.tenant_id == user.tenant_id, Lead.assigned_to == user.id)
)
```

For create operations:

```python
# Before
lead = Lead(name=data.name, phone=data.phone, ...)

# After
lead = Lead(name=data.name, phone=data.phone, tenant_id=current_user.tenant_id, ...)
```

**Complete list of API files to modify:**

| File | Complexity | Notes |
|------|-----------|-------|
| `api/auth.py` | HIGH | Login, telegram auth, tenant registration |
| `api/leads.py` | MEDIUM | Add tenant_id filter to all queries |
| `api/projects.py` | MEDIUM | Add tenant_id filter to all queries |
| `api/dashboard.py` | MEDIUM | All aggregation queries |
| `api/accounting.py` | MEDIUM | Financial queries |
| `api/ai.py` | LOW | No direct DB queries (uses services) |
| `api/users.py` | MEDIUM | User CRUD, team management |
| `api/customers.py` | MEDIUM | Customer CRUD |
| `api/contracts.py` | MEDIUM | Contract CRUD |
| `api/quotations.py` | MEDIUM | Quotation CRUD |
| `api/inventory.py` | MEDIUM | Material CRUD |
| `api/pl.py` | MEDIUM | P&L aggregation |
| `api/salary_grades.py` | LOW | Simple CRUD |
| `api/fixed_costs.py` | LOW | Simple CRUD |
| `api/variable_costs.py` | LOW | Simple CRUD |
| `api/commission_structures.py` | LOW | Simple CRUD |
| `api/telegram_workflow.py` | MEDIUM | Telegram bot endpoints |
| `api/notifications.py` | LOW | Filter by user's tenant |
| `api/automation.py` | MEDIUM | Automation settings per tenant |
| `api/ai_settings.py` | LOW | AI settings per tenant |
| `api/backup.py` | LOW | Backup settings per tenant |
| `api/instant_quote.py` | MEDIUM | Price items per tenant |
| `api/hr.py` | MEDIUM | Resignation, transfers |
| `api/kpi.py` | MEDIUM | KPI aggregation |
| `api/zalo.py` | HIGH | Zalo session per tenant |
| `api/feedback.py` | LOW | Simple CRUD |
| `api/audit.py` | LOW | Audit logs per tenant |
| `api/attendance.py` | MEDIUM | Attendance records |
| `api/approvals.py` | MEDIUM | Approval workflows |
| `api/leaves.py` | MEDIUM | Leave management |
| `api/payroll.py` | HIGH | Payroll generation per tenant |

**Helper pattern** -- create a base query helper to reduce boilerplate:

```python
# backend/app/middleware/tenant.py
from sqlalchemy import Select
from app.database import Base

def tenant_filter(query: Select, model: type[Base], tenant_id: str) -> Select:
    """Apply tenant_id filter to a query if the model has tenant_id."""
    if hasattr(model, "tenant_id"):
        return query.where(model.tenant_id == tenant_id)
    return query
```

Usage in routers:

```python
from app.middleware.tenant import tenant_filter

@router.get("/leads")
async def list_leads(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = select(Lead)
    query = tenant_filter(query, Lead, current_user.tenant_id)
    result = await db.execute(query)
    return result.scalars().all()
```

---

### Step 8: Update Services Layer

**Files to modify:**
- `backend/app/services/approval_engine.py`
- `backend/app/services/attendance_service.py`
- `backend/app/services/audit.py`
- `backend/app/services/automation.py`
- `backend/app/services/backup_service.py`
- `backend/app/services/bod_report.py`
- `backend/app/services/instant_quote.py`
- `backend/app/services/kpi_engine.py`
- `backend/app/services/llm_config.py`

Each service that queries the database must accept and use `tenant_id`.

---

### Step 9: Update Agents

**Files to modify:**
- `backend/app/agents/lead_intake.py`
- `backend/app/agents/lead_scoring.py`
- `backend/app/agents/sales_copilot.py`
- `backend/app/agents/task_coordinator.py`
- `backend/app/agents/insight_agent.py`

Each agent that creates or reads data must be tenant-aware.

---

### Step 10: Update Worker

**File to modify:**
- `backend/app/worker.py`

The background worker must iterate over tenants:

```python
async def run_all_automation():
    """Run automation for each active tenant."""
    async with async_session() as db:
        result = await db.execute(
            select(Tenant).where(Tenant.status == "active")
        )
        tenants = result.scalars().all()

    for tenant in tenants:
        try:
            async with async_session() as db:
                # Set tenant context
                await db.execute(text(f"SET LOCAL app.current_tenant_id = '{tenant.id}'"))
                await run_automation_for_tenant(db, tenant)
        except Exception as e:
            logger.error(f"Automation failed for tenant {tenant.slug}: {e}")
```

---

### Step 11: Update Telegram Bot

**Files to modify:**
- `telegram-bot/bot/api_client.py`
- `telegram-bot/bot/main.py`
- All handler files in `telegram-bot/bot/handlers/`

The bot's API client must include tenant context:

```python
class ApiClient:
    def __init__(self, base_url: str):
        self.base_url = base_url
        self._tenant_cache: dict[int, str] = {}  # telegram_user_id -> tenant_id

    async def _get_tenant_id(self, telegram_user_id: int) -> str | None:
        """Get tenant_id for a telegram user (cached)."""
        if telegram_user_id in self._tenant_cache:
            return self._tenant_cache[telegram_user_id]
        # First call: resolve via auth endpoint
        data = await self.post("/auth/telegram", json={
            "telegram_user_id": telegram_user_id
        })
        if data and "user" in data:
            tenant_id = data["user"].get("tenant_id")
            self._tenant_cache[telegram_user_id] = tenant_id
            return tenant_id
        return None

    async def request(self, method, endpoint, telegram_user_id, **kwargs):
        headers = kwargs.pop("headers", {})
        tenant_id = await self._get_tenant_id(telegram_user_id)
        if tenant_id:
            headers["X-Tenant-ID"] = tenant_id
        # ... standard request logic
```

---

### Step 12: Update Zalo Listener

**Files to modify:**
- `zalo-listener/src/` (main API client)

The ingest service sends `X-Tenant-ID` header when pushing messages. The tenant_id is configured as an environment variable per listener instance, or resolved from the group configuration.

---

### Step 13: Update Frontend

**Files to create:**
- `frontend/src/lib/tenant.ts`

**Files to modify:**
- `frontend/src/lib/api.ts` (API client includes tenant context)
- `frontend/src/lib/auth.tsx` (login returns tenant, store tenant info)
- `frontend/src/app/layout.tsx` (apply tenant branding)
- `frontend/src/app/login/page.tsx` (show tenant name/logo)
- Sidebar/navigation components (feature-gated)

#### `frontend/src/lib/tenant.ts`

```typescript
export interface TenantConfig {
  id: string;
  slug: string;
  name: string;
  logo_url: string | null;
  favicon_url: string | null;
  primary_color: string;
  accent_color: string;
  tagline: string | null;
  features: {
    modules: Record<string, boolean>;
    limits: Record<string, number>;
    custom_roles: Array<{
      slug: string;
      label: string;
      extends: string;
      permissions: string[];
    }>;
    currency: string;
    vat_rate: number;
  };
}

export function getStoredTenant(): TenantConfig | null {
  if (typeof window === 'undefined') return null;
  const stored = localStorage.getItem('jama_tenant');
  if (!stored) return null;
  try { return JSON.parse(stored); } catch { return null; }
}

export function storeTenant(tenant: TenantConfig) {
  localStorage.setItem('jama_tenant', JSON.stringify(tenant));
  applyBranding(tenant);
}

export function applyBranding(tenant: TenantConfig) {
  document.documentElement.style.setProperty('--color-primary', tenant.primary_color);
  document.documentElement.style.setProperty('--color-accent', tenant.accent_color);
  if (tenant.favicon_url) {
    const link = document.querySelector('link[rel="icon"]') as HTMLLinkElement;
    if (link) link.href = tenant.favicon_url;
  }
  document.title = `${tenant.name} CRM`;
}

export function isFeatureEnabled(feature: string): boolean {
  const tenant = getStoredTenant();
  if (!tenant) return true; // default: all features enabled
  return tenant.features?.modules?.[feature] ?? false;
}
```

#### Modify `frontend/src/lib/auth.tsx`

Add tenant to login response handling:

```typescript
const login = async (email: string, password: string) => {
  // ... existing logic ...
  const data = await api.login(email, password);
  setUser(data.user);
  if (data.tenant) {
    storeTenant(data.tenant);
  }
  // ...
};
```

#### Modify `frontend/src/lib/api.ts`

Add `TenantBrief` type to `TokenResponse`:

```typescript
export interface TokenResponse {
  access_token: string;
  user: User;
  tenant?: TenantConfig;  // new field
}
```

---

### Step 14: Platform Admin API

**Files to create:**
- `backend/app/api/platform.py`
- `backend/app/models/platform_admin.py`
- `backend/app/schemas/platform_admin.py`

**File to modify:**
- `backend/app/main.py` (register platform router)

The platform admin endpoints manage tenants, plans, and cross-tenant operations. Protected by a separate auth flow (platform_admin token, not tenant-scoped).

---

### Step 15: Tenant Admin API

**Files to create:**
- `backend/app/api/tenant_admin.py`

**File to modify:**
- `backend/app/main.py` (register tenant admin router)

Endpoints for tenant admins to manage their own tenant:
- Update branding (logo, colors)
- View/manage feature flags
- Invite users
- View usage stats
- Manage subscription

---

### Step 16: Update Alembic env.py

**File to modify:**
- `backend/alembic/env.py`

Add new model imports so Alembic autogenerate can detect the new tables:

```python
from app.models.tenant import Plan, Tenant, TenantInvite  # noqa
```

---

### Step 17: Update Tests

**Files to modify:**
- `backend/tests/conftest.py` (create test tenant in fixtures)
- `backend/tests/test_auth_rbac.py` (tenant-aware auth tests)
- All other test files

Add new test file:
- `backend/tests/test_multi_tenant.py`

Key test cases:
1. Tenant A cannot read Tenant B's leads
2. RLS blocks cross-tenant raw queries
3. Login returns correct tenant
4. User creation respects tenant user limits
5. Feature-gated endpoints return 403 when feature disabled
6. Platform admin can access any tenant
7. Tenant invite flow works end-to-end

---

## Implementation Order & Dependencies

```
Week 1:
  Day 1: Steps 1-3 (models, migration) -- foundation
  Day 2: Step 4 (middleware/context) -- tenant resolution
  Day 3: Step 5-6 (auth, seed) -- auth flow with tenant

Week 2:
  Day 4-5: Step 7 (all API routers) -- bulk of the work
  Day 5: Steps 8-10 (services, agents, worker)

Week 3:
  Day 6: Steps 11-12 (Telegram bot, Zalo listener)
  Day 7: Step 13 (frontend)
  Day 7: Steps 14-17 (platform admin, tenant admin, tests, alembic)
```

---

## Quick Reference: Files Changed

### New Files (to create)

| File | Purpose |
|------|---------|
| `backend/app/models/tenant.py` | Plan, Tenant, TenantInvite models |
| `backend/app/schemas/tenant.py` | Tenant Pydantic schemas |
| `backend/app/middleware/tenant.py` | Tenant resolution + context helpers |
| `backend/app/context.py` | ContextVar for tenant_id |
| `backend/app/api/platform.py` | Platform admin endpoints |
| `backend/app/models/platform_admin.py` | PlatformAdmin model |
| `backend/app/schemas/platform_admin.py` | Platform admin schemas |
| `backend/app/api/tenant_admin.py` | Tenant admin endpoints |
| `backend/alembic/versions/i01_2026a001_multi_tenant.py` | Migration script |
| `frontend/src/lib/tenant.ts` | Frontend tenant utilities |
| `backend/tests/test_multi_tenant.py` | Tenant isolation tests |

### Modified Files (33 model files + 30 API files + services + frontend)

**Models (22 files)**: Add `tenant_id` column + update unique constraints
**API (30+ files)**: Add tenant_id filter to all queries
**Middleware (2 files)**: `auth.py`, `rbac.py`
**Core (3 files)**: `database.py`, `main.py`, `config.py`
**Services (9 files)**: Tenant-aware queries
**Agents (5 files)**: Tenant-aware operations
**Worker (1 file)**: Per-tenant automation loop
**Frontend (3+ files)**: `api.ts`, `auth.tsx`, `layout.tsx`
**Telegram bot (12+ files)**: API client + handlers
**Zalo listener**: API client
**Tests (18+ files)**: Tenant-aware fixtures + new tests
**Alembic (2 files)**: `env.py` + new migration

---

## Rollback Plan

If multi-tenant migration causes issues:

1. Run `alembic downgrade h09_2026a001` (previous migration)
2. Deploy previous backend version
3. Existing single-tenant data is intact (tenant_id column removed)

**Important**: Test migration on a staging database copy before production.
