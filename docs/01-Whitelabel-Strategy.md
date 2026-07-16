# Whitelabel Strategy

> **Status**: Draft
> **Last Updated**: 2026-07-16
> **Author**: Product Strategy
> **Decision needed by**: 2026-08-15

---

## 1. Executive Summary

JAMA HOME CRM was purpose-built for a single construction/interior design company. Its modular architecture -- 27 independent API routers, config-driven settings via `SystemSetting` key-value store, role-based access with 8 distinct roles, and Telegram bot integration -- makes it a strong candidate for whitelabel deployment across adjacent industries in Vietnam's SME market.

This document proposes a phased whitelabel strategy: start with configurable branding and feature toggles (Phase 1), evolve to multi-tenant SaaS with per-org isolation (Phase 2), and expand to a platform with API access and marketplace integrations (Phase 3).

---

## 2. What Needs to Be Configurable

### 2.1 Branding (Phase 1 -- Quick Wins)

| Config Item | Current State | Required Change |
|-------------|---------------|-----------------|
| App name | Hardcoded `"JAMA HOME CRM"` in `config.py` `APP_NAME` | Already configurable via env var. Add to tenant config DB. |
| Logo | Not configurable | New `TenantConfig` table: `logo_url`, `favicon_url` |
| Primary/secondary colors | Hardcoded in frontend CSS | Extract to CSS variables loaded from tenant config |
| Login page branding | Fixed layout | Dynamic: company name, logo, tagline |
| Email/notification templates | Hardcoded Vietnamese strings | Move to config-driven template system |
| Footer/credits | Hardcoded `"Developer: Duong Anh Thien"` | Configurable or hideable per tenant |
| Currency | VND hardcoded in payroll/commission | Add `currency` + `currency_symbol` to tenant config |
| Locale/language | Vietnamese only (`Asia/Ho_Chi_Minh` timezone) | Extract i18n strings; add locale config |

### 2.2 Feature Toggles (Phase 1)

Current codebase has 13 logical modules. Each should be toggleable per tenant:

| Module | API Routers | Toggle Key | Default |
|--------|------------|------------|---------|
| Leads & Pipeline | `leads` | `module_leads` | ON |
| Projects & Tasks | `projects` | `module_projects` | ON |
| Accounting & Finance | `accounting`, `pl`, `salary_grades`, `fixed_costs`, `variable_costs`, `commission_structures` | `module_finance` | ON |
| HR & Payroll | `hr`, `attendance`, `payroll`, `leaves`, `approvals` | `module_hr` | ON |
| Inventory | `inventory` | `module_inventory` | ON |
| KPI & Performance | `kpi` | `module_kpi` | ON |
| AI Features | `ai`, `ai_settings`, `instant_quote` | `module_ai` | ON |
| Telegram Bot | `telegram_workflow` | `module_telegram` | ON |
| Automation | `automation` | `module_automation` | ON |
| Contracts | `contracts` | `module_contracts` | ON |
| Quotations | `quotations` | `module_quotations` | ON |
| Notifications | `notifications` | `module_notifications` | ON |
| Audit & Backup | `audit`, `backup` | `module_admin` | ON |

Implementation approach:
- Add `enabled_modules` JSON field to `TenantConfig`
- Middleware checks toggle before routing to each module
- Frontend dynamically renders sidebar/navigation based on active modules

### 2.3 Domain-Specific Customization (Phase 1-2)

| Item | Construction (Current) | Real Estate | Interior Design | Manufacturing |
|------|----------------------|-------------|-----------------|---------------|
| Lead pipeline stages | new/interested/survey/potential/signed | inquiry/site-visit/offer/negotiation/closed | inquiry/consultation/proposal/signed | inquiry/specification/bid/won |
| Project stages | design/quotation/procurement/construction/acceptance | land-aq/tpermitting/development/handover | concept/design/production/installation | quotation/procurement/production/delivery |
| Default task templates | 19 construction tasks | 8 real estate tasks | 12 design tasks | 10 manufacturing tasks |
| Material categories | Construction materials | N/A | Furniture/finishes | Raw materials/components |
| KPI formulas | Sales conversion + project completion | Revenue/sqf sold | Design approval rate + on-time delivery | OEE + defect rate |
| Tax rules | Vietnam PIT + BHXH | Same | Same | Same + CIT |

