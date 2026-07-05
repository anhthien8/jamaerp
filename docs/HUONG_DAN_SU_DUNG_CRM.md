# 📘 HƯỚNG DẪN SỬ DỤNG HỆ THỐNG JAMA HOME ERP/CRM

> **Phiên bản:** 1.0 — Cập nhật: 05/07/2026
> **Dành cho:** Toàn bộ nhân sự JAMA HOME
> **Địa chỉ truy cập:** `http://localhost:3000` (Frontend) | `http://localhost:8000` (Backend API)

---

## 📑 MỤC LỤC

1. [Giới thiệu hệ thống](#1-giới-thiệu-hệ-thống)
2. [Đăng nhập & Giao diện chung](#2-đăng-nhập--giao-diện-chung)
3. [Dashboard — Trang tổng quan](#3-dashboard--trang-tổng-quan)
4. [Pipeline Leads — Quản lý khách hàng tiềm năng](#4-pipeline-leads--quản-lý-khách-hàng-tiềm-năng)
5. [Projects — Quản lý dự án](#5-projects--quản-lý-dự-án)
6. [Customers — Quản lý khách hàng](#6-customers--quản-lý-khách-hàng)
7. [Contracts — Quản lý hợp đồng](#7-contracts--quản-lý-hợp-đồng)
8. [Quotations — Quản lý báo giá](#8-quotations--quản-lý-báo-giá)
9. [Inventory — Kho vật tư](#9-inventory--kho-vật-tư)
10. [Accounting — Kế toán](#10-accounting--kế-toán)
11. [HR — Nhân sự](#11-hr--nhân-sự)
12. [Finance — Tài chính](#12-finance--tài-chính)
13. [P&L — Báo cáo Lãi/Lỗ](#13-pl--báo-cáo-lãilỗ)
14. [Reports — Báo cáo](#14-reports--báo-cáo)
15. [Settings — Cài đặt](#15-settings--cài-đặt)
16. [🤖 Telegram Bot — Trợ lý bán hàng trên điện thoại](#16-telegram-bot--trợ-lý-bán-hàng-trên-điện-thoại)
17. [Bảng phân quyền theo vai trò](#17-bảng-phân-quyền-theo-vai-trò)
18. [Quy trình vận hành tổng thể](#18-quy-trình-vận-hành-tổng-thể)
19. [Câu hỏi thường gặp (FAQ)](#19-câu-hỏi-thường-gặp)

---

## 1. Giới thiệu hệ thống

### JAMA HOME ERP/CRM là gì?

Hệ thống quản lý tổng thể dành riêng cho **JAMA HOME — Nội thất cao cấp**, bao gồm:

- **CRM** (Customer Relationship Management): Quản lý khách hàng tiềm năng, pipeline bán hàng
- **ERP** (Enterprise Resource Planning): Quản lý dự án, vật tư, tài chính, nhân sự

### Hệ thống có 2 chế độ hoạt động:

| Chế độ | Mô tả | Khi nào dùng |
|--------|--------|--------------|
| **🟢 Work Mode** | Kết nối dữ liệu thật từ server | Làm việc hàng ngày |
| **🟡 Demo Mode** | Dữ liệu mẫu, không ảnh hưởng dữ liệu thật | Training nhân sự mới, demo khách hàng |

> 💡 **Mẹo:** Khi đăng nhập, bạn sẽ thấy banner ở đầu trang cho biết đang ở chế độ nào. Có thể chuyển đổi giữa 2 chế độ ngay tại Sidebar.

---

## 2. Đăng nhập & Giao diện chung

### 2.1 Cách đăng nhập

1. Mở trình duyệt, truy cập: **`http://localhost:3000/login`**
2. Nhập **Email** và **Mật khẩu** được cấp
3. Nhấn **"Đăng nhập"**

### 2.2 Tài khoản theo vai trò

| Vai trò | Email | Mật khẩu | Ghi chú |
|---------|-------|-----------|---------|
| 🔴 **Giám đốc (Admin)** | `admin@jamahome.vn` | `admin123` | Toàn quyền |
| 🟣 **Ban Quản Trị (CEO)** | `ceo@jamahome.vn` | `ceo123` | Xem Dashboard tổng, P&L |
| 🟠 **Trưởng phòng (Leader)** | `leader@jamahome.vn` | `leader123` | Quản lý team, xem báo cáo |
| 🔵 **Nhân viên Sale** | `sales@jamahome.vn` | `sales123` | Pipeline, hợp đồng |
| 🟢 **Kế toán / Nhân sự** | `accountant@jamahome.vn` | `account123` | Kế toán, HR, P&L |
| 🟡 **Nhân viên Thiết kế** | `designer@jamahome.vn` | `designer123` | Dự án, báo giá |
| 🔵 **Trưởng Dự án (PM)** | `pm@jamahome.vn` | `pm123` | Quản lý dự án, vật tư |
| 🟤 **Nhân viên Thu mua** | `purchasing@jamahome.vn` | `purchase123` | Kho vật tư |

### 2.3 Giao diện chung

Sau khi đăng nhập, giao diện gồm 2 phần chính:

```
┌──────────┬─────────────────────────────────────────┐
│          │                                         │
│  SIDEBAR │          NỘI DUNG TRANG                 │
│  (Menu)  │                                         │
│          │    Thay đổi tùy theo trang bạn chọn     │
│  📊 Dashboard                                      │
│  🎯 Pipeline                                       │
│  📁 Dự án                                          │
│  👥 Khách hàng                                     │
│  📋 Hợp đồng                                      │
│  💰 Báo giá                                        │
│  📦 Kho vật tư                                     │
│  🧾 Kế toán                                        │
│  👨‍💼 Nhân sự                                        │
│  💵 Tài chính                                      │
│  📈 P&L                                            │
│  📊 Báo cáo                                        │
│  ⚙️  Cài đặt                                       │
│          │                                         │
└──────────┴─────────────────────────────────────────┘
```

> ⚠️ **Lưu ý:** Sidebar chỉ hiển thị các mục bạn có quyền truy cập. Nếu bạn không thấy một mục nào đó, nghĩa là vai trò của bạn không được phân quyền cho chức năng đó.

---

## 3. Dashboard — Trang tổng quan

**Đường dẫn:** `http://localhost:3000/` (Trang chủ)
**Ai được xem:** Tất cả nhân sự

Dashboard hiển thị **tổng quan hoạt động kinh doanh** với nội dung khác nhau tùy vai trò:

### 3.1 Dashboard dành cho Giám đốc / Ban Quản Trị
- **Tổng doanh thu** tháng/quý/năm
- **Số leads mới** trong kỳ
- **Tỷ lệ chuyển đổi** (lead → khách hàng)
- **Leads quá hạn** cần chăm sóc (highlight đỏ)
- **Biểu đồ tổng quan** theo thời gian
- **Top nhân viên kinh doanh** theo hiệu suất

### 3.2 Dashboard dành cho Trưởng phòng
- Dữ liệu của **team mình** phụ trách
- Tiến độ dự án đang triển khai
- Leads cần follow-up trong ngày

### 3.3 Dashboard dành cho Nhân viên
- Leads/Dự án **được giao cho mình**
- Lịch follow-up hôm nay
- Thông báo công việc cần làm

### 3.4 Dashboard dành cho Kế toán
- Tổng hợp tài chính
- Công nợ phải thu/phải trả
- Hợp đồng cần thanh toán

---

## 4. Pipeline Leads — Quản lý khách hàng tiềm năng

**Đường dẫn:** `http://localhost:3000/leads`
**Ai được xem:** Admin, Leader, Sales

### 4.1 Pipeline là gì?

Pipeline hiển thị khách hàng tiềm năng (Leads) dưới dạng **bảng Kanban** — mỗi cột đại diện cho một giai đoạn trong quy trình bán hàng:

```
┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐
│   MỚI    │  │ QUAN TÂM │  │  ĐÃ HẸN  │  │  TIỀM    │  │  ĐÃ KÝ  │
│  (New)   │→ │(Interest)│→ │ KHẢO SÁT │→ │  NĂNG    │→ │ HỢP ĐỒNG│
│          │  │          │  │(Surveyed)│  │(Potential)│  │ (Signed) │
│ Card 1   │  │ Card 3   │  │ Card 5   │  │          │  │          │
│ Card 2   │  │ Card 4   │  │          │  │          │  │          │
└──────────┘  └──────────┘  └──────────┘  └──────────┘  └──────────┘
```

### 4.2 Các giai đoạn Lead

| Giai đoạn | Mô tả | Hành động tiếp theo |
|-----------|--------|---------------------|
| **Mới (New)** | Lead vừa nhập vào hệ thống | Liên hệ lần đầu, xác nhận nhu cầu |
| **Quan tâm (Interested)** | Khách hàng đã thể hiện quan tâm | Tư vấn chi tiết, gửi portfolio |
| **Đã hẹn khảo sát (Survey Scheduled)** | Đã lên lịch đến khảo sát hiện trạng | Đi khảo sát, chụp ảnh, đo đạc |
| **Tiềm năng (Potential)** | Khách hàng có khả năng ký hợp đồng cao | Gửi báo giá sơ bộ, thương thảo |
| **Đã ký HĐ Thiết kế (Signed Design)** | Đã ký hợp đồng thiết kế | ✅ Tự động chuyển sang **Dự án** |
| **Mất (Lost)** | Khách hàng không tiếp tục | Ghi lý do mất để phân tích |

### 4.3 Cách sử dụng

#### Thêm Lead mới
1. Nhấn nút **"+ Thêm Lead"** ở góc trên phải
2. Điền thông tin: Tên khách hàng, Số điện thoại, Email, Nguồn lead, Giá trị dự kiến
3. Nhấn **"Lưu"**

#### Chuyển giai đoạn Lead
1. Click vào thẻ Lead trên bảng Kanban
2. Trong popup chi tiết, chọn **giai đoạn mới** từ dropdown
3. Hệ thống tự động cập nhật và di chuyển thẻ

#### Ghi hoạt động (Activity)
1. Click vào thẻ Lead
2. Trong phần **"Ghi chú"**, nhập nội dung cuộc gọi/gặp mặt
3. Nhấn **"Gửi"** → hoạt động được lưu lại theo timeline

#### Đánh dấu Lead bị mất
1. Click vào Lead → chọn giai đoạn **"Lost"**
2. Chọn lý do mất:
   - Giá cao
   - Chọn đối thủ
   - Không phản hồi
   - Hoãn dự án
   - Lý do khác (nhập tùy chỉnh)

#### Tìm kiếm Lead
- Sử dụng ô tìm kiếm ở đầu trang để lọc theo tên, số điện thoại hoặc email

> 🔄 **Chuyển đổi tự động:** Khi Lead chuyển sang giai đoạn **"Đã ký HĐ Thiết kế"**, hệ thống tự động tạo:
> - 1 **Khách hàng** mới trong danh sách Customers
> - 1 **Dự án** mới với **19 đầu việc** theo quy trình chuẩn
> - Không cần nhập lại thông tin!

---

## 5. Projects — Quản lý dự án

**Đường dẫn:** `http://localhost:3000/projects`
**Ai được xem:** Tất cả (phạm vi xem khác nhau tùy vai trò)

### 5.1 Hai chế độ xem

| Chế độ | Biểu tượng | Mô tả |
|--------|------------|--------|
| **📊 Pipeline Kanban** | Mặc định | Xem dự án theo 6 giai đoạn trên bảng Kanban |
| **📋 Danh sách** | Nút toggle | Xem dạng bảng truyền thống |

### 5.2 Pipeline dự án — 6 giai đoạn

```
Thiết kế → Báo giá → Thu mua → Thi công → Nghiệm thu & Bàn giao → Hoàn thành
  (5 việc)  (4 việc) (3 việc)  (4 việc)     (3 việc)
```

| Giai đoạn | Đầu việc chính | Phòng phụ trách |
|-----------|----------------|-----------------|
| **Thiết kế** | Concept, Phối cảnh 3D, Bản vẽ kỹ thuật, Chốt thiết kế, Trình bày KH | Phòng Thiết kế |
| **Báo giá** | Bóc tách vật tư, Tổng hợp báo giá, Duyệt nội bộ, Gửi khách hàng | Phòng Thiết kế + Sale |
| **Thu mua** | Chọn nhà cung cấp, Đặt hàng, Kiểm tra nhận hàng | Phòng Thu mua |
| **Thi công** | Chuẩn bị, Lắp đặt, Hoàn thiện, Vệ sinh bàn giao | Phòng Thi công / PM |
| **Nghiệm thu** | Nghiệm thu nội bộ, Nghiệm thu khách hàng, Bàn giao | PM + Sale |

### 5.3 Quản lý đầu việc (Tasks)

#### Xem đầu việc theo nhóm
1. Click vào thẻ dự án trên Kanban
2. Popup hiển thị tất cả đầu việc, **được nhóm theo giai đoạn** (Thiết kế, Báo giá, Thu mua...)
3. Mỗi đầu việc hiển thị: Tên, trạng thái, người phụ trách

#### Cập nhật trạng thái đầu việc
1. Click vào đầu việc cụ thể
2. Chọn trạng thái:
   - ⏳ **Chờ** (Todo)
   - 🔄 **Đang làm** (In Progress)
   - ✅ **Hoàn thành** (Done)
3. Thanh tiến độ tự động cập nhật theo % hoàn thành

#### Ghi chú & Upload file cho đầu việc
1. Click vào đầu việc → mở **Task Detail Modal**
2. Trong phần **"Ghi chú & Media"**:
   - Nhập nội dung ghi chú
   - **Upload file**: Click biểu tượng 📎 để đính kèm ảnh, PDF, DWG, SKP
   - Hỗ trợ đa file: ảnh nghiệm thu, file báo giá, bản vẽ kỹ thuật...
3. Nhấn **"Gửi"** → ghi chú + file được lưu trên timeline hoạt động

#### Lưu file kết quả chốt (Final File)
- Mỗi đầu việc có ô **"File kết quả chốt"** để lưu link file quan trọng nhất
- Ví dụ: Link file bản vẽ chốt cuối cùng, file báo giá đã duyệt, biên bản nghiệm thu

### 5.4 Bộ lọc dự án
- **Theo trạng thái:** Đang thực hiện / Tạm dừng / Hoàn thành / Hủy
- **Theo quý:** Q1, Q2, Q3, Q4
- **Tìm kiếm:** Theo tên dự án, tên khách hàng
- **Việc của tôi:** Toggle để chỉ xem các task được giao cho mình

### 5.5 Tạo dự án mới (Admin, Leader, PM)
1. Nhấn **"+ Dự án mới"**
2. Điền thông tin: Tên dự án, Khách hàng, Địa chỉ, Loại hình, Giá trị, Ngày bắt đầu
3. Nhấn **"Tạo dự án"** → Hệ thống tự động tạo 19 đầu việc chuẩn

---

## 6. Customers — Quản lý khách hàng

**Đường dẫn:** `http://localhost:3000/customers`
**Ai được xem:** Admin, Leader, Sales, Kế toán, PM (chỉ đọc)

### 6.1 Chức năng chính
- Danh sách khách hàng đã ký hợp đồng
- Thông tin liên hệ: Tên, SĐT, Email, Địa chỉ
- Lịch sử dự án của khách hàng
- Nguồn khách hàng (từ Lead nào chuyển đổi sang)

### 6.2 Cách sử dụng
- **Xem danh sách:** Trang hiển thị bảng với phân trang
- **Tìm kiếm:** Lọc theo tên, SĐT, email
- **Xem chi tiết:** Click vào tên khách hàng để xem lịch sử

> 💡 Khách hàng được **tạo tự động** khi Lead chuyển sang giai đoạn "Đã ký HĐ Thiết kế". Bạn cũng có thể thêm thủ công.

---

## 7. Contracts — Quản lý hợp đồng

**Đường dẫn:** `http://localhost:3000/contracts`
**Ai được xem:** Admin, Leader, Sales, PM, Kế toán

### 7.1 Thông tin hợp đồng
- **Mã hợp đồng** (tự sinh)
- **Khách hàng** liên kết
- **Dự án** liên kết
- **Giá trị hợp đồng**
- **Loại:** Thiết kế / Thi công / Trọn gói
- **Trạng thái:** Dự thảo / Đã ký / Đang thực hiện / Hoàn thành
- **Ngày ký**, **Ngày bắt đầu**, **Ngày dự kiến kết thúc**

### 7.2 Tạo hợp đồng mới
1. Nhấn **"+ Thêm hợp đồng"**
2. Chọn khách hàng, dự án, loại hợp đồng
3. Nhập giá trị và các mốc thời gian
4. Nhấn **"Lưu"**

### 7.3 Sửa hợp đồng
- Click vào hợp đồng → nhấn biểu tượng ✏️ **Sửa**
- Chỉnh sửa trực tiếp trên form → nhấn **"Cập nhật"**

---

## 8. Quotations — Quản lý báo giá

**Đường dẫn:** `http://localhost:3000/quotations`
**Ai được xem:** Admin, Leader, Sales, Designer, PM

### 8.1 Chức năng
- Tạo và quản lý báo giá cho từng dự án
- Liên kết với dự án và khách hàng
- Upload file báo giá (PDF, Excel)
- Theo dõi trạng thái: Dự thảo → Gửi khách → Duyệt → Từ chối

### 8.2 Tạo báo giá mới (Designer, PM, Sales)
1. Nhấn **"+ Báo giá mới"**
2. Chọn dự án liên kết
3. Nhập tên báo giá, giá trị, mô tả
4. Upload file báo giá đính kèm
5. Nhấn **"Lưu"**

### 8.3 Upload nhiều file
- Hỗ trợ upload đa file: PDF, ảnh (JPG/PNG), DWG, SKP
- Kéo thả file hoặc click để chọn từ máy tính

---

## 9. Inventory — Kho vật tư

**Đường dẫn:** `http://localhost:3000/inventory`
**Ai được xem:** ⚠️ **Chỉ Admin và Thu mua** (các vai trò khác không thấy mục này trên Sidebar)

### 9.1 Chức năng
- Quản lý danh sách vật tư, vật liệu
- Theo dõi tồn kho: Số lượng nhập, xuất, tồn
- Giá nhập, nhà cung cấp
- Giao dịch xuất/nhập kho theo dự án

### 9.2 Yêu cầu vật tư từ PM
- **Trưởng Dự án (PM)** có thể gửi yêu cầu vật tư trực tiếp từ trang dự án
- Yêu cầu sẽ hiển thị trong danh sách chờ duyệt của bộ phận Thu mua

### 9.3 Phân quyền đặc biệt

| Vai trò | Quyền hạn |
|---------|-----------|
| Admin | Xem, thêm, sửa, xóa toàn bộ |
| Thu mua | Xem, thêm, sửa, xóa toàn bộ |
| PM | Chỉ gửi yêu cầu vật tư (từ trang Dự án) |
| Kế toán | Xem để theo dõi chi phí |
| Các vai trò khác | ❌ Không có quyền truy cập |

---

## 10. Accounting — Kế toán

**Đường dẫn:** `http://localhost:3000/accounting`
**Ai được xem:** Admin, Kế toán, Leader (chỉ đọc)

### 10.1 Chức năng
- **Sổ giao dịch:** Thu/Chi theo dự án và danh mục
- **Công nợ phải thu:** Danh sách khách hàng còn nợ, phân loại theo tuổi nợ
- **Bộ lọc thời gian:** Lọc theo ngày, tháng, quý, năm
- **Xuất CSV:** Xuất dữ liệu kế toán ra file Excel/CSV

### 10.2 Ghi nhận giao dịch
1. Nhấn **"+ Giao dịch mới"**
2. Chọn loại: **Thu** hoặc **Chi**
3. Nhập số tiền, danh mục, dự án liên quan
4. Nhấn **"Lưu"**

### 10.3 Công nợ phải thu (Receivables Aging)
- Hiển thị bảng phân loại nợ theo thời gian:
  - 🟢 Dưới 30 ngày
  - 🟡 30-60 ngày
  - 🟠 60-90 ngày
  - 🔴 Trên 90 ngày

### 10.4 Xuất dữ liệu
- Nhấn nút **"📥 Xuất CSV"** để tải file kế toán
- File hỗ trợ mở trực tiếp bằng Excel, Google Sheets

---

## 11. HR — Nhân sự

**Đường dẫn:** `http://localhost:3000/hr`
**Ai được xem:** Admin, Kế toán (quản lý), Leader (chỉ đọc)

### 11.1 Chức năng
- **Danh sách nhân viên:** Tên, email, vai trò, phòng ban, trạng thái
- **Thêm nhân viên mới:** Tạo tài khoản đăng nhập cho nhân sự mới
- **Nghỉ việc (Offboard):** Vô hiệu hóa tài khoản nhân viên đã nghỉ

### 11.2 Thêm nhân viên mới (Chỉ Admin, Kế toán)
1. Nhấn nút **"+ Thêm Nhân viên"**
2. Điền: Họ tên, Email, SĐT, Mật khẩu, Vai trò, Phòng ban
3. Nhấn **"Tạo"** → Nhân viên mới có thể đăng nhập ngay

### 11.3 Xử lý nghỉ việc (Chỉ Admin, Kế toán)
1. Tìm nhân viên trong danh sách
2. Nhấn nút **"Nghỉ việc"** (biểu tượng 🚫)
3. Xác nhận → Tài khoản bị vô hiệu hóa, không thể đăng nhập

> ⚠️ **Lưu ý:** Nút "Thêm Nhân viên" và "Nghỉ việc" chỉ hiển thị cho Admin và Kế toán. Các vai trò khác chỉ xem danh sách.

---

## 12. Finance — Tài chính

**Đường dẫn:** `http://localhost:3000/finance`
**Ai được xem:** Admin, Kế toán

### 12.1 Bốn tab quản lý

#### Tab 1: Bậc lương
- Quản lý 6 bậc lương từ Bậc 1 → Bậc 6
- Mỗi bậc gồm: Lương cơ bản, tỷ lệ BHXH (10.5%), BHYT (1.5%), BHTN (1%)
- Tỷ lệ đóng BHXH phía công ty: 21.5%

| Bậc | Lương cơ bản |
|-----|-------------|
| Bậc 1 | 8,000,000đ |
| Bậc 2 | 10,000,000đ |
| Bậc 3 | 12,000,000đ |
| Bậc 4 | 15,000,000đ |
| Bậc 5 | 20,000,000đ |
| Bậc 6 | 25,000,000đ |

#### Tab 2: Định phí (Chi phí cố định)
- Tiền mặt bằng, điện nước, internet, bảo hiểm văn phòng
- Lọc và nhập theo tháng
- Thêm/sửa trực tiếp trên bảng

#### Tab 3: Biến phí (Chi phí biến đổi)
- Chi phí phát sinh theo dự án: di lại, hao hụt vật liệu
- Liên kết với dự án cụ thể
- Lọc theo tháng/quý/năm

#### Tab 4: Hoa hồng (Commission)
- Cấu trúc hoa hồng theo phòng ban:
  - **Sales:** 3% HĐ thiết kế, 2% HĐ thi công
  - **Leader:** 0.5% override
  - **Designer:** 1% phí thiết kế
  - **PM:** 0.5% giá trị dự án

---

## 13. P&L — Báo cáo Lãi/Lỗ

**Đường dẫn:** `http://localhost:3000/pl`
**Ai được xem:** ⚠️ **Chỉ Admin, Ban Quản Trị, Kế toán** (C-level only)

### 13.1 Nội dung
- **Tổng doanh thu** từ hợp đồng
- **Tổng chi phí** (vật tư + nhân công + vận hành)
- **Lợi nhuận gộp** và **biên lợi nhuận (%)**
- Phân tích theo dự án, theo tháng

### 13.2 Lưu ý hiển thị
- Trên **Desktop**: Hiển thị bảng P&L đầy đủ
- Trên **Mobile**: Hiển thị dạng thẻ gọn gàng (ẩn bảng chi tiết)

---

## 14. Reports — Báo cáo

**Đường dẫn:** `http://localhost:3000/reports`
**Ai được xem:** Admin, Leader, Sales, PM, Kế toán

### 14.1 Các loại báo cáo
- Báo cáo doanh thu theo thời gian
- Báo cáo pipeline (tỷ lệ chuyển đổi)
- Báo cáo hiệu suất nhân viên
- Báo cáo dự án (tiến độ, chi phí)

---

## 15. Settings — Cài đặt

**Đường dẫn:** `http://localhost:3000/settings`
**Ai được xem:** Tất cả nhân sự

### 15.1 Chức năng
- Thay đổi thông tin cá nhân
- Đổi mật khẩu
- Chuyển đổi chế độ Demo/Work
- Cài đặt thông báo

---

## 16. 🤖 Telegram Bot — Trợ lý bán hàng trên điện thoại

**Dành cho:** Nhân viên Sale, Leader, Admin
**Yêu cầu:** Ứng dụng Telegram trên điện thoại

### 16.1 Telegram Bot là gì?

Telegram Bot là **trợ lý bán hàng tự động** chạy trên ứng dụng Telegram, cho phép nhân viên Sale thao tác với CRM **ngay trên điện thoại** mà không cần mở trình duyệt web. Bot đặc biệt hữu ích khi:

- 📱 Đang đi gặp khách hàng ngoài công trường
- ⚡ Cần nhập lead nhanh từ tin nhắn Zalo/Facebook
- 🌅 Xem briefing đầu ngày để biết việc cần làm
- 📊 Kiểm tra nhanh tình trạng pipeline

### 16.2 Thiết lập ban đầu (1 lần duy nhất)

1. Mở ứng dụng **Telegram** trên điện thoại
2. Tìm bot: `@JamaHomeCRM_bot` (tên bot do Admin cung cấp)
3. Nhấn **"Start"** hoặc gõ `/start`
4. Bot sẽ tự nhận dạng tài khoản CRM qua Telegram ID của bạn
5. Nếu thành công, bot hiển thị:
   ```
   🏠 Chào mừng [Tên bạn]!
   📋 Vai trò: [Vai trò của bạn]
   👥 Phòng ban: [Phòng ban]
   ```

> ⚠️ Nếu bot báo **"Chưa liên kết tài khoản CRM"**, hãy gửi Telegram ID cho Admin để được liên kết. Bot sẽ hiển thị Telegram ID của bạn trong tin nhắn lỗi.

### 16.3 Các lệnh chính

| Lệnh | Chức năng | Ai dùng |
|-------|-----------|--------|
| `/start` | Đăng nhập / Kiểm tra kết nối | Tất cả |
| `/lead` | Nhập lead mới từ tin nhắn Zalo | Sale, Leader, Admin |
| `/pipeline` | Xem tổng quan pipeline | Sale, Leader, Admin |
| `/briefing` | Briefing cá nhân đầu ngày | Sale, Leader, Admin |
| `/suggest` | Gợi ý AI cho lead cụ thể | Sale, Leader, Admin |

---

### 16.4 Lệnh `/lead` — Nhập lead mới (⭐ Quan trọng nhất)

Đây là tính năng **mạnh nhất** của bot — cho phép bạn copy tin nhắn khách hàng từ Zalo rồi paste vào Telegram, bot sẽ **tự động phân tích bằng AI** và trích xuất thông tin.

#### Cách sử dụng:

**Bước 1:** Gõ `/lead` trong Telegram
```
📝 Nhập lead mới

Copy/paste tin nhắn khách hàng từ Zalo vào đây.
Bot sẽ tự động phân tích và trích xuất thông tin.
```

**Bước 2:** Copy tin nhắn từ Zalo/Facebook, paste vào Telegram
```
Anh Minh 0901234567
Địa chỉ: 123 Nguyễn Huệ Q1
Cần thiết kế nội thất căn hộ 85m2
Ngân sách khoảng 500 triệu
Bạn bè giới thiệu
```

**Bước 3:** Bot AI tự động phân tích và hiển thị:
```
🟢 Kết quả phân tích (Độ chính xác: 95%)

👤 Tên: Anh Minh
📱 SĐT: 0901234567
📍 Địa chỉ: 123 Nguyễn Huệ Q1
🏠 Loại: Căn hộ
📐 Diện tích: 85 m²
💰 Ngân sách: 500 triệu
📋 Nhu cầu: Thiết kế nội thất
📢 Nguồn: Bạn bè giới thiệu
```

**Bước 4:** Nhấn nút xác nhận:
- ✅ **Xác nhận lưu** → Lead được lưu vào CRM ngay lập tức
- ✏️ **Sửa** → Chỉnh sửa thông tin trước khi lưu
- ❌ **Hủy** → Không lưu

#### Tính năng tự động nhận dạng:
Bot cũng có thể **tự động nhận dạng** tin nhắn có chứa thông tin lead (SĐT, tên khách) mà không cần gõ `/lead` trước. Chỉ cần forward hoặc paste tin nhắn vào chat bot.

---

### 16.5 Lệnh `/pipeline` — Xem Pipeline

Hiển thị tổng quan pipeline dạng biểu đồ text ngay trong Telegram:

```
📊 PIPELINE CRM

🆕 Mới tiếp nhận: 5
█████
💡 Có nhu cầu: 3
███
📅 Đã hẹn khảo sát: 2
██
⭐ KH tiềm năng: 1
█
✍️ Ký thiết kế: 1
█

📈 Tổng quan:
• Tổng leads: 12
• Tỷ lệ chuyển đổi: 8.3%
• Giá trị pipeline: 2.5 tỷ ₫
• Chưa phân công: 0
```

---

### 16.6 Lệnh `/briefing` — Briefing đầu ngày

Mỗi sáng, nhân viên Sale gõ `/briefing` để xem:

```
☀️ Briefing — Nguyễn Văn A

📊 Tổng lead đang xử lý: 8

Theo giai đoạn:
  🆕 Mới: 3
  💡 Có nhu cầu: 2
  📅 Hẹn khảo sát: 2
  ⭐ Tiềm năng: 1

💰 Giá trị pipeline: 1.8 tỷ ₫

🚨 Cần liên hệ ngay (2):
  ⚠️ Chị Lan — 3 ngày chưa liên hệ
  ⚠️ Anh Tùng — 5 ngày chưa liên hệ

🤖 Gợi ý AI:
  💡 Gọi lại Chị Lan — đang ở giai đoạn tiềm năng
  💡 Gửi báo giá sơ bộ cho Anh Tùng
```

---

### 16.7 Lệnh `/suggest` — Gợi ý AI

Nhập ID lead để nhận gợi ý hành động tiếp theo từ AI:
```
/suggest abc12345
```
Bot sẽ phân tích lịch sử tương tác và đề xuất bước tiếp theo tối ưu.

---

### 16.8 So sánh Web CRM vs Telegram Bot

| Tính năng | Web CRM | Telegram Bot |
|-----------|:-------:|:------------:|
| Xem Dashboard đầy đủ | ✅ | ❌ |
| Nhập lead từ Zalo (AI parse) | ❌ | ✅ |
| Xem Pipeline Kanban | ✅ (đầy đủ) | ✅ (dạng text) |
| Briefing đầu ngày | ✅ | ✅ |
| Quản lý dự án | ✅ | ❌ |
| Upload file báo giá | ✅ | ❌ |
| Kế toán, HR, Finance | ✅ | ❌ |
| Gợi ý AI | ✅ | ✅ |
| Dùng khi đi công trường | ❌ (cần mở web) | ✅ (nhanh, gọn) |

> 💡 **Mẹo:** Dùng **Telegram Bot** để nhập lead nhanh khi đi ngoài, sau đó dùng **Web CRM** để quản lý chi tiết tại văn phòng.

---

### 16.9 Use Case Telegram Bot theo từng vai trò

Telegram Bot được thiết kế để phục vụ **tất cả vai trò** trong hệ thống, không chỉ riêng Sale. Dưới đây là bảng use case chi tiết:

#### 🔑 Ký hiệu: ✅ = Đã có | 🔜 = Sẽ phát triển

---

#### 👔 Giám đốc (admin)

| Use Case | Lệnh | Trạng thái |
|----------|-------|:----------:|
| Xem tổng quan pipeline & doanh số | `/pipeline` | ✅ |
| Briefing hàng ngày — KPI, leads mới, doanh thu | `/briefing` | ✅ |
| Nhận cảnh báo khi lead quá hạn follow-up | `/briefing` (tự động) | ✅ |
| Nhập lead trực tiếp nếu cần | `/lead` | ✅ |
| Xem báo cáo P&L tóm tắt | `/report` | 🔜 |
| Nhận thông báo khi hợp đồng mới được ký | Push notification | 🔜 |
| Duyệt báo giá / yêu cầu từ nhân viên | `/approve` | 🔜 |

**Kịch bản thực tế:** Mỗi sáng Giám đốc mở Telegram → `/briefing` → thấy ngay: 3 leads mới, 2 leads quá hạn, pipeline value 5.2 tỷ, 1 hợp đồng chờ duyệt → nắm tình hình mà không cần mở laptop.

---

#### 👥 Trưởng phòng (leader)

| Use Case | Lệnh | Trạng thái |
|----------|-------|:----------:|
| Xem pipeline team mình quản lý | `/pipeline` | ✅ |
| Briefing hàng ngày — leads team, hiệu suất nhân viên | `/briefing` | ✅ |
| Nhập lead mới từ Zalo/Facebook | `/lead` | ✅ |
| Gợi ý AI cho lead đang xử lý | `/suggest` | ✅ |
| Xem hiệu suất từng nhân viên Sale | `/team` | 🔜 |
| Phân công lead mới cho nhân viên | `/assign` | 🔜 |
| Nhận cảnh báo khi nhân viên chưa follow-up | Push notification | 🔜 |

**Kịch bản thực tế:** Leader nhận tin nhắn khách từ Zalo → copy paste vào Telegram → bot AI parse → xác nhận lưu → sau đó vào web phân công cho nhân viên phụ trách.

---

#### 💼 Nhân viên Sale (data_entry)

| Use Case | Lệnh | Trạng thái |
|----------|-------|:----------:|
| Nhập lead mới từ Zalo (⭐ tính năng chính) | `/lead` | ✅ |
| Xem pipeline leads cá nhân | `/pipeline` | ✅ |
| Briefing đầu ngày — leads cần follow-up | `/briefing` | ✅ |
| Gợi ý AI hành động tiếp theo | `/suggest` | ✅ |
| Tự động nhận diện lead từ tin nhắn forward | Auto-parse | ✅ |
| Ghi chú nhanh sau cuộc gặp khách | `/note` | 🔜 |
| Chuyển giai đoạn lead nhanh | `/move` | 🔜 |
| Nhận nhắc lịch hẹn khảo sát | Push notification | 🔜 |

**Kịch bản thực tế:** Sale đang ở công trường → nhận tin nhắn Zalo mới "Anh Minh 0901234567, cần thiết kế nội thất 85m2, ngân sách 500 triệu" → forward vào bot → bot tự phân tích → nhấn ✅ lưu → Lead vào CRM ngay, không cần mở laptop.

---

#### 🎨 Nhân viên Thiết kế (designer)

| Use Case | Lệnh | Trạng thái |
|----------|-------|:----------:|
| Nhận thông báo khi được giao task thiết kế mới | Push notification | 🔜 |
| Xem danh sách task đang chờ | `/tasks` | 🔜 |
| Cập nhật trạng thái task (hoàn thành, đang làm) | `/done [task_id]` | 🔜 |
| Upload file thiết kế nhanh | `/upload` | 🔜 |
| Nhận brief thiết kế từ Sale/PM | Push notification | 🔜 |

**Kịch bản thực tế:** Designer nhận thông báo Telegram "Bạn có task mới: Thiết kế 3D phòng khách cho Anh Minh - Deadline 10/07" → xem chi tiết → hoàn thành → gõ `/done TK-001` → trạng thái cập nhật trên CRM.

---

#### 📋 Trưởng Dự án — PM (pm)

| Use Case | Lệnh | Trạng thái |
|----------|-------|:----------:|
| Xem tổng quan dự án đang quản lý | `/projects` | 🔜 |
| Nhận cảnh báo khi task trễ deadline | Push notification | 🔜 |
| Cập nhật tiến độ dự án nhanh | `/progress [project_id] [%]` | 🔜 |
| Xem danh sách vật tư cần đặt | `/materials [project_id]` | 🔜 |
| Gửi yêu cầu mua vật tư cho Thu mua | `/request-material` | 🔜 |
| Nhận thông báo khi nghiệm thu đợt hoàn thành | Push notification | 🔜 |

**Kịch bản thực tế:** PM đang ở công trường → gõ `/progress DA-003 75%` → tiến độ dự án cập nhật → nếu có vật tư thiếu → `/request-material DA-003 Sơn Jotun 20 thùng` → Thu mua nhận thông báo.

---

#### 💰 Kế toán / Nhân sự (accountant)

| Use Case | Lệnh | Trạng thái |
|----------|-------|:----------:|
| Nhận thông báo khi có hợp đồng mới cần tạo phiếu thu | Push notification | 🔜 |
| Xem tóm tắt thu chi tháng | `/finance-summary` | 🔜 |
| Nhận cảnh báo công nợ quá hạn | Push notification | 🔜 |
| Tóm tắt bảng lương tháng | `/payroll-summary` | 🔜 |
| Ghi nhanh giao dịch thu/chi | `/transaction` | 🔜 |

**Kịch bản thực tế:** Kế toán nhận thông báo "Hợp đồng mới: DA Anh Minh - 500 triệu - Đợt 1: 150 triệu" → kiểm tra → tạo phiếu thu trên web.

---

#### 🛒 Nhân viên Thu mua (purchasing)

| Use Case | Lệnh | Trạng thái |
|----------|-------|:----------:|
| Nhận yêu cầu mua vật tư từ PM | Push notification | 🔜 |
| Xem tồn kho nhanh | `/stock [vật tư]` | 🔜 |
| Cập nhật trạng thái đơn hàng | `/po-update` | 🔜 |
| Nhận cảnh báo tồn kho thấp | Push notification | 🔜 |
| Ghi nhận vật tư nhập kho nhanh | `/receive [PO_id]` | 🔜 |

**Kịch bản thực tế:** Thu mua nhận thông báo "PM Hoàng yêu cầu: 20 thùng Sơn Jotun cho DA-003" → kiểm tra tồn kho → liên hệ nhà cung cấp → cập nhật `/po-update PO-015 đã đặt`.

---

#### 🏛️ Ban Quản Trị (executive)

| Use Case | Lệnh | Trạng thái |
|----------|-------|:----------:|
| Xem tổng quan pipeline & doanh số | `/pipeline` | 🔜 |
| Nhận báo cáo P&L tóm tắt hàng tháng | `/pl-summary` | 🔜 |
| Xem KPI toàn công ty | `/kpi` | 🔜 |
| Nhận cảnh báo rủi ro (dự án trễ, công nợ xấu) | Push notification | 🔜 |

**Kịch bản thực tế:** Ban QT nhận báo cáo tự động mỗi thứ Hai: "Tuần qua: 5 leads mới, 1 HĐ ký 800 triệu, Pipeline 8.5 tỷ, P&L tháng 6: Lãi 12%".

---

#### 📊 Tổng hợp: Ma trận tính năng Bot × Vai trò

| Tính năng Bot | Giám đốc | Leader | Sale | Thiết kế | PM | Kế toán | Thu mua | Ban QT |
|---------------|:--------:|:------:|:----:|:--------:|:--:|:-------:|:-------:|:------:|
| `/lead` — Nhập lead AI | ✅ | ✅ | ⭐ | ❌ | ❌ | ❌ | ❌ | ❌ |
| `/pipeline` — Pipeline | ✅ | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ | 🔜 |
| `/briefing` — Briefing | ✅ | ✅ | ✅ | 🔜 | 🔜 | 🔜 | 🔜 | 🔜 |
| `/suggest` — AI gợi ý | ✅ | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ |
| `/tasks` — Xem task | 🔜 | 🔜 | ❌ | 🔜 | 🔜 | ❌ | ❌ | ❌ |
| `/projects` — Dự án | 🔜 | 🔜 | ❌ | 🔜 | 🔜 | ❌ | ❌ | 🔜 |
| Push notifications | 🔜 | 🔜 | 🔜 | 🔜 | 🔜 | 🔜 | 🔜 | 🔜 |
| `/report` — Báo cáo | 🔜 | 🔜 | ❌ | ❌ | ❌ | 🔜 | ❌ | 🔜 |

> **Chú thích:** ⭐ = Tính năng chính | ✅ = Đã triển khai | 🔜 = Lộ trình phát triển | ❌ = Không áp dụng

---

## 17. Bảng phân quyền theo vai trò

### 17.1 Ma trận phân quyền chi tiết

| Chức năng | Giám đốc | Trưởng phòng | Sale | Thiết kế | PM | Kế toán | Thu mua | Ban QT |
|-----------|:--------:|:------------:|:----:|:--------:|:--:|:-------:|:-------:|:------:|
| **Dashboard** | ✅ Executive | ✅ Team | ✅ Personal | ✅ Personal | ✅ Team | ✅ Financial | ✅ Personal | ✅ Executive |
| **Pipeline (Leads)** | ✅ Toàn bộ | ✅ Theo team | ✅ Của mình | ❌ | ❌ | ❌ | ❌ | ❌ |
| **Dự án** | ✅ CRUD | ✅ CRU | ✅ Đọc | ✅ Đọc (giao) | ✅ CRUD | ✅ Đọc | ✅ Đọc | ✅ Đọc |
| **Khách hàng** | ✅ CRUD | ✅ CRUD | ✅ CRUD | ✅ Đọc | ✅ Đọc | ✅ CRUD | ❌ | ✅ Đọc |
| **Hợp đồng** | ✅ CRUD | ✅ CRU | ✅ CRUD | ❌ | ✅ CRUD | ✅ CRUD | ✅ Đọc | ✅ Đọc |
| **Báo giá** | ✅ CRUD | ✅ CRUD | ✅ CRUD | ✅ CRUD | ✅ CRUD | ✅ Đọc | ❌ | ❌ |
| **Kho vật tư** | ✅ CRUD | ❌ | ❌ | ❌ | ✅ Đọc | ✅ Đọc | ✅ CRUD | ❌ |
| **Kế toán** | ✅ CRUD | ✅ Đọc | ❌ | ❌ | ❌ | ✅ CRUD | ❌ | ❌ |
| **Nhân sự** | ✅ CRUD | ✅ Đọc | ❌ | ❌ | ❌ | ✅ CRUD | ❌ | ❌ |
| **Tài chính** | ✅ CRUD | ❌ | ❌ | ❌ | ❌ | ✅ CRUD | ❌ | ❌ |
| **P&L** | ✅ | ❌ | ❌ | ❌ | ❌ | ✅ | ❌ | ✅ |
| **Báo cáo** | ✅ | ✅ | ✅ | ❌ | ✅ | ✅ | ❌ | ✅ |
| **Cài đặt** | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |

> **Chú thích:** CRUD = Tạo (C) + Đọc (R) + Sửa (U) + Xóa (D)

---

## 18. Quy trình vận hành tổng thể

### 18.1 Quy trình từ Lead đến Hoàn thành dự án

```
                      JAMA HOME — QUY TRÌNH VẬN HÀNH
┌─────────────────────────────────────────────────────────────────┐
│                                                                 │
│  1️⃣  SALE TÌM KIẾM KHÁCH HÀNG                                  │
│     └→ Nhập Lead vào Pipeline                                  │
│     └→ Follow-up, tư vấn, hẹn khảo sát                        │
│                                                                 │
│  2️⃣  KÝ HỢP ĐỒNG THIẾT KẾ                                     │
│     └→ Lead chuyển giai đoạn "Đã ký HĐ Thiết kế"              │
│     └→ ⚡ HỆ THỐNG TỰ ĐỘNG TẠO:                                │
│         • Khách hàng mới                                        │
│         • Dự án mới + 19 đầu việc                              │
│                                                                 │
│  3️⃣  THIẾT KẾ (Phòng Thiết kế)                                 │
│     └→ Concept, 3D, bản vẽ kỹ thuật                           │
│     └→ Upload file vào đầu việc tương ứng                      │
│     └→ Chốt thiết kế với khách hàng                            │
│                                                                 │
│  4️⃣  BÁO GIÁ (Thiết kế + Sale)                                 │
│     └→ Bóc tách vật tư, tổng hợp giá                          │
│     └→ Upload file báo giá                                      │
│     └→ Duyệt nội bộ → Gửi khách hàng                          │
│                                                                 │
│  5️⃣  THU MUA (Phòng Thu mua)                                    │
│     └→ Chọn NCC, đặt hàng, kiểm tra nhận hàng                │
│     └→ Quản lý trong Kho vật tư                                │
│                                                                 │
│  6️⃣  THI CÔNG (PM + Đội thi công)                               │
│     └→ Chuẩn bị → Lắp đặt → Hoàn thiện → Vệ sinh            │
│     └→ Upload ảnh tiến độ vào ghi chú                          │
│                                                                 │
│  7️⃣  NGHIỆM THU & BÀN GIAO                                    │
│     └→ Nghiệm thu nội bộ → Nghiệm thu KH → Bàn giao         │
│     └→ Upload biên bản nghiệm thu                              │
│                                                                 │
│  8️⃣  KẾ TOÁN QUYẾT TOÁN                                        │
│     └→ Ghi nhận giao dịch thu/chi                              │
│     └→ Xuất báo cáo CSV                                        │
│     └→ Theo dõi công nợ                                        │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### 18.2 Sơ đồ vai trò theo quy trình

```
Sale ──────→ Thiết kế ──→ Báo giá ──→ Thu mua ──→ Thi công ──→ Nghiệm thu
 │             │            │           │            │            │
 ▼             ▼            ▼           ▼            ▼            ▼
data_entry   designer    designer    purchasing      pm          pm
leader       pm          pm          admin          leader      sales
admin        admin       sales       kế toán        admin       admin
                         admin
```

---

## 19. Câu hỏi thường gặp

### ❓ Tôi không thấy mục "Kho vật tư" trên menu?
→ Chỉ vai trò **Admin** và **Thu mua** mới thấy mục này. Liên hệ Admin nếu cần quyền truy cập.

### ❓ Tôi không thể thêm nhân viên mới?
→ Chức năng này chỉ dành cho **Admin** và **Kế toán**. Các vai trò khác chỉ xem danh sách.

### ❓ Lead đã ký hợp đồng nhưng không thấy dự án mới?
→ Kiểm tra lead đã chuyển đúng sang giai đoạn **"Đã ký HĐ Thiết kế (signed_design)"** chưa. Hệ thống chỉ tự động tạo dự án khi chuyển sang giai đoạn này.

### ❓ Làm sao upload file nghiệm thu, báo giá?
→ Vào **Dự án** → Click dự án → Click đầu việc cụ thể → Phần **"Ghi chú & Media"** → Upload file hoặc dán link.

### ❓ Làm sao xuất dữ liệu kế toán?
→ Vào trang **Kế toán** → Nhấn nút **"📥 Xuất CSV"** ở góc trên phải.

### ❓ Tôi quên mật khẩu?
→ Liên hệ **Admin** hoặc **Kế toán** để đặt lại mật khẩu. Hiện chưa có chức năng "Quên mật khẩu" tự động.

### ❓ Demo Mode là gì?
→ Chế độ dùng dữ liệu mẫu để trải nghiệm hệ thống mà không ảnh hưởng dữ liệu thật. Thích hợp để training nhân sự mới.

### ❓ Làm sao chuyển từ Demo sang Work Mode?
→ Khi đăng nhập, chọn chế độ tại trang Login hoặc chuyển đổi trên Sidebar.

### ❓ Hệ thống có hoạt động trên điện thoại không?
→ Có. Giao diện đã được tối ưu responsive cho mobile. Một số bảng phức tạp (như P&L) sẽ hiển thị dạng thẻ gọn gàng trên màn hình nhỏ.

---

## 📞 Hỗ trợ kỹ thuật

Nếu gặp lỗi hoặc cần hỗ trợ, vui lòng liên hệ:

- **Admin hệ thống:** admin@jamahome.vn
- **Hotline kỹ thuật:** (liên hệ bộ phận IT)

---

> 📝 *Tài liệu này được tạo và cập nhật theo phiên bản hệ thống.*
> *Phiên bản: 1.0 — Ngày: 05/07/2026*
