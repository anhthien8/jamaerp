# Module: HR & Payroll (Nhân sự & Bảng lương)

## Overview

The HR & Payroll module manages employee profiles, salary grades, payroll generation with Vietnamese tax/insurance compliance (BHXH, BHYT, BHTN, PIT), salary advances, and payslip distribution. It integrates with Attendance for work days and with the Approval engine for payroll approval workflows.

## Use Case Diagram

```mermaid
graph TB
    subgraph Actors
        AccountantActor["Kế toán"]
        AdminActor["Admin"]
        EmployeeActor["Nhân viên"]
        LeaderActor["Leader"]
        SystemActor["Hệ thống"]
    end

    subgraph HRUseCases["HR Use Cases"]
        UC1["Quản lý hồ sơ nhân viên"]
        UC2["Thêm nhân viên mới"]
        UC3["Vô hiệu hóa / nghỉ việc"]
        UC4["Quản lý bậc lương"]
        UC5["Ủy quyền phê duyệt"]
        UC6["Xem danh sách nhân viên"]
    end

    subgraph PayrollUseCases["Payroll Use Cases"]
        UC7["Tạo bảng lương kỳ"]
        UC8["Duyệt bảng lương"]
        UC9["Gửi phiếu lương"]
        UC10["Xem phiếu lương cá nhân"]
        UC11["Đăng ký tạm ứng lương"]
        UC12["Duyệt tạm ứng"]
        UC13["Quản lý cấu trúc hoa hồng"]
    end

    AccountantActor --> UC1
    AccountantActor --> UC4
    AccountantActor --> UC7
    AccountantActor --> UC8
    AccountantActor --> UC9
    AccountantActor --> UC13

    AdminActor --> UC2
    AdminActor --> UC3
    AdminActor --> UC6

    EmployeeActor --> UC10
    EmployeeActor --> UC11

    LeaderActor --> UC6
    LeaderActor --> UC12

    SystemActor --> UC7
```

## Roles (8 total)

| Role | Vietnamese | Department | Key Permissions |
|------|-----------|-----------|----------------|
| `admin` | Quản trị viên | EXEC | Full system access |
| `executive` | Giám đốc | EXEC | View all reports, dashboards |
| `leader` | Trưởng nhóm | SALES/DESIGN/PM | Team management, approve requests |
| `data_entry` | Nhân viên nhập liệu | SALES | CRM data entry |
| `accountant` | Kế toán | ACCT | Finance, payroll, accounting |
| `purchasing` | Thu mua | ACCT | Inventory, pricing |
| `designer` | Thiết kế viên | DESIGN | Design tasks |
| `pm` | Quản lý dự án | PM | Project management |

## Payroll Generation Flow

```mermaid
sequenceDiagram
    autonumber
    participant A as Accountant
    participant PE as Payroll Engine
    participant AS as Attendance Service
    participant DB as Database
    participant AE as Approval Engine
    participant E as Employee

    A->>PE: generate_period(period="2026-07")
    PE->>DB: Check if period already locked

    PE->>DB: DELETE old drafts

    loop Mỗi nhân viên active
        PE->>DB: GET User + SalaryGrade
        PE->>AS: month_summary(user_id, period)
        AS-->>PE: work_days, ot_hours

        PE->>PE: build_payroll_row()
        Note over PE: base_salary × (work_days / 22)
        Note over PE: + ot_pay (hourly × ot_hours × 1.5)
        Note over PE: + commission (approved)
        Note over PE: - BHXH NLĐ (8+1.5+1% capped)
        Note over PE: - PIT (lũy tiến 7 bậc)
        Note over PE: - advance_deduction

        PE->>DB: INSERT Payroll (status=draft)
    end

    A->>A: Review bảng lương
    A->>AE: Submit cho duyệt

    Note over AE: Approval flow<br/>(Leader → Admin)

    AE->>PE: Side-effect: status → approved
    A->>PE: Mark as paid
    PE->>E: Gửi phiếu lương qua Telegram DM
```

## Salary Computation Formula

```mermaid
flowchart TD
    A["Lương cơ bản<br/>(base_salary từ SalaryGrade)"] --> B["Lương theo công<br/>= base × (work_days / 22)"]

    C["OT Pay<br/>= (base/22/8) × ot_hours × 1.5"] --> D["Tổng thu nhập (Gross)"]
    B --> D
    E["Hoa hồng (approved)"] --> D
    F["Thưởng + Phụ cấp"] --> D

    D --> G["BHXH NLĐ<br/>= (8+1.5+1%) × min(base, trần)"]
    D --> H["Thu nhập tính thuế<br/>= Gross - BHXH - giảm trừ bản thân<br/>- (người phụ thuộc × 4.4M)"]

    H --> I["Thuế TNCN (PIT)<br/>Biểu lũy tiến 7 bậc"]

    D --> J["Net Salary<br/>= Gross - BHXH - PIT - tạm ứng"]
    G --> J
    I --> J
```

## PIT Brackets (Vietnamese Personal Income Tax)

| Bracket | Taxable Income (VND/month) | Rate |
|---------|---------------------------|------|
| 1 | 0 - 5,000,000 | 5% |
| 2 | 5,000,001 - 10,000,000 | 10% |
| 3 | 10,000,001 - 18,000,000 | 15% |
| 4 | 18,000,001 - 32,000,000 | 20% |
| 5 | 32,000,001 - 52,000,000 | 25% |
| 6 | 52,000,001 - 80,000,000 | 30% |
| 7 | > 80,000,000 | 35% |

## Deductions

