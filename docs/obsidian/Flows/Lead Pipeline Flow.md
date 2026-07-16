# Flow: Lead Pipeline (Quy trình Pipeline Lead)

## End-to-End Lead Lifecycle

This flow traces a lead from initial capture through all pipeline stages to either conversion or loss, showing cross-module interactions.

```mermaid
sequenceDiagram
    autonumber
    participant FB as Facebook/Zalo/Website
    participant DE as Data Entry
    participant S as CRM System
    participant AI as AI Service
    participant L as Leader
    participant Sales as Sales Staff
    participant C as Customer
    participant AE as Approval Engine
    participant P as Project Module
    participant Auto as Automation

    Note over FB,S === GIAI ĐOẠN 1: TIẾP NHẬN LEAD ===
    FB->>S: Lead từ nguồn (FB/Zalo/Web/Ref)
    S->>S: Tạo Lead (stage=new)
    S->>AI: Request AI scoring
    AI-->>S: ai_score + ai_notes
    L->>S: Giao lead cho nhân viên
    S->>S: assigned_to = sales_user
    S->>Sales: Notify [Lead được giao]

    Note over Sales,C === GIAI ĐOẠN 2: LIÊN HỆ & TƯ VẤN ===
    Sales->>C: Gọi điện / Nhắn tin
    Sales->>S: Ghi Activity (type=call)
    C-->>Sales: Phản hồi quan tâm
    Sales->>S: Chuyển stage: new → interested
    S->>S: Log stage_change activity
    S->>S: Update last_contacted_at

    Note over Auto,S --- Automation ---
    Auto->>S: Check: lead không liên hệ > 3 ngày?
    S->>Sales: Notify [Nhắc CSKH]

    Note over Sales,C === GIAI ĐOẠN 3: ĐẶT LỊCH KHẢO SÁT ===
    Sales->>C: Hẹn lịch khảo sát
    C-->>Sales: Đồng ý ngày khảo sát
    Sales->>S: Chuyển stage: interested → survey_scheduled
    Sales->>S: Set survey_date

    Note over Sales,C === GIAI ĐOẠN 4: KHẢO SÁT THỰC ĐỊA ===
    Sales->>C: Khảo sát thực địa
    Sales->>S: Ghi Activity (type=survey)
    Sales->>S: Upload survey_photos
    Sales->>S: Cập nhật area_sqm, property_type
    C-->>Sales: Xác nhận muốn ký HĐ
    Sales->>S: Chuyển stage: survey_scheduled → potential

    Note over Sales,C === GIAI ĐOẠN 5: CHỐT DEAL ===
    Sales->>S: Tạo Quotation (design)
    Sales->>C: Gửi báo giá
    C-->>Sales: Đồng ý ký HĐ
    Sales->>S: Chuyển stage: potential → signed_design
    S->>S: Set design_contract_value

    Note over S,P === GIAI ĐOẠN 6: CHUYỂN ĐỔI ===
    S->>S: Tạo Customer từ Lead
    S->>S: Tạo Contract từ Quotation
    S->>P: Tạo Project mới
    S->>P: Assign PM + Designer
    P->>Sales: Notify [Dự án đã tạo]

    Note over Auto,S --- Nếu KH từ chối ---
    Note over Sales: KH không phản hồi / từ chối
    Sales->>S: Chuyển stage → lost hoặc dormant
    S->>S: Ghi lý do lost
```

## Stage Transition Rules

```mermaid
flowchart TD
    subgraph Valid["Chuyển hợp lệ"]
        N["new"] -->|"KH phản hồi"| I["interested"]
        N -->|"KH từ chối"| L["lost"]
        N -->|"KH không phản hồi"| D["dormant"]

        I -->|"Đặt lịch KS"| SS["survey_scheduled"]
        I -->|"KH từ chối"| L
        I -->|"KH không phản hồi"| D

        SS -->|"KS thành công"| P["potential"]
        SS -->|"KH hủy"| L
        SS -->|"KH không tham gia"| D

        P -->|"Ký HĐ"| SD["signed_design"]
        P -->|"KH không ký"| L
        P -->|"KH tạm hoãn"| D

        D -->|"KH quay lại"| I
        D -->|"Xác nhận mất"| L
    end

    style SD fill:#22c55e,color:#000
    style L fill:#ef4444,color:#fff
    style D fill:#f59e0b,color:#000
```

## Automation Touchpoints

```mermaid
flowchart LR
    subgraph Daily["Automation hàng ngày (07:00 VN)"]
        A1["Follow-up reminder<br/>(3 ngày không liên hệ)"]
        A2["Lead recall<br/>(7 ngày inactive)"]
        A3["Payment reminder<br/>(đợt thanh toán pending)"]
    end

    subgraph Events["Event-driven"]
        E1["Stage change → log activity"]
        E2["Lead assigned → notify"]
        E3["Lead recalled → notify 2 users"]
        E4["Contract signed → create project"]
    end

    A1 --> Sales["Sales Staff"]
    A2 --> Sales
    A3 --> Accountant["Kế toán"]
    E2 --> Sales
    E3 --> Sales
    E4 --> PM["Project Manager"]
```

## Lead Recall Process

```mermaid
sequenceDiagram
    autonumber
    participant Auto as Automation (07:00)
    participant S as System
    participant Sales1 as Sales A (hiện tại)
    participant Sales2 as Sales B (mới)
    participant L as Leader

    Auto->>S: Quét leads active<br/>last_contacted > recall_days

    loop Mỗi lead quá hạn
        S->>S: Tìm team leader
        L->>S: Hoặc auto-assign theo round-robin
        S->>S: Reassign: Sales A → Sales B
        S->>S: Ghi Activity (type=assignment)
        S->>Sales1: Notify [Lead bị thu hồi]
        S->>Sales2: Notify [Lead được giao mới]
        S->>S: Ghi AuditLog
    end
```

## KPI Impact

Each stage action affects the performer's KPI metrics:

| Action | KPI Metric Affected |
|--------|-------------------|
| Ghi Activity | Activity Rate (+) |
| Liên hệ trong 3 ngày | SLA Compliance (+) |
| Liên hệ đầu tiên | First Touch Hours (measured) |
| Chuyển stage → signed | Signed Count (+), Signed Value (+) |
| Chuyển stage (any) | Stage Conversion (measured) |
| Lead bị lost | Lost No-Response Rate (-) |
| Lead active | Pipeline Value Weighted (measured) |

## Tags

#flow #lead-pipeline #crm #cross-module #jama-home
