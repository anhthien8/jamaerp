# JAMA HOME CRM -- Multi-Tenant / Whitelabel Architecture Strategy

> Status: DESIGN DRAFT
> Created: 2026-07-16
> Related: [[JAMA CRM Deployment]]

---

## 1. Current State Summary

The JAMA HOME CRM is a **single-tenant monolith** deployed on Railway (backend) + Vercel (frontend):

| Component | Stack | Hosting |
|-----------|-------|---------|
| Backend API | FastAPI + SQLAlchemy (async) + Alembic | Railway |
| Frontend | Next.js 15, React, TailwindCSS | Vercel |
| Database | PostgreSQL (asyncpg) | Railway |
| Telegram Bot | aiogram 3.x | Railway |
| Zalo Listener | Node.js (zca-js) | Railway |

**33 models** across 22 table files, 8 RBAC roles, 30+ API routers. All data is globally shared -- no tenant boundary exists anywhere in the schema, middleware, or queries.

---

## 2. Architecture Options

### Option A -- Shared Database, tenant_id Column (Phase 1)

**How it works**: Every business table gets a `tenant_id UUID` column referencing a new `tenants` table. All queries are filtered by the current tenant's ID. PostgreSQL Row-Level Security (RLS) provides a second safety net.

**Pros**:
- Cheapest to operate: one database, one Railway service
- Simplest migration from current single-tenant state
- Cross-tenant analytics possible for the platform operator (if desired)
- Single Alembic migration, single backup set

