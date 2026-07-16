# Module: Inventory Management (Quản lý Vật tư)

## Overview

The Inventory Management module tracks construction and design materials, manages stock levels, records material usage per project, and provides low-stock alerts. It supports the purchasing department in maintaining adequate supplies for ongoing projects.

## Use Case Diagram

```mermaid
graph TB
    subgraph Actors
        PurchasingActor["Thu mua"]
        PMActor["Project Manager"]
        AccountantActor["Kế toán"]
        AdminActor["Admin"]
        SystemActor["Hệ thống"]
    end

    subgraph UseCases["Inventory Use Cases"]
        UC1["Quản lý danh mục vật tư"]
        UC2["Cập nhật tồn kho"]
        UC3["Ghi nhận xuất kho<br/>(sử dụng cho dự án)"]
        UC4["Xem tồn kho hiện tại"]
        UC5["Kiểm tra vật tư thấp<br/>(low stock alert)"]
        UC6["Xem lịch sử xuất kho"]
        UC7["Xem chi phí vật tư theo dự án"]
        UC8["Quản lý nhà cung cấp"]
        UC9["Quản lý bảng đơn giá<br/>(Price Items)"]
    end

    PurchasingActor --> UC1
    PurchasingActor --> UC2
    PurchasingActor --> UC5
    PurchasingActor --> UC8
    PurchasingActor --> UC9

    PMActor --> UC3
    PMActor --> UC6
    PMActor --> UC7

    AccountantActor --> UC7
    AdminActor --> UC4
    SystemActor --> UC5
```

## Material Categories

| Category | Vietnamese | Unit Examples |
|----------|-----------|---------------|
| `wood` | Gỗ | m2, tấm |
| `stone` | Đá | m2 |
| `metal` | Kim loại | kg, m |
| `paint` | Sơn | lít, hộp |
| `electrical` | Điện | bộ, cuộn |
| `plumbing` | Nước | bộ, m |
| `furniture` | Nội thất | bộ, cái |
| `fabric` | Vải | m, cuộn |
| `glass` | Kính | m2, tấm |
| `general` | Tổng hợp | cái |

## Units

| Unit | Vietnamese | Description |
|------|-----------|-------------|
| `cái` | Cái | Piece |
| `m2` | Mét vuông | Square meter |
| `m` | Mét | Meter (length) |
| `kg` | Kilogram | Weight |
| `tấm` | Tấm | Sheet/panel |
| `bộ` | Bộ | Set |
| `cuộn` | Cuộn | Roll |
| `hộp` | Hộp | Box |
| `lít` | Lít | Liter |

## Material Usage Flow

```mermaid
sequenceDiagram
    autonumber
    participant PM as Project Manager
    participant S as System
    participant DB as Database
    participant A as Accountant

    PM->>S: Ghi nhận xuất kho<br/>(material_id, project_id, quantity)
    S->>DB: SELECT material (check stock)
    S->>S: Tính total_cost = quantity × unit_price_at_use
    S->>DB: INSERT MaterialUsage
    S->>DB: UPDATE material.quantity_in_stock -= quantity
    S->>DB: Check low_stock condition

    alt Low Stock
        S->>S: Trigger low stock notification
        S->>A: Notify "Vật tư X dưới mức tối thiểu"
    end

    Note over A: Kế toán xem chi phí vật tư/dự án
    A->>S: GET /inventory/usage?project_id=X
    S->>DB: SUM(total_cost) by material
    S-->>A: Cost breakdown
```

## Low Stock Detection

```mermaid
flowchart TD
    A["quantity_in_stock <= min_stock?"] -->|"Có"| B["is_low_stock = true"]
    A -->|"Không"| C["is_low_stock = false"]

    B --> D["Tạo Notification<br/>cho Purchasing"]
    B --> E["Hiển thị cảnh báo<br/>trên dashboard"]
```

## Price Items (Bảng đơn giá)

The PriceItem table serves the Instant Quote feature, providing standardized pricing across 3 segments.

