# Module: Lead Management (Quản lý Lead)

## Overview

The Lead Management module implements a 7-stage CRM pipeline for JAMA HOME's sales operations. Leads flow from capture through qualification to either conversion (signed design contract) or loss. The module includes AI-powered scoring, automated follow-up reminders, and lead recall mechanisms.

## Use Case Diagram

```mermaid
graph TB
    subgraph Actors
        DataEntry["Data Entry<br/>Nhân viên nhập liệu"]
        Leader["Leader<br/>Trưởng nhóm"]
        Admin["Admin"]
        System["Hệ thống tự động"]
        AI["AI Service<br/>GPT-4o-mini"]
        ZaloListener["Zalo Listener"]
    end

    subgraph UseCases["Lead Management Use Cases"]
        UC1["Tạo lead mới"]
        UC2["Cập nhật thông tin lead"]
        UC3["Chuyển giai đoạn pipeline"]
        UC4["Ghi hoạt động CSKH<br/>(call/email/meeting/survey)"]
        UC5["Giao lead cho nhân viên"]
        UC6["Thu hồi lead không chăm sóc"]
        UC7["Nhắc nhở follow-up"]
        UC8["AI chấm điểm lead"]
        UC9["Xem pipeline Kanban"]
        UC10["Tìm kiếm & lọc lead"]
        UC11["Import lead từ Zalo"]
        UC12["Chuyển lead thành khách hàng"]
        UC13["Xem báo cáo pipeline"]
        UC14["Đặt lịch khảo sát"]
        UC15["Đính kèm ảnh khảo sát"]
    end

    DataEntry --> UC1
    DataEntry --> UC2
    DataEntry --> UC3
    DataEntry --> UC4
    DataEntry --> UC10
    DataEntry --> UC14
    DataEntry --> UC15

    Leader --> UC5
    Leader --> UC6
    Leader --> UC13
    Leader --> UC1

    Admin --> UC5
    Admin --> UC6
    Admin --> UC13

    System --> UC7
    System --> UC6
    AI --> UC8
    ZaloListener --> UC11
    UC3 -->|"signed_design"| UC12
```

## Pipeline Stages

```mermaid
stateDiagram-v2
    [*] --> new: Lead tạo mới

    new --> interested: Liên hệ được KH
    new --> lost: Không liên hệ được
    new --> dormant: Không phản hồi

    interested --> survey_scheduled: Đặt lịch khảo sát
    interested --> lost: KH từ chối
    interested --> dormant: KH không phản hồi

    survey_scheduled --> potential: Khảo sát thành công
    survey_scheduled --> lost: KH hủy
    survey_scheduled --> dormant: KH không tham gia

    potential --> signed_design: Ký hợp đồng thiết kế
    potential --> lost: KH không ký
    potential --> dormant: KH tạm hoãn

    signed_design --> [*]

    dormant --> interested: KH quay lại
    dormant --> lost: Xác nhận mất

    lost --> [*]
```

### Stage Definitions

| Stage | Vietnamese | Weight (KPI) | Description |
|-------|-----------|-------------|-------------|
| new | Mới | 10% | Lead vừa tiếp nhận, chưa liên hệ |
| interested | Quan tâm | 25% | Đã liên hệ, KH có nhu cầu |
| survey_scheduled | Đặt lịch khảo sát | 50% | KH đồng ý khảo sát thực địa |
| potential | Tiềm năng | 75% | Đã khảo sát, KH muốn ký |
| signed_design | Ký thiết kế | 100% | Ký HĐ, chuyển sang Project |
| lost | Mất | 0% | Không convert được |
| dormant | Tạm ngưng | 0% | KH tạm dừng, có thể quay lại |

### Valid Stage Transitions

```python
VALID_STAGE_TRANSITIONS = {
    "new": ["interested", "lost", "dormant"],
    "interested": ["survey_scheduled", "lost", "dormant"],
    "survey_scheduled": ["potential", "lost", "dormant"],
    "potential": ["signed_design", "lost", "dormant"],
    "signed_design": [],          # Terminal
    "lost": [],                   # Terminal
    "dormant": ["interested", "lost"],
}
```

## Lead Sources & Channels

```mermaid
graph LR
    subgraph Sources["Nguồn (Platform)"]
        FB["Facebook"]
        Zalo["Zalo"]
        Website["Website"]
        Referral["Giới thiệu"]
        TikTok["TikTok"]
        Other["Khác"]
    end

    subgraph Channels["Kênh phân bổ"]
        KA["Kênh A"]
        KB["Kênh B"]
        KC["Kênh Chính"]
        KS["Kênh Sale"]
        KAff["Kênh Affiliate"]
        KX["Khác"]
    end

    Sources -->|"Platform gốc"| Channels
    Channels -->|"Phân công"| SalesTeam["Team Kinh doanh"]
```

