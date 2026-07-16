# Module: Zalo Listener (Trợ lý nghe nhóm Zalo)

## Overview

The Zalo Listener module ingests messages from Zalo groups (both internal and customer-facing) via a Node.js ingest service, analyzes them for business signals (lead candidates, commitments, quote requests), and surfaces actionable insights to the sales team. Raw messages are short-lived (7-day retention), while signals are permanent.

## Use Case Diagram

```mermaid
graph TB
    subgraph Actors
        AdminActor["Admin"]
        SalesActor["Nhân viên Sales"]
        IngestService["Zalo Ingest Service<br/>(Node.js / zca-js)"]
        SystemActor["Hệ thống phân tích"]
    end

    subgraph UseCases["Zalo Listener Use Cases"]
        UC1["Quản lý phiên đăng nhập Zalo<br/>(QR code)"]
        UC2["Quản nhóm theo dõi<br/>(internal/customer)"]
        UC3["Nhận tin nhắn từ nhóm"]
        UC4["Phân tích tín hiệu kinh doanh"]
        UC5["Xem & xử lý signals"]
        UC6["Tạo lead từ signal"]
        UC7["Xóa tin nhắn cũ (>7 ngày)"]
        UC8["Gán nhân viên phụ trách nhóm"]
    end

    AdminActor --> UC1
    AdminActor --> UC2
    AdminActor --> UC8

    IngestService --> UC3
    IngestService --> UC1

    SystemActor --> UC4
    SystemActor --> UC7

    SalesActor --> UC5
    SalesActor --> UC6
```

## Architecture

```mermaid
sequenceDiagram
    autonumber
    participant Z as Zalo App
    participant N as Node.js Ingest<br/>(zca-js)
    participant API as FastAPI Backend
    participant DB as PostgreSQL
    participant TG as Telegram Bot
    participant Sales as Nhân viên Sales

    Note over N,API: Login Flow
    Admin->>API: Request login
    API->>DB: Set login_requested = true
    N->>API: Poll /zalo/session (heartbeat)
    N->>N: Generate QR code
    N->>API: Push QR image
    API->>DB: Update ZaloSession (qr_ready)
    Admin->>API: Scan QR via web UI

    Note over Z,N: Message Ingestion
    Z->>N: Group message received
    N->>API: POST /zalo/messages
    API->>DB: INSERT ZaloMessage

    Note over API,DB: Signal Analysis
    API->>API: Analyze message content
    alt Business signal detected
        API->>DB: INSERT ZaloSignal
        API->>TG: Notify assigned user
    end

    Note over DB: Cleanup (nightly)
    API->>DB: DELETE messages WHERE created_at < now - 7 days
```

## Session States

```mermaid
stateDiagram-v2
    [*] --> logged_out: Khởi tạo

    logged_out --> awaiting_qr: Admin yêu cầu đăng nhập
    awaiting_qr --> qr_ready: Ingest service tạo QR
    qr_ready --> logged_in: Quét QR thành công
    qr_ready --> error: QR hết hạn / lỗi
    logged_in --> logged_out: Đăng xuất
    logged_in --> error: Mất kết nối
    error --> logged_out: Reset
    error --> awaiting_qr: Thử lại

    note right of qr_ready
        QR image = base64 data URI
        Hiển thị trên web UI
    end note
```

## Signal Types

| Type | Vietnamese | Description | Example |
|------|-----------|-------------|---------|
| `lead_candidate` | Ứng viên tiềm năng | Message indicating potential customer | "Mình cần thiết kế căn hộ 80m2" |
| `commitment` | Cam kết | Customer commitment statement | "Ok em, mình ký hợp đồng nhé" |
| `quote_request` | Yêu cầu báo giá | Request for pricing | "Báo giá nội thất giúp mình" |
| `unanswered` | Chưa trả lời | Customer message not answered | Customer question > 24h without reply |
| `deal_risk` | Rủi ro deal | Risk of losing the deal | "Mình đang xem bên khác..." |
| `faq` | Câu hỏi thường gặp | Common question | "Thời gian thi công bao lâu?" |

## Signal Lifecycle

```mermaid
stateDiagram-v2
    [*] --> new: Tạo signal

    new --> actioned: Đã xử lý
    new --> dismissed: Bỏ qua

    actioned --> [*]
    dismissed --> [*]

    note right of new
        Hiển thị trên dashboard
        Push Telegram cho người phụ trách
    end note
```

## Group Types

| Kind | Vietnamese | Description |
|------|-----------|-------------|
| `internal` | Nội bộ | Company internal groups |
| `customer` | Khách hàng | Customer-facing groups |

## Data Retention Policy

```mermaid
flowchart LR
    A["ZaloMessage<br/>(Raw messages)"] -->|"7 ngày"| B["Xóa tự động<br/>(job đêm)"]

    C["ZaloSignal<br/>(Business signals)"] -->|"Vĩnh viễn"| D["Giữ lại<br/>(asset)"]
```

## Data Model

```mermaid
erDiagram
    ZaloSession {
        string id PK "default (singleton)"
        string status "logged_out|awaiting_qr|qr_ready|logged_in|error"
        text qr_image "base64 data URI"
        string account_name
        string error_msg
        bool login_requested
        datetime last_seen "heartbeat"
    }

    ZaloGroup {
        uuid id PK
        string zalo_group_id UK
        string name
        string kind "internal|customer"
        uuid assigned_user_id FK "phụ trách"
        bool monitoring "đang theo dõi"
        string consent_ref "tuân thủ pháp luật"
    }

    ZaloMessage {
        uuid id PK
        uuid group_id FK
        string sender_zalo_id
        string sender_name
        text text
        string media_ref "link ảnh/media"
    }

    ZaloSignal {
        uuid id PK
        uuid group_id FK
        string source_msg_id
        string type "lead_candidate|commitment|quote_request|unanswered|deal_risk|faq"
        string summary
        text payload_json
        string status "new|actioned|dismissed"
        uuid assigned_user_id FK
        datetime resolved_at
    }

    ZaloGroup ||--o{ ZaloMessage : "messages (7d retention)"
    ZaloGroup ||--o{ ZaloSignal : "signals (permanent)"
    ZaloGroup }o--o| User : "assigned_user"
    ZaloSignal }o--o| User : "handler"
```

## API Endpoints

| Method | Endpoint | Description | Roles |
|--------|----------|-------------|-------|
| GET | `/zalo/session` | Get session status + QR | Admin |
| POST | `/zalo/session/login` | Request login | Admin |
| POST | `/zalo/session/logout` | Logout | Admin |
| PUT | `/zalo/session/heartbeat` | Ingest service heartbeat | Internal |
| PUT | `/zalo/session/qr` | Push QR image | Internal |
| GET | `/zalo/groups` | List monitored groups | Admin, Sales |
| POST | `/zalo/groups` | Add group to monitoring | Admin |
| PUT | `/zalo/groups/{id}` | Update group settings | Admin |
| POST | `/zalo/messages` | Ingest message | Internal (Ingest) |
| GET | `/zalo/signals` | List signals | Sales, Admin |
| PUT | `/zalo/signals/{id}` | Update signal status | Sales |
| POST | `/zalo/signals/{id}/create-lead` | Create lead from signal | Sales |

## Frontend Pages

- `/settings/zalo` — Zalo session management (QR login, status)
- `/settings/zalo/groups` — Group monitoring configuration
- `/zalo/signals` — Signal dashboard (new/actioned/dismissed)

## Tags

#module #zalo #listener #signals #messaging #jama-home
