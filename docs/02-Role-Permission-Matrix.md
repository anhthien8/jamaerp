# Role-Permission Matrix

> **Source of truth**: `frontend/src/lib/roles.ts` + backend API RBAC checks
> **Last Updated**: 2026-07-16

---

## Role Definitions

| Role Key | Vietnamese Label | English Label | Typical User |
|----------|-----------------|---------------|-------------|
| `admin` | Giam doc | Director / Admin | Company owner, C-level |
| `leader` | Truong phong | Team Leader | Sales team leads, department heads |
| `data_entry` | Nhan vien Sale | Sales Staff | Junior salespeople, lead collectors |
| `accountant` | Ke toan / Nhan su | Accountant / HR | Finance team, HR staff |
| `executive` | Ban Quan Tri | Executive Board | Non-operational board members |
| `purchasing` | Nhan vien Thu mua | Procurement Staff | Material buyers, suppliers liaison |
| `designer` | Nhan vien Thiet ke | Designer | Interior/architectural designers |
| `pm` | Truong Du an | Project Manager | Construction project leads |

---

## Dashboard Access

| Role | Dashboard Type | Visible Metrics |
|------|---------------|----------------|
| admin | Executive | Total leads, pipeline value, conversion rate, active projects, avg progress, SLA compliance, team performance, overdue leads |
| leader | Team | Team leads, team pipeline, team workload, team conversion |
| data_entry | Personal | Own leads, own pipeline, own weekly KPIs, priority items |
| accountant | Financial | Income/expense summary, payroll status, commission totals |
| executive | Executive | Same as admin (read-only) |
| purchasing | Personal | Assigned tasks, material requests status |
| designer | Personal | Assigned projects, task queue, design deliverables |
| pm | Team | Projects by department, task progress, material requests |

---

## Module Permission Matrix

### Leads & Pipeline

| Permission | admin | leader | data_entry | accountant | executive | purchasing | designer | pm |
|------------|:-----:|:------:|:----------:|:----------:|:---------:|:----------:|:--------:|:--:|
| View Leads | All | Team | Own | None | None | None | None | None |
| Create Lead | Yes | Yes | Yes | No | No | No | No | No |
| Edit Lead | All | Team | Own | No | No | No | No | No |
| Assign Lead | All | Team | No | No | No | No | No | No |
| Change Stage | All | Team | Own | No | No | No | No | No |
| View Pipeline Stats | Yes | Team | Own | No | No | No | No | No |
| View Kanban | Yes | Team | Own | No | No | No | No | No |
| View Workload | Yes | Team | No | No | No | No | No | No |
| Bulk Assign | Yes | Team | No | No | No | No | No | No |
| Bulk Stage Change | Yes | Team | No | No | No | No | No | No |
| Export CSV | Yes | Yes | Yes | No | No | No | No | No |

### Projects & Tasks

| Permission | admin | leader | data_entry | accountant | executive | purchasing | designer | pm |
|------------|:-----:|:------:|:----------:|:----------:|:---------:|:----------:|:--------:|:--:|
| View Projects | All | All | Yes | Read | Yes | Read | Assigned | Yes |
| Create Project | Yes | Yes | No | No | Yes | No | No | Yes |
| Edit Project | Yes | Yes | No | No | No | No | No | Yes |
| Update Stage | Yes | Yes | No | No | No | No | No | Yes |
| View Tasks | All | All | Yes | Read | Yes | Yes | Own | Yes |
| Create Task | Yes | Yes | No | No | No | No | Yes | Yes |
| Edit Task Status | Yes | Yes | No | No | No | Yes | Own | Yes |
| Bulk Assign Tasks | Yes | Yes | No | No | No | No | No | Yes |
| View Task Activities | All | All | Yes | Yes | Yes | Yes | Assigned | Yes |
| Create Task Activity | Yes | Yes | Yes | No | No | Yes | Yes | Yes |

### Accounting & Finance

| Permission | admin | leader | data_entry | accountant | executive | purchasing | designer | pm |
|------------|:-----:|:------:|:----------:|:----------:|:---------:|:----------:|:--------:|:--:|
| View Transactions | Yes | Yes | Yes | Yes | No | No | No | No |
| Create Transaction | Yes | No | No | Yes | No | No | No | No |
| Edit Transaction | Yes | No | No | Yes | No | No | No | No |
| Delete Transaction | Yes | No | No | Yes | No | No | No | No |
| View Commissions | Yes | Yes | Yes | Yes | No | No | No | No |
| Create Commission | Yes | No | No | Yes | No | No | No | No |
| View Payroll (all) | Yes | No | No | Yes | No | No | No | No |
| View P&L | Yes | No | No | Yes | Yes | No | No | No |
| View Salary Grades | Yes | No | No | Yes | No | No | No | No |
| Manage Fixed Costs | Yes | No | No | Yes | No | No | No | No |
| Manage Variable Costs | Yes | No | No | Yes | No | No | No | No |
| Manage Commission Rules | Yes | No | No | Yes | No | No | No | No |

### HR, Attendance & Payroll