### 2.4 Roles & Permissions (Phase 2)

Current 8 roles are construction-specific. Whitelabel needs configurable roles:

```python
# Proposed: TenantRoleConfig
class TenantRole:
    id: str
    tenant_id: str
    role_key: str          # "admin", "manager", "staff", etc.
    display_name: str      # Localized label
    permissions: dict      # Same shape as ROLE_PERMISSIONS in roles.ts
    dashboard_type: str    # "executive" | "team" | "personal" | "financial"
    is_system: bool        # System roles can't be deleted
```

Industries would start with a template role set:
- **Construction**: admin, leader, data_entry, accountant, executive, purchasing, designer, pm (current)
- **Real estate**: admin, sales_manager, agent, admin_staff, finance, executive
- **Manufacturing**: admin, production_manager, operator, quality, procurement, finance

### 2.5 Workflows (Phase 2)

| Workflow | Current | Configurable Version |
|----------|---------|---------------------|
| Approval chain | Fixed: leader -> admin | Configurable N-step chain with role-based routing |
| Lead auto-assign | Round-robin within team | Strategy selector: round-robin, least-loaded, skill-based, manual |
| Leave approval | Fixed: <=3 days leader, >3 days + admin | Configurable by leave type, department, amount threshold |
| Payroll approval | Accountant -> Admin (2-step) | Configurable chain with optional finance director step |
| Material approval | Accountant/Purchasing/Admin (any) | Configurable: amount thresholds, department routing |

### 2.6 Domain & Email (Phase 2)

| Config | Description |
|--------|-------------|
| `domain` | Custom domain per tenant (e.g., `crm.acme-construction.vn`) |
| `email_from` | Transactional email sender address |
| `email_templates` | JSON-configurable templates for: leave notifications, payroll slips, payment reminders |
| `sms_provider` | Optional SMS integration for OTP/alerts |

---

## 3. Multi-Tenancy Architecture

### Option A: Shared Database, Tenant ID Column (Recommended for Phase 2)

```
┌──────────────────────────────────────────────┐
│              Shared PostgreSQL                │
│  ┌────────────┐  ┌────────────┐  ┌────────┐ │
│  │ leads       │  │ projects   │  │ users  │ │
│  │ tenant_id * │  │ tenant_id *│  │ten_id *│ │
│  └────────────┘  └────────────┘  └────────┘ │
└──────────────────────────────────────────────┘
         * = NOT NULL, indexed, FK to tenants
```

**Pros**:
- Single deployment, lower ops cost
- Shared infra scales economically
- Cross-tenant analytics for platform owner
- Fits Vietnam SME market (most tenants < 200 users)

**Cons**:
- Data leakage risk (mitigated by mandatory `tenant_id` filter in every query)
- Noisy neighbor on shared DB
- Schema migration must be backward-compatible

**Implementation**:
1. Add `tenant_id` column to every table
2. Create `Tenant` model: `id, name, domain, config_json, subscription_tier, status`
3. Middleware injects `tenant_id` filter into every SQLAlchemy query via `@event.listens_for`
4. Database row-level security via PostgreSQL RLS policies

### Option B: Schema-per-Tenant (Phase 3, Enterprise)

Each tenant gets its own PostgreSQL schema within the same database instance.

**Pros**: Stronger isolation, tenant-specific migrations
**Cons**: Schema count limited (~1000 practical), more complex migrations

### Option C: Separate Database per Tenant (Phase 3, Enterprise+)

Each tenant gets a dedicated database on separate instances.

**Pros**: Maximum isolation, independent scaling, independent backup/restore
**Cons**: Highest cost, complex deployment, cold-start issues

