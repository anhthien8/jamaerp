# 📖 JAMA HOME CRM — Hướng dẫn sử dụng hệ thống

> Tài liệu dành cho nhân viên mới onboard. Cập nhật: 25/06/2026

---

## 📋 Mục lục
1. [Giới thiệu hệ thống](#1-giới-thiệu-hệ-thống)
2. [Đăng nhập](#2-đăng-nhập)
3. [Dashboard — Tổng quan](#3-dashboard--tổng-quan)
4. [Pipeline CRM — Quản lý Lead](#4-pipeline-crm--quản-lý-lead)
5. [Dự án — Quản lý thi công](#5-dự-án--quản-lý-thi-công)
6. [Kế toán — Thu chi & Lương](#6-kế-toán--thu-chi--lương)
7. [Báo cáo](#7-báo-cáo)
8. [Cài đặt](#8-cài-đặt)
9. [Quy trình làm việc hàng ngày](#9-quy-trình-làm-việc-hàng-ngày)
10. [FAQ — Câu hỏi thường gặp](#10-faq--câu-hỏi-thường-gặp)

---

## 1. Giới thiệu hệ thống

JAMA HOME CRM là hệ thống quản lý tổng thể cho công ty thiết kế nội thất JAMA HOME, bao gồm:

| Module | Chức năng |
|--------|-----------|
| **Pipeline CRM** | Quản lý khách hàng tiềm năng (leads), theo dõi từ lúc tiếp nhận đến ký hợp đồng |
| **Dự án** | Theo dõi tiến độ thiết kế & thi công, công việc, ngân sách |
| **Kế toán** | Thu chi, hoa hồng sales, bảng lương nhân viên |
| **Báo cáo** | KPI, tỷ lệ chuyển đổi, hiệu suất đội nhóm |
| **AI Agent** | Tự động phân tích lead, gợi ý hành động tiếp theo |

### Phân quyền

| Vai trò | Quyền hạn |
|---------|-----------|
| **Admin** | Xem tất cả dữ liệu, quản lý user, cài đặt hệ thống |
| **Leader** | Xem leads/dự án của team mình, phân công công việc |
| **Sales (Data Entry)** | Xem/sửa leads được phân công cho mình |

---

## 2. Đăng nhập

1. Truy cập **http://localhost:3001** (hoặc domain công ty)
2. Nhập **email** và **mật khẩu** được IT cung cấp
3. Nhấn **"Đăng nhập"**

### Tài khoản mặc định (dev/test)

| Email | Mật khẩu | Vai trò |
|-------|-----------|---------|
| `admin@jamahome.vn` | `admin123` | Admin |
| `leader@jamahome.vn` | `leader123` | Leader |
| `sales@jamahome.vn` | `sales123` | Sales |

> ⚠️ **Lưu ý bảo mật**: Đổi mật khẩu ngay sau lần đăng nhập đầu tiên.

---

## 3. Dashboard — Tổng quan

Sau khi đăng nhập, bạn thấy **Dashboard** với các chỉ số:

- **Tổng leads** — Số khách hàng tiềm năng trong hệ thống
- **Tỷ lệ chuyển đổi** — % leads đã ký hợp đồng
- **Pipeline value** — Tổng giá trị ngân sách các leads đang theo
- **Dự án active** — Số dự án đang thực hiện
- **SLA Compliance** — % leads được follow-up đúng hạn (≤3 ngày)
- **Leads quá hạn** — Leads chưa liên hệ >3 ngày

### Hiệu suất đội nhóm
Bảng so sánh giữa các team: tổng leads, số ký HĐ, tỷ lệ chuyển đổi.

---

## 4. Pipeline CRM — Quản lý Lead

### 4.1 Kanban Board

Pipeline hiển thị dạng **Kanban** với 5 cột giai đoạn:

```
🆕 Mới tiếp nhận → 💡 Có nhu cầu → 📅 Đã hẹn khảo sát → ⭐ KH tiềm năng → ✍️ Ký thiết kế
```

Mỗi **card lead** hiển thị:
- Tên khách hàng
- Số điện thoại
- Loại BĐS & diện tích
- AI Score (thanh tiến độ)
- Nhân viên phụ trách
- Nguồn lead

### 4.2 Thêm Lead mới

1. Nhấn nút **"+ Thêm Lead"** góc phải trên
2. Điền thông tin bắt buộc: **Tên KH** và **SĐT**
3. Chọn thông tin bổ sung: loại BĐS, diện tích, ngân sách, nguồn, mức ưu tiên
4. Mô tả nhu cầu chi tiết
5. Nhấn **"✅ Tạo Lead"**

### 4.3 Xem chi tiết Lead

Click vào bất kỳ card nào → popup **Chi tiết Lead**:

- **Thông tin liên hệ**: SĐT, email, địa chỉ, nguồn, người phụ trách
- **Nhu cầu & Dự án**: Loại BĐS, diện tích, ngân sách, yêu cầu chi tiết
- **Lịch sử hoạt động**: Timeline các cuộc gọi, ghi chú, thay đổi giai đoạn
- **Chuyển giai đoạn**: Nút chuyển nhanh sang các giai đoạn khác

### 4.4 Thêm ghi chú / hoạt động

Trong popup chi tiết:
1. Nhập ghi chú vào ô **"Thêm ghi chú..."** phía dưới timeline
2. Nhấn **Enter** hoặc nút **"Gửi"**
3. Ghi chú được lưu ngay lập tức vào lịch sử

### 4.5 Chuyển giai đoạn Lead

Trong popup chi tiết:
1. Cuộn xuống mục **"Chuyển giai đoạn"**
2. Nhấn nút giai đoạn muốn chuyển đến
3. Hệ thống tự động ghi nhận lịch sử thay đổi

### 4.6 Bộ lọc & Sắp xếp

- **Lọc theo nguồn**: Zalo, Facebook, TikTok, Website, Giới thiệu
- **Lọc theo ưu tiên**: Khẩn cấp, Cao, Trung bình, Thấp
- **Sắp xếp**: Mới nhất, Budget cao→thấp, AI Score cao→thấp
- Nhấn **"✕ Xóa bộ lọc"** để reset

---

## 5. Dự án — Quản lý thi công

### 5.1 Danh sách dự án

Mỗi dự án hiển thị:
- **Vòng tròn tiến độ** — % hoàn thành
- **Mã dự án** — VD: `PRJ-2026-001`
- **Trạng thái**: Đang thực hiện / Tạm dừng / Hoàn thành
- **Tên KH** và **tổng giá trị hợp đồng**
- **Thanh ngân sách** — Đã chi / Tổng budget

### 5.2 Lọc dự án

Nhấn nút lọc: Tất cả / Đang thực hiện / Thiết kế / Hoàn thành / Tạm dừng

### 5.3 Chi tiết dự án

Click vào dự án → popup hiển thị:

- **Tóm tắt**: Tiến độ, tổng giá trị, đã chi, loại dự án
- **Thông tin KH**: Tên, SĐT, địa chỉ
- **Giá trị hợp đồng**: HĐ Thiết kế + HĐ Thi công
- **Danh sách công việc**: Tasks kèm trạng thái (Xong ✅ / Đang làm 🔄 / Chờ ⏳)
- **Timeline**: Ngày bắt đầu, dự kiến kết thúc

---

## 6. Kế toán — Thu chi & Lương

Trang kế toán có **4 tab**:

### 6.1 Tổng quan
- **Tổng thu** — Tổng doanh thu đã ghi nhận
- **Tổng chi** — Tổng chi phí đã phát sinh
- **Lợi nhuận** — Thu - Chi
- **Phân tích theo danh mục** — Chi tiết thu/chi theo loại

### 6.2 Giao dịch
Bảng giao dịch chi tiết:
- Mã giao dịch, loại (Thu ↑ / Chi ↓), danh mục, mô tả
- Số tiền, ngày, trạng thái (Đã xử lý / Chờ duyệt)

### 6.3 Hoa hồng
Bảng hoa hồng sales:
- Nhân viên, loại hoa hồng, mốc thanh toán
- Giá trị cơ sở, tỷ lệ %, số tiền hoa hồng
- Trạng thái (Đã trả / Chờ)

**Quy tắc hoa hồng JAMA HOME:**

| Loại | Tỷ lệ |
|------|--------|
| HĐ Thiết kế | 3% giá trị HĐ |
| HĐ Thi công | 2% giá trị HĐ |
| Leader Override | 0.5% trên deal của team |

**Mốc thanh toán hoa hồng:**

| Mốc | Tỷ lệ thanh toán |
|-----|-------------------|
| Ký hợp đồng | 50% hoa hồng |
| Nghiệm thu thô | 30% hoa hồng |
| Bàn giao | 20% hoa hồng |

### 6.4 Bảng lương
Bảng lương nhân viên:
- Lương cơ bản, hoa hồng, thưởng, khấu trừ, thực lĩnh
- Kỳ lương, trạng thái thanh toán

---

## 7. Báo cáo

Trang báo cáo tổng hợp dữ liệu từ tất cả module:

- **Doanh thu** — Biểu đồ doanh thu theo danh mục
- **Pipeline Funnel** — Tỷ lệ chuyển đổi + số leads theo từng giai đoạn
- **Hiệu suất đội nhóm** — Bảng so sánh giữa các team
- **KPI tổng hợp** — 8 chỉ số chính: leads, conversion, pipeline, SLA...

---

## 8. Cài đặt

- **Thông tin cá nhân**: Xem tên, email, vai trò, phòng ban
- **Telegram Bot**: Liên kết Telegram để nhận briefing hàng ngày
- **Hệ thống**: Phiên bản, backend, AI model

---

## 9. Quy trình làm việc hàng ngày

### Buổi sáng (8:00 - 9:00)
1. Đăng nhập → xem **Dashboard**
2. Kiểm tra **leads quá hạn** (chưa liên hệ >3 ngày)
3. Ưu tiên gọi lại các leads quá hạn

### Trong ngày
4. Nhận lead mới → **Thêm Lead** vào Pipeline
5. Sau mỗi cuộc gọi/meeting → **Thêm ghi chú** vào lead
6. Khi lead đồng ý → **Chuyển giai đoạn** (VD: "Mới" → "Có nhu cầu")
7. Khi ký HĐ → Chuyển sang **"Ký thiết kế"**, hệ thống tự tạo Project

### Cuối ngày
8. Review lại Pipeline → đảm bảo không lead nào bị bỏ sót
9. Kiểm tra **SLA Compliance** — mục tiêu >90%

### Hàng tuần
10. Xem **Báo cáo** → đánh giá hiệu suất cá nhân/team
11. Leader: Review pipeline + coaching 1-on-1 với sales

---

## 10. FAQ — Câu hỏi thường gặp

### Q: Tôi không đăng nhập được?
**A:** Kiểm tra email/mật khẩu chính xác. Nếu vẫn lỗi, liên hệ IT để reset mật khẩu.

### Q: Lead của tôi biến mất khỏi Pipeline?
**A:** Kiểm tra bộ lọc — có thể đang lọc theo nguồn/ưu tiên cụ thể. Nhấn "Xóa bộ lọc" để xem tất cả. Lead ở giai đoạn "Mất" hoặc "Ngủ đông" không hiển thị trên Kanban.

### Q: Làm sao thêm ghi chú cho lead?
**A:** Click vào card lead → cuộn xuống phần "Lịch sử hoạt động" → nhập ghi chú → Enter/Gửi.

### Q: AI Score là gì?
**A:** Điểm do AI đánh giá khả năng chuyển đổi (0-100). Dựa trên: ngân sách, loại BĐS, diện tích, nhu cầu. Score ≥80 = tiềm năng cao (🟢), 60-79 = trung bình (🟡), <60 = thấp (🔴).

### Q: Hoa hồng tính như thế nào?
**A:** Xem chi tiết ở mục [6.3 Hoa hồng](#63-hoa-hồng). Hoa hồng tự động tính khi dự án đạt các mốc: Ký HĐ (50%), Nghiệm thu thô (30%), Bàn giao (20%).

### Q: Dữ liệu có bị mất không?
**A:** Không. Dữ liệu lưu trong database backend. Mỗi thay đổi được ghi nhận vào lịch sử hoạt động.

### Q: Tôi cần hỗ trợ kỹ thuật?
**A:** Liên hệ IT qua email hoặc Telegram group nội bộ.

---

## 🔧 Thông tin kỹ thuật (dành cho IT)

### Khởi động hệ thống

**Backend** (FastAPI + SQLite):
```bash
cd jama-crm/backend
pip install -r app/requirements.txt
PYTHONIOENCODING=utf-8 python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

**Frontend** (Next.js):
```bash
cd jama-crm/frontend
npm install
npm run dev -- -p 3001
```

### URL
- Frontend: `http://localhost:3001`
- Backend API: `http://localhost:8000`
- API Docs (Swagger): `http://localhost:8000/docs`
- Health Check: `http://localhost:8000/health`

### Database
- SQLite file: `jama-crm/backend/jama.db`
- Auto-seed on first startup: 3 users, 4 teams, 7 leads, 5 projects, 15 activities, 12 transactions

### Biến môi trường
- `PYTHONIOENCODING=utf-8` — Bắt buộc trên Windows để tránh lỗi Unicode
- `NEXT_PUBLIC_API_URL` — URL backend API (mặc định: `http://localhost:8000/api/v1`)

---

> 📞 **Hỗ trợ**: Liên hệ IT Team — Telegram @jamahome_it
