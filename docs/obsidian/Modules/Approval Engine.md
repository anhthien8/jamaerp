# Module: Approval Engine (Phê duyệt)

## Overview

The Approval Engine is a shared, pluggable approval system used across multiple business domains: leave requests, salary advances, payroll periods, expenses, and overtime. It supports multi-step approval chains (1-3 levels), delegation, escalation, and side-effect execution on approval.

## Use Case Diagram

```mermaid
graph TB
    subgraph Actors
        Requester["Người tạo đơn<br/>(Mọi nhân viên)"]
        Approver["Người duyệt<br/>(Leader/Accountant/Admin)"]
        Delegate["Người được ủy quyền"]
        AdminActor["Admin"]
        SystemActor["Hệ thống tự động"]
    end

    subgraph UseCases["Approval Use Cases"]
        UC1["Tạo đơn phê duyệt"]
        UC2["Duyệt đơn"]
        UC3["Từ chối đơn"]
        UC4["Y cầu sửa đổi"]
        UC5["Nộp lại đơn đã sửa"]
        UC6["Hủy đơn"]
        UC7["Ủy quyền duyệt"]
        UC8["Escalate đơn quá hạn"]
        UC9["Tái phân đơn mồ côi"]
        UC10["Xem danh sách chờ duyệt"]
        UC11["Xem lịch sử duyệt"]
    end

    Requester --> UC1
    Requester --> UC5
    Requester --> UC6

    Approver --> UC2
    Approver --> UC3
    Approver --> UC4
    Approver --> UC10
    Approver --> UC11

    Delegate --> UC2
    Delegate --> UC3
    Delegate --> UC4

    AdminActor --> UC2
    AdminActor --> UC6
    AdminActor --> UC11

    SystemActor --> UC8
    SystemActor --> UC9
```

## Approval Types

| Type | Vietnamese | Source Module | Side Effect on Approve |
|------|-----------|-------------|----------------------|
| `leave` | Nghỉ phép | Attendance & Leave | Update LeaveRequest.status → approved, deduct LeaveBalance |
| `advance` | Tạm ứng | Payroll | Update SalaryAdvance.status → approved |
| `payroll_period` | Bảng lương | Payroll | Lock period, send payslips |
| `expense` | Chi phí | Finance | Record transaction |
| `overtime` | Tăng ca | Attendance | Update AttendanceRecord.ot_status → approved |

## State Machine

```mermaid
stateDiagram-v2
    [*] --> pending: Tạo đơn

    pending --> approved: Duyệt (cấp cuối)
    pending --> rejected: Từ chối
    pending --> changes_requested: Yêu cầu sửa
    pending --> cancelled: Hủy

    pending --> pending: Duyệt cấp tiếp<br/>(step++, next approver)

    changes_requested --> pending: Nộp lại

    approved --> [*]
    rejected --> [*]
    cancelled --> [*]

    note right of pending
        SLA: 24h/approver
        Quá hạn → escalate
    end note

    note right of changes_requested
        Chỉ requester mới nộp lại
    end note
```

## Multi-Step Approval Flow

```mermaid
sequenceDiagram
    autonumber
    participant R as Requester
    participant S as System
    participant A1 as Approver Cấp 1<br/>(Leader)
    participant A2 as Approver Cấp 2<br/>(Accountant)
    participant N as Notification

    R->>S: Tạo đơn (leave/advance/...)
    S->>S: Tạo ApprovalRequest<br/>step=1, total_steps=2
    S->>A1: Notify [Chờ duyệt]
    S->>N: In-app + Telegram

    A1->>S: Duyệt (step 1)
    S->>S: step++ → 2<br/>current_approver = A2
    S->>A2: Notify [Chờ duyệt]
    S->>N: In-app + Telegram

    A2->>S: Duyệt (step 2 - final)
    S->>S: status = approved
    S->>S: Run side-effect<br/>(e.g. approve leave)
    S->>R: Notify [Đã duyệt]
    S->>N: In-app + Telegram
```

## Delegation Flow

