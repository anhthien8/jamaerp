# Module: Finance & Accounting (Tài chính & Kế toán)

## Overview

The Finance & Accounting module manages all financial transactions, commission structures, profit & loss reporting, fixed/variable cost tracking, and payroll-related accounting. It provides the Accountant role with tools to manage company finances and generate financial reports.

## Use Case Diagram

```mermaid
graph TB
    subgraph Actors
        AccountantActor["Kế toán"]
        AdminActor["Admin"]
        LeaderActor["Leader"]
        SystemActor["Hệ thống"]
        ExecutiveActor["BOD"]
    end

    subgraph UseCases["Finance Use Cases"]
        UC1["Ghi sổ giao dịch<br/>(income/expense)"]
        UC2["Quản lý chi phí cố định"]
        UC3["Quản lý chi phí biến đổi"]
        UC4["Xem báo cáo P&L"]
        UC5["Quản lý cấu trúc hoa hồng"]
        UC6["Tính & phân bổ hoa hồng"]
        UC7["Xem báo cáo theo dự án"]
        UC8["Duyệt bảng lương"]
        UC9["Xem BOD Dashboard"]
        UC10["Báo cáo doanh thu theo kênh"]
    end

    AccountantActor --> UC1
    AccountantActor --> UC2
    AccountantActor --> UC3
    AccountantActor --> UC4
    AccountantActor --> UC5
    AccountantActor --> UC6
    AccountantActor --> UC7
    AccountantActor --> UC8

    AdminActor --> UC4
    AdminActor --> UC8

    ExecutiveActor --> UC9
    ExecutiveActor --> UC10
    LeaderActor --> UC7
    SystemActor --> UC6
```

## Financial Data Flow

```mermaid
flowchart TB
    subgraph Income["DOANH THU"]
        ContractValue["Giá trị Hợp đồng"]
        DesignFee["Phí thiết kế"]
        ConstructionFee["Phí thi công"]
    end

    subgraph Costs["CHI PHÍ"]
        FixedCosts["Chi phí cố định<br/>Thuê văn phòng, Lương cố định,<br/>Điện nước, Internet..."]
        VariableCosts["Chi phí biến đổi<br/>Vật tư, Nhân công,<br/>Phát sinh dự án..."]
        Commissions["Hoa hồng<br/>Sales, Leader override"]
        PayrollCosts["Lương nhân viên<br/>Gross + BHXH công ty"]
    end

    subgraph Reports["BÁO CÁO"]
        PL["P&L Statement"]
        ProjectCost["Chi phí theo dự án"]
        BODDash["BOD Dashboard"]
    end

    Income --> PL
    Costs --> PL
    ContractValue --> ProjectCost
    VariableCosts --> ProjectCost
    Commissions --> ProjectCost
    PL --> BODDash
```

## Transaction Model

```mermaid
graph LR
    subgraph Types["Loại giao dịch"]
        Income["income<br/>(Thu)"]
        Expense["expense<br/>(Chi)"]
    end

    subgraph Categories["Danh mục"]
        DC["design_contract"]
        CC["construction_contract"]
        MAT["material"]
        LAB["labor"]
        COM["commission"]
        SAL["salary"]
        OTH["other"]
    end

    Income --> DC
    Income --> CC
    Expense --> MAT
    Expense --> LAB
    Expense --> COM
    Expense --> SAL
    Expense --> OTH
```

## Profit & Loss Structure

```mermaid
flowchart TD
    A["DOANH THU THUẦN"] --> B["(-) Giá vốn hàng bán"]
    B --> C["= LÃI GỘP"]

    C --> D["(-) Chi phí hoạt động"]
    D --> E["Chi phí cố định"]
    D --> F["Chi phí nhân sự<br/>(Lương + BHXH công ty)"]
    D --> G["Chi phí bán hàng<br/>(Hoa hồng)"]

    C --> H["= LÃI RÒNG"]
    H --> I["P&L Report"]
```

## Commission Structure

### Types

| Type | Vietnamese | Description |
|------|-----------|-------------|
| `design_commission` | HH Thiết kế | % trên giá trị HĐ thiết kế |
| `construction_commission` | HH Thi công | % trên giá trị HĐ thi công |
| `leader_override` | HH Leader | % override cho leader team |

### Milestones (Payment Schedule)

```mermaid
gantt
    title Lịch thanh toán hoa hồng theo milestone
    dateFormat X
    axisFormat %s%%

    section Milestones
    Ký hợp đồng (50%)       :done, m1, 0, 50
    Nghiệm thu phần thô (30%):active, m2, 50, 80
    Bàn giao (20%)          :m3, 80, 100
```