### Recommended Phased Approach

| Phase | Architecture | Tenant Count | Cost |
|-------|-------------|-------------|------|
| Phase 2 (MVP) | Shared DB + tenant_id | 1-50 | Low |
| Phase 3 | Schema-per-tenant for enterprise | 50-500 | Medium |
| Phase 4 | Separate DB for enterprise+ | 500+ | High |

---

## 4. Pricing Model

### Tiered SaaS Subscription

| Tier | Price (VND/month) | Target | Included Modules | Limits |
|------|-------------------|--------|-----------------|--------|
| **Starter** | 500,000 (~$20) | Small firm, 1-10 users | Leads, Projects (basic), Attendance | 10 users, 50 leads, 5 projects |
| **Professional** | 2,000,000 (~$80) | Mid-size, 10-50 users | All modules | 50 users, unlimited leads/projects |
| **Enterprise** | 5,000,000 (~$200) | Large, 50-200+ users | All modules + custom roles + API | 200 users, custom domain, priority support |
| **White-label** | Negotiable | Resellers/agencies | Full platform + rebranding | Unlimited tenants, API access |

### Per-Seat Add-ons

| Add-on | Price/user/month |
|--------|-----------------|
| Extra user beyond tier limit | 50,000 VND |
| AI features (scoring + insights) | 30,000 VND |
| Telegram bot integration | 20,000 VND |
| Custom domain | 100,000 VND |

### Annual Discount
- 12-month commitment: 20% off
- 24-month commitment: 30% off

---

## 5. Target Industries

### Priority Matrix

| Industry | Market Size (Vietnam) | Pain Point | JAMA Fit | Priority |
|----------|----------------------|------------|----------|----------|
| **Construction** | 500B+ VND market | Fragmented tools, no unified CRM+PM+HR | Native (current) | P0 -- protect & grow |
| **Interior Design** | 100B+ VND market | Lead-to-project gap, design iteration tracking | 90% fit (sub-stages differ) | P1 -- quick expansion |
| **Real Estate** | 300B+ VND market | Agent management, site-visit tracking, commission | 70% fit (pipeline differs) | P1 -- high revenue |
| **Manufacturing (SME)** | 200B+ VND market | Production tracking, quality, procurement | 60% fit (needs new modules) | P2 -- deeper product |
| **Architecture Firms** | 50B+ VND market | Similar to design, with more compliance | 85% fit | P2 -- niche |
| **Renovation/Remodeling** | Subset of construction | Shorter cycle, material-heavy | 95% fit | P0 -- natural extension |

### Industry Adaptation Effort

| Industry | Pipeline Stages | Task Templates | New Fields | New Modules | Effort |
|----------|----------------|---------------|------------|-------------|--------|
| Renovation | 3 stage tweaks | Minimal | None | None | 1 week |
| Interior Design | 5 stage tweaks | 12 templates | Design file fields | None | 2 weeks |
| Real Estate | Full redesign | 8 templates | Property fields | Property listing | 6 weeks |
| Manufacturing | Full redesign | 10 templates | BOM fields | Production tracking | 12 weeks |

---

## 6. Revenue Opportunities

### 6.1 SaaS Subscriptions (Primary)
- Recurring revenue from tiered subscriptions
- Vietnam SME market: ~500,000 potential businesses with 5+ employees
- Target: 5,000 paying customers within 3 years
- **ARR projection**: 12B VND (~$500K) at Year 3 (conservative)

### 6.2 White-Label Licensing (Secondary)
- License the platform to business consultants, accounting firms, and industry associations
- They rebrand and resell to their client base
- Revenue model: licensing fee + per-tenant rev-share
- **Advantage**: Leverages existing distribution channels

### 6.3 API Access (Tertiary)
- Open API for integrations: accounting software (MISA, Fast), bank feeds, Zalo OA, government portals
- API access tier: 500K VND/month for developers
- Marketplace commission: 15% on third-party integrations

