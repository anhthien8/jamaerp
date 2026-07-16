# Flow: Approval Process (Quy trình Phê duyệt)

## Universal Approval Flow

The approval engine is shared across all approval types. This diagram shows the complete lifecycle including delegation, escalation, and side-effects.

```mermaid
sequenceDiagram
    autonumber
    participant Req as Requester<br/>(Nhân viên)
    participant S as System
    participant AE as Approval Engine
    participant A1 as Approver Cấp 1<br/>(Leader)
    participant Del as Delegate<br/>(nếu Leader vắng)
    participant A2 as Approver Cấp 2<br/>(Accountant/Admin)
    participant Sys as Automation
    participant Admin as Admin

    Note over Req,S === TẠO ĐƠN ===
    Req->>S: Tạo đơn (leave/advance/expense/OT)
    S->>AE: create_request(type, ref_id, approver_ids)
    AE->>AE: Loại requester khỏi chuỗi duyệt
    AE->>AE: Tạo ApprovalRequest<br/>step=1, total_steps=len(chain)
    AE->>A1: Notify [Chờ duyệt]<br/>(in-app + Telegram)
    AE->>S: Ghi AuditLog

    Note over A1,S === DUYỆT CẤP 1 ===
    alt A1 có mặt
        A1->>AE: approve(request_id)
    else A1 ủy quyền cho Del
        A1->>S: delegate_to = Del (trước đó)
        Del->>AE: approve(request_id)
        AE->>AE: Kiểm tra ủy quyền hợp lệ
    end

    AE->>AE: step < total_steps?
    AE->>AE: step++ → 2
    AE->>AE: current_approver = A2
    AE->>A2: Notify [Chờ duyệt]
    AE->>S: Ghi AuditLog (approval.approve_step)

    Note over A2,S === DUYỆT CẤP CUỐI ===
    A2->>AE: approve(request_id)
    AE->>AE: step == total_steps → FINAL
    AE->>AE: status = "approved"
    AE->>AE: Run side-effect(type)
    AE->>Req: Notify [Đã duyệt]
    AE->>S: Ghi AuditLog (approval.approve)
```

## Side-Effects by Type

```mermaid
flowchart TD
    subgraph Approved["Đơn được duyệt"]
        A["approval.status = approved"]
    end

    A --> B{"Type?"}

    B -->|"leave"| C["LeaveRequest.status → approved<br/>LeaveBalance.annual_used += days<br/>Tạo AttendanceRecord (source=leave)"]

    B -->|"advance"| D["SalaryAdvance.status → approved<br/>Chờ trừ vào kỳ lương kế tiếp"]

    B -->|"payroll_period"| E["Payroll.status → approved<br/>Khóa kỳ lương<br/>Gửi phiếu lương Telegram DM"]

    B -->|"expense"| F["Tạo Transaction (type=expense)<br/>Ghi sổ kế toán"]

    B -->|"overtime"| G["AttendanceRecord.ot_status → approved<br/>OT giờ được tính lương"]
```

## Rejection Flow

```mermaid
sequenceDiagram
    autonumber
    participant A as Approver
    participant AE as Approval Engine
    participant S as System
    participant Req as Requester

    A->>AE: reject(request_id, reason)
    AE->>AE: Kiểm tra quyền (authorize)
    AE->>AE: status = "rejected"
    AE->>AE: Run reject_effect(type)
    AE->>Req: Notify [Bị từ chối]<br/>+ reason
    AE->>S: Ghi AuditLog

    Note over Req: Requester xem lý do<br/>tạo đơn mới nếu cần
```

## Request Changes Flow

```mermaid
sequenceDiagram
    autonumber
    participant A as Approver
    participant AE as Approval Engine
    participant Req as Requester

    A->>AE: request_changes(request_id, reason)
    AE->>AE: status = "changes_requested"
    AE->>Req: Notify [Cần sửa lại]<br/>+ reason

    Req->>Req: Sửa đổi theo yêu cầu
    Req->>AE: resubmit(request_id)
    AE->>AE: status = "pending"<br/>reset due_at
    AE->>A: Notify [Đã sửa, chờ duyệt lại]
```

## Escalation Flow (Overdue Approvals)

```mermaid
flowchart TD
    A["Scheduler 00:00 VN<br/>escalate_overdue()"] --> B{"Quét đơn pending<br/>due_at < now"}

    B -->|"Không có"| Z["Kết thúc"]

    B -->|"Có"| C{"Overdue<br/>bao lâu?"}

    C -->|"< 24h"| D["escalated = 0?"]
    D -->|"Có"| E["Nhắc approver<br/>⏰ Quá hạn duyệt"]
    D -->|"Không (đã nhắc)"| Z

    C -->|"≥ 24h"| F{"escalated ≥ 1?"}
    F -->|"Có"| G["Tìm admin active"]
    G --> H["Chuyển đơn cho admin"]
    H --> I["Notify admin<br/>🚨 Escalate"]
    H --> J["Ghi AuditLog"]
    F -->|"Không"| E
```

## Orphaned Approval Reassignment

```mermaid
flowchart TD
    A["Scheduler 00:30 VN<br/>reassign_orphaned()"] --> B{"Duyệt đơn pending"}

    B --> C{"Approver hiện tại?"}

    C -->|"NULL"| D["Chuyển cho admin"]
    C -->|"User active"| E["Giữ nguyên"]
    C -->|"User inactive<br/>(đã nghỉ việc)"| D

    D --> F["current_approver_id = admin"]
    D --> G["Ghi AuditLog<br/>approval.reassign_orphan"]
```

## Authorization Rules

```mermaid
flowchart TD
    A["Actor muốn approve/reject"] --> B{"Actor == requester?"}
    B -->|"Có"| REJECT["TỪ CHỐI<br/>Không tự duyệt"]
    B -->|"Không"| C{"Actor.role == admin?"}
    C -->|"Có"| ALLOW["CHO PHÉP<br/>Admin always OK"]
    C -->|"Không"| D{"Actor == current_approver?"}
    D -->|"Có"| ALLOW
    D -->|"Không"| E{"Actor là delegate<br/>của approver?"}
    E -->|"Có"| F{"delegate_until<br/>>= now?"}
    F -->|"Có"| ALLOW
    F -->|"Không"| REJECT
    E -->|"Không"| REJECT
```

## State Machine (Complete)

```mermaid
stateDiagram-v2
    [*] --> pending: create_request()

    pending --> pending: approve(step N)<br/>→ step N+1, next approver
    pending --> approved: approve(final step)<br/>→ run side-effect
    pending --> rejected: reject(reason)<br/>→ run reject_effect
    pending --> changes_requested: request_changes(reason)
    pending --> cancelled: cancel()

    changes_requested --> pending: resubmit()

    approved --> [*]
    rejected --> [*]
    cancelled --> [*]

    note right of pending
        SLA: 24h/approver
        Quá hạn → escalate
        Approver nghỉ việc → reassign
    end note
```

## Cross-Module Integration Points

| Module | Creates Approval | Side-Effect on Approve |
|--------|-----------------|----------------------|
| Attendance & Leave | `type="leave"` | Update leave request + balance |
| Payroll | `type="advance"` | Update salary advance status |
| Payroll | `type="payroll_period"` | Lock payroll period |
| Finance | `type="expense"` | Record transaction |
| Attendance | `type="overtime"` | Approve OT hours |

## Tags

#flow #approval #workflow #delegation #escalation #cross-module #jama-home