| Milestone | Vietnamese | Percentage |
|-----------|-----------|------------|
| `signing` | Ký hợp đồng | 50% |
| `rough_complete` | Nghiệm thu phần thô | 30% |
| `handover` | Bàn giao | 20% |

### Commission Flow

```mermaid
sequenceDiagram
    autonumber
    participant PM as Project Manager
    participant S as System
    participant L as Leader
    participant A as Accountant
    participant P as Payroll

    PM->>S: Cập nhật milestone dự án
    S->>S: Detect milestone completion
    S->>S: Tính commission theo rate × base_amount × milestone_pct

    S->>S: Tạo Commission (status=pending)
    L->>S: Review commission
    L->>S: Approve commission
    A->>S: Final review

    Note over P: Khi generate payroll
    P->>S: SUM(commission WHERE status=approved AND period=YYYY-MM)
    S->>P: commission_total
```

## Cost Management

### Fixed Costs (Chi phí cố định)

| Category Examples | Vietnamese |
|------------------|-----------|
| Office rent | Thuê văn phòng |
| Utilities | Điện, nước, internet |
| Software licenses | Phần mềm |
| Insurance | Bảo hiểm tài sản |

### Variable Costs (Chi phí biến đổi)

| Category Examples | Vietnamese |
|------------------|-----------|
| Materials | Vật tư |
| Labor | Nhân công |
| Transportation | Vận chuyển |
| Subcontractors | Thầu phụ |

## BOD Dashboard Metrics

```mermaid
graph TB
    subgraph BOD["BOD Dashboard"]
        Revenue["Doanh thu tháng"]
        Profit["Lãi ròng"]
        Margin["Biên lợi nhuận %"]
        Pipeline["Pipeline value"]
        Projects["Dự án active"]
        Headcount["Nhân sự"]
        CashFlow["Dòng tiền"]
        BurnRate["Burn rate"]
    end
```

## Data Model

```mermaid
erDiagram
    Transaction {
        uuid id PK
        string code
        string type "income|expense"
        string category
        string description
        float amount
        uuid project_id FK
        uuid lead_id FK
        uuid created_by FK
        string status "pending|completed|cancelled"
        datetime date
    }

    Commission {
        uuid id PK
        uuid user_id FK
        uuid project_id FK
        uuid lead_id FK
        string type "design|construction|leader_override"
        float rate
        float base_amount
        float commission_amount
        string milestone "signing|rough_complete|handover"
        float milestone_pct
        string status "pending|approved|paid"
        string period "YYYY-MM"
    }

    FixedCost {
        uuid id PK
        string category
        float amount
        string month "YYYY-MM"
    }

    VariableCost {
        uuid id PK
        string category
        float amount
        uuid project_id
        string month "YYYY-MM"
    }

    CommissionStructure {
        uuid id PK
        string department
        string commission_type
        float rate
        date effective_date
    }

    Transaction }o--o| Project : "linked"
    Commission }o--|| User : "earns"
    Commission }o--o| Project : "from project"
```

## API Endpoints

| Method | Endpoint | Description | Roles |
|--------|----------|-------------|-------|
| GET | `/accounting/transactions` | List transactions | Accountant, Admin |
| POST | `/accounting/transactions` | Create transaction | Accountant |
| PUT | `/accounting/transactions/{id}` | Update transaction | Accountant |
| GET | `/accounting/pl?month=YYYY-MM` | P&L report | Accountant, Admin, Executive |
| GET | `/accounting/project/{id}` | Project financials | Accountant, PM, Leader |
| GET | `/fixed-costs` | List fixed costs | Accountant |
| POST | `/fixed-costs` | Create fixed cost | Accountant |
| GET | `/variable-costs` | List variable costs | Accountant |
| POST | `/variable-costs` | Create variable cost | Accountant |
| GET | `/commissions` | List commissions | Accountant, Admin |
| PUT | `/commissions/{id}/approve` | Approve commission | Leader, Accountant |
| GET | `/commission-structures` | List structures | Accountant |
| POST | `/commission-structures` | Create structure | Accountant |

## Frontend Pages

- `/finance` — Financial overview dashboard
- `/accounting` — Transaction ledger
- `/pl` — Profit & Loss report
- `/finance/fixed-costs` — Fixed cost management
- `/finance/variable-costs` — Variable cost management
- `/reports` — BOD executive reports

## Tags

#module #finance #accounting #commission #pnl #jama-home
