# Workflow Tích Hợp Telegram Group & Bot Cho JamaCRM

Hệ thống kết hợp giữa **Web App JamaCRM**, **Telegram Group (Kênh thảo luận nội bộ)** và **Telegram Bot (Trợ lý hiện trường)** giúp tối ưu hóa luồng trao đổi thông tin giữa Văn phòng (Thiết kế, Kế toán, Mua hàng) và Công trình (Giám sát, Thi công).

---

## 1. Mô hình Phối Hợp Tổng Quan

```mermaid
graph TD
    subgraph Hiện Trường (Công Trình)
        GS[Giám sát / Thiết kế]
        GS -->|1. Check-in / Gửi ảnh báo cáo| Bot(Telegram Bot)
        GS -->|2. Gõ lệnh /vatlieu yêu cầu vật tư| Bot
    end

    subgraph Hệ Thống JamaCRM
        Bot <-->|Đồng bộ realtime qua Webhook| API[JamaCRM Backend]
        API <--> DB[(Cơ sở dữ liệu)]
    end

    subgraph Văn Phòng (Quản lý & Hậu cần)
        API -->|3. Bắn thông báo sự cố/tiến độ| Group[Group Telegram Chung]
        API -->|4. Đẩy yêu cầu vật tư lên UI| UI[Web App CRM]
        KToan[Kế toán / Thu mua] -->|5. Phê duyệt mua hàng| UI
        UI -->|6. Báo cáo đã mua hàng| Group
    end

    style Bot fill:#229ED9,stroke:#fff,stroke-width:2px,color:#fff
    style Group fill:#229ED9,stroke:#fff,stroke-width:2px,color:#fff
    style UI fill:#C9A96E,stroke:#fff,stroke-width:2px,color:#fff
```

---

## 2. Chi Tiết Luồng Công Việc (Workflow) Thực Tế

### Luồng 1: Báo cáo Tiến độ & Nhật ký Công trình (Real-time Site Logging)
* **Khó khăn cũ:** Giám sát phải chụp ảnh lưu máy, tối về văn phòng bật laptop viết nhật ký công trình lên CRM, rất dễ quên hoặc lười cập nhật.
* **Workflow tối ưu:**
  1. Giám sát đến công trình, chat với Bot gửi vị trí: Bot tự động check-in ghi nhận ngày công.
  2. Giám sát chụp ảnh các hạng mục vừa thi công xong, gửi trực tiếp vào Telegram Chat kèm cú pháp: `/baocao [Mã_dự_án] Sơn bả tường phòng khách xong đợt 1`.
  3. Bot nhận ảnh và text $\rightarrow$ gọi API lưu thẳng vào **Activity Log** của dự án đó trên JamaCRM.
  4. Đồng thời, Bot tự động gửi tin nhắn tổng hợp vào **Group Telegram chung**:
     > 📢 **CẬP NHẬT CÔNG TRÌNH:**
     > * **Dự án:** Biệt thự An Lạc (JMH-0601)
     > * **Nhân sự:** Trần Văn Giám Sát
     > * **Nội dung:** Sơn bả tường phòng khách xong đợt 1
     > * [Ảnh công trình kèm theo]

---

### Luồng 2: Yêu cầu Vật tư & Phê duyệt nhanh (Material Request & Fast Approval)
* **Khó khăn cũ:** Công trình thiếu 5 bao keo dán gạch, giám sát gọi điện cho Thu mua, Thu mua quên ghi lại, hoặc phải làm form đề xuất lằng nhằng duyệt mất cả ngày.
* **Workflow tối ưu:**
  1. Giám sát tại công trình chat với Bot: `/vatlieu JMH-0601 Keo dán gạch đá - 5 bao`.
  2. Bot kiểm tra danh mục vật tư định mức của dự án đó trên CRM:
     * *Nếu nằm trong định mức:* Bot tạo ngay một phiếu yêu cầu mua vật tư trên CRM trạng thái *Chờ duyệt*, đồng thời ping nhóm **Thu mua / Kế toán**.
     * *Nếu vượt định mức:* Bot cảnh báo ngay cho Giám sát và gửi yêu cầu giải trình.
  3. Thu mua/Kế toán nhận tin nhắn trên Telegram có kèm nút bấm phê duyệt nhanh (**Inline Buttons**):
     > 📦 **YÊU CẦU VẬT TƯ MỚI:**
     > * **Dự án:** JMH-0601
     > * **Vật tư:** Keo dán gạch đá (5 bao)
     > * **Người yêu cầu:** Nguyễn Văn A
     > * **Trạng thái:** Trong định mức thiết kế
     > 
     > `[ ✅ Phê duyệt ]`   `[ ❌ Từ chối ]`
  4. Kế toán nhấn **`[ Phê duyệt ]`** ngay trên Telegram $\rightarrow$ trạng thái trên JamaCRM đổi thành *Đã duyệt* $\rightarrow$ thông báo phản hồi lại cho Giám sát: *"Yêu cầu 5 bao keo dán gạch của bạn đã được duyệt, dự kiến giao vào chiều nay."*

