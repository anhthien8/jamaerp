# Module: Attendance & Leave (Chấm công & Nghỉ phép)

## Overview

The Attendance & Leave module manages employee check-in/out (both office and construction site), leave requests with approval workflows, overtime tracking, and feeds data to the Payroll engine. It enforces 1 record per user per day and handles edge cases like forgotten checkouts.

## Use Case Diagram

```mermaid
graph TB
    subgraph Actors
        Employee["Nhân viên"]
        LeaderActor["Leader"]
        AdminActor["Admin"]
        SystemActor["Hệ thống"]
        AccountantActor["Kế toán"]
    end

    subgraph UseCases["Attendance Use Cases"]
        UC1["Check-in (web/Telegram)"]
        UC2["Check-out"]
        UC3["Xem bảng chấm công tháng"]
        UC4["Sửa giờ công (leader)"]
        UC5["Đăng ký tăng ca"]
        UC6["Duyệt tăng ca"]
        UC7["Tự đóng ca quên checkout"]
        UC8["Xác nhận ca cần review"]
    end

    subgraph LeaveUseCases["Leave Use Cases"]
        UC9["Tạo đơn nghỉ phép"]
        UC10["Duyệt/từ chối nghỉ phép"]
        UC11["Xem số dư phép năm"]
        UC12["Hủy đơn nghỉ phép"]
    end

    Employee --> UC1
    Employee --> UC2
    Employee --> UC3
    Employee --> UC5
    Employee --> UC9
    Employee --> UC12

    LeaderActor --> UC4
    LeaderActor --> UC6
    LeaderActor --> UC8
    LeaderActor --> UC10

    SystemActor --> UC7
    AccountantActor --> UC3
    AdminActor --> UC3
```

## Attendance Flow

```mermaid
sequenceDiagram
    autonumber
    participant E as Nhân viên
    participant W as Web/Telegram
    participant S as Attendance Service
    participant DB as Database
    participant L as Leader

    E->>W: Check-in (có GPS tùy chọn)
    W->>S: record_checkin(user, source, project_id, lat, lng)
    S->>DB: SELECT today's record
    alt Chưa có record hôm nay
        S->>DB: INSERT AttendanceRecord
        S-->>W: (record, created=true)
    else Đã check-in rồi
        S-->>W: (existing_record, created=false)
    end

    Note over E: ... Làm việc ...

    E->>W: Check-out
    W->>S: record_checkout(user)
    S->>DB: SELECT today's record
    S->>S: Tính work_hours = min(elapsed, 8h)
    S->>S: Tính ot_hours = max(0, elapsed - 8h)
    alt ot_hours >= 0.5h
        S->>S: ot_status = "pending"
    end
    S->>DB: UPDATE record
    S-->>W: record (work_hours, ot_hours)
```

## Auto-Close Forgotten Checkout

```mermaid
flowchart TD
    A["Scheduler 00:00 VN<br/>auto_close_open_shifts()"] --> B{"Tìm records hôm nay<br/>check_in IS NOT NULL<br/>check_out IS NULL"}

    B -->|"Không có"| Z["Kết thúc"]
    B -->|"Có N records"| C["Với mỗi record:"]

    C --> D["check_out = now()"]
    D --> E["work_hours = min(elapsed, 8h)"]
    E --> F["ot_hours = 0<br/>(không tính OT từ quên checkout)"]
    F --> G["needs_review = true"]
    G --> H["note += 'auto-close: quên checkout'"]

    H --> I["Leader thấy trên dashboard<br/>→ Xác nhận/correct giờ"]
```

## Attendance Rules

| Rule | Description |
|------|-------------|
| 1 record/user/day | Check-in lần đầu tạo record, các lần sau bỏ qua |
| work_hours = min(elapsed, 8h) | Tối đa 8h công/ngày |
| ot_hours = elapsed - 8h | Chỉ tính nếu >= 0.5h |
| OT needs approval | ot_status = "pending" until leader approves |
| Period locked | Kỳ lương approved/paid → từ chối mọi sửa đổi |
| Forgotten checkout | Job đêm tự đóng 8h, needs_review = true |
| Source tracking | web / telegram / leave / auto |

## Leave Types