**Cons**:
- Noisy-neighbor risk (one tenant's heavy queries affect all)
- Schema customization per tenant is harder (but feature flags cover most needs)
- Accidental data leak if a query forgets tenant_id (mitigated by RLS)

**When to use**: 1-50 tenants, standard CRM features, no strict data residency requirements.

### Option B -- Schema-per-Tenant (Phase 2)

**How it works**: Each tenant gets its own PostgreSQL schema (e.g., `tenant_jamahome`, `tenant_abc_decor`). Shared tables (`tenants`, `plans`, platform-level `admin_users`) live in a `public` schema. Alembic runs per-schema.

**Pros**:
- Strongest isolation: impossible for a query to leak cross-tenant
- Per-tenant schema migrations (roll out features gradually)
- Easier per-tenant backup/restore
- Compliant with stricter data residency requirements

**Cons**:
- More complex connection management (schema search_path per request)
- Alembic migration complexity (loop per schema)
- Higher memory/connection usage
- More expensive at scale (each schema has its own indexes)

**When to use**: 50+ tenants, enterprise clients requiring isolation guarantees, per-tenant compliance requirements.

### Recommendation

**Start with Option A (Phase 1).** The codebase is at 33 tables -- adding tenant_id is mechanical. Phase 2 migration is designed-in from the start (tenant_id column doubles as the schema selector key).

---

## 3. Phase 1: Shared Database Design

### 3.1 New Tables

#### `tenants` -- Tenant Company Registry

```sql
CREATE TABLE tenants (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    slug          VARCHAR(50) UNIQUE NOT NULL,       -- URL-safe: "jamahome", "abc-decor"
    name          VARCHAR(255) NOT NULL,             -- "JAMA HOME", "ABC Decor"
    domain        VARCHAR(255) UNIQUE,               -- custom domain: "crm.abc-decor.vn"
    logo_url      VARCHAR(500),
    favicon_url   VARCHAR(500),
    primary_color VARCHAR(7) DEFAULT '#3B82F6',      -- hex color
    accent_color  VARCHAR(7) DEFAULT '#10B981',
    tagline       VARCHAR(255),                      -- "Nội thất cao cấp"
    timezone      VARCHAR(50) DEFAULT 'Asia/Ho_Chi_Minh',
    locale        VARCHAR(10) DEFAULT 'vi',

    -- Billing / plan
    plan_id       UUID REFERENCES plans(id),
    status        VARCHAR(20) DEFAULT 'active',      -- active, suspended, trial, cancelled
    trial_ends_at TIMESTAMP,
    billing_email VARCHAR(255),

    -- Limits (cached from plan, overridable per tenant)
    max_users     INTEGER DEFAULT 20,
    max_storage_mb INTEGER DEFAULT 5000,
    max_api_rpm   INTEGER DEFAULT 300,               -- requests per minute

    -- Feature flags (JSON blob)
    features      JSONB DEFAULT '{}',

    -- Metadata
    created_at    TIMESTAMP DEFAULT NOW(),
    updated_at    TIMESTAMP DEFAULT NOW()
);

CREATE INDEX ix_tenants_slug ON tenants(slug);
CREATE INDEX ix_tenants_domain ON tenants(domain);
CREATE INDEX ix_tenants_status ON tenants(status);
```

#### `plans` -- Subscription Plans

```sql
CREATE TABLE plans (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name            VARCHAR(100) NOT NULL,           -- "Starter", "Professional", "Enterprise"
    slug            VARCHAR(50) UNIQUE NOT NULL,
    price_monthly   NUMERIC(12,2) DEFAULT 0,         -- VND/month
    price_yearly    NUMERIC(12,2) DEFAULT 0,
    max_users       INTEGER NOT NULL DEFAULT 20,
    max_storage_mb  INTEGER NOT NULL DEFAULT 5000,
    max_api_rpm     INTEGER NOT NULL DEFAULT 300,
    features        JSONB DEFAULT '{}',              -- available feature flags
    is_active       BOOLEAN DEFAULT true,
    created_at      TIMESTAMP DEFAULT NOW()
);
```

#### `tenant_invites` -- Invitation Links

```sql
CREATE TABLE tenant_invites (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id   UUID REFERENCES tenants(id) NOT NULL,
    email       VARCHAR(255) NOT NULL,
    role        VARCHAR(20) NOT NULL DEFAULT 'data_entry',
    token       VARCHAR(64) UNIQUE NOT NULL,
    invited_by  UUID REFERENCES users(id),
    expires_at  TIMESTAMP NOT NULL,
    used_at     TIMESTAMP,
    created_at  TIMESTAMP DEFAULT NOW()
);
```

### 3.2 Tables Requiring `tenant_id`

Every business-data table needs `tenant_id UUID NOT NULL REFERENCES tenants(id)`. The tables fall into three categories:

**Tier 1 -- Core Business Data (MUST have tenant_id)**

| Table | Model File | Notes |
|-------|-----------|-------|
| `users` | `models/user.py` | Users belong to a tenant |
| `teams` | `models/user.py` | Teams are per-tenant |
| `leads` | `models/lead.py` | Leads are per-tenant |
| `activities` | `models/lead.py` | Activity logs are per-tenant |
| `projects` | `models/project.py` | Projects are per-tenant |
| `tasks` | `models/project.py` | Tasks are per-tenant |
| `task_activities` | `models/project.py` | Task activity logs |
| `customers` | `models/customer.py` | Customers are per-tenant |
| `contracts` | `models/contract.py` | Contracts are per-tenant |
| `quotations` | `models/quotation.py` | Quotations are per-tenant |

**Tier 2 -- Financial / HR Data (MUST have tenant_id)**

| Table | Model File | Notes |
|-------|-----------|-------|
| `transactions` | `models/payroll.py` | Financial transactions |
| `commissions` | `models/payroll.py` | Sales commissions |
| `payrolls` | `models/payroll.py` | Payroll records |
| `salary_advances` | `models/payroll.py` | Salary advance requests |
| `salary_grades` | `models/salary_grade.py` | Salary grade definitions |
| `fixed_costs` | `models/fixed_cost.py` | Fixed cost entries |
| `variable_costs` | `models/variable_cost.py` | Variable cost entries |
| `commission_structures` | `models/commission_structure.py` | Commission rate definitions |
| `attendance_records` | `models/attendance.py` | Attendance records |
| `approval_requests` | `models/approval.py` | Approval workflows |
| `leave_balances` | `models/leave.py` | Leave balance tracking |
| `leave_requests` | `models/leave.py` | Leave requests |

**Tier 3 -- Inventory / Communication / System (MUST have tenant_id)**

| Table | Model File | Notes |
|-------|-----------|-------|
| `materials` | `models/inventory.py` | Material inventory |
| `material_usages` | `models/inventory.py` | Material usage logs |
| `price_items` | `models/pricing.py` | Price catalog |
| `notifications` | `models/notification.py` | In-app notifications |
| `system_settings` | `models/notification.py` | Automation settings (key-value) |
| `audit_logs` | `models/audit.py` | Audit trail |
| `feedbacks` | `models/feedback.py` | Employee feedback |
| `kpi_snapshots` | `models/performance.py` | KPI snapshots |
| `coaching_notes` | `models/performance.py` | Coaching notes |
| `review_cycles` | `models/performance.py` | Review cycles |
| `zalo_session` | `models/zalo.py` | Zalo login state (per-tenant) |
| `zalo_groups` | `models/zalo.py` | Zalo monitored groups |
| `zalo_messages` | `models/zalo.py` | Zalo raw messages |
| `zalo_signals` | `models/zalo.py` | Zalo signals |

**Tier 4 -- Tenant-Scoped Configurations (already have tenant_id via being on the tenants table)**

| Table | Notes |
|-------|-------|
| `plans` | Shared, no tenant_id needed |
| `tenants` | Is the tenant itself |
| `tenant_invites` | Has tenant_id by design |

**Total: 33 existing tables need `tenant_id` added.**

### 3.3 Unique Constraint Changes

Some tables have `UNIQUE` constraints that must become **composite** with `tenant_id`:

| Table | Current Constraint | New Constraint |
|-------|-------------------|---------------|
| `users` | `email UNIQUE` | `(tenant_id, email) UNIQUE` |
| `teams` | `code UNIQUE` | `(tenant_id, code) UNIQUE` |
| `materials` | `code UNIQUE` | `(tenant_id, code) UNIQUE` |
| `contracts` | `code UNIQUE` | `(tenant_id, code) UNIQUE` |
| `quotations` | `code UNIQUE` | `(tenant_id, code) UNIQUE` |
| `projects` | `code UNIQUE` | `(tenant_id, code) UNIQUE` |
| `price_items` | `code UNIQUE` | `(tenant_id, code) UNIQUE` |
| `payrolls` | `(user_id, period) UNIQUE` | `(tenant_id, user_id, period) UNIQUE` |
| `kpi_snapshots` | `(user_id, period) UNIQUE` | `(tenant_id, user_id, period) UNIQUE` |
| `review_cycles` | `(user_id, period) UNIQUE` | `(tenant_id, user_id, period) UNIQUE` |
| `attendance_records` | `(user_id, work_date) UNIQUE` | `(tenant_id, user_id, work_date) UNIQUE` |
| `leave_balances` | `(user_id, year) UNIQUE` | `(tenant_id, user_id, year) UNIQUE` |
| `zalo_groups` | `zalo_group_id UNIQUE` | `(tenant_id, zalo_group_id) UNIQUE` |
| `zalo_session` | id='default' (singleton) | id=tenant_id (one per tenant) |

**Impact**: Alembic must DROP old unique constraints and CREATE new composite ones. This is a multi-step migration (see Implementation Plan).

### 3.4 Row-Level Security (RLS) Strategy

PostgreSQL RLS provides a **defense-in-depth** layer. Even if application code forgets to filter by tenant_id, the database enforces it.

```sql
-- Enable RLS on all business tables
ALTER TABLE leads ENABLE ROW LEVEL SECURITY;
ALTER TABLE projects ENABLE ROW LEVEL SECURITY;
-- ... (all 33 tables)

-- Policy: session variable approach
-- The app sets app.current_tenant_id per connection/transaction
CREATE POLICY tenant_isolation_leads ON leads
    USING (tenant_id = current_setting('app.current_tenant_id')::uuid);

CREATE POLICY tenant_isolation_projects ON projects
    USING (tenant_id = current_setting('app.current_tenant_id')::uuid);

-- For users table (special: super_admin can see all)
CREATE POLICY tenant_isolation_users ON users
    USING (
        tenant_id = current_setting('app.current_tenant_id')::uuid
        OR current_setting('app.current_user_role', true) = 'platform_admin'
    );
```

**How to set the session variable**:

In `database.py`, modify the session factory to inject tenant_id after acquiring a connection:

```python
@event.listens_for(engine.sync_engine, "connect")
def _set_tenant_context(dbapi_connection, connection_record):
    # Will be set per-request via middleware
    connection_record.info["tenant_id"] = None
```

In the tenant middleware (new file `middleware/tenant.py`):

```python
from sqlalchemy import event, text

async def set_tenant_on_session(session: AsyncSession, tenant_id: str):
    """Set PostgreSQL session variable for RLS."""
    await session.execute(text(f"SET app.current_tenant_id = '{tenant_id}'"))
```

### 3.5 JWT Token Changes

The current JWT payload:

```json
{
  "sub": "user-uuid",
  "role": "admin",
  "department": "EXEC",
  "exp": 1234567890
}
```

Must become:

```json
{
  "sub": "user-uuid",
  "tenant_id": "tenant-uuid",
  "tenant_slug": "jamahome",
  "role": "admin",
  "department": "EXEC",
  "exp": 1234567890
}
```

**Impact**: All existing tokens become invalid after migration. Users must re-login. This is acceptable for a major version upgrade.

### 3.6 Tenant Resolution Order

The backend must identify the tenant from each request. Resolution order:

1. **Custom domain** (Phase 2): `Host: crm.abc-decor.vn` -> look up `tenants.domain`
2. **Subdomain**: `jamahome.crm.phanmemvip.shop` -> look up `tenants.slug`
3. **Path prefix**: `/api/v1/t/jamahome/leads` -> look up `tenants.slug`
4. **JWT claim**: `tenant_id` in the token (for authenticated requests)
5. **Header**: `X-Tenant-ID: <uuid>` (for API-to-API calls from Telegram bot / Zalo listener)

**Phase 1 uses options 3, 4, and 5.** Subdomain/custom domain requires DNS configuration and wildcard SSL.

### 3.7 Whitelabel Customization

The `tenants` table stores branding:

```json
{
  "slug": "jamahome",
  "name": "JAMA HOME",
  "logo_url": "/uploads/jamahome/logo.png",
  "primary_color": "#3B82F6",
  "accent_color": "#10B981",
  "tagline": "Noi that cao cap"
}
```

Frontend resolves tenant from subdomain or login response, applies CSS variables:

```typescript
// lib/tenant.ts
export function applyTenantBranding(tenant: TenantConfig) {
  document.documentElement.style.setProperty('--color-primary', tenant.primary_color);
  document.documentElement.style.setProperty('--color-accent', tenant.accent_color);
  if (tenant.favicon_url) {
    document.querySelector('link[rel="icon"]')?.setAttribute('href', tenant.favicon_url);
  }
  document.title = `${tenant.name} CRM`;
}
```

### 3.8 Feature Flags Per Tenant

Stored as JSONB in `tenants.features`:

```json
{
  "modules": {
    "leads": true,
    "projects": true,
    "inventory": true,
    "hr": true,
    "payroll": true,
    "zalo_listener": false,
    "telegram_bot": true,
    "ai_copilot": true,
    "instant_quote": true,
    "kpi": true,
    "p_and_l": true,
    "attendance": true,
    "approvals": true,
    "leave": true
  },
  "limits": {
    "max_leads_per_month": 500,
    "max_projects_active": 50,
    "ai_requests_per_day": 100
  },
  "custom_roles": [
    {
      "slug": "showroom_manager",
      "label": "Quan ly Showroom",
      "permissions": ["leads.read", "leads.write", "customers.read"]
    }
  ],
  "pipeline_stages": ["new", "interested", "survey_scheduled", "potential", "signed_design", "lost"],
  "lead_sources": ["facebook", "zalo", "website", "referral", "tiktok", "other"],
  "currency": "VND",
  "vat_rate": 10
}
```

The API checks feature flags before serving endpoints:

```python
# middleware/feature_gate.py
def require_feature(feature_key: str):
    """Dependency that checks tenant feature flag."""
    async def check(tenant: Tenant = Depends(get_current_tenant)):
        features = tenant.features or {}
        modules = features.get("modules", {})
        if not modules.get(feature_key, False):
            raise HTTPException(403, f"Feature '{feature_key}' not enabled for this tenant")
    return check
```

### 3.9 Custom Role Definitions

The 8 built-in roles (admin, executive, leader, data_entry, accountant, purchasing, designer, pm) remain as base roles. Tenants can define **custom roles** via `features.custom_roles`:

```json
{
  "custom_roles": [
    {
      "slug": "showroom_manager",
      "label": "Quản lý Showroom",
      "extends": "leader",
      "permissions": [
        "leads.read", "leads.write", "leads.assign",
        "customers.read", "customers.write",
        "inventory.read",
        "quotations.read", "quotations.write"
      ]
    }
  ]
}
```

Custom roles inherit from a base role and add/restrict specific permissions. The RBAC system (`middleware/rbac.py`) checks:

1. Is the user's role a built-in role? -> Use existing logic
2. Is it a custom role? -> Look up in `tenant.features.custom_roles`, evaluate permissions

### 3.10 Billing & Limits

| Plan | Max Users | Storage | API RPM | Features |
|------|-----------|---------|---------|----------|
| **Starter** | 10 | 2 GB | 100 | Leads, Projects, Customers, basic Accounting |
| **Professional** | 30 | 10 GB | 300 | + HR, Payroll, Inventory, Telegram Bot, KPI |
| **Enterprise** | 100 | 50 GB | 1000 | + Zalo Listener, AI Copilot, Instant Quote, Custom Roles, API Access |

**Enforcement points**:

1. **User limit**: Checked in `POST /api/v1/users` (create user endpoint)
2. **Storage limit**: Checked in file upload endpoints (survey photos, task files)
3. **API rate limit**: New middleware using Redis (or in-memory for small tenants):

```python
# middleware/rate_limiter.py
async def rate_limit_middleware(request: Request, call_next):
    tenant = request.state.tenant
    if not tenant:
        return await call_next(request)
    rpm_key = f"rpm:{tenant.id}:{current_minute()}"
    current = await redis.incr(rpm_key)
    if current == 1:
        await redis.expire(rpm_key, 60)
    if current > tenant.max_api_rpm:
        return JSONResponse(429, {"detail": "Rate limit exceeded"})
    return await call_next(request)
```

---

## 4. Phase 2: Schema-per-Tenant Migration Path

### When to Migrate

Trigger Phase 2 when any of:
- More than 50 active tenants
- A tenant requests data residency isolation (e.g., government contract)
- Query performance degrades due to table bloat (large tenant skews indexes)
- Compliance requirement for physical data separation

### How Schema-per-Tenant Works

1. Each tenant gets a PostgreSQL schema: `tenant_<slug>`
2. Shared `public` schema holds: `tenants`, `plans`, `platform_admins`
3. Connection pool selects schema via `SET search_path TO tenant_<slug>, public`
4. Alembic runs migrations per-schema in a loop
5. RLS is removed (schema boundary replaces it)

### Migration Steps (Phase 1 -> Phase 2)

1. Create schema per tenant: `CREATE SCHEMA tenant_jamahome`
2. `pg_dump` with `--schema=public` and filter to tenant's rows
3. Load into tenant schema
4. Update connection factory to set `search_path` based on tenant
5. Run Alembic per schema
6. Update RLS policies (or remove, since schemas provide isolation)

**This is a planned future migration, not part of Phase 1.**

---

## 5. Service-Level Changes

### 5.1 Telegram Bot

Currently: One bot token, all users share the same bot.

Multi-tenant approach:
- **Option A (Recommended)**: One shared bot, tenant resolved from `telegram_user_id` -> `users.tenant_id`
- **Option B**: One bot per tenant (complex, requires multiple bot tokens)

For Option A:
- Bot stores tenant context per user after /auth
- All API calls include `X-Tenant-ID` header
- Bot greeting message includes tenant name/branding

### 5.2 Zalo Listener

Currently: One Zalo account, one ingest service.

Multi-tenant approach:
- Each tenant can have its own Zalo listener (separate ingest service instance)
- Or: one shared listener, tenant resolved from `zalo_group.tenant_id`
- The `zalo_session` table becomes per-tenant (id = tenant_id instead of 'default')

### 5.3 File Storage

Currently: Files stored locally or referenced by URL.

Multi-tenant approach:
- Path convention: `uploads/<tenant_slug>/...`
- Survey photos: `uploads/<tenant_slug>/survey_photos/<lead_id>/...`
- Task files: `uploads/<tenant_slug>/task_files/<task_id>/...`
- Logos/branding: `uploads/<tenant_slug>/branding/...`
- S3/R2 bucket structure: `s3://jama-crm-uploads/<tenant_slug>/...`

### 5.4 Background Workers

The `worker.py` (background tasks like automation, BOD reports, payroll generation) must be tenant-aware:

```python
async def run_automation_cycle():
    """Run automation for all active tenants."""
    tenants = await get_active_tenants()
    for tenant in tenants:
        async with get_tenant_session(tenant.id) as db:
            await run_followup_reminders(db, tenant)
            await run_lead_recall(db, tenant)
            await run_payment_reminders(db, tenant)
```

---

## 6. Security Considerations

### 6.1 Data Isolation Layers (Defense in Depth)

| Layer | Mechanism | Prevents |
|-------|-----------|----------|
| **L1: Application** | Every query includes `WHERE tenant_id = ?` | 99% of cases |
| **L2: Middleware** | `get_current_tenant` dependency injects tenant_id | Forgotten filters |
| **L3: PostgreSQL RLS** | `SET app.current_tenant_id` per session | SQL injection, raw queries |
| **L4: Database Roles** | Separate DB user per tenant (Phase 2) | Superuser mistakes |

### 6.2 Auth Isolation

- Users authenticate against their tenant (email scoped to tenant)
- JWT includes tenant_id -- cannot be used across tenants
- Login endpoint verifies `user.tenant_id == resolved_tenant.id`
- Tenant admins cannot see/manage other tenants' users

### 6.3 Platform Admin (Super Admin)

A separate `platform_admins` table (not tenant-scoped) for the SaaS operator:

```sql
CREATE TABLE platform_admins (
    id UUID PRIMARY KEY,
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    created_at TIMESTAMP DEFAULT NOW()
);
```

Platform admins can:
- Create/suspend/delete tenants
- View cross-tenant analytics
- Manage plans and billing
- Access any tenant's data (for support)

---

## 7. API Route Changes

### 7.1 Path Prefix Strategy

All existing routes gain a tenant context. Two approaches:

**Approach A: Tenant in JWT only (Recommended for Phase 1)**

Routes stay the same: `/api/v1/leads`, `/api/v1/projects`, etc. Tenant is resolved from the JWT's `tenant_id` claim. No URL changes needed.

- Pros: Minimal frontend changes, backward compatible
- Cons: Cannot serve multiple tenants from the same authenticated session (not needed for CRM)

**Approach B: Tenant in URL path**

Routes become: `/api/v1/t/{tenant_slug}/leads`, `/api/v1/t/{tenant_slug}/projects`

- Pros: Explicit tenant in every request, cacheable per tenant
- Cons: Every API call in frontend/bot/ingest must change

**Decision: Use Approach A.** The CRM use case does not require cross-tenant sessions.

### 7.2 New API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/v1/platform/tenants` | GET | List all tenants (platform admin) |
| `/api/v1/platform/tenants` | POST | Create tenant |
| `/api/v1/platform/tenants/{id}` | PUT | Update tenant |
| `/api/v1/platform/tenants/{id}/suspend` | POST | Suspend tenant |
| `/api/v1/platform/plans` | GET | List plans |
| `/api/v1/tenant/settings` | GET | Get current tenant settings |
| `/api/v1/tenant/settings` | PUT | Update tenant settings (tenant admin) |
| `/api/v1/tenant/branding` | GET | Get branding config |
| `/api/v1/tenant/branding` | PUT | Update branding |
| `/api/v1/tenant/features` | GET | Get feature flags |
| `/api/v1/tenant/usage` | GET | Get usage stats (users, storage) |
| `/api/v1/tenant/invite` | POST | Invite user by email |
| `/api/v1/tenant/accept/{token}` | POST | Accept invitation |
| `/api/v1/tenant/users` | GET | List tenant users |
| `/api/v1/auth/register-tenant` | POST | Self-service tenant registration |

---

## 8. Frontend Multi-Tenant Changes

### 8.1 Tenant Resolution

On load, the frontend resolves the tenant:

1. From subdomain: `jamahome.crm.phanmemvip.shop` -> slug = "jamahome"
2. From the login response (which includes tenant branding)
3. Stored in `localStorage` as `jama_tenant`

### 8.2 Dynamic Branding

```typescript
// lib/tenant.ts
export interface TenantConfig {
  id: string;
  slug: string;
  name: string;
  logo_url: string | null;
  primary_color: string;
  accent_color: string;
  tagline: string | null;
  features: Record<string, boolean>;
}

export function getTenantFromHost(): string | null {
  if (typeof window === 'undefined') return null;
  const host = window.location.hostname;
  // jamahome.crm.phanmemvip.shop -> jamahome
  const parts = host.split('.');
  if (parts.length >= 3) return parts[0];
  return null;
}
```

### 8.3 Feature-Gated Navigation

The sidebar/navigation reads from `tenant.features.modules`:

```typescript
const NAV_ITEMS = [
  { label: 'Tong quan', path: '/', feature: null },                    // always shown
  { label: 'Lead', path: '/leads', feature: 'leads' },
  { label: 'Du an', path: '/projects', feature: 'projects' },
  { label: 'Khach hang', path: '/customers', feature: 'customers' },
  { label: 'Bao gia', path: '/quotations', feature: 'quotations' },
  { label: 'Hop dong', path: '/contracts', feature: 'contracts' },
  { label: 'Ton kho', path: '/inventory', feature: 'inventory' },
  { label: 'Ke toan', path: '/accounting', feature: 'accounting' },
  { label: 'Nhan su', path: '/hr', feature: 'hr' },
  { label: 'Luong', path: '/payroll', feature: 'payroll' },
  { label: 'Cham cong', path: '/attendance', feature: 'attendance' },
  { label: 'KPI', path: '/kpi', feature: 'kpi' },
  { label: 'Zalo', path: '/zalo', feature: 'zalo_listener' },
  { label: 'Cai dat', path: '/settings', feature: null },
].filter(item => !item.feature || tenant.features.modules[item.feature]);
```

---

## 9. Database Migration Strategy

### 9.1 Migration Sequence

The migration is executed as a single Alembic migration with multiple phases:

**Step 1**: Create `plans` and `tenants` tables
**Step 2**: Insert default tenant ("JAMA HOME") and default plan ("Enterprise")
**Step 3**: Add `tenant_id UUID` nullable column to all 33 tables
**Step 4**: Backfill all existing rows with default tenant's ID
**Step 5**: Set `tenant_id NOT NULL` on all tables
**Step 6**: Drop old unique constraints, create new composite unique constraints
**Step 7**: Add new indexes including tenant_id
**Step 8**: Enable RLS policies on all tables
**Step 9**: Update foreign key relationships

### 9.2 Zero-Downtime Approach

Since the system is deployed on Railway with a single instance:

1. Deploy migration alongside app (Alembic runs at startup)
2. Step 3 (nullable tenant_id) is backward compatible -- existing queries still work
3. Step 4 (backfill) runs as a single UPDATE per table
4. Step 5 (NOT NULL) only runs after Step 4 confirms all rows have tenant_id
5. Step 6 (unique constraints) may cause brief locks -- acceptable for single-tenant current state

### 9.3 Rollback Plan

Each step has a corresponding DOWN migration:
- Step 5 DOWN: Remove NOT NULL constraint
- Step 4 DOWN: Set tenant_id to NULL (data loss warning)
- Step 3 DOWN: DROP tenant_id column
- Step 2 DOWN: DELETE default tenant and plan
- Step 1 DOWN: DROP tenants and plans tables

---

## 10. Testing Strategy

### 10.1 Tenant Isolation Tests

```python
async def test_tenant_a_cannot_see_tenant_b_leads():
    """Verify cross-tenant data isolation."""
    # Create lead for tenant A
    # Login as tenant B user
    # GET /leads should return 0 results
    # GET /leads/{tenant_a_lead_id} should return 404
```

### 10.2 RLS Enforcement Tests

```python
async def test_rls_blocks_cross_tenant_raw_query():
    """Even raw SQL should be blocked by RLS."""
    # Set session to tenant A
    # Raw SELECT on leads WHERE tenant_id = tenant_b_id -> 0 rows
```

### 10.3 Feature Flag Tests

```python
async def test_disabled_module_returns_403():
    tenant.features = {"modules": {"leads": False}}
    response = await client.get("/api/v1/leads")
    assert response.status_code == 403
```

---

## 11. Deployment Architecture

```
                           +------------------+
                           |   Vercel (FE)    |
                           |  Next.js 15      |
                           |  *.vercel.app    |
                           +--------+---------+
                                    |
                           +--------v---------+
                           | Railway (BE)     |
                           | FastAPI          |
                           | + Worker         |
                           | + Telegram Bot   |
                           +--------+---------+
                                    |
                           +--------v---------+
                           | Railway (DB)     |
                           | PostgreSQL       |
                           | + RLS enabled    |
                           +------------------+
```

For custom domains per tenant:
```
crm.abc-decor.vn  -> CNAME -> cname.vercel-dns.com -> Vercel
api.abc-decor.vn  -> CNAME -> Railway public domain
```

Vercel supports multi-domain via the `domains` API. Railway supports custom domains via CNAME.

---

## 12. Risks & Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Query misses tenant_id filter | High (during migration) | Data leak | RLS as safety net |
| Unique constraint migration fails | Medium | Downtime | Run in maintenance window, test on staging first |
| Performance degradation | Low (<50 tenants) | Slow queries | Add tenant_id to all indexes, monitor with pg_stat |
| Tenant exceeds limits | Medium | Resource abuse | Rate limiter + usage monitoring + alerts |
| Breaking change for existing users | Certain | Login required | Show maintenance banner, auto-redirect to login |
| Telegram bot cross-tenant confusion | Low | Wrong data | Bot caches tenant_id per user, validates on each call |