## Activity Types

| Type | Vietnamese | Description |
|------|-----------|-------------|
| call | Gọi điện | Phone call to customer |
| email | Email | Email correspondence |
| meeting | Họp | In-person or virtual meeting |
| survey | Khảo sát | Site survey visit |
| note | Ghi chú | Internal note |
| stage_change | Chuyển stage | Automated log on stage transition |
| assignment | Phân công | Automated log on reassignment |

## Classifications

### Property Types
`townhouse` (Nhà phố) | `apartment` (Căn hộ) | `villa` (Biệt thự) | `office` (Văn phòng) | `shophouse` | `other`

### Property Classes
`luxury` (Cao cấp) | `mid_range` (Trung cấp) | `budget` (Tiết kiệm)

### Priorities
`low` (Thấp) | `medium` (Trung bình) | `high` (Cao) | `urgent` (Khẩn cấp)

### Contact Statuses
`reachable` (Liên hệ được) | `unreachable` (Không liên hệ được) | `wrong_number` (Sai số) | `no_need` (Không có nhu cầu) | `pending` (Chờ xác nhận)

## Automation Rules

```mermaid
flowchart TD
    A["Scheduler chạy hàng ngày 07:00 VN"] --> B{Lead active<br/>stage ∈ [new, interested,<br/>survey_scheduled, potential]?}

    B -->|"Có"| C{Ngày kể từ lần<br/>liên hệ cuối > N?}
    B -->|"Không"| Z["Bỏ qua"]

    C -->|"3 ngày (followup)"| D["Tạo Notification<br/>Nhắc CSKH"]
    C -->|"7 ngày (recall)"| E{Recall<br/>enabled?}
    C -->|"< 3 ngày"| Z

    E -->|"Có"| F["Thu hồi lead<br/>Giao cho sale khác"]
    E -->|"Không"| D

    D --> G["Push Telegram<br/>cho nhân viên phụ trách"]
    F --> H["Notify cả 2 nhân viên<br/>(cũ + mới)"]
    F --> I["Ghi AuditLog"]
```

## AI Lead Scoring

The AI scoring system evaluates leads based on multiple signals:

```mermaid
graph LR
    subgraph Inputs["Đầu vào"]
        Area["Diện tích (m²)"]
        Budget["Ngân sách dự kiến"]
        Property["Loại BĐS"]
        Segment["Phân khúc"]
        Source["Nguồn lead"]
        Activity["Tần suất CSKH"]
    end

    subgraph AI["GPT-4o-mini"]
        Score["AI Score<br/>0.0 - 1.0"]
        Notes["AI Notes<br/>Lý do đánh giá"]
    end

    Inputs --> AI
    AI --> Score
    AI --> Notes
```

## Data Model Relationships

```mermaid
erDiagram
    Lead ||--o{ Activity : "has activities"
    Lead ||--o{ Quotation : "has quotes"
    Lead ||--o| Customer : "converts to"
    Lead ||--o| Project : "becomes project"
    Lead }o--o| User : "assigned_to"
    Lead }o--o| Team : "team"
    Activity }o--|| User : "performed by"
```

## API Endpoints

| Method | Endpoint | Description | Roles |
|--------|----------|-------------|-------|
| GET | `/leads` | List leads (filtered, paginated) | All sales |
| POST | `/leads` | Create new lead | data_entry, leader, admin |
| GET | `/leads/{id}` | Get lead detail | All sales |
| PUT | `/leads/{id}` | Update lead | assigned user, leader, admin |
| PUT | `/leads/{id}/stage` | Change pipeline stage | assigned user, leader, admin |
| POST | `/leads/{id}/activities` | Log activity | assigned user |
| POST | `/leads/{id}/assign` | Assign to user | leader, admin |
| POST | `/leads/{id}/survey` | Set survey date + photos | assigned user |
| POST | `/leads/{id}/convert` | Convert to customer + project | leader, admin |
| GET | `/leads/pipeline` | Kanban pipeline view | All sales |
| GET | `/leads/stats` | Pipeline statistics | leader, admin |

## Frontend Pages

- `/leads` — Pipeline Kanban board (drag-and-drop stage changes)
- `/leads?view=table` — Table view with filters
- `/leads?id={id}` — Lead detail page (info + activities + quotes)
- `/customers` — Customer list (converted leads)

## Tags

#module #crm #lead-management #pipeline #jama-home