```mermaid
sequenceDiagram
    autonumber
    participant L as Leader
    participant S as System
    participant D as Delegate (Leader khác)
    participant Req as Requester

    Note over L: Nghỉ phép / Đi công tác
    L->>S: Set delegate_to = D<br/>delegate_until = end_date

    Req->>S: Tạo đơn phê duyệt
    S->>S: Approver = L<br/>nhưng L.delegate_to = D<br/>và delegate_until >= now

    D->>S: Duyệt đơn (thay mặt L)
    S->>S: Kiểm tra ủy quyền hợp lệ
    S->>S: Chấp nhận duyệt
    S->>Req: Notify [Đã duyệt]
```

## Escalation Flow

```mermaid
flowchart TD
    A["Scheduler 00:00 VN<br/>chạy escalate_overdue()"] --> B{"Đơn pending<br/>có due_at < now?"}

    B -->|"Không"| Z["Kết thúc"]
    B -->|"Có"| C{"Quá hạn<br/>bao lâu?"}

    C -->|"< 24h"| D["Nhắc approver hiện tại<br/>escalated = 1"]
    C -->|"≥ 24h và<br/>escalated ≥ 1"| E["Tìm admin active<br/>Chuyển đơn cho admin"]
    C -->|"đã escalate"| Z

    D --> F["Notify qua Telegram<br/>⏰ Quá hạn duyệt"]
    E --> G["Notify admin<br/>🚨 Escalate"]
    E --> H["Ghi AuditLog"]
```

## Orphaned Approval Reassignment

```mermaid
flowchart TD
    A["Scheduler 00:30 VN<br/>reassign_orphaned()"] --> B{"Duyệt tất cả<br/>đơn pending"}

    B --> C{"Approver hiện tại<br/>còn active?"}

    C -->|"Không (đã nghỉ việc)"| D["Chuyển đơn cho admin"]
    C -->|"Có"| E["Giữ nguyên"]

    D --> F["Ghi AuditLog<br/>approval.reassign_orphan"]
```

## Business Rules (Invariants)

| # | Rule | Enforcement |
|---|------|------------|
| 1 | Side-effect chỉ chạy khi đủ `total_steps` approve | `approve()` checks step == total_steps |
| 2 | Đơn đã resolve không thể approve/reject lần nữa | Status check → HTTP 409 |
| 3 | Requester không thể tự duyệt đơn của mình | `_authorize_actor()` checks requester_id |
| 4 | Mọi chuyển trạng thái ghi AuditLog | `log_action()` called in every state transition |
| 5 | Row-level lock prevents concurrent approve/reject | `with_for_update()` on query |
| 6 | Admin always authorized | `_authorize_actor()` role check |
| 7 | Delegation only valid within `delegate_until` | Time comparison in `_authorize_actor()` |

## Data Model

```mermaid
erDiagram
    ApprovalRequest {
        uuid id PK
        string type "leave|advance|payroll|expense|overtime"
        string ref_id "FK to source"
        string title
        float amount
        uuid requester_id FK
        uuid current_approver_id FK
        string next_approvers_csv
        int step
        int total_steps
        string status
        string reason
        string acted_via "web|telegram"
        datetime due_at
        int escalated
        datetime resolved_at
    }

    ApprovalRequest }o--|| User : "requester"
    ApprovalRequest }o--o| User : "current_approver"
```

## API Endpoints

| Method | Endpoint | Description | Roles |
|--------|----------|-------------|-------|
| GET | `/approvals` | List approvals (filtered by role) | All |
| GET | `/approvals/{id}` | Get approval detail | requester, approver, admin |
| POST | `/approvals/{id}/approve` | Approve current step | approver, delegate, admin |
| POST | `/approvals/{id}/reject` | Reject with reason | approver, delegate, admin |
| POST | `/approvals/{id}/request-changes` | Request modifications | approver, delegate, admin |
| POST | `/approvals/{id}/resubmit` | Resubmit after changes | requester |
| POST | `/approvals/{id}/cancel` | Cancel request | requester, admin |

## Tags

#module #approval #workflow #delegation #jama-home
