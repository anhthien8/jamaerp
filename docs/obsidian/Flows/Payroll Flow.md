# Flow: Payroll Generation (Quy trình Tính lương)

## End-to-End Payroll Flow

```mermaid
sequenceDiagram
    autonumber
    participant A as Kế toán
    participant PE as Payroll Engine
    participant AS as Attendance Service
    participant AE as Approval Engine
    participant DB as Database
    participant L as Leader / Admin
    participant E as Nhân viên
    participant TG as Telegram Bot

    Note over A,DB === BƯỚC 1: GENERATE BẢNG LƯƠNG ===
    A->>PE: generate_period(period="2026-07")
    PE->>DB: Check: kỳ đã khóa chưa?
    alt Kỳ đã approved/paid
        PE-->>A: Error: "Kỳ đã khóa"
    end
    PE->>DB: DELETE old drafts of period

    loop Mỗi nhân viên active
        PE->>DB: GET User + SalaryGrade
        PE->>AS: month_summary(user_id, period)
        AS->>DB: Aggregate attendance records
        AS-->>PE: {work_days, ot_approved_hours}

        PE->>DB: SUM(commission WHERE approved)
        PE->>DB: SUM(salary_advance WHERE approved)
        PE->>PE: build_payroll_row()

        Note over PE
            gross = base × (work_days/22) + ot_pay + commission
            BHXH = 10.5% × min(base, cap)
            taxable = gross - BHXH - 11M - (deps × 4.4M)
            PIT = lũy tiến 7 bậc
            net = gross - BHXH - PIT - advances
        end note

        PE->>DB: INSERT Payroll (status=draft)
    end

    PE-->>A: {created: 200, total_net: X, missing_grade: N}

    Note over A,PE === BƯỚC 2: REVIEW & CHỈNH SỬA ===
    A->>DB: Xem bảng lương draft
    A->>DB: Chỉnh sửa bonus/allowance (nếu cần)

    Note over A,AE === BƯỚC 3: SUBMIT DUYỆT ===
    A->>AE: Submit payroll_period cho duyệt
    AE->>AE: Tạo ApprovalRequest
    AE->>L: Notify [Chờ duyệt bảng lương]

    Note over L,AE === BƯỚC 4: DUYỆT ===
    L->>AE: approve()
    AE->>AE: status = approved
    AE->>PE: Side-effect: Payroll.status → approved
    PE->>DB: Lock period (khóa mọi sửa attendance/OT)
    AE->>A: Notify [Bảng lương đã duyệt]

    Note over A,DB === BƯỚC 5: ĐÁNH DẤU ĐÃ TRẢ ===
    A->>PE: Mark payroll period as paid
    PE->>DB: Payroll.status → paid, paid_at = now

    Note over PE,TG === BƯỚC 6: GỬI PHIẾU LƯƠNG ===
    A->>PE: send_payslips(period)
    loop Mỗi payslip (status=paid)
        PE->>DB: GET Payroll + User
        alt User có telegram_user_id
            PE->>PE: format_payslip()
            PE->>TG: Send DM (chat riêng)
            PE->>DB: payslip_sent_at = now
        else User chưa liên kết Telegram
            PE->>PE: Thêm vào no_telegram list
        end
    end
    PE-->>A: {sent: 195, manual_delivery: ["Nguyễn X", "Trần Y"]}
```

## Salary Calculation Breakdown

```mermaid
flowchart TD
    subgraph Input["Đầu vào"]
        Base["Lương cơ bản<br/>(SalaryGrade)"]
        WD["Công thực tế<br/>(Attendance)"]
        OT["OT đã duyệt<br/>(Attendance)"]
        COM["Hoa hồng approved<br/>(Commission)"]
        ADV["Tạm ứng approved<br/>(SalaryAdvance)"]
        DEP["Số người phụ thuộc<br/>(User)"]
    end

    subgraph Calc["Tính toán"]
        C1["Lương theo công<br/>= base × (work_days / 22)"]
        C2["OT pay<br/>= (base/22/8) × ot_hours × 1.5"]
        C3["Gross<br/>= C1 + C2 + COM + bonus + allowance"]
        C4["BHXH NLĐ<br/>= 10.5% × min(base, 46.8M)"]
        C5["Thu nhập tính thuế<br/>= C3 - C4 - 11M - (DEP × 4.4M)"]
        C6["PIT lũy tiến 7 bậc"]
        C7["Net<br/>= C3 - C4 - C6 - ADV"]
    end

    Input --> Calc
    Base --> C1
    WD --> C1
    OT --> C2
    COM --> C3
    ADV --> C7
    DEP --> C5

    C1 --> C3
    C2 --> C3
    C4 --> C5
    C5 --> C6
    C6 --> C7
    C4 --> C7
```

## Payroll Status Lifecycle

```mermaid
stateDiagram-v2
    [*] --> draft: generate_period()

    draft --> pending_approval: submit()

    pending_approval --> approved: approve()
    pending_approval --> draft: reject()

    approved --> paid: mark_paid()

    paid --> [*]: send_payslips()

    note right of draft
        Kế toán sửa bonus, allowance
        Có thể regenerate (xóa cũ tạo mới)
    end note

    note right of approved
        Kỳ bị khóa:
        - Attendance không sửa được
        - OT không duyệt/từ chối được
    end note

    note right of paid
        Phiếu lương gửi qua
        Telegram chat riêng
    end note
```

## Period Locking

When payroll is approved or paid, the attendance service refuses modifications:

```mermaid
flowchart TD
    A["User sửa attendance"] --> B["is_period_locked(period)?"]
    B -->|"Có (approved/paid)"| C["TỪ CHỐI<br/>Kỳ lương đã khóa"]
    B -->|"Không (draft)"| D["CHO PHÉP sửa"]
```

## Insurance & Tax Reference

```mermaid
graph TB
    subgraph BHXH["Bảo hiểm xã hội"]
        B1["BHXH NLĐ: 8%"]
        B2["BHYT NLĐ: 1.5%"]
        B3["BHTN NLĐ: 1%"]
        B4["Tổng NLĐ: 10.5%"]
        B5["BHXH NSDLĐ: 21.5%"]
        B6["Trần: 46,800,000 VND"]
    end

    subgraph PIT["Thuế TNCN"]
        P1["Giảm trừ bản thân: 11,000,000đ"]
        P2["Giảm trừ/người phụ thuộc: 4,400,000đ"]
        P3["Biểu lũy tiến 7 bậc: 5%→35%"]
    end

    subgraph OT["Tăng ca"]
        O1["Hệ số: 1.5 (ngày thường)"]
        O2["Tối thiểu 0.5h mới tính"]
    end
```

## Tags

#flow #payroll #salary #tax #bhxh #cross-module #jama-home