| Deduction | Rate | Cap |
|-----------|------|-----|
| BHXH (Social Insurance) - Employee | 8% | Trần lương BHXH (46.8M default) |
| BHYT (Health Insurance) - Employee | 1.5% | Same cap |
| BHTN (Unemployment) - Employee | 1% | Same cap |
| BHXH - Company | 21.5% | Same cap |
| Personal deduction | 11,000,000 VND/month | Configurable |
| Dependent deduction | 4,400,000 VND/person/month | Configurable |

## Payroll Status Flow

```mermaid
stateDiagram-v2
    [*] --> draft: generate_period()

    draft --> pending_approval: Submit cho duyệt

    pending_approval --> approved: Duyệt thành công
    pending_approval --> draft: Từ chối (sửa lại)

    approved --> paid: Đánh dấu đã trả

    paid --> [*]: Gửi phiếu lương

    note right of draft
        Kế toán sửa bonus/allowance
        Xem trước net salary
    end note

    note right of approved
        Kỳ lương bị khóa
        Không sửa attendance/OT
    end note
```

## Salary Advance Flow

```mermaid
sequenceDiagram
    autonumber
    participant E as Nhân viên
    participant S as System
    participant AE as Approval Engine
    participant L as Leader
    participant PE as Payroll Engine

    E->>S: Đăng ký tạm ứng (amount, reason)
    S->>AE: create_request(type="advance")
    AE->>L: Notify [Chờ duyệt]

    L->>AE: Approve
    AE->>S: Side-effect: status → approved
    S->>E: Notify [Đã duyệt]

    Note over PE: Khi generate payroll kỳ sau
    PE->>S: SUM(SalaryAdvance WHERE status=approved)
    PE->>PE: advance_deduction = sum
    PE->>S: SalaryAdvance.status → deducted
    PE->>S: salary_advance.period_deducted = period
```

## Payslip Format (Telegram DM)

```
Phiếu lương kỳ 2026-07 — Nguyễn Văn A

Lương cơ bản: 15,000,000đ
Công thực tế: 22/22 ngày
Tăng ca (8h): +1,363,636đ
Hoa hồng: +2,500,000đ
Tổng thu nhập (gross): 18,863,636đ

BHXH/BHYT/BHTN: -1,575,000đ
Thuế TNCN: -836,364đ
Trừ tạm ứng: -3,000,000đ

THỰC LĨNH: 13,452,272đ

Phiếu lương bảo mật — vui lòng không chia sẻ.
```

## Data Model

```mermaid
erDiagram
    SalaryGrade {
        uuid id PK
        string grade_name
        float base_salary
        float bhxh_rate "10.5% default"
        float bhxh_company_rate "21.5%"
        float bhyt_rate "1.5%"
        float bhtn_rate "1.0%"
        date effective_date
    }

    Payroll {
        uuid id PK
        uuid user_id FK
        string period "YYYY-MM"
        float base_salary
        float commission_total
        float bonus
        float deductions
        float net_salary
        float work_days
        float standard_days "22"
        float ot_hours
        float ot_pay
        float allowance
        float bhxh_employee
        float bhxh_company
        float pit
        float taxable_income
        float advance_deduction
        float gross_salary
        uuid salary_grade_id
        uuid approved_by
        datetime paid_at
        datetime payslip_sent_at
        string status "draft|pending_approval|approved|paid"
    }

    SalaryAdvance {
        uuid id PK
        uuid user_id FK
        float amount
        string reason
        string status "pending|approved|deducted|rejected|cancelled"
        uuid approval_id
        string period_deducted "YYYY-MM"
    }

    User }o--o| SalaryGrade : "grade"
    User ||--o{ Payroll : "monthly payslips"
    User ||--o{ SalaryAdvance : "advances"
    Payroll }o--o| ApprovalRequest : "approval"
    SalaryAdvance }o--o| ApprovalRequest : "approval"
```

## API Endpoints

| Method | Endpoint | Description | Roles |
|--------|----------|-------------|-------|
| GET | `/hr/employees` | List employees | Admin, Accountant, Leader |
| POST | `/hr/employees` | Create employee | Admin |
| PUT | `/hr/employees/{id}` | Update employee | Admin |
| PUT | `/hr/employees/{id}/resign` | Mark resignation | Admin |
| POST | `/hr/employees/{id}/undo-resign` | Undo resignation | Admin |
| GET | `/salary-grades` | List salary grades | Admin, Accountant |
| POST | `/salary-grades` | Create salary grade | Admin |
| PUT | `/salary-grades/{id}` | Update salary grade | Admin |
| GET | `/payroll?period=YYYY-MM` | List payroll records | Accountant, Admin |
| POST | `/payroll/generate?period=YYYY-MM` | Generate payroll | Accountant |
| PUT | `/payroll/{id}` | Update bonus/allowance | Accountant |
| POST | `/payroll/submit?period=YYYY-MM` | Submit for approval | Accountant |
| POST | `/payroll/{id}/pay` | Mark as paid | Accountant |
| POST | `/payroll/send-payslips?period=YYYY-MM` | Send via Telegram | Accountant |
| GET | `/payroll/me?period=YYYY-MM` | My payslip | All employees |
| POST | `/salary-advances` | Request advance | All employees |
| GET | `/salary-advances` | List advances | All (own), Accountant (all) |

## Frontend Pages

- `/hr` — Employee directory
- `/hr/salary-grades` — Salary grade management
- `/payroll` — Payroll period management
- `/payroll/me` — My payslip

## Tags

#module #hr #payroll #salary #tax #bhxh #jama-home
