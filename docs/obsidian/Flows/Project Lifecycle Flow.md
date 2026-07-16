# Flow: Project Lifecycle (Quy trình Vòng đời Dự án)

## End-to-End Project Lifecycle

```mermaid
sequenceDiagram
    autonumber
    participant Sales as Sales
    participant S as CRM System
    participant PM as Project Manager
    participant Designer as Designer
    participant Purchasing as Thu mua
    participant ACCT as Kế toán
    participant Customer as Khách hàng
    participant Inventory as Inventory Module

    Note over Sales,S === KHỞI TẠO DỰ ÁN ===
    Sales->>S: Lead stage = signed_design
    S->>S: Tạo Customer từ Lead
    S->>S: Tạo Contract từ Quotation
    S->>S: Tạo Project (stage=design)
    S->>PM: Giao dự án cho PM
    S->>Designer: Giao task thiết kế

    Note over Designer,Customer === GIAI ĐOẠN 1: THIẾT KẾ (design) ===
    Designer->>S: Tạo tasks (phác thảo, 3D, chỉnh sửa)
    Designer->>S: Upload bản vẽ
    Designer->>S: Ghi TaskActivity (comment, file)
    Designer->>Customer: Trình bày bản vẽ
    Customer-->>Designer: Phản hồi, yêu cầu sửa
    Designer->>S: Cập nhật task status → done
    S->>S: Project.stage = quotation

    Note over ACCT,Customer === GIAI ĐOẠN 2: BÁO GIÁ (quotation) ===
    Sales->>S: Tạo báo giá chi tiết
    ACCT->>S: Review pricing
    S->>Customer: Gửi báo giá
    Customer-->>S: Duyệt báo giá
    S->>S: Tạo/generate Contract
    S->>S: Project.stage = procurement

    Note over Purchasing,Inventory === GIAI ĐOẠN 3: MUA SẮM (procurement) ===
    PM->>S: Tạo danh sách vật tư cần mua
    Purchasing->>S: Cập nhật Material tồn kho
    Purchasing->>Inventory: Mua vật tư thiếu
    Inventory->>S: Cập nhật quantity_in_stock
    S->>S: Project.stage = construction

    Note over PM,Customer === GIAI ĐOẠN 4: THI CÔNG (construction) ===
    PM->>S: Quản lý tasks thi công
    PM->>S: Ghi nhận xuất kho (MaterialUsage)
    Inventory->>Inventory: Trừ tồn kho
    PM->>S: Cập nhật progress (%)
    PM->>ACCT: Báo cáo chi phí thực tế
    ACCT->>S: Ghi Transaction (expense)

    Note over PM,Customer === GIAI ĐOẠN 5: NGHIỆM THU (acceptance) ===
    PM->>Customer: Mời nghiệm thu
    Customer-->>PM: Nghiệm thu + yêu cầu chỉnh sửa
    PM->>S: Hoàn thiện task cuối
    S->>S: Project.stage = completed
    ACCT->>S: Ghi nhận thanh toán cuối

    Note over S === HOÀN THÀNH ===
    S->>S: Project.status = completed
    S->>S: Tính toán final financials
```

## Project Stage Flowchart

```mermaid
flowchart TD
    A["Lead ký HĐ<br/>signed_design"] --> B["Tạo Project<br/>stage=design"]

    B --> C["DESIGN<br/>Bản vẽ + Khách duyệt"]
    C --> D["QUOTATION<br/>Báo giá chi tiết"]
    D --> E["PROCUREMENT<br/>Mua vật tư"]
    E --> F["CONSTRUCTION<br/>Thi công"]
    F --> G["ACCEPTANCE<br/>Nghiệm thu"]
    G --> H["COMPLETED<br/>Hoàn thành"]

    C -->|"Khách không duyệt"| C2["Chỉnh sửa bản vẽ"]
    C2 --> C

    D -->|"Giá thay đổi"| D2["Cập nhật báo giá"]
    D2 --> D

    F -->|"Phát sinh"| F2["VariableCost<br/>+ MaterialUsage"]
    F2 --> F
```

## Task Management per Stage

```mermaid
graph TB
    subgraph Design["Design Stage"]
        T1["Phác thảo concept"]
        T2["Bản vẽ 3D"]
        T3["Chỉnh sửa theo feedback"]
        T4["Upload file cuối"]
    end

    subgraph Quotation["Quotation Stage"]
        T5["Dự toán chi phí"]
        T6["Lập báo giá"]
        T7["Gửi khách duyệt"]
    end

    subgraph Procurement["Procurement Stage"]
        T8["Danh sách vật tư"]
        T9["Đặt hàng nhà cung cấp"]
        T10["Nhập kho"]
    end

    subgraph Construction["Construction Stage"]
        T11["Thi công phần thô"]
        T12["Lắp đặt nội thất"]
        T13["Hoàn thiện"]
    end

    subgraph Acceptance["Acceptance Stage"]
        T14["Kiểm tra chất lượng"]
        T15["Nghiệm thu với khách"]
        T16["Bàn giao + hướng dẫn"]
    end

    Design --> Quotation --> Procurement --> Construction --> Acceptance
```

## Financial Tracking per Project

```mermaid
flowchart LR
    subgraph Budget["Ngân sách"]
        DV["Design Value"]
        CV["Construction Value"]
        TV["Total Value"]
    end

    subgraph Actual["Thực tế"]
        Spent["Spent<br/>(Transactions + MaterialUsage)"]
        Margin["Margin<br/>= Total - Spent"]
    end

    DV --> TV
    CV --> TV
    TV --> Margin
    Spent --> Margin
```

## Payment Milestones

```mermaid
gantt
    title Thanh toán theo tiến độ dự án
    dateFormat X
    axisFormat %s%%

    section Hợp đồng
    Đợt 1: Đặt cọc 25%        :done, m1, 0, 25
    Đợt 2: Phần thô 25%       :active, m2, 25, 50
    Đợt 3: Nội thất 25%       :m3, 50, 75
    Đợt 4: Bàn giao 25%       :m4, 75, 100
```

## Material Usage Integration

```mermaid
sequenceDiagram
    autonumber
    participant PM as Project Manager
    participant S as System
    participant I as Inventory Module
    participant A as Accountant

    PM->>S: Ghi nhận xuất kho cho dự án
    S->>I: Check stock availability
    I-->>S: Stock OK

    S->>I: MaterialUsage(material, project, qty)
    I->>I: quantity_in_stock -= qty
    I->>I: Check low_stock

    S->>S: Tính total_cost = qty × unit_price
    S->>A: Transaction linked to project

    alt Low stock
        I->>I: Notify Purchasing
    end
```

## Commission Trigger

```mermaid
flowchart TD
    A["Project milestone completed"] --> B{"Which milestone?"}

    B -->|"signing"| C["Commission 50%<br/>(signing × rate × base)"]
    B -->|"rough_complete"| D["Commission 30%"]
    B -->|"handover"| E["Commission 20%"]

    C --> F["Create Commission<br/>(status=pending)"]
    D --> F
    E --> F

    F --> G["Leader reviews"]
    G --> H["Approve → status=approved"]
    H --> I["Included in next payroll"]
```

## Tags

#flow #project #lifecycle #cross-module #construction #jama-home
