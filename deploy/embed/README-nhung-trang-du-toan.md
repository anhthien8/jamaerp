# 🧲 Nhúng công cụ Báo giá vào trang Dự Toán — jamahome.vn

Hai cách, chọn 1. **Điều kiện chung:** backend JAMA CRM phải được deploy công khai trước (có domain, ví dụ `https://jamacrm-production.up.railway.app`).

---

## Cách A — iframe (nhanh nhất, 5 phút, khuyên dùng để chạy trước)

Không đụng cấu hình gì thêm. Trong trang **Dự Toán** của website, thêm 1 khối **HTML tùy chỉnh** và dán:

```html
<iframe
  src="https://YOUR-FRONTEND-DOMAIN/bao-gia"
  width="100%"
  height="760"
  style="border:none; max-width:680px; display:block; margin:0 auto;"
  title="Báo giá nội thất JAMA HOME">
</iframe>
```

Thay `YOUR-FRONTEND-DOMAIN` bằng domain **frontend** đã deploy (nơi có trang `/bao-gia`).

- ✅ Ưu điểm: không cần chỉnh CORS, cập nhật công cụ là website tự có bản mới.
- ⚠️ Nhược điểm nhỏ: là khung nhúng nên không "liền" 100% với theme.
- 📱 Trên mobile khung tự co; nếu nội dung dài hơn, tăng `height`.

---

## Cách B — widget native (đẹp, liền theme, 15 phút)

Dùng file `jama-bao-gia-widget.html` (cùng thư mục). Trông như một phần của website, tự gọi API tạo lead.

**Bước 1 — Cho phép website gọi API (CORS).**
Trong biến môi trường backend, thêm domain website vào `CORS_ORIGINS` (phân cách bằng dấu phẩy), ví dụ:

```
CORS_ORIGINS=https://jamahome.vn,https://www.jamahome.vn,https://jamacrm-production.up.railway.app
```

Trên Railway: service backend → tab **Variables** → sửa `CORS_ORIGINS` → Redeploy.

**Bước 2 — Sửa domain trong file.**
Mở `jama-bao-gia-widget.html`, sửa đúng 1 dòng:

```js
var API_BASE = "https://YOUR-BACKEND-DOMAIN/api/v1";
```

thành domain **backend** thật (giữ đuôi `/api/v1`).

**Bước 3 — Dán vào website.**
Copy toàn bộ nội dung file → dán vào khối **HTML tùy chỉnh** trong trang Dự Toán.
- WordPress: block **Custom HTML** (không phải "Paragraph").
- Wix / Squarespace: phần tử **Embed HTML / Code**.

- ✅ Ưu điểm: giao diện đẹp, màu JAMA, liền theme, responsive.
- ⚠️ Cần chỉnh CORS đúng (bước 1) nếu không sẽ báo lỗi kết nối.

---

## Kiểm tra sau khi nhúng

1. Mở trang Dự Toán ngoài trình duyệt (chế độ ẩn danh cho chắc).
2. Nhập thử: tên "Test", SĐT của bạn, 75m², căn hộ → bấm nhận báo giá.
3. Phải thấy 3 khoảng giá hiện ra.
4. Đăng nhập JAMA CRM → Pipeline → thấy lead "Test" nguồn **Website**, ưu tiên **cao**.
5. Xóa lead test đó đi là xong.

## Bảo mật (đã tích hợp sẵn)

- Endpoint public giới hạn **5 lượt/giờ/IP** — chống spam/cào giá.
- Widget **không lộ đơn giá chi tiết** — chỉ trả khoảng giá 3 phương án.
- Chống tạo lead trùng theo số điện thoại.

## Gợi ý đặt link (để lấy nhiều lead)

Đặt link trang báo giá (hoặc trang Dự Toán đã nhúng) ở: bio Facebook/Zalo OA/TikTok, nút CTA quảng cáo (thay vì Messenger), chữ ký email, QR tại showroom và name card. Chạy content "Báo giá nội thất 30 giây".