```mermaid
graph LR
    subgraph Categories["Danh mục đơn giá"]
        TV["Trần & vách<br/>thạch cao"]
        SAN["Sàn<br/>(gỗ/gạch)"]
        SON["Sơn & giấy<br/>dán tường"]
        TUBEP["Tủ bếp &<br/>phụ kiện"]
        TUO["Tủ áo &<br/>đồ gỗ"]
        SOFA["Sofa, bàn ghế"]
        GIUONG["Giường & nệm"]
        DEN["Đèn & điện"]
        REM["Rèm & trang trí"]
        THIETBI["Thiết bị<br/>(bếp, vệ sinh)"]
        KHAC["Khác"]
    end

    subgraph Segments["Phân khúc giá"]
        Basic["Basic<br/>Tiết kiệm"]
        Standard["Standard<br/>Trung cấp"]
        Premium["Premium<br/>Cao cấp"]
    end

    Categories --> Basic
    Categories --> Standard
    Categories --> Premium
```

### Price Categories

| Code | Vietnamese | Description |
|------|-----------|-------------|
| `tran_vach` | Trần & vách thạch cao | Ceiling & gypsum walls |
| `san` | Sàn | Flooring (wood/tile) |
| `son_giay` | Sơn & giấy dán tường | Paint & wallpaper |
| `tu_bep` | Tủ bếp & phụ kiện | Kitchen cabinets |
| `tu_ao_go` | Tủ áo & đồ gỗ nội thất | Wardrobes & woodwork |
| `sofa_ban_ghe` | Sofa, bàn ghế | Sofas & tables |
| `giuong_nem` | Giường & nệm | Beds & mattresses |
| `den_dien` | Đèn & điện | Lighting & electrical |
| `rem_trang_tri` | Rèm & trang trí | Curtains & decor |
| `thiet_bi` | Thiết bị | Appliances (kitchen, bath) |
| `khac` | Khác | Other (transport, labor) |

## Data Model

```mermaid
erDiagram
    Material {
        uuid id PK
        string code UK
        string name
        string category "wood|stone|metal|..."
        string unit "cái|m2|m|kg|..."
        float unit_price
        float quantity_in_stock
        float min_stock "low stock threshold"
        string supplier
    }

    MaterialUsage {
        uuid id PK
        uuid material_id FK
        uuid project_id FK
        float quantity
        float unit_price_at_use "snapshot at time of use"
        float total_cost "quantity × unit_price"
        datetime date
        uuid created_by FK
    }

    PriceItem {
        uuid id PK
        string code UK "e.g. TRAN-01"
        string name
        string category
        string unit "m2|md|bo|cai|tron_goi"
        float price_basic
        float price_standard
        float price_premium
        bool is_active
    }

    Material ||--o{ MaterialUsage : "usages"
    Project ||--o{ MaterialUsage : "consumes"
    MaterialUsage }o--|| User : "created_by"
```

## API Endpoints

| Method | Endpoint | Description | Roles |
|--------|----------|-------------|-------|
| GET | `/inventory/materials` | List materials | Purchasing, PM, Admin |
| POST | `/inventory/materials` | Create material | Purchasing |
| PUT | `/inventory/materials/{id}` | Update material | Purchasing |
| GET | `/inventory/materials/low-stock` | Low stock alerts | Purchasing |
| POST | `/inventory/usage` | Record material usage | PM, Purchasing |
| GET | `/inventory/usage?project_id=X` | Usage by project | PM, Accountant |
| GET | `/inventory/usage?material_id=X` | Usage by material | Purchasing |
| GET | `/price-items` | List price items | All |
| POST | `/price-items` | Create price item | Purchasing |
| PUT | `/price-items/{id}` | Update price item | Purchasing |

## Frontend Pages

- `/inventory` — Material catalog + stock levels
- `/inventory/usage` — Material usage history
- `/inventory/low-stock` — Low stock alerts
- `/quote-tool` — Instant quote calculator (uses PriceItems)

## Tags

#module #inventory #materials #purchasing #pricing #jama-home
