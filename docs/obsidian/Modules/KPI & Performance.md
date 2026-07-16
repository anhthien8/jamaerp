# Module: KPI & Performance (KPI & Hiệu suất)

## Overview

The KPI & Performance module computes 8 sales performance metrics using aggregate SQL, generates monthly snapshots with team/overall rankings, detects burnout signals, and maintains an anonymized leaderboard. It also supports coaching notes and quarterly review cycles.

## Use Case Diagram

```mermaid
graph TB
    subgraph Actors
        SalesStaff["Nhân viên Sales"]
        LeaderActor["Leader"]
        ExecutiveActor["BOD / Executive"]
        SystemActor["Hệ thống"]
    end

    subgraph UseCases["KPI Use Cases"]
        UC1["Xem KPI cá nhân"]
        UC2["Xem bảng xếp hạng (Leaderboard)"]
        UC3["Snapshot KPI hàng tháng"]
        UC4["Xem KPI team"]
        UC5["Phát hiện burnout"]
        UC6["Ghi coaching note"]
        UC7["Tự đánh giá (review cycle)"]
        UC8["Leader đánh giá nhân viên"]
        UC9["Xem báo cáo KPI toàn công ty"]
        UC10["Cấu hình trọng số KPI"]
    end

    SalesStaff --> UC1
    SalesStaff --> UC2
    SalesStaff --> UC7

    LeaderActor --> UC4
    LeaderActor --> UC6
    LeaderActor --> UC8

    ExecutiveActor --> UC9
    ExecutiveActor --> UC10

    SystemActor --> UC3
    SystemActor --> UC5
```

## 8 KPI Metrics

```mermaid
graph TB
    subgraph Effort["Effort (30%)"]
        M1["Activity Rate<br/>hoạt động / ngày công"]
        M2["SLA Compliance<br/>% lead liên hệ trong 3 ngày"]
        M3["First Touch Hours<br/>giờ từ tạo lead → liên hệ đầu"]
    end

    subgraph Outcome["Outcome (50%)"]
        M4["Signed Count<br/>số lead ký HĐ"]
        M5["Signed Value<br/>tổng giá trị ký"]
        M6["Stage Conversion<br/>% lead chuyển stage"]
        M7["Pipeline Value Weighted<br/>Σ (deal_value × stage_weight)"]
    end

    subgraph Quality["Quality (20%)"]
        M8["Lost No-Response Rate<br/>% lead lost do không liên hệ"]
    end

    M1 --> Score["Composite Score<br/>0-100"]
    M2 --> Score
    M3 --> Score
    M4 --> Score
    M5 --> Score
    M6 --> Score
    M7 --> Score
    M8 --> Score
```

### Metric Details

| # | Metric | Formula | Weight Category |
|---|--------|---------|----------------|
| 1 | Activity Rate | activities / work_days | Effort |
| 2 | SLA Compliance | % leads contacted within 3 days | Effort |
| 3 | First Touch Hours | median(hours from creation to first activity) | Effort |
| 4 | Signed Count | count(leads signed in period) | Outcome |
| 5 | Signed Value | sum(deal_value of signed leads) | Outcome |
| 6 | Stage Conversion | converted / new_leads × 100 | Outcome |
| 7 | Pipeline Value Weighted | Σ deal_value × stage_weight | Outcome |
| 8 | Lost No-Response Rate | lost_leads / total_leads × 100 | Quality |

### Stage Weights (for Pipeline Value Weighted)

| Stage | Weight |
|-------|--------|
| new | 0.10 |
| interested | 0.25 |
| survey_scheduled | 0.50 |
| potential | 0.75 |
| signed_design | 1.00 |

### Composite Score Formula

```
effort_score = min(100, activity_rate × 5 + sla_compliance × 0.5 + max(0, 48 - first_touch_hours) × 2)
outcome_score = min(100, signed_count × 20 + stage_conversion × 0.5 + pipeline_weighted / 100M)
quality_score = max(0, 100 - recall_rate × 10 - lost_no_response_rate)

score = effort_score × 0.30 + outcome_score × 0.50 + quality_score × 0.20
```

## KPI Snapshot Flow

```mermaid
sequenceDiagram
    autonumber
    participant S as Scheduler<br/>Monthly 00:10 VN
    participant KE as KPI Engine
    participant DB as Database
    participant U as User

    S->>KE: snapshot_all(period="2026-07")
    KE->>DB: SELECT all active sales users

    loop Mỗi user
        KE->>DB: Aggregate queries (8 metrics)
        KE->>KE: Compute composite score
        KE->>DB: UPSERT KpiSnapshot
    end

    KE->>KE: _compute_ranks()
    KE->>DB: Set rank_in_team, rank_overall

    Note over U: User xem KPI trên dashboard
    U->>KE: GET /kpi?period=2026-07
    KE->>DB: SELECT KpiSnapshot
    KE-->>U: metrics + score + rank
```

## Burnout Detection

