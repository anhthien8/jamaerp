# Module: Projects (Dự án)

## Overview

The Projects module manages the lifecycle of interior design and construction projects, from contract signing through completion. It includes task management per project stage, team assignment (PM, Designer, Sales), financial tracking, and file management.

## Use Case Diagram

```mermaid
graph TB
    subgraph Actors
        PMActor["Project Manager"]
        DesignerActor["Designer"]
        SalesActor["Sales / Data Entry"]
        AccountantActor["Kế toán"]
        AdminActor["Admin"]
        LeaderActor["Leader"]
    end

    subgraph UseCases["Project Use Cases"]
        UC1["Tạo dự án mới<br/>(từ lead signed)"]
        UC2["Cập nhật thông tin dự án"]
        UC3["Quản lý task theo giai đoạn"]
        UC4["Giao task cho nhân viên"]
        UC5["Cập nhật tiến độ task"]
        UC6["Ghi hoạt động task<br/>(comment, file)"]
        UC7["Chuyển giai đoạn dự án"]
        UC8["Xem dashboard dự án"]
        UC9["Quản lý báo giá"]
        UC10["Quản lý hợp đồng"]
        UC11["Theo dõi chi phí dự án"]
        UC12["Upload file cuối cùng"]
    end

    PMActor --> UC1
    PMActor --> UC2
    PMActor --> UC3
    PMActor --> UC4
    PMActor --> UC7
    PMActor --> UC8
    PMActor --> UC11

    DesignerActor --> UC5
    DesignerActor --> UC6
    DesignerActor --> UC12

    SalesActor --> UC1
    SalesActor --> UC9

    AccountantActor --> UC10
    AccountantActor --> UC11

    AdminActor --> UC2
    AdminActor --> UC8

    LeaderActor --> UC8
```

## Project Lifecycle

```mermaid
stateDiagram-v2
    [*] --> design: Lead ký HĐ thiết kế

    design --> quotation: Hoàn thành bản vẽ
    quotation --> procurement: Khách duyệt báo giá
    procurement --> construction: Vật tư sẵn sàng
    construction --> acceptance: Thi công xong
    acceptance --> completed: Khách nghiệm thu

    design --> design: Tasks trong giai đoạn thiết kế
    quotation --> quotation: Tasks báo giá
    procurement --> procurement: Tasks mua sắm
    construction --> construction: Tasks thi công
    acceptance --> acceptance: Tasks nghiệm thu

    note right of design
        Designer tạo bản vẽ
        Tasks: phác thảo, 3D, chỉnh sửa
    end note

    note right of construction
        PM quản lý tiến độ
        Tasks: phần thô, nội thất, hoàn thiện
    end note
```

## Project Types

| Type | Vietnamese | Description |
|------|-----------|-------------|
| `design_only` | Chỉ thiết kế | Design contract only |
| `design_build` | Thiết kế + Thi công | Full service |
| `construction_only` | Chỉ thi công | Construction contract only |

## Project Status

| Status | Vietnamese | Description |
|--------|-----------|-------------|
| `active` | Đang thực hiện | Active project |
| `paused` | Tạm ngưng | Temporarily paused |
| `completed` | Hoàn thành | Project completed |
| `cancelled` | Hủy | Project cancelled |

## Task Stages & Departments

```mermaid
graph TB
    subgraph Stages["Giai đoạn Task"]
        S1["design<br/>Thiết kế"]
        S2["quotation<br/>Báo giá"]
        S3["procurement<br/>Mua sắm"]
        S4["construction<br/>Thi công"]
        S5["acceptance<br/>Nghiệm thu"]
    end

    subgraph Departments["Phòng ban phụ trách"]
        D1["design<br/>Phòng Thiết kế"]
        D2["quotation<br/>Phòng KD / Kế toán"]
        D3["procurement<br/>Thu mua"]
        D4["construction<br/>Phòng QLDA"]
        D5["accounting<br/>Kế toán"]
        D6["sales<br/>Kinh doanh"]
    end

    S1 --> D1
    S2 --> D2
    S3 --> D3
    S4 --> D4
    S5 --> D5
```

## Task Status

| Status | Vietnamese |
|--------|-----------|
| `not_started` | Chưa bắt đầu |
| `in_progress` | Đang thực hiện |
| `done` | Hoàn thành |

## Quotation Flow

