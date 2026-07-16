# Module: Notifications & System (Thông báo & Hệ thống)

## Overview

The Notifications & System module provides in-app notifications with deduplication, Telegram push integration, system settings management, employee feedback collection, and comprehensive audit logging for sensitive operations.

## Use Case Diagram

```mermaid
graph TB
    subgraph Actors
        AllEmployees["Mọi nhân viên"]
        AdminActor["Admin"]
        SystemActor["Hệ thống"]
        TelegramBot["Telegram Bot"]
    end

    subgraph NotificationUCs["Notification Use Cases"]
        UC1["Xem thông báo"]
        UC2["Đánh dấu đã đọc"]
        UC3["Nhận push Telegram"]
    end

    subgraph SystemUCs["System Use Cases"]
        UC4["Quản lý cài đặt hệ thống"]
        UC5["Gửi phản hồi / góp ý"]
        UC6["Xem & trả lời phản hồi"]
        UC7["Xem nhật ký audit"]
    end

    AllEmployees --> UC1
    AllEmployees --> UC2
    AllEmployees --> UC5

    SystemActor --> UC3
    AdminActor --> UC4
    AdminActor --> UC6
    AdminActor --> UC7
    TelegramBot --> UC3
```

## Notification Types

| Type | Vietnamese | Trigger | Recipient |
|------|-----------|---------|-----------|
| `followup_reminder` | Nhắc CSKH | Lead không liên hệ > 3 ngày | Assigned sales |
| `lead_recalled` | Lead bị thu hồi | Lead recalled after 7 days inactive | Old + new owner |
| `lead_assigned` | Lead được giao | Leader assigns lead | New owner |
| `payment_reminder` | Nhắc thanh toán | Payment installment pending | Accountant |
| `contract_signed` | Khách ký HĐ | Contract signed | PM, Sales |
| `bod_report` | Báo cáo BOD | Daily report generated | Executive |
| `system` | Hệ thống | General system notifications | Targeted user |

## Notification Flow

```mermaid
flowchart TD
    A["Event triggered<br/>(approval, lead, contract...)"] --> B["_notify()"]

    B --> C{"Dedupe check<br/>unread same<br/>type + ref_id?"}
    C -->|"Có (trùng)"| D["Skip — không tạo"]
    C -->|"Không"| E["Tạo Notification<br/>(in-app)"]

    E --> F{"User có<br/>telegram_user_id?"}
    F -->|"Có"| G["Push Telegram<br/>chat riêng"]
    F -->|"Không"| H["Chỉ in-app"]

    G --> I["Hiển thị trên<br/>notification bell"]
    H --> I
```

## System Settings

Configurable automation parameters stored in `system_settings` table:

| Setting | Default | Description |
|---------|---------|-------------|
| `followup_reminder_days` | 3 | Nhắc CSKH sau N ngày không liên hệ |
| `lead_recall_days` | 7 | Thu hồi lead sau N ngày không chăm sóc |
| `lead_recall_enabled` | true | Bật/tắt tính năng thu hồi lead |
| `payment_reminder_days` | 3 | Nhắc thanh toán đợt pending sau N ngày ký HĐ |
| `bod_report_enabled` | true | Bật/tắt báo cáo BOD hàng ngày |
| `bod_report_hour` | 8 | Giờ gửi báo cáo (Asia/Ho_Chi_Minh) |
| `telegram_group_chat_id` | "" | Chat ID nhóm Telegram công ty |
| `group_briefing_enabled` | true | Gửi briefing nhóm hàng ngày |
| `pit_personal_deduction` | 11,000,000 | Giảm trừ gia cảnh (VND/tháng) |
| `pit_dependent_deduction` | 4,400,000 | Giảm trừ người phụ thuộc |
| `bhxh_salary_cap` | 46,800,000 | Trần lương đóng BHXH |

## Feedback System

```mermaid
stateDiagram-v2
    [*] --> new: Nhân viên gửi góp ý

    new --> reviewed: Admin xem
    new --> resolved: Admin giải quyết

    reviewed --> resolved: Admin reply + resolve

    resolved --> [*]
```

### Feedback Categories

| Category | Vietnamese | Description |
|----------|-----------|-------------|
| `bug` | Lỗi phần mềm | Software bug report |
| `feature_request` | Đề xuất tính năng | Feature suggestion |
| `workflow_improvement` | Cải tiến quy trình | Process improvement |
| `other` | Khác | Other feedback |

## Audit Log

All sensitive operations are logged to `audit_logs` for compliance and traceability.

### Tracked Actions