| Permission | admin | leader | data_entry | accountant | executive | purchasing | designer | pm |
|------------|:-----:|:------:|:----------:|:----------:|:---------:|:----------:|:--------:|:--:|
| Check-in/out (self) | Yes | Yes | Yes | Yes | Yes | Yes | Yes | Yes |
| View Own Attendance | Yes | Yes | Yes | Yes | Yes | Yes | Yes | Yes |
| View Team Attendance | Yes | Team | No | All | No | No | No | No |
| Edit Attendance | Yes | Team | No | All | No | No | No | No |
| Approve OT | Yes | Team | No | Yes | No | No | No | No |
| Create Leave Request | Yes | Yes | Yes | Yes | Yes | Yes | Yes | Yes |
| View Leave Calendar | Yes | Team | Team | All | Team | Team | Team | Team |
| Generate Payroll | Yes | No | No | Yes | No | No | No | No |
| Edit Payroll Rows | Yes | No | No | Yes | No | No | No | No |
| Submit Payroll | Yes | No | No | Yes | No | No | No | No |
| Approve Payroll | Yes | No | No | No | No | No | No | No |
| Mark Payroll Paid | Yes | No | No | Yes | No | No | No | No |
| Create Salary Advance | Yes | Yes | Yes | Yes | Yes | Yes | Yes | Yes |
| Resignation Processing | Yes | Yes | No | No | No | No | No | No |

### Approval Engine

| Permission | admin | leader | data_entry | accountant | executive | purchasing | designer | pm |
|------------|:-----:|:------:|:----------:|:----------:|:---------:|:----------:|:--------:|:--:|
| View Pending Approvals | Yes | Yes (team) | No | Yes | No | Yes | No | Yes |
| Approve/Reject | Yes (all) | Yes (team) | No | Yes | No | Yes | No | Yes |
| Delegate Approval | Yes | Yes | No | Yes | No | Yes | No | Yes |
| View My Requests | Yes | Yes | Yes | Yes | Yes | Yes | Yes | Yes |
| View Handled History | Yes | Own+acted | Own+acted | Own+acted | Own+acted | Own+acted | Own+acted | Own+acted |

### Inventory

| Permission | admin | leader | data_entry | accountant | executive | purchasing | designer | pm |
|------------|:-----:|:------:|:----------:|:----------:|:---------:|:----------:|:--------:|:--:|
| View Materials | Yes | No | No | Yes | No | Yes | No | No |
| Create/Edit Materials | Yes | No | No | No | No | Yes | No | No |
| Adjust Stock | Yes | No | No | No | No | Yes | No | No |
| Record Usage | Yes | No | No | No | No | Yes | No | No |
| View Low Stock Alerts | Yes | No | No | Yes | No | Yes | No | No |

### KPI & Performance

| Permission | admin | leader | data_entry | accountant | executive | purchasing | designer | pm |
|------------|:-----:|:------:|:----------:|:----------:|:---------:|:----------:|:--------:|:--:|
| View Personal KPI | Yes | Yes | Yes | Yes | Yes | Yes | Yes | Yes |
| View Team KPI | Yes | Team | No | No | Yes | No | No | No |
| View Leaderboard | Yes | Yes | Yes | Yes | Yes | Yes | Yes | Yes |
| Trigger Snapshot | Yes | No | No | No | No | No | No | No |
| Create Coaching Note | Yes | Team | No | No | No | No | No | No |
| Submit Self Review | Yes | Yes | Yes | Yes | Yes | Yes | Yes | Yes |
| Submit Leader Review | Yes | Team | No | No | No | No | No | No |

### Administration

| Permission | admin | leader | data_entry | accountant | executive | purchasing | designer | pm |
|------------|:-----:|:------:|:----------:|:----------:|:---------:|:----------:|:--------:|:--:|
| Manage Users | Yes | No | No | Yes | No | No | No | No |
| View Audit Logs | Yes | No | No | No | No | No | No | No |
| Manage Automation | Yes | No | No | No | Yes | No | No | No |
| Manage BOD Reports | Yes | No | No | No | Yes | No | No | No |
| Backup/Restore | Yes | No | No | No | No | No | No | No |
| Update Payroll Settings | Yes | No | No | Yes | No | No | No | No |

---

## Telegram Bot Command Access

| Command | Requires Role | Auth Method |
|---------|:-------------|:------------|
| `/checkin [project_code]` | Any active user | Telegram user ID mapped to User |
| `/checkout` | Any active user | Telegram user ID |
| `/baocao [project_code]` | Any active user | Telegram user ID |
| `/vatlieu [project_code]` | Any active user | Telegram user ID |
| `/suco [project_code]` | Any active user | Telegram user ID |
| `/duan [project_code]` | Any active user | Telegram user ID |
| `/congcuatoi` | Any active user | Telegram user ID |
| Approve/reject material | admin/accountant/purchasing | Telegram user ID |
| Approve/reject approval | Any delegated approver | Telegram user ID |

---

## Data Scoping Rules

| Role | Leads | Projects | Attendance | Payroll | KPI |
|------|-------|----------|------------|---------|-----|
| admin | All | All | All | All | All |
| leader | Team | All (read) | Team | None | Team |
| data_entry | Own | Assigned (read) | Own | Own payslip | Own |
| accountant | None | Read-only | All (edit) | All | None |
| executive | None | Read | None | None | None |
| purchasing | None | Read-only | Own | Own payslip | Own |
| designer | None | Assigned only | Own | Own payslip | Own |
| pm | None | Assigned | Own | Own payslip | Own |