```mermaid
sequenceDiagram
    autonumber
    participant S as Sales
    participant Sys as System
    participant L as Leader
    participant C as Customer

    S->>Sys: Tạo báo giá (type: design/construction)
    Sys->>Sys: Generate code (QT-YYYYMMDD-NNN)
    S->>Sys: Thêm line items (JSON)
    Sys->>Sys: Tính total_amount

    S->>Sys: Submit báo giá
    L->>Sys: Duyệt báo giá
    Sys->>Sys: status = approved

    S->>C: Gửi báo giá cho KH
    alt Khách đồng ý
        C->>Sys: status = sent → signed
        Sys->>Sys: Tạo Contract từ Quotation
    else Khách từ chối
        C->>Sys: status = rejected
    end
```

## Contract Payment Terms

Default: 4 installments at 25% each

```mermaid
gantt
    title Lịch thanh toán hợp đồng (mặc định 4 đợt)
    dateFormat X
    axisFormat %s%%

    section Installments
    Đợt 1: Đặt cọc (25%)           :done, p1, 0, 25
    Đợt 2: Nghiệm thu phần thô (25%):active, p2, 25, 50
    Đợt 3: Nghiệm thu nội thất (25%):p3, 50, 75
    Đợt 4: Bàn giao (25%)           :p4, 75, 100
```

| Installment | Vietnamese | Milestone | Default % |
|------------|-----------|-----------|-----------|
| 1 | Đợt 1 (Đặt cọc) | signing | 25% |
| 2 | Đợt 2 (Nghiệm thu phần thô) | rough_complete | 25% |
| 3 | Đợt 3 (Nghiệm thu nội thất) | interior_complete | 25% |
| 4 | Đợt 4 (Bàn giao) | handover | 25% |

## Data Model

```mermaid
erDiagram
    Project {
        uuid id PK
        string code UK
        string name
        uuid lead_id FK
        uuid customer_id FK
        string client_name
        string client_phone
        string address
        string project_type "design_only|design_build|construction_only"
        string status "active|paused|completed|cancelled"
        string stage "design|quotation|procurement|construction|acceptance|completed"
        float design_value
        float construction_value
        float total_value
        float spent
        int progress "0-100"
        uuid pm_id FK
        uuid designer_id FK
        uuid sales_id FK
        date start_date
        date target_end_date
    }

    Task {
        uuid id PK
        uuid project_id FK
        string title
        text description
        string status "not_started|in_progress|done"
        string stage
        string department
        string final_file_url
        uuid assigned_to FK
        int order
        date due_date
        datetime completed_at
    }

    TaskActivity {
        uuid id PK
        uuid task_id FK
        uuid user_id FK
        text content
        string media_url
    }

    Quotation {
        uuid id PK
        string code UK
        string type "design|construction"
        uuid project_id FK
        uuid lead_id FK
        string title
        string status "draft|approved|sent|rejected|expired"
        float total_amount
        json items
        int revision
    }

    Contract {
        uuid id PK
        string code UK
        uuid project_id FK
        uuid quotation_id FK
        string title
        string status "draft|approved|sent|signed|completed|cancelled"
        float total_value
        json payment_terms
        date signed_date
    }

    Project ||--o{ Task : "tasks"
    Project ||--o{ Quotation : "quotations"
    Project ||--o{ Contract : "contracts"
    Task ||--o{ TaskActivity : "activities"
    Project }o--o| Lead : "from lead"
    Project }o--o| Customer : "for customer"
    Quotation ||--o| Contract : "generates"
    Task }o--o| User : "assigned_to"
    Project }o--o| User : "PM"
    Project }o--o| User : "designer"
    Project }o--o| User : "sales"
```

## API Endpoints

| Method | Endpoint | Description | Roles |
|--------|----------|-------------|-------|
| GET | `/projects` | List projects | PM, Leader, Admin, Accountant |
| POST | `/projects` | Create project | PM, Admin |
| GET | `/projects/{id}` | Project detail | PM, Designer, Sales, Admin |
| PUT | `/projects/{id}` | Update project | PM, Admin |
| GET | `/projects/{id}/tasks` | List tasks | PM, Designer |
| POST | `/projects/{id}/tasks` | Create task | PM |
| PUT | `/tasks/{id}` | Update task | PM, assigned user |
| POST | `/tasks/{id}/activities` | Add task activity | assigned user |
| GET | `/quotations` | List quotations | Sales, Accountant |
| POST | `/quotations` | Create quotation | Sales |
| PUT | `/quotations/{id}` | Update quotation | Sales |
| GET | `/contracts` | List contracts | Accountant, PM |
| POST | `/contracts` | Create contract | Accountant |
| PUT | `/contracts/{id}/payment` | Update payment status | Accountant |

## Frontend Pages

- `/projects` — Project list (grid/table with filters)
- `/projects/{id}` — Project detail (info + tasks + timeline + finances)
- `/quotations` — Quotation management
- `/contracts` — Contract management
- `/bao-gia` — Instant quote tool

## Tags

#module #projects #tasks #quotations #contracts #jama-home