| Action | Entity Type | Description |
|--------|------------|-------------|
| `user.create` | user | Tạo nhân viên mới |
| `user.role_change` | user | Thay đổi vai trò |
| `user.deactivate` | user | Vô hiệu hóa tài khoản |
| `user.resign` | user | Đánh dấu nghỉ việc |
| `user.undo_resign` | user | Hoàn tác nghỉ việc |
| `salary_grade.update` | salary_grade | Cập nhật bậc lương |
| `payroll.generate` | payroll | Tạo bảng lương |
| `payroll.submit` | payroll | Submit duyệt lương |
| `payroll.approve` | payroll | Duyệt bảng lương |
| `payroll.reject` | payroll | Từ chối bảng lương |
| `payroll.pay` | payroll | Đánh dấu đã trả |
| `attendance.edit` | attendance | Sửa giờ công |
| `ot.approve` | attendance | Duyệt tăng ca |
| `ot.reject` | attendance | Từ chối tăng ca |
| `leave.approve` | leave | Duyệt nghỉ phép |
| `leave.reject` | leave | Từ chối nghỉ phép |
| `approval.create` | approval | Tạo đơn phê duyệt |
| `approval.approve` | approval | Duyệt đơn |
| `approval.approve_step` | approval | Duyệt cấp |
| `approval.reject` | approval | Từ chối đơn |
| `approval.request_changes` | approval | Yêu cầu sửa đổi |
| `approval.resubmit` | approval | Nộp lại đơn |
| `approval.cancel` | approval | Hủy đơn |
| `approval.escalate` | approval | Escalate đơn |
| `approval.reassign_orphan` | approval | Tái phân đơn mồ côi |

## BOD Daily Report

Generated at 07:00 VN daily (configurable):

```mermaid
flowchart TD
    A["Scheduler 07:00 VN"] --> B{"bod_report_enabled?"}
    B -->|"Không"| Z["Skip"]
    B -->|"Có"| C["Tổng hợp dữ liệu"]

    C --> D["Doanh thu hôm qua"]
    C --> E["Lead mới / chuyển stage"]
    C --> F["Dự án quan trọng"]
    C --> G["Phê duyệt pending"]
    C --> H["Nhân viên nghỉ phép"]
    C --> I["Cảnh báo burnout"]

    D --> J["Gửi Telegram<br/>Executive group"]
    E --> J
    F --> J
    G --> J
    H --> J
    I --> J
```

## Group Briefing

Daily briefing sent to company Telegram group (excluding financial data):

```mermaid
flowchart TD
    A["Scheduler 07:00 VN"] --> B{"group_briefing_enabled?"}
    B -->|"Không"| Z["Skip"]
    B -->|"Có"| C["Briefing content"]

    C --> D["Sinh nhật nhân viên"]
    C --> E["Nhân viên nghỉ phép hôm nay"]
    C --> F["Dự án milestone sắp到期"]
    C --> G["Lead mới cần chăm sóc"]
    C --> H["Không bao gồm tài chính!<br/>(bảo mật)"]

    D --> I["Gửi nhóm Telegram<br/>telegram_group_chat_id"]
    E --> I
    F --> I
    G --> I
```

## Data Model

```mermaid
erDiagram
    Notification {
        uuid id PK
        uuid user_id FK
        string type
        string title
        text body
        string link "frontend route"
        string ref_id "dedupe key"
        bool read
    }

    SystemSetting {
        string key PK
        string value
    }

    Feedback {
        uuid id PK
        uuid user_id
        bigint telegram_user_id
        string category "bug|feature|workflow|other"
        text content
        string status "new|reviewed|resolved"
        text admin_reply
    }

    AuditLog {
        uuid id PK
        uuid actor_id
        string actor_name "snapshot"
        string action
        string entity_type
        uuid entity_id
        text before_json
        text after_json
        string note
    }

    User ||--o{ Notification : "receives"
```

## API Endpoints

| Method | Endpoint | Description | Roles |
|--------|----------|-------------|-------|
| GET | `/notifications` | List my notifications | All |
| PUT | `/notifications/{id}/read` | Mark as read | All |
| PUT | `/notifications/read-all` | Mark all as read | All |
| GET | `/notifications/unread-count` | Unread count | All |
| GET | `/settings` | List system settings | Admin |
| PUT | `/settings/{key}` | Update setting | Admin |
| POST | `/feedback` | Submit feedback | All |
| GET | `/feedback` | List feedback | Admin |
| PUT | `/feedback/{id}` | Reply & resolve | Admin |
| GET | `/audit` | List audit logs | Admin |
| GET | `/audit?entity_type=X&entity_id=Y` | Audit for entity | Admin |

## Frontend Pages

- `/settings` — System settings management
- `/feedback` — Feedback management (Admin)
- `/audit` — Audit log viewer (Admin)

## Tags

#module #notifications #system #audit #feedback #settings #jama-home