```mermaid
flowchart TD
    A["detect_burnout(user_id)"] --> B{"OT > 10h/tuần<br/>× 3 tuần liên tiếp?"}
    A --> C{"Chủ nhật làm việc<br/>≥ 3 ngày/tháng?"}
    A --> D{"Không nghỉ phép<br/>90 ngày liên tiếp?"}
    A --> E{"Lead overload<br/>> 25 lead active?"}

    B -->|"Có"| F["signal: ot_extended"]
    C -->|"Có"| G["signal: sunday_work"]
    D -->|"Có"| H["signal: no_leave"]
    E -->|"Có"| I["signal: lead_overload"]

    F --> J{"Đếm signals"}
    G --> J
    H --> J
    I --> J

    J -->|"0 signals"| K["risk_level = GREEN"]
    J -->|"1 signal"| K
    J -->|"2 signals"| L["risk_level = YELLOW<br/>⚠️ Cảnh báo"]
    J -->|"≥ 3 signals"| M["risk_level = RED<br/>🚨 Cần can thiệp"]
```

### Burnout Signals

| Signal | Vietnamese | Condition |
|--------|-----------|-----------|
| `ot_extended` | OT kéo dài | OT > 10h/tuần × 3 tuần liên tiếp |
| `sunday_work` | Làm CN | Làm việc chủ nhật ≥ 3 ngày/tháng |
| `no_leave` | Không nghỉ phép | 90 ngày liên tiếp không nghỉ |
| `lead_overload` | Quá tải lead | > 25 lead active cùng lúc |

### Risk Levels

| Level | Signals | Action |
|-------|---------|--------|
| GREEN | 0-1 | Bình thường |
| YELLOW | 2 | Cảnh báo leader, khuyến khích nghỉ ngơi |
| RED | >= 3 | Cần can thiệp, coaching note |

## Leaderboard

```mermaid
graph TB
    subgraph Leaderboard["Bảng xếp hạng kỳ 2026-07"]
        R1["🥇 #1 Nguyễn V.A. — 92.5"]
        R2["🥈 #2 Trần B.C. — 88.3"]
        R3["🥉 #3 Lê D.E. — 85.1"]
        R4["#4 *** — 82.0"]
        R5["#5 *** — 79.5"]
        RHidden["#6-20 ẩn tên<br/>(chỉ thấy rank mình)"]
    end

    Note["Top 5: hiện tên<br/>Còn lại: ẩn tên (anonymous)<br/>Luôn hiện rank của mình"]
```

## Review Cycle

```mermaid
stateDiagram-v2
    [*] --> pending_self: Tạo review cycle (quarterly)
    pending_self --> pending_leader: Nhân viên tự đánh giá
    pending_leader --> done: Leader đánh giá + goals

    note right of pending_self
        self_json: Tự đánh giá
    end note

    note right of pending_leader
        leader_json: Đánh giá từ leader
        goals_json: Mục tiêu quý tới
    end note

    note right of done
        suggested_grade_change: Đề xuất
        thay đổi bậc lương
    end note
```

## Coaching Notes

| Kind | Vietnamese | Description |
|------|-----------|-------------|
| `one_on_one` | 1-on-1 | Meeting notes |
| `praise` | Khen ngợi | Positive feedback |
| `concern` | Lo ngại | Performance concern |
| `plan` | Kế hoạch | Improvement plan |

## Data Model

```mermaid
erDiagram
    KpiSnapshot {
        uuid id PK
        uuid user_id FK
        string period "YYYY-MM"
        text metrics_json "8 metrics"
        float score "0-100"
        int rank_in_team
        int rank_overall
    }

    CoachingNote {
        uuid id PK
        uuid user_id FK
        uuid coach_id FK
        text note
        string kind "one_on_one|praise|concern|plan"
    }

    ReviewCycle {
        uuid id PK
        uuid user_id FK
        string period "YYYY-Qn"
        text self_json
        text leader_json
        text goals_json
        string status "pending_self|pending_leader|done"
        string suggested_grade_change
    }

    User ||--o{ KpiSnapshot : "monthly snapshot"
    User ||--o{ CoachingNote : "receives"
    User ||--o{ CoachingNote : "writes as coach"
    User ||--o{ ReviewCycle : "quarterly review"
```

## API Endpoints

| Method | Endpoint | Description | Roles |
|--------|----------|-------------|-------|
| GET | `/kpi/me?period=YYYY-MM` | My KPI snapshot | All sales |
| GET | `/kpi/team?period=YYYY-MM` | Team KPI overview | Leader |
| GET | `/kpi/leaderboard?period=YYYY-MM` | Leaderboard (anonymized) | All sales |
| GET | `/kpi/burnout` | My burnout signals | All sales |
| GET | `/kpi/burnout/{user_id}` | User burnout check | Leader, Admin |
| POST | `/kpi/snapshot?period=YYYY-MM` | Trigger snapshot | Admin |
| POST | `/kpi/coaching` | Create coaching note | Leader |
| GET | `/kpi/coaching?user_id=X` | List coaching notes | Leader, Admin |
| GET | `/kpi/review?period=YYYY-Qn` | Review cycle | All |
| POST | `/kpi/review/self` | Submit self-evaluation | Employee |
| POST | `/kpi/review/leader` | Submit leader evaluation | Leader |

## Frontend Pages

- `/kpi` — My KPI dashboard (metrics + score + trend chart)
- `/kpi/leaderboard` — Anonymized leaderboard
- `/kpi/team` — Team comparison (Leader view)
- `/kpi/coaching` — Coaching notes management

## Tags

#module #kpi #performance #burnout #leaderboard #jama-home