---

### Luồng 3: Cảnh báo Sự cố & Phối hợp xử lý (Incident Escalation)
* **Khó khăn cũ:** Phát hiện tường bị thấm ẩm từ nhà bên cạnh, giám sát gửi ảnh vào group chat chung trôi tin nhắn, thiết kế không thấy để sửa bản vẽ.
* **Workflow tối ưu:**
  1. Giám sát gửi ảnh vị trí bị thấm vào Bot kèm lệnh `/suco JMH-0601 Thấm tường vách trục C`.
  2. Bot ghi nhận sự cố cấp độ **Khẩn cấp (High)** lên JamaCRM, tag trực tiếp **Thiết kế** phụ trách dự án đó.
  3. Bot gửi tin nhắn khẩn cấp vào Group Telegram:
     > ⚠️ **SỰ CỐ HIỆN TRƯỜNG KHẨN CẤP:**
     > * **Dự án:** Biệt thự An Lạc (JMH-0601)
     > * **Vấn đề:** Thấm tường vách trục C
     > * **Người phụ trách:** Designer Lê Văn B (đã được tag trực tiếp)
     > * Giám sát yêu cầu khảo sát lại chi tiết bản vẽ thi công.
  4. Khi Thiết kế cập nhật lại phương án xử lý trên CRM, hệ thống tự động báo lại trong group Telegram để thi công nắm thông tin.

---

## 3. Các Lệnh Tiêu Biểu Cho Nhân Sự Hiện Trường

| Lệnh Chat | Tác dụng | Người dùng |
| :--- | :--- | :--- |
| `/duan [Mã_dự_án]` | Xem nhanh thông tin dự án, số điện thoại chủ nhà, địa chỉ công trình, tiến độ hiện tại. | Tất cả |
| `/baocao [Mã_dự_án] [Nội_dung]` | Gửi kèm ảnh để ghi nhật ký công trình tự động lưu lên CRM. | Giám sát / Thiết kế |
| `/vatlieu [Mã_dự_án] [Tên_vật_tư] - [Số_lượng]` | Đề xuất cấp vật tư nhanh về văn phòng. | Giám sát |
| `/suco [Mã_dự_án] [Mô_tả]` | Báo cáo sự cố khẩn cấp tại công trường, tự động tạo Task khẩn cấp. | Giám sát / Thi công |
| `/checkin` / `/checkout` | Ghi nhận vị trí (GPS) và thời gian bắt đầu/kết thúc ca làm việc tại công trình. | Tất cả |

---

## 4. Lợi ích tối ưu hiệu suất
1. **Dữ liệu tập trung:** Nhân viên không phải nhập liệu 2 lần. Mọi hoạt động chat qua Telegram đều được lưu vết sạch sẽ trong lịch sử dự án trên Web App CRM.
2. **Ra quyết định tức thì:** Giám đốc hoặc Thu mua có thể duyệt chi phí, vật tư từ xa ngay trên điện thoại qua nút bấm Telegram, không cần mở máy tính hay đăng nhập web.
3. **Phối hợp liên phòng ban:** Sự cố công trường được chuyển tiếp chính xác đến đúng Kỹ sư/Thiết kế chịu trách nhiệm chỉ trong 2 giây.