| Type | Vietnamese | Salary | Quota |
|------|-----------|--------|-------|
| `annual` | Phép năm | Có lương | 12 ngày/năm (theo luật) |
| `sick` | Phép ốm | BHXH chi trả | Theo quy định BHXH |
| `unpaid` | Không lương | Không | Không giới hạn |

## Leave Request Flow

```mermaid
sequenceDiagram
    autonumber
    participant E as Nhân viên
    participant S as System
    participant A as Approval Engine
    participant L as Leader
    participant DB as Database

    E->>S: Tạo đơn nghỉ phép<br/>(type, dates, reason)
    S->>DB: Tạo LeaveRequest (status=pending)
    S->>A: create_request(type="leave", ref_id=leave_id)
    A->>L: Notify [Chờ duyệt]

    alt Duyệt
        L->>A: approve()
        A->>S: Side-effect: approve leave
        S->>DB: LeaveRequest.status = "approved"
        S->>DB: LeaveBalance.annual_used += days
        S->>DB: Tạo AttendanceRecord (source="leave")
        A->>E: Notify [Đã duyệt]
    else Từ chối
        L->>A: reject(reason)
        A->>S: Side-effect: reject leave
        S->>DB: LeaveRequest.status = "rejected"
        A->>E: Notify [Bị từ chối]
    end
```

## Leave Balance Calculation

```mermaid
flowchart LR
    A["LeaveBalance<br/>annual_total = 12"] --> B["annual_used"]
    A --> C["sick_used"]
    A --> D["unpaid_used"]

    B --> E["Còn lại = annual_total - annual_used"]
    E --> F["Hiển thị trên dashboard"]
```

## Data Model

```mermaid
erDiagram
    AttendanceRecord {
        uuid id PK
        uuid user_id FK
        date work_date "unique per user"
        datetime check_in
        datetime check_out
        float check_in_lat
        float check_in_lng
        uuid project_id FK "on-site work"
        string source "web|telegram|leave|auto"
        float work_hours "max 8h"
        float ot_hours
        string ot_status "none|pending|approved|rejected"
        bool needs_review
        string note
    }

    LeaveBalance {
        uuid id PK
        uuid user_id FK
        int year
        float annual_total "12"
        float annual_used
        float sick_used
        float unpaid_used
    }

    LeaveRequest {
        uuid id PK
        uuid user_id FK
        string leave_type "annual|sick|unpaid"
        date start_date
        date end_date
        float days "supports 0.5"
        string reason
        string status "pending|approved|rejected|cancelled"
        uuid approval_id
        datetime resolved_at
    }

    User ||--o{ AttendanceRecord : "records"
    User ||--o{ LeaveBalance : "balance per year"
    User ||--o{ LeaveRequest : "requests"
    LeaveRequest }o--o| ApprovalRequest : "linked via approval_id"
    AttendanceRecord }o--o| Project : "on-site project"
```

## Month Summary (for Payroll)

The `month_summary()` function computes:

| Field | Description |
|-------|-------------|
| `records` | Total attendance records in month |
| `work_days` | Days with work_hours > 0 |
| `work_days_fraction` | Sum of (hours/8), capped at 1.0 per day |
| `total_hours` | Sum of all work_hours |
| `ot_approved_hours` | Sum of OT hours where ot_status = "approved" |
| `needs_review` | Count of records needing leader review |

## API Endpoints

| Method | Endpoint | Description | Roles |
|--------|----------|-------------|-------|
| POST | `/attendance/checkin` | Check-in (GPS optional) | All employees |
| POST | `/attendance/checkout` | Check-out | All employees |
| GET | `/attendance/today` | Today's record | All employees |
| GET | `/attendance/month?period=YYYY-MM` | Monthly summary | All (own), Leader (team) |
| PUT | `/attendance/{id}` | Edit attendance | Leader, Admin |
| PUT | `/attendance/{id}/ot` | Approve/reject OT | Leader, Admin |
| GET | `/leaves/balance` | Leave balance | All employees |
| POST | `/leaves` | Create leave request | All employees |
| GET | `/leaves` | List leave requests | All (own), Leader (team) |
| PUT | `/leaves/{id}/cancel` | Cancel leave request | Requester |

## Frontend Pages

- `/attendance` — Check-in/out button + today's status + monthly calendar
- `/attendance/team` — Team attendance overview (Leader/Accountant)
- `/leaves` — Leave request form + history + balance

## Tags

#module #attendance #leave #cham-cong #nghi-phep #jama-home