### 6.4 Professional Services
- Implementation packages: 5M-20M VND per tenant setup
- Custom integration consulting: hourly rate
- Training workshops: 2M-5M VND per session

### 6.5 Data & Analytics (Future)
- Aggregated industry benchmarks (anonymized)
- Lead quality scoring across industries
- Market trend reports

---

## 7. Competitive Advantages vs Existing Solutions in Vietnam

### Competitive Landscape

| Solution | Type | Price | Strength | Weakness vs JAMA |
|----------|------|-------|----------|-----------------|
| **Monday.com** | Global SaaS | $8-16/user/mo | Beautiful UI, flexible | No Vietnam localization, no BHXH/PIT, no Telegram |
| **HubSpot** | Global CRM | Free-$800/mo | Best-in-class CRM | Overkill for SME, no project delivery, no HR |
| **Zoho CRM** | Global SaaS | $14-52/user/mo | Affordable, many features | No construction workflow, no Vietnam tax rules |
| **MISA** | Vietnam ERP | Varies | Local compliance | Separate modules, no unified CRM+PM |
| **Base.vn** | Vietnam SaaS | Varies | Local market knowledge | Generic, not construction-focused |
| **Custom Excel** | DIY | Free | Familiar | No automation, no approval workflow, data silos |

### JAMA's Differentiators

1. **Vertical Integration**: CRM + Project Delivery + HR + Payroll + Inventory in one platform. Competitors cover 1-2 of these; none cover all 5 for construction SMEs.

2. **Telegram-First Field Operations**: Construction workers are on Telegram, not desktop. JAMA's bot enables site reporting, material requests, check-in/out, and incident reporting -- all without opening a browser. No competitor does this.

3. **Vietnam Compliance Built-In**: BHXH, BHYT, BHTN calculations, PIT progressive tax tables, mandatory leave tracking per Vietnamese Labor Code. Global CRMs require expensive customization for this.

4. **Approval Engine with Delegation**: Multi-step approval chains (leave, expenses, payroll, material requests) with delegation when absent. Generic tools lack this workflow depth.

5. **AI Scoring on Local Data**: Lead scoring trained on Vietnamese construction market patterns. Not a generic ML model -- tuned for property types, regions, and budget ranges common in Vietnam.

6. **Zero-Friction Onboarding**: SQLite for local dev, PostgreSQL for production. Railway + Vercel for one-click deploy. No DevOps team needed.

7. **Pricing for Vietnam SMEs**: At 500K-5M VND/month, JAMA is 10-50x cheaper than importing global SaaS tools.

---

## 8. Phased Implementation Roadmap

### Phase 1: Whitelabel Foundation (8 weeks)

| Week | Deliverable |
|------|-------------|
| 1-2 | `TenantConfig` model + API + middleware injection |
| 2-3 | Frontend theming system (CSS variables, logo, name) |
| 3-4 | Feature toggle middleware (all 13 modules) |
| 4-5 | Configurable pipeline stages + project stages |
| 5-6 | Configurable role templates (3 industry presets) |
| 6-7 | i18n framework (extract all hardcoded Vietnamese strings) |
| 7-8 | Tenant provisioning API + admin panel |

### Phase 2: Multi-Tenant SaaS (12 weeks)

| Week | Deliverable |
|------|-------------|
| 1-3 | Database schema: add `tenant_id` to all 20+ tables |
| 3-5 | Row-level security + query middleware |
| 5-7 | Subscription management (Stripe integration) |
| 7-9 | Tenant admin console (users, billing, settings) |
| 9-11 | Billing engine (usage tracking, invoicing) |
| 11-12 | Load testing + security audit |

### Phase 3: Platform & Marketplace (16 weeks)

| Week | Deliverable |
|------|-------------|
| 1-4 | Public REST API with API key management |
| 4-8 | Webhook system for event-driven integrations |
| 8-12 | Integration marketplace (MISA, Zalo, bank feeds) |
| 12-16 | White-label reseller portal + onboarding flow |
